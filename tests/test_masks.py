import json
from fractions import Fraction

import av
import pytest
from PIL import Image

from cell_tracking.masks import CellMask, CellMasks, VideoInfo, color_for


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


def test_colors_follow_sorted_ids(tmp_path):
    colors = masks().colors()
    assert list(colors) == ["a", "b"] and colors["a"] == color_for(0, 2) and colors["b"] == color_for(1, 2)


def test_video_info_reports_size_and_every_frame_time(tmp_path):
    video = tmp_path / "clip.avi"
    write_video(video)
    info = VideoInfo.probe(video)
    assert (info.width, info.height) == (32, 24) and len(info.timestamps_s) == 3
    assert info.timestamps_s == sorted(info.timestamps_s)
