"""Render whole-cell masks over source video frames."""

import argparse
import hashlib
import json
from fractions import Fraction
from math import ceil
from pathlib import Path
from tempfile import TemporaryDirectory

import av
from PIL import Image, ImageColor, ImageDraw, ImageFont

from cell_tracking.core import Record, mask_center
from cell_tracking.hashing import hash_file
from cell_tracking.masks import CellMasks, VideoInfo


class RenderReport(Record):
    annotation_sha256: str
    source_sha256: str
    output_sha256: str
    labels: bool
    cell_colors: dict[str, str]
    frame_indices: list[int]
    source_timestamps_s: list[float]
    output_timestamps_s: list[float] | None
    source_duration_s: float | None
    output_duration_s: float | None
    output_source_frame_indices: list[int] | None = None


def render_frame(
    image: Image.Image, masks: CellMasks, colors: dict[str, str], frame_index: int, *, cell_ids: set[str], labels: bool
) -> Image.Image:
    rgb = {cell: ImageColor.getrgb(color) for cell, color in colors.items()}
    overlay = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(overlay)
    anchors: list[tuple[str, tuple[float, float]]] = []
    entries = sorted((e for e in masks.masks if e.frame == frame_index and e.cell in cell_ids), key=lambda e: e.cell)
    for entry in entries:
        for y, start, end in entry.mask:
            draw.line((start, y, end - 1, y), fill=(*rgb[entry.cell], 110))
        if (center := mask_center(entry.mask)) is not None:
            anchors.append((entry.cell, center))
    if labels:
        draw_labels(draw, anchors, colors=rgb, size=image.size)
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def draw_labels(
    draw: ImageDraw.ImageDraw,
    anchors: list[tuple[str, tuple[float, float]]],
    *,
    colors: dict[str, tuple[int, ...]],
    size: tuple[int, int],
) -> None:
    font = ImageFont.load_default(size=14)
    occupied: list[tuple[int, int, int, int]] = []
    for identity, (x, y) in anchors:
        left, top, right, bottom = draw.textbbox((0, 0), identity, font=font)
        width, height = ceil(right - left) + 6, ceil(bottom - top) + 6
        if width > size[0] or height > size[1]:
            raise ValueError(f"ID label does not fit frame: {identity!r}; use --no-labels")
        candidates = []
        for distance in (12, 30, 50, 75, 110):
            for dx, dy in ((distance, -height), (distance, distance), (-width - distance, -height), (-width, distance)):
                lx = max(0, min(size[0] - width, round(x + dx)))
                ly = max(0, min(size[1] - height, round(y + dy)))
                rectangle = (lx, ly, lx + width, ly + height)
                collisions = sum(
                    lx < occupied_right
                    and lx + width > occupied_left
                    and ly < occupied_bottom
                    and ly + height > occupied_top
                    for occupied_left, occupied_top, occupied_right, occupied_bottom in occupied
                )
                candidates.append((collisions, rectangle))
        _, rectangle = min(candidates, key=lambda candidate: candidate[0])
        occupied.append(rectangle)
        lx, ly, _, _ = rectangle
        color = colors[identity]
        draw.line((round(x), round(y), lx + width // 2, ly + height // 2), fill=(*color, 255))
        draw.rectangle(rectangle, fill=(0, 0, 0, 210), outline=(*color, 255))
        draw.text((lx + 3 - left, ly + 3 - top), identity, font=font, fill=(255, 255, 255, 255))


def check_frame(frame: av.VideoFrame, info: VideoInfo) -> None:
    if (frame.width, frame.height) != (info.width, info.height):
        raise ValueError("Decoded frame dimensions differ from the probed video")


def render(
    source: Path,
    annotation_path: Path,
    output: Path,
    *,
    frame_index: int | None,
    cell_ids: set[str] | None,
    labels: bool,
) -> RenderReport:
    annotation_bytes = annotation_path.read_bytes()
    masks = CellMasks.model_validate_json(annotation_bytes)
    info = VideoInfo.probe(source)
    frame_count = len(info.timestamps_s)
    masks.check_bounds(info.width, info.height, frame_count)
    report_path = output.with_suffix(output.suffix + ".json")
    if any(path.resolve() in (source.resolve(), annotation_path.resolve()) for path in (output, report_path)):
        raise ValueError("Output would overwrite an input")
    colors = masks.colors()
    selected = set(colors) if cell_ids is None else cell_ids
    if selected - set(colors):
        raise ValueError(f"Unknown cell IDs: {sorted(selected - set(colors))}")
    if frame_index is not None and not 0 <= frame_index < frame_count:
        raise ValueError(f"Source has no frame {frame_index}")
    expected_suffix = ".mp4" if frame_index is None else ".png"
    if output.suffix.lower() != expected_suffix:
        raise ValueError(f"Output must use {expected_suffix}")
    if frame_index is None and (info.width % 2 or info.height % 2):
        raise ValueError("H.264 yuv420p video needs even frame dimensions; export PNG frames for this source")
    output.parent.mkdir(parents=True, exist_ok=True)
    indices = list(range(frame_count)) if frame_index is None else [frame_index]
    output_times: list[float] | None = None
    source_duration: float | None = None
    output_duration: float | None = None
    output_indices: list[int] | None = None
    with TemporaryDirectory(dir=output.parent, prefix=".cell-render-") as temporary:
        rendered_path = Path(temporary) / output.name
        if frame_index is not None:
            with av.open(str(source)) as container:
                for index, frame in enumerate(container.decode(video=0)):
                    if index == frame_index:
                        check_frame(frame, info)
                        render_frame(frame.to_image(), masks, colors, index, cell_ids=selected, labels=labels).save(rendered_path)
                        break
        else:
            source_duration = measure_source(source, info)
            # Repeat frames at 30 fps for phone playback, keeping the source's total duration
            # (rounded up by less than one output frame) and its existing constant cadence.
            rate = 30
            frame_span = Fraction(str(source_duration)) * rate / frame_count
            output_indices = []
            with av.open(str(source)) as input_video, av.open(
                str(rendered_path), mode="w", format="mp4", options={"movflags": "+faststart"}
            ) as encoded:
                stream = encoded.add_stream(
                    "libx264", rate=rate,
                    options={"crf": "18", "preset": "medium", "profile": "high", "level": "4.0"},
                )
                stream.width = info.width
                stream.height = info.height
                stream.pix_fmt = "yuv420p"
                stream.codec_context.codec_tag = "avc1"
                stream.codec_context.thread_count = 2
                for index, frame in enumerate(input_video.decode(video=0)):
                    check_frame(frame, info)
                    image = render_frame(frame.to_image(), masks, colors, index, cell_ids=selected, labels=labels)
                    for output_index in range(len(output_indices), ceil((index + 1) * frame_span)):
                        rendered = av.VideoFrame.from_image(image)
                        rendered.pts = output_index
                        rendered.time_base = Fraction(1, rate)
                        for packet in stream.encode(rendered):
                            encoded.mux(packet)
                        output_indices.append(index)
                for packet in stream.encode():
                    encoded.mux(packet)
            output_times, output_duration = inspect_output(rendered_path, info, frame_count=len(output_indices))
        report = RenderReport(
            annotation_sha256=hashlib.sha256(annotation_bytes).hexdigest(),
            source_sha256=hash_file(source),
            output_sha256=hash_file(rendered_path),
            labels=labels,
            cell_colors={cell: color for cell, color in colors.items() if cell in selected},
            frame_indices=indices,
            source_timestamps_s=[info.timestamps_s[index] for index in indices],
            output_timestamps_s=output_times,
            source_duration_s=source_duration,
            output_duration_s=output_duration,
            output_source_frame_indices=output_indices,
        )
        temporary_report = Path(temporary) / report_path.name
        temporary_report.write_text(report.model_dump_json(indent=2) + "\n")
        rendered_path.replace(output)
        temporary_report.replace(report_path)
    return report


def measure_source(source: Path, info: VideoInfo) -> float:
    with av.open(str(source)) as container:
        end: Fraction | None = None
        for frame in container.decode(video=0):
            check_frame(frame, info)
            if frame.pts is None or frame.time_base is None or frame.duration <= 0:
                raise ValueError("Source needs explicit frame timestamps and positive frame durations")
            end = (frame.pts + frame.duration) * frame.time_base
        if end is None:
            raise ValueError("Source contains no video frames")
    return float(end) - info.timestamps_s[0]


def inspect_output(path: Path, info: VideoInfo, *, frame_count: int) -> tuple[list[float], float]:
    timestamps: list[float] = []
    end: Fraction | None = None
    with av.open(str(path)) as container:
        for frame in container.decode(video=0):
            if (frame.width, frame.height) != (info.width, info.height):
                raise ValueError("Encoded MP4 changed frame dimensions")
            if frame.time is None or frame.pts is None or frame.time_base is None or frame.duration <= 0:
                raise ValueError("Encoded MP4 lacks timestamps or frame durations")
            timestamps.append(frame.time)
            end = (frame.pts + frame.duration) * frame.time_base
    if len(timestamps) != frame_count or end is None:
        raise ValueError("Encoded MP4 changed frame count")
    return timestamps, float(end)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--frame", type=int, help="Render one frame to PNG; omit to export the entire H.264 MP4")
    parser.add_argument("--cell", action="append", help="Render only this cell id; repeat to select several")
    parser.add_argument("--no-labels", action="store_true")
    arguments = parser.parse_args()
    report = render(
        arguments.source,
        arguments.annotations,
        arguments.output,
        frame_index=arguments.frame,
        cell_ids=None if arguments.cell is None else set(arguments.cell),
        labels=not arguments.no_labels,
    )
    print(json.dumps({"output": str(arguments.output), "frames": len(report.frame_indices)}))


if __name__ == "__main__":
    main()
