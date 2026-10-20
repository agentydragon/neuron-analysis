import json
from fractions import Fraction

import av
import pytest
from PIL import Image

from cell_tracking.annotations import Annotations
from cell_tracking.masks import CellMask, CellMasks, color_for, load_annotations, to_annotations
from cell_tracking.render import Layer, hash_file, render


def write_video(path, count=3, size=(32, 24)):
    with av.open(str(path), mode="w", format="avi") as container:
        stream = container.add_stream("ffv1", rate=Fraction(2))
        stream.width, stream.height, stream.pix_fmt = size[0], size[1], "bgr0"
        for index in range(count):
            image = Image.new("RGB", size, (40 * index, 90, 200 - 40 * index))
            for packet in stream.encode(av.VideoFrame.from_image(image)):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def masks():
    return CellMasks(
        masks=[
            CellMask(cell="b", frame=0, mask=[(5, 4, 9)]),
            CellMask(cell="a", frame=0, mask=[(10, 12, 20), (11, 12, 15)]),
            CellMask(cell="a", frame=2, mask=[(10, 14, 22)]),
        ]
    )


def test_a_cell_may_appear_once_per_frame_and_never_with_an_empty_mask():
    with pytest.raises(ValueError, match="Duplicate"):
        CellMasks(masks=[CellMask(cell="a", frame=0, mask=[(1, 1, 2)]), CellMask(cell="a", frame=0, mask=[(2, 1, 2)])])
    with pytest.raises(ValueError, match="at least 1 item"):
        CellMasks(masks=[CellMask(cell="a", frame=0, mask=[])])


def test_bounds_and_run_order_are_checked_against_the_video():
    masks().check_bounds(32, 24, 3)
    with pytest.raises(ValueError, match="Out-of-bounds"):
        masks().check_bounds(16, 24, 3)
    with pytest.raises(ValueError, match="past the end"):
        masks().check_bounds(32, 24, 2)
    unsorted = CellMasks(masks=[CellMask(cell="a", frame=0, mask=[(9, 1, 3), (8, 1, 3)])])
    with pytest.raises(ValueError, match="sorted, disjoint and coalesced"):
        unsorted.check_bounds(32, 24)
    touching = CellMasks(masks=[CellMask(cell="a", frame=0, mask=[(9, 1, 3), (9, 3, 5)])])
    with pytest.raises(ValueError, match="sorted, disjoint and coalesced"):
        touching.check_bounds(32, 24)


def test_colors_are_assigned_deterministically_and_distinctly():
    colors = [color_for(index, 6) for index in range(6)]
    assert len(set(colors)) == 6 and colors == [color_for(index, 6) for index in range(6)]


def test_full_format_gets_sorted_ids_assigned_colors_and_absent_frames(tmp_path):
    video = tmp_path / "clip.avi"
    write_video(video)
    annotations = load_annotations(masks().model_dump_json(), video)
    assert [cell.id for cell in annotations.cells] == ["a", "b"]
    assert len({cell.color for cell in annotations.cells}) == 2
    assert len(annotations.frames) == 3 and len(annotations.observations) == 6
    absent = next(o for o in annotations.observations if o.cell_id == "b" and o.frame_index == 1)
    assert absent.visibility == "not_visible" and absent.body == []
    assert annotations.source.sha256 == hash_file(video) and (annotations.source.width, annotations.source.height) == (32, 24)


def test_full_format_files_still_load_for_rendering(tmp_path):
    video = tmp_path / "clip.avi"
    write_video(video)
    full = load_annotations(masks().model_dump_json(), video)
    again = load_annotations(full.model_dump_json(), video)
    assert again == full and isinstance(again, Annotations)


def test_renderer_draws_whole_cell_masks(tmp_path):
    video = tmp_path / "clip.avi"
    write_video(video)
    path = tmp_path / "annotations.json"
    path.write_text(masks().model_dump_json())
    report = render(video, path, tmp_path / "out" / "frame.png", frame_index=0, layer=Layer.COMBINED, cell_ids=None, labels=True)
    assert (tmp_path / "out" / "frame.png").exists() and report.frame_indices == [0]
    path.write_text(json.dumps({"masks": [{"cell": "a", "frame": 9, "mask": [[1, 1, 2]]}]}))
    with pytest.raises(ValueError, match="past the end"):
        render(video, path, tmp_path / "out" / "other.png", frame_index=0, layer=Layer.COMBINED, cell_ids=None, labels=True)
