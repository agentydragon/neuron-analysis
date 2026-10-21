"""Derive identity marks from hand-painted frames and score annotations against them."""

import argparse
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Annotated, Literal, Self

from PIL import Image
from pydantic import Field, StrictInt, ValidationError, computed_field, model_validator

from cell_tracking.core import Mask, Record, Source
from cell_tracking.eval_frames import FramesManifest
from cell_tracking.hashing import hash_file
from cell_tracking.masks import CellMasks

type Pixels = set[tuple[int, int]]


class FrameMark(Record):
    frame_index: Annotated[StrictInt, Field(ge=0)]
    pixels: Mask


class Cell(Record):
    color: Annotated[str, Field(pattern="^#[0-9a-f]{6}$")]
    marks: Annotated[list[FrameMark], Field(min_length=1)]


class Group(Record):
    """Marked frames whose colors share one meaning; colors do not carry over between groups."""

    name: Annotated[str, Field(min_length=1)]
    frames: Annotated[list[StrictInt], Field(min_length=1)]
    cells: Annotated[list[Cell], Field(min_length=1)]


class IdentityMarks(Record):
    schema_version: Annotated[StrictInt, Field(ge=1, le=1)]
    source: Source
    groups: Annotated[list[Group], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_groups(self) -> Self:
        if len({group.name for group in self.groups}) != len(self.groups):
            raise ValueError("Duplicate group name")
        for group in self.groups:
            if group.frames != sorted(set(group.frames)):
                raise ValueError(f"Group {group.name}: frames must be unique and sorted")
            if len({cell.color for cell in group.cells}) != len(group.cells):
                raise ValueError(f"Group {group.name}: duplicate cell color")
            claimed: dict[int, Pixels] = {}
            for cell in group.cells:
                if len({mark.frame_index for mark in cell.marks}) != len(cell.marks):
                    raise ValueError(f"Group {group.name}, {cell.color}: more than one mark in a frame")
                for mark in cell.marks:
                    if mark.frame_index not in group.frames:
                        raise ValueError(f"Group {group.name}, {cell.color}: frame {mark.frame_index} not in group")
                    pixels = to_pixels(mark.pixels)
                    if not pixels or any(
                        not (0 <= y < self.source.height and 0 <= x < self.source.width) for x, y in pixels
                    ):
                        raise ValueError(f"Group {group.name}, {cell.color}: empty or out-of-bounds mark")
                    if claimed.setdefault(mark.frame_index, set()) & pixels:
                        raise ValueError(f"Group {group.name}: marks overlap in frame {mark.frame_index}")
                    claimed[mark.frame_index] |= pixels
        return self


def to_pixels(mask: Mask) -> Pixels:
    return {(x, y) for y, start, end in mask for x in range(start, end)}


def to_runs(pixels: Pixels) -> Mask:
    runs: Mask = []
    for y, x in sorted((y, x) for x, y in pixels):
        if runs and runs[-1][0] == y and runs[-1][2] == x:
            runs[-1] = (y, runs[-1][1], x + 1)
        else:
            runs.append((y, x, x + 1))
    return runs


def components(pixels: Pixels) -> list[Pixels]:
    remaining, found = set(pixels), []
    while remaining:
        stack, component = [remaining.pop()], set()
        while stack:
            x, y = stack.pop()
            component.add((x, y))
            for neighbor in ((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
        found.append(component)
    return found


def fill_holes(pixels: Pixels, blocked: Pixels) -> Pixels:
    """Add unmarked pixels enclosed by the mark so outlines cover the cell they surround."""
    left, right = min(x for x, _ in pixels) - 1, max(x for x, _ in pixels) + 1
    top, bottom = min(y for _, y in pixels) - 1, max(y for _, y in pixels) + 1
    outside, stack = {(left, top)}, [(left, top)]
    while stack:
        x, y = stack.pop()
        for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if left <= neighbor[0] <= right and top <= neighbor[1] <= bottom and neighbor not in outside and neighbor not in pixels:
                outside.add(neighbor)
                stack.append(neighbor)
    holes = {(x, y) for x in range(left, right + 1) for y in range(top, bottom + 1)} - outside - pixels
    if holes & blocked:
        raise ValueError("A mark encloses another mark")
    return pixels | holes


def read_marks(original: Path, marked: Path) -> dict[str, Pixels]:
    """Map exact mark colors to their pixels: those differing from the original frame."""
    base = Image.open(original).convert("RGB")
    painted = Image.open(marked)
    if painted.size != base.size:
        raise ValueError(f"{marked}: size differs from {original}")
    if painted.mode == "RGBA" and painted.getchannel("A").getextrema() != (255, 255):
        raise ValueError(f"{marked}: marks must be fully opaque")
    painted = painted.convert("RGB")
    before, after, width = base.tobytes(), painted.tobytes(), base.width
    by_color: dict[str, Pixels] = {}
    for y in range(base.height):
        row = slice(y * width * 3, (y + 1) * width * 3)
        if before[row] == after[row]:
            continue
        for x in range(width):
            offset = (y * width + x) * 3
            if before[offset : offset + 3] != after[offset : offset + 3]:
                by_color.setdefault("#%02x%02x%02x" % tuple(after[offset : offset + 3]), set()).add((x, y))
    everything = set().union(*by_color.values()) if by_color else set()
    result = {}
    for color, pixels in by_color.items():
        if len(components(pixels)) != 1:
            raise ValueError(f"{marked}: color {color} has more than one disconnected mark")
        result[color] = fill_holes(pixels, everything - pixels)
    return result


def derive(frames_dir: Path, marked_dir: Path) -> IdentityMarks:
    manifest = FramesManifest.model_validate_json((frames_dir.parent / "frames.json").read_text())
    recorded = {record.frame_index: record for record in manifest.frames}
    width, height = manifest.frames[0].width, manifest.frames[0].height
    groups = []
    for group_dir in sorted(path for path in marked_dir.iterdir() if path.is_dir()):
        cells: dict[str, list[FrameMark]] = {}
        indices = []
        for marked in sorted(group_dir.glob("frame_*.png")):
            index = int(marked.stem.removeprefix("frame_"))
            original = frames_dir / f"frame_{index:03d}.png"
            if index not in recorded or hash_file(original) != recorded[index].sha256:
                raise ValueError(f"{original}: not the frame recorded in frames.json")
            indices.append(index)
            for color, pixels in read_marks(original, marked).items():
                cells.setdefault(color, []).append(FrameMark(frame_index=index, pixels=to_runs(pixels)))
        groups.append(
            Group(
                name=group_dir.name,
                frames=indices,
                cells=[Cell(color=color, marks=marks) for color, marks in sorted(cells.items())],
            )
        )
    source = Source(path=manifest.source, sha256=manifest.source_sha256, width=width, height=height)
    return IdentityMarks(schema_version=1, source=source, groups=groups)


class MarkMatch(Record):
    """How the predicted cells cover one of your marks."""

    group: str
    color: str
    frame_index: int
    owners: Annotated[list[str], Field(description="Cells with the most mask pixels under the mark; ties keep every tied id.")]
    share: Annotated[float, Field(description="Fraction of the mark's pixels under the best-matching cell.")]
    shares: Annotated[dict[str, float], Field(description="Each cell's part of the mark; a pixel under several cells is split evenly.")]


class PairScore(Record):
    """Two marks that should be the same cell (same color) or different cells (different colors)."""

    kind: Literal["same_cell", "different_cell"]
    first: MarkMatch
    second: MarkMatch

    @computed_field
    @property
    def passed(self) -> bool:
        both = bool(self.first.owners) and bool(self.second.owners)
        shared = set(self.first.owners) & set(self.second.owners)
        if self.kind == "same_cell":
            return both and bool(shared)
        return both and not (len(self.first.owners) == 1 and self.first.owners == self.second.owners)

    @computed_field
    @property
    def score(self) -> float:
        """Pick a random pixel from each mark: the chance both are under the same cell (same-cell pairs) or under
        two different cells (different-cell pairs). Unmatched pixels count for neither."""
        first, second = self.first.shares, self.second.shares
        same = sum(share * second.get(cell, 0.0) for cell, share in first.items())
        if self.kind == "same_cell":
            return same
        return max(0.0, sum(first.values()) * sum(second.values()) - same)


class PairSummary(Record):
    passed: int
    total: int
    score: Annotated[float, Field(description="Mean pair score.")]


class Coverage(Record):
    passed: Annotated[int, Field(description="Marks touched by at least one predicted cell.")]
    total: int


class Evaluation(Record):
    """The scores for one annotation file; when it could not be scored, `valid` is false and `reason` says why."""

    valid: bool
    reason: str | None = None
    cells: Annotated[int, Field(description="Distinct cell ids in the file.")] = 0
    entries: Annotated[int, Field(description="Mask entries (cell, frame) in the file.")] = 0
    marks_covered: Coverage = Coverage(passed=0, total=0)
    mark_share: Annotated[float, Field(description="Mean over marks of the share under the best-matching cell.")] = 0.0
    same_cell: PairSummary = PairSummary(passed=0, total=0, score=0.0)
    different_cell: PairSummary = PairSummary(passed=0, total=0, score=0.0)
    failures: list[PairScore] = []

    @computed_field
    @property
    def all_pass(self) -> bool:
        covered = self.marks_covered
        return self.valid and not self.failures and covered.total > 0 and covered.passed == covered.total

    @classmethod
    def invalid(cls, reason: str) -> Self:
        return cls(valid=False, reason=reason[:2000])


def match_mark(mark: Pixels, masks: CellMasks, frame_index: int, *, group: str, color: str) -> MarkMatch:
    hits: dict[str, Pixels] = {}
    for entry in masks.masks:
        if entry.frame != frame_index:
            continue
        hit = {(x, y) for y, start, end in entry.mask for x in range(start, end) if (x, y) in mark}
        if hit:
            hits[entry.cell] = hit
    best = max((len(hit) for hit in hits.values()), default=0)
    covering = Counter(pixel for hit in hits.values() for pixel in hit)
    return MarkMatch(
        group=group,
        color=color,
        frame_index=frame_index,
        owners=sorted(cell for cell, hit in hits.items() if len(hit) == best),
        share=best / len(mark),
        shares={cell: sum(1 / covering[pixel] for pixel in hit) / len(mark) for cell, hit in hits.items()},
    )


def pair_scores(masks: CellMasks, marks: IdentityMarks) -> list[PairScore]:
    result = []
    for group in marks.groups:
        matches = [
            match_mark(to_pixels(mark.pixels), masks, mark.frame_index, group=group.name, color=cell.color)
            for cell in group.cells
            for mark in cell.marks
        ]
        for first, second in combinations(matches, 2):
            if first.frame_index == second.frame_index and first.color == second.color:
                continue
            result.append(PairScore(kind="same_cell" if first.color == second.color else "different_cell", first=first, second=second))
    return result


def score(masks: CellMasks, marks: IdentityMarks) -> Evaluation:
    pairs = pair_scores(masks, marks)
    matches = {(p.first.group, p.first.color, p.first.frame_index): p.first for p in pairs} | {
        (p.second.group, p.second.color, p.second.frame_index): p.second for p in pairs
    }

    def summary(kind: str) -> PairSummary:
        chosen = [p for p in pairs if p.kind == kind]
        mean = sum(p.score for p in chosen) / len(chosen) if chosen else 0.0
        return PairSummary(passed=sum(p.passed for p in chosen), total=len(chosen), score=mean)

    return Evaluation(
        valid=True,
        cells=len({entry.cell for entry in masks.masks}),
        entries=len(masks.masks),
        marks_covered=Coverage(passed=sum(bool(m.owners) for m in matches.values()), total=len(matches)),
        mark_share=sum(m.share for m in matches.values()) / len(matches) if matches else 0.0,
        same_cell=summary("same_cell"),
        different_cell=summary("different_cell"),
        failures=[p for p in pairs if not p.passed],
    )


def evaluate(annotations_json: str | bytes, marks: IdentityMarks, frame_count: int | None = None) -> Evaluation:
    """Score annotation JSON text; malformed or out-of-bounds input gives an invalid Evaluation, not an exception."""
    try:
        masks = CellMasks.model_validate_json(annotations_json)
        masks.check_bounds(marks.source.width, marks.source.height, frame_count)
        return score(masks, marks)
    except (ValidationError, ValueError) as error:
        return Evaluation.invalid(str(error))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    derive_parser = commands.add_parser("derive", help="Write identity marks from marked frame folders")
    derive_parser.add_argument("--frames", required=True, type=Path, help="Directory of original frames")
    derive_parser.add_argument("--marked", required=True, type=Path, help="Directory of one folder per group")
    derive_parser.add_argument("--output", required=True, type=Path)
    check_parser = commands.add_parser("check", help="Score annotations against identity marks")
    check_parser.add_argument("--annotations", required=True, type=Path)
    check_parser.add_argument("--marks", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.command == "derive":
        marks = derive(arguments.frames, arguments.marked)
        arguments.output.write_text(marks.model_dump_json(indent=1) + "\n")
        print(json.dumps({group.name: [cell.color for cell in group.cells] for group in marks.groups}))
        return
    marks = IdentityMarks.model_validate_json(arguments.marks.read_bytes())
    evaluation = evaluate(arguments.annotations.read_bytes(), marks)
    print(evaluation.model_dump_json(indent=2))
    if not evaluation.all_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
