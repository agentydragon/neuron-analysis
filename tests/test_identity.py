import json

import pytest
from PIL import Image, ImageDraw

from cell_tracking.annotations import Annotations
from cell_tracking.eval_frames import FramesManifest, FrameRecord
from cell_tracking.identity import derive, evaluate, fill_holes, from_annotations, summarize, to_pixels, verdicts
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


def full_annotations(owner_of_red):
    """Cell 'a' sits under the red marks and 'b' under blue, unless owner_of_red says otherwise."""
    boxes = {"a": (4, 4, 9, 8), "b": (20, 20, 24, 24), "c": (30, 2, 34, 6)}
    observations = []
    for index in (0, 1):
        for cell, (left, top, right, bottom) in boxes.items():
            runs = [[y, left, right] for y in range(top, bottom)]
            if cell == "a" and owner_of_red(index) != "a":
                runs = []
            if cell == owner_of_red(index) != "a":
                runs = [[y, 4, 9] for y in range(4, 8)]
            observations.append(
                {
                    "cell_id": cell,
                    "frame_index": index,
                    "visibility": "visible" if runs else "not_visible",
                    "body": runs,
                    "branches": [],
                    "uncertain": [],
                    "review": "proposed",
                }
            )
    return Annotations.model_validate_json(
        json.dumps(
            {
            "schema_version": 1,
            "revision": 1,
            "source": {"path": "clip.avi", "sha256": "a" * 64, "width": SIZE[0], "height": SIZE[1]},
            "frames": [{"frame_index": 0, "timestamp_s": 0.0}, {"frame_index": 1, "timestamp_s": 1.0}],
            "cells": [{"id": n, "color": c} for n, c in (("a", "#ff0000"), ("b", "#00ff00"), ("c", "#0000ff"))],
            "observations": observations,
            }
        )
    )


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
    report = summarize(verdicts(masks_for(lambda index: "a"), marks))
    assert report["failures"] == []
    assert report["same_cell"] == {"passed": 2, "total": 2}
    assert report["different_cell"] == {"passed": 4, "total": 4}


def test_flags_identity_switch(tmp_path):
    marks = derive(*make_eval(tmp_path, paint_two_cells))
    report = summarize(verdicts(masks_for(lambda index: "a" if index == 0 else "c"), marks))
    assert report["same_cell"] == {"passed": 1, "total": 2}
    assert [failure["kind"] for failure in report["failures"]] == ["same_cell"]


def test_flags_merged_cells_and_missed_marks(tmp_path):
    def paint(index, draw):
        draw.rectangle((4, 4, 6, 7), fill=RED)
        draw.rectangle((7, 4, 8, 7), fill=BLUE)  # beside red, inside the same cell
        draw.rectangle((30, 22, 33, 25), fill=(255, 242, 0))  # no cell here

    marks = derive(*make_eval(tmp_path, paint))
    report = summarize(verdicts(masks_for(lambda index: "a"), marks))
    assert report["marks_covered"] == {"passed": 4, "total": 6}
    assert any(failure["kind"] == "different_cell" for failure in report["failures"])


def test_rejects_mark_enclosing_another(tmp_path):
    def paint(index, draw):
        draw.rectangle((4, 4, 9, 9), fill=RED)
        draw.rectangle((6, 6, 7, 7), fill=BLUE)

    frames, marked = make_eval(tmp_path, paint)
    with pytest.raises(ValueError, match="encloses"):
        derive(frames, marked)


def test_evaluate_reports_invalid_input_instead_of_raising(tmp_path):
    marks = derive(*make_eval(tmp_path, paint_two_cells))
    assert evaluate("{not json", marks)["valid"] is False
    good = evaluate(masks_for(lambda index: "a").model_dump_json(), marks, frame_count=2)
    assert good["valid"] is True and good["failures"] == [] and good["cells"] == 3 and good["entries"] == 6
    outside = CellMasks(masks=[CellMask(cell="a", frame=0, mask=[(2, 30, 60)])])
    assert "Out-of-bounds" in evaluate(outside.model_dump_json(), marks)["reason"]
    late = CellMasks(masks=[CellMask(cell="a", frame=5, mask=[(2, 3, 6)])])
    assert "past the end" in evaluate(late.model_dump_json(), marks, frame_count=2)["reason"]


def test_full_format_files_are_scored_through_conversion(tmp_path):
    marks = derive(*make_eval(tmp_path, paint_two_cells))
    report = evaluate(full_annotations(lambda index: "a").model_dump_json(), marks, frame_count=2)
    assert report["valid"] is True and report["failures"] == []


def test_conversion_merges_every_layer_of_visible_observations():
    document = json.loads(full_annotations(lambda index: "a").model_dump_json())
    row = next(row for row in document["observations"] if row["cell_id"] == "b" and row["frame_index"] == 0)
    row["branches"], row["uncertain"] = [[25, 20, 24]], [[26, 20, 22]]
    masks = from_annotations(Annotations.model_validate_json(json.dumps(document)))
    entry = next(entry for entry in masks.masks if entry.cell == "b" and entry.frame == 0)
    assert len(to_pixels(entry.mask)) == 16 + 4 + 2
    assert not any(entry.cell == "a" and entry.frame == 5 for entry in masks.masks)


def test_files_saved_with_the_earlier_field_names_are_still_read():
    from cell_tracking.legacy import parse_annotations

    current = full_annotations(lambda index: "a")
    legacy = json.loads(current.model_dump_json())
    legacy["neurons"] = legacy.pop("cells")
    for row in legacy["observations"]:
        row["neuron_id"] = row.pop("cell_id")
    assert "cells" not in legacy and "neuron_id" in legacy["observations"][0]
    assert parse_annotations(json.dumps(legacy)) == current
    assert parse_annotations(current.model_dump_json()) == current
