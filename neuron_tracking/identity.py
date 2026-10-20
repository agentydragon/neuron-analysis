"""Derive identity marks from hand-painted frames and score annotations against them."""

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Annotated, Self

from PIL import Image
from pydantic import Field, StrictInt, ValidationError, model_validator

from neuron_tracking.annotations import Annotations, Mask, Record, Source
from neuron_tracking.render import hash_file

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
    manifest = json.loads((frames_dir.parent / "frames.json").read_text())
    recorded = {record["frame_index"]: record for record in manifest["frames"]}
    width, height = next(iter(recorded.values()))["width"], next(iter(recorded.values()))["height"]
    groups = []
    for group_dir in sorted(path for path in marked_dir.iterdir() if path.is_dir()):
        cells: dict[str, list[FrameMark]] = {}
        indices = []
        for marked in sorted(group_dir.glob("frame_*.png")):
            index = int(marked.stem.removeprefix("frame_"))
            original = frames_dir / f"frame_{index:03d}.png"
            if index not in recorded or hash_file(original) != recorded[index]["sha256"]:
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
    source = Source(path=manifest["source"], sha256=manifest["source_sha256"], width=width, height=height)
    return IdentityMarks(schema_version=1, source=source, groups=groups)


@dataclass(frozen=True)
class Owned:
    group: str
    color: str
    frame_index: int
    owners: frozenset[str]


@dataclass(frozen=True)
class Verdict:
    kind: str
    first: Owned
    second: Owned

    @property
    def passed(self) -> bool:
        both = bool(self.first.owners) and bool(self.second.owners)
        if self.kind == "same_cell":
            return both and bool(self.first.owners & self.second.owners)
        return both and not (len(self.first.owners) == 1 and self.first.owners == self.second.owners)


def owners_of(mark: Pixels, annotations: Annotations, frame_index: int) -> frozenset[str]:
    """Neurons with the most mask pixels (any layer) under the mark; ties keep every tied ID."""
    overlap: Counter[str] = Counter()
    for observation in annotations.observations:
        if observation.frame_index != frame_index:
            continue
        for _, mask in observation.iter_masks():
            for y, start, end in mask:
                overlap[observation.neuron_id] += sum(1 for x in range(start, end) if (x, y) in mark)
    best = max(overlap.values(), default=0)
    return frozenset(neuron for neuron, count in overlap.items() if best > 0 and count == best)


def verdicts(annotations: Annotations, marks: IdentityMarks) -> list[Verdict]:
    source = annotations.source
    if (source.sha256, source.width, source.height) != (marks.source.sha256, marks.source.width, marks.source.height):
        raise ValueError(f"Annotation source does not match identity marks for {marks.source.path}")
    available = {frame.frame_index for frame in annotations.frames}
    result = []
    for group in marks.groups:
        if missing := sorted(set(group.frames) - available):
            raise ValueError(f"Group {group.name}: annotations lack frames {missing}")
        owned = [
            Owned(group.name, cell.color, mark.frame_index, owners_of(to_pixels(mark.pixels), annotations, mark.frame_index))
            for cell in group.cells
            for mark in cell.marks
        ]
        for first, second in combinations(owned, 2):
            if first.frame_index == second.frame_index and first.color == second.color:
                continue
            result.append(Verdict("same_cell" if first.color == second.color else "different_cell", first, second))
    return result


def summarize(items: list[Verdict]) -> dict:
    def describe(owned: Owned) -> dict:
        return {"cell": owned.color, "frame": owned.frame_index, "neurons": sorted(owned.owners)}

    marks = {(v.first.group, v.first.color, v.first.frame_index): v.first for v in items} | {
        (v.second.group, v.second.color, v.second.frame_index): v.second for v in items
    }
    totals = {kind: [v for v in items if v.kind == kind] for kind in ("same_cell", "different_cell")}
    return {
        "marks_with_a_neuron": {"passed": sum(bool(m.owners) for m in marks.values()), "total": len(marks)},
        **{kind: {"passed": sum(v.passed for v in vs), "total": len(vs)} for kind, vs in totals.items()},
        "failures": [
            {"group": v.first.group, "kind": v.kind, "first": describe(v.first), "second": describe(v.second)}
            for v in items
            if not v.passed
        ],
    }


def evaluate(annotations_json: str | bytes, marks: IdentityMarks) -> dict:
    """Score annotation JSON text; malformed or mismatched input is reported, not raised."""
    try:
        annotations = Annotations.model_validate_json(annotations_json)
        report = summarize(verdicts(annotations, marks))
    except (ValidationError, ValueError) as error:
        return {"valid": False, "reason": str(error)[:2000]}
    return {"valid": True, **report}


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
    items = verdicts(
        Annotations.model_validate_json(arguments.annotations.read_bytes()),
        IdentityMarks.model_validate_json(arguments.marks.read_bytes()),
    )
    report = summarize(items)
    print(json.dumps(report, indent=2))
    if report["failures"] or report["marks_with_a_neuron"]["passed"] != report["marks_with_a_neuron"]["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
