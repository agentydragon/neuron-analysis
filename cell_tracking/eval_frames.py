"""Extract lossless source frames and contact sheets for identity-mark labelling."""

import argparse
import json
from pathlib import Path
from typing import Annotated

import av
from PIL import Image, ImageDraw, ImageFont
from pydantic import Field, StrictInt

from cell_tracking.annotations import Record
from cell_tracking.hashing import hash_file


class FrameRecord(Record):
    frame_index: Annotated[StrictInt, Field(ge=0)]
    timestamp_s: float
    file: str
    width: Annotated[StrictInt, Field(gt=0)]
    height: Annotated[StrictInt, Field(gt=0)]
    sha256: Annotated[str, Field(pattern="^[0-9a-f]{64}$")]


class FramesManifest(Record):
    """frames.json: the source video and each extracted frame, pinned by hash."""

    source: str
    source_sha256: Annotated[str, Field(pattern="^[0-9a-f]{64}$")]
    frames: Annotated[list[FrameRecord], Field(min_length=1)]


def decode(source: Path) -> list[tuple[Image.Image, float]]:
    with av.open(str(source)) as container:
        return [(frame.to_image(), float(frame.time)) for frame in container.decode(video=0)]


def contact_sheets(frames: list[tuple[Image.Image, float]], output: Path, *, per_sheet: int, columns: int, width: int) -> list[str]:
    height = round(width * frames[0][0].height / frames[0][0].width)
    font = ImageFont.load_default(size=22)
    rows = -(-per_sheet // columns)
    names = []
    for start in range(0, len(frames), per_sheet):
        sheet = Image.new("RGB", (columns * width, rows * height))
        draw = ImageDraw.Draw(sheet)
        for offset, (image, timestamp) in enumerate(frames[start : start + per_sheet]):
            left, top = (offset % columns) * width, (offset // columns) * height
            sheet.paste(image.resize((width, height), Image.Resampling.LANCZOS), (left, top))
            text = f"{start + offset}  {timestamp:.1f}s"
            draw.rectangle((left, top, left + 11 * len(text) + 8, top + 30), fill="black")
            draw.text((left + 4, top + 3), text, fill="yellow", font=font)
        name = f"sheet_{start:03d}-{min(start + per_sheet, len(frames)) - 1:03d}.png"
        sheet.save(output / name)
        names.append(name)
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Directory for frames/ and sheets/")
    parser.add_argument("--frame", type=int, action="append", default=[], help="Frame index to extract; repeatable")
    parser.add_argument("--sheets", action="store_true", help="Also write labelled contact sheets of every frame")
    arguments = parser.parse_args()
    frames = decode(arguments.source)
    bad = [index for index in arguments.frame if not 0 <= index < len(frames)]
    if bad:
        raise ValueError(f"Source has {len(frames)} frames; no frame(s) {bad}")
    frame_dir = arguments.output / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for index in sorted(set(arguments.frame)):
        image, timestamp = frames[index]
        path = frame_dir / f"frame_{index:03d}.png"
        image.save(path)
        records.append(
            FrameRecord(
                frame_index=index,
                timestamp_s=timestamp,
                file=path.name,
                width=image.width,
                height=image.height,
                sha256=hash_file(path),
            )
        )
    if records:
        manifest = FramesManifest(source=arguments.source.name, source_sha256=hash_file(arguments.source), frames=records)
        (arguments.output / "frames.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    if arguments.sheets:
        sheet_dir = arguments.output / "sheets"
        sheet_dir.mkdir(exist_ok=True)
        contact_sheets(frames, sheet_dir, per_sheet=20, columns=4, width=480)
    print(json.dumps({"frames": [record.frame_index for record in records], "source_frames": len(frames)}))


if __name__ == "__main__":
    main()
