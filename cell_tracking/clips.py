"""Cut short lossless clips around marked groups, with identity marks remapped to the clip."""

from fractions import Fraction
from pathlib import Path

import av

from cell_tracking.core import Source
from cell_tracking.identity import FrameMark, Group, IdentityMarks
from cell_tracking.render import hash_file


def clip_range(group: Group, margin: int, frame_count: int) -> tuple[int, int]:
    """First and last source frame, inclusive: the group's frames plus a margin, within the video."""
    return max(0, group.frames[0] - margin), min(frame_count - 1, group.frames[-1] + margin)


def cut_clip(source: Path, first: int, last: int, output: Path) -> int:
    """Write source frames first..last as a lossless FFV1 AVI of RGB pixels; returns the frame count."""
    output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with av.open(str(source)) as reader, av.open(str(output), mode="w", format="avi") as writer:
        stream = None
        for index, frame in enumerate(reader.decode(video=0)):
            if index > last:
                break
            if index < first:
                continue
            if stream is None:
                stream = writer.add_stream("ffv1", rate=Fraction(2))
                stream.width, stream.height, stream.pix_fmt = frame.width, frame.height, "bgr0"
            for packet in stream.encode(av.VideoFrame.from_image(frame.to_image())):
                writer.mux(packet)
            written += 1
        if stream is not None:
            for packet in stream.encode():
                writer.mux(packet)
    if written != last - first + 1:
        raise ValueError(f"Source has no frames {first}..{last}")
    return written


def clip_marks(marks: IdentityMarks, group_name: str, first: int, clip: Path) -> IdentityMarks:
    """Marks for one group only, pointing at the clip with frame indices counted from the clip's start."""
    group = next(group for group in marks.groups if group.name == group_name)
    shifted = Group(
        name=group.name,
        frames=[index - first for index in group.frames],
        cells=[
            cell.model_copy(
                update={"marks": [FrameMark(frame_index=mark.frame_index - first, pixels=mark.pixels) for mark in cell.marks]}
            )
            for cell in group.cells
        ],
    )
    with av.open(str(clip)) as container:
        stream = container.streams.video[0]
        if (stream.width, stream.height) != (marks.source.width, marks.source.height):
            raise ValueError(f"{clip} is {stream.width}x{stream.height} but the marks are for {marks.source.width}x{marks.source.height}")
    source = Source(path=clip.name, sha256=hash_file(clip), width=marks.source.width, height=marks.source.height)
    return IdentityMarks(schema_version=1, source=source, groups=[shifted])
