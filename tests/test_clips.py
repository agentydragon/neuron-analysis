from fractions import Fraction

import av
import pytest
from PIL import Image

from neuron_tracking.clips import clip_marks, clip_range, cut_clip
from neuron_tracking.identity import Cell, FrameMark, Group, IdentityMarks
from neuron_tracking.annotations import Source


def write_source(path, count=10):
    with av.open(str(path), mode="w", format="avi") as container:
        stream = container.add_stream("ffv1", rate=Fraction(2))
        stream.width, stream.height, stream.pix_fmt = 32, 24, "bgr0"
        for index in range(count):
            image = Image.new("RGB", (32, 24), (index * 20, 255 - index * 20, 7 * index))
            for packet in stream.encode(av.VideoFrame.from_image(image)):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def frames(path):
    with av.open(str(path)) as container:
        return [frame.to_image().tobytes() for frame in container.decode(video=0)]


def make_marks():
    cell = Cell(color="#ff0000", marks=[FrameMark(frame_index=3, pixels=[(5, 4, 8)]), FrameMark(frame_index=6, pixels=[(6, 4, 8)])])
    group = Group(name="3-6", frames=[3, 6], cells=[cell])
    return IdentityMarks(schema_version=1, source=Source(path="a.avi", sha256="a" * 64, width=32, height=24), groups=[group])


def test_clip_range_adds_margin_within_the_video():
    group = make_marks().groups[0]
    assert clip_range(group, 2, 10) == (1, 8)
    assert clip_range(group, 5, 10) == (0, 9)


def test_clip_is_pixel_identical_to_the_source_frames(tmp_path):
    source = tmp_path / "a.avi"
    write_source(source)
    assert cut_clip(source, 2, 7, tmp_path / "clip.avi") == 6
    assert frames(tmp_path / "clip.avi") == frames(source)[2:8]


def test_cut_clip_rejects_frames_past_the_end(tmp_path):
    source = tmp_path / "a.avi"
    write_source(source, count=4)
    with pytest.raises(ValueError, match="no frames"):
        cut_clip(source, 2, 7, tmp_path / "clip.avi")


def test_marks_follow_the_clip_with_shifted_frame_indices(tmp_path):
    source = tmp_path / "a.avi"
    write_source(source)
    cut_clip(source, 2, 7, tmp_path / "clip.avi")
    shifted = clip_marks(make_marks(), "3-6", 2, tmp_path / "clip.avi")
    group = shifted.groups[0]
    assert group.frames == [1, 4]
    assert [mark.frame_index for mark in group.cells[0].marks] == [1, 4]
    assert shifted.source.path == "clip.avi" and shifted.source.sha256 != "a" * 64
