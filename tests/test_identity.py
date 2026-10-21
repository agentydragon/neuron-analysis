import json

import pytest
from PIL import Image, ImageDraw

from cell_tracking.eval_frames import FramesManifest, FrameRecord
from cell_tracking.identity import derive, evaluate, fill_holes, match_mark, pair_scores, score, to_pixels
from cell_tracking.masks import CellMask, CellMasks
from cell_tracking.render import hash_file

RED, BLUE = (237, 28, 36), (0, 162, 232)
SIZE = (40, 30)


def make_eval(tmp_path, paint):
    """Two gray frames, 0 and 1, with one group whose marks come from paint(frame_index, draw)."""
    frames = tmp_path / "frames"
    frames.mkdir()
    records = []
    for index in (0, 1):
        path = frames / f"frame_{index:03d}.png"
        Image.new("RGB", SIZE, (120, 120, 120)).save(path)
        records.append(FrameRecord(frame_index=index, timestamp_s=float(index), file=path.name, width=SIZE[0], height=SIZE[1], sha256=hash_file(path)))
        painted = Image.new("RGBA", SIZE, (120, 120, 120, 255))
        paint(index, ImageDraw.Draw(painted))
        (tmp_path / "marked" / "pair").mkdir(parents=True, exist_ok=True)
        painted.save(tmp_path / "marked" / "pair" / path.name)
    (tmp_path / "frames.json").write_text(FramesManifest(source="clip.avi", source_sha256="a" * 64, frames=records).model_dump_json())
    return frames, tmp_path / "marked"


def paint_two_cells(index, draw):
    draw.rectangle((4 + index, 4, 7 + index, 7), fill=RED)
    draw.rectangle((20, 20, 23, 23), fill=BLUE)


def masks_for(owner_of_red):
    """Whole-cell masks: 'a' sits under the red marks and 'b' under blue, unless owner_of_red says otherwise."""
    boxes = {"a": (4, 4, 9, 8), "b": (20, 20, 24, 24), "c": (30, 2, 34, 6)}
    entries = []
    for index in (0, 1):
        for cell, (left, top, right, bottom) in boxes.items():
            runs = [(y, left, right) for y in range(top, bottom)]
            if cell == "a" and owner_of_red(index) != "a":
                runs = []
            if cell == owner_of_red(index) != "a":
                runs = [(y, 4, 9) for y in range(4, 8)]
            if runs:
                entries.append(CellMask(cell=cell, frame=index, mask=runs))
    return CellMasks(masks=entries)


def test_fill_holes_covers_outlined_cell():
    ring = {(x, y) for x in range(2, 7) for y in range(2, 7)} - {(x, y) for x in range(3, 6) for y in range(3, 6)}
    assert len(fill_holes(ring, set())) == 25


def test_derive_reads_only_changed_pixels(tmp_path):
    frames, marked = make_eval(tmp_path, paint_two_cells)
    marks = derive(frames, marked)
    group = marks.groups[0]
    assert group.frames == [0, 1]
    assert [cell.color for cell in group.cells] == ["#00a2e8", "#ed1c24"]
    assert len(to_pixels(group.cells[1].marks[0].pixels)) == 16


def test_derive_rejects_two_blobs_of_one_color(tmp_path):
    def paint(index, draw):
        draw.rectangle((1, 1, 3, 3), fill=RED)
        draw.rectangle((20, 20, 23, 23), fill=RED)

    frames, marked = make_eval(tmp_path, paint)
    with pytest.raises(ValueError, match="disconnected"):
        derive(frames, marked)


def test_scores_consistent_tracking(tmp_path):
    marks = derive(*make_eval(tmp_path, paint_two_cells))
    report = score(masks_for(lambda index: "a"), marks)
    assert report.failures == [] and report.all_pass
    assert (report.same_cell.passed, report.same_cell.total, report.same_cell.score) == (2, 2, 1.0)
    assert (report.different_cell.passed, report.different_cell.total, report.different_cell.score) == (4, 4, 1.0)
    assert report.mark_share == 1.0


def test_flags_identity_switch(tmp_path):
    marks = derive(*make_eval(tmp_path, paint_two_cells))
    report = score(masks_for(lambda index: "a" if index == 0 else "c"), marks)
    assert (report.same_cell.passed, report.same_cell.total, report.same_cell.score) == (1, 2, 0.5)
    assert [failure.kind for failure in report.failures] == ["same_cell"] and not report.all_pass


def test_flags_merged_cells_and_missed_marks(tmp_path):
    def paint(index, draw):
        draw.rectangle((4, 4, 6, 7), fill=RED)
        draw.rectangle((7, 4, 8, 7), fill=BLUE)  # beside red, inside the same cell
        draw.rectangle((30, 22, 33, 25), fill=(255, 242, 0))  # no cell here

    marks = derive(*make_eval(tmp_path, paint))
    report = score(masks_for(lambda index: "a"), marks)
    assert (report.marks_covered.passed, report.marks_covered.total) == (4, 6)
    assert any(failure.kind == "different_cell" for failure in report.failures)


def test_rejects_mark_enclosing_another(tmp_path):
    def paint(index, draw):
        draw.rectangle((4, 4, 9, 9), fill=RED)
        draw.rectangle((6, 6, 7, 7), fill=BLUE)

    frames, marked = make_eval(tmp_path, paint)
    with pytest.raises(ValueError, match="encloses"):
        derive(frames, marked)


def test_evaluate_reports_invalid_input_instead_of_raising(tmp_path):
    marks = derive(*make_eval(tmp_path, paint_two_cells))
    broken = evaluate("{not json", marks)
    assert broken.valid is False and broken.reason and not broken.all_pass
    good = evaluate(masks_for(lambda index: "a").model_dump_json(), marks, frame_count=2)
    assert good.valid and good.failures == [] and (good.cells, good.entries) == (3, 6)
    outside = CellMasks(masks=[CellMask(cell="a", frame=0, mask=[(2, 30, 60)])])
    assert "Out-of-bounds" in (evaluate(outside.model_dump_json(), marks).reason or "")
    late = CellMasks(masks=[CellMask(cell="a", frame=5, mask=[(2, 3, 6)])])
    assert "past the end" in (evaluate(late.model_dump_json(), marks, frame_count=2).reason or "")
    assert evaluate('{"masks": [], "extra": 1}', marks).valid is False  # unknown keys are rejected


def test_mark_share_reflects_partial_coverage_splits_and_misses(tmp_path):
    marks = derive(*make_eval(tmp_path, paint_two_cells))  # red 4x4 mark at x 4..7 (frame 0), blue 4x4 at x 20..23
    full = masks_for(lambda index: "a")
    assert score(full, marks).mark_share == 1.0
    # 'a' covers only the left half (x 4..5) of the red mark in both frames; 'b' covers the whole blue mark
    half = CellMasks(masks=[
        *(CellMask(cell="a", frame=index, mask=[(y, 4, 6) for y in range(4, 8)]) for index in (0, 1)),
        *(CellMask(cell="b", frame=index, mask=[(y, 20, 24) for y in range(20, 24)]) for index in (0, 1)),
    ])
    report = score(half, marks)
    assert (report.marks_covered.passed, report.marks_covered.total) == (4, 4)
    # red marks: frame 0 covers x 4..5 of 4..7 (0.5), frame 1 covers x 5 of 5..8 (0.25); blue marks: 1.0 each
    assert report.mark_share == pytest.approx((0.5 + 0.25 + 1.0 + 1.0) / 4)
    # a split: two cells share the red mark 8 pixels each, so the best cell covers half of it
    split = CellMasks(masks=[
        CellMask(cell="a", frame=0, mask=[(y, 4, 6) for y in range(4, 8)]),
        CellMask(cell="c", frame=0, mask=[(y, 6, 8) for y in range(4, 8)]),
        CellMask(cell="b", frame=0, mask=[(y, 20, 24) for y in range(20, 24)]),
    ])
    # only frame 0 has masks: red 0.5 (a tie, 8 of 16 pixels each), blue 1.0, and the two frame-1 marks are unmatched
    assert score(split, marks).mark_share == pytest.approx((0.5 + 1.0 + 0 + 0) / 4)
    nothing = CellMasks(masks=[CellMask(cell="z", frame=0, mask=[(25, 1, 3)])])
    assert score(nothing, marks).mark_share == 0.0


def test_pair_scores_are_fractions_for_split_and_partly_covered_marks(tmp_path):
    marks = derive(*make_eval(tmp_path, paint_two_cells))  # red: x 4..7 at frame 0, x 5..8 at frame 1; blue: x 20..23
    blue = [CellMask(cell="b", frame=index, mask=[(y, 20, 24) for y in range(20, 24)]) for index in (0, 1)]
    # frame 0: the red mark is split evenly between a and c; frame 1: it is entirely under a
    split = CellMasks(masks=[
        CellMask(cell="a", frame=0, mask=[(y, 4, 6) for y in range(4, 8)]),
        CellMask(cell="c", frame=0, mask=[(y, 6, 8) for y in range(4, 8)]),
        CellMask(cell="a", frame=1, mask=[(y, 5, 9) for y in range(4, 8)]),
        *blue,
    ])
    items = pair_scores(split, marks)
    same = next(v for v in items if v.kind == "same_cell" and v.first.color == "#ed1c24")
    assert same.score == pytest.approx(0.5) and same.passed  # binary view: a owns the frame-1 mark and ties with c in frame 0
    other = [v for v in items if v.kind == "different_cell"]
    assert all(v.score == pytest.approx(1.0) for v in other)
    report = score(split, marks)
    assert report.same_cell.score == pytest.approx((0.5 + 1.0) / 2)
    assert report.different_cell.score == pytest.approx(1.0)
    # the same cell covering only half of each red mark: 0.5 * 0.25 of random pixel pairs are under it in both
    half = CellMasks(masks=[
        *(CellMask(cell="a", frame=index, mask=[(y, 4, 6) for y in range(4, 8)]) for index in (0, 1)),
        *blue,
    ])
    soft = next(v for v in pair_scores(half, marks) if v.kind == "same_cell" and v.first.color == "#ed1c24")
    assert soft.score == pytest.approx(0.5 * 0.25)


def test_a_pixel_under_several_cells_is_split_evenly_between_them():
    mark = {(x, y) for x in range(4) for y in range(2)}
    twins = CellMasks(masks=[CellMask(cell=cell, frame=0, mask=[(y, 0, 4) for y in range(2)]) for cell in ("a", "b")])
    match = match_mark(mark, twins, 0, group="g", color="#ff0000")
    assert match.owners == ["a", "b"] and match.share == 1.0
    assert match.shares == {"a": pytest.approx(0.5), "b": pytest.approx(0.5)}




def test_rescale_resamples_marks_onto_a_larger_video():
    from cell_tracking.core import Source
    from cell_tracking.identity import Cell, FrameMark, Group, IdentityMarks, rescale, scale_pixels

    cell = Cell(color="#ff0000", marks=[FrameMark(frame_index=0, pixels=[(2, 1, 3), (3, 1, 3)])])
    marks = IdentityMarks(
        schema_version=1,
        source=Source(path="a.avi", sha256="a" * 64, width=8, height=6),
        groups=[Group(name="g", frames=[0], cells=[cell])],
    )
    target = Source(path="b.avi", sha256="b" * 64, width=16, height=12)
    scaled = rescale(marks, target)
    assert scaled.source == target
    # 2x in both directions: each old pixel becomes a 2x2 block, so 4 pixels -> 16
    assert len(to_pixels(scaled.groups[0].cells[0].marks[0].pixels)) == 16
    assert scale_pixels({(0, 0)}, (4, 4), (6, 6)) == {(0, 0), (1, 0), (0, 1), (1, 1)}
