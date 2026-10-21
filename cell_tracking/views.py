"""Export full-resolution source or mask-overlay PNGs and labelled contact sheets."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Annotated

import av
from PIL import Image, ImageDraw, ImageFont
from pydantic import Field, StrictInt

from cell_tracking.core import Record
from cell_tracking.hashing import hash_file
from cell_tracking.masks import CellMasks
from cell_tracking.render import render_frame


class FrameRecord(Record):
    frame_index: Annotated[StrictInt, Field(ge=0)]
    timestamp_s: float
    file: str
    width: Annotated[StrictInt, Field(gt=0)]
    height: Annotated[StrictInt, Field(gt=0)]
    sha256: Annotated[str, Field(pattern="^[0-9a-f]{64}$")]


class FramesManifest(Record):
    """frames.json: source, optional saved masks, and exported frames pinned by hash."""

    source: str
    source_sha256: Annotated[str, Field(pattern="^[0-9a-f]{64}$")]
    frames: Annotated[list[FrameRecord], Field(min_length=1)]
    annotation_sha256: Annotated[str, Field(pattern="^[0-9a-f]{64}$")] | None = None
    cell_colors: dict[str, str] | None = None
    sheets: list[str] = Field(default_factory=list)


def contact_sheets(frames: list[tuple[Image.Image, float]], output: Path, *, per_sheet: int, columns: int, width: int) -> list[str]:
    """Label every frame in decode order; scale only the sheets, never the exported frame PNGs."""
    if min(per_sheet, columns, width) <= 0:
        raise ValueError("per_sheet, columns and width must be positive")
    if not frames:
        return []
    output.mkdir(parents=True, exist_ok=True)
    height = max(1, round(width * frames[0][0].height / frames[0][0].width))
    font = ImageFont.load_default(size=22)
    names = []
    for start in range(0, len(frames), per_sheet):
        page = frames[start:start + per_sheet]
        rows = -(-len(page) // columns)
        sheet = Image.new("RGB", (columns * width, rows * height))
        draw = ImageDraw.Draw(sheet)
        for offset, (image, timestamp) in enumerate(page):
            left, top = (offset % columns) * width, (offset // columns) * height
            sheet.paste(image.resize((width, height), Image.Resampling.LANCZOS), (left, top))
            text = f"{start + offset}  {timestamp:.1f}s"
            draw.rectangle((left, top, left + 11 * len(text) + 8, top + 30), fill="black")
            draw.text((left + 4, top + 3), text, fill="yellow", font=font)
        name = f"sheet_{start:03d}-{start + len(page) - 1:03d}.png"
        sheet.save(output / name)
        names.append(name)
    return names


def export_views(source: Path, output: Path, *, annotations: Path | None = None,
                 per_sheet: int = 20, columns: int = 4, width: int = 480) -> FramesManifest:
    if min(per_sheet, columns, width) <= 0:
        raise ValueError("per_sheet, columns and width must be positive")
    annotation_bytes = annotations.read_bytes() if annotations is not None else None
    masks = CellMasks.model_validate_json(annotation_bytes) if annotation_bytes is not None else None
    colors = masks.colors() if masks is not None else {}
    # A fresh directory keeps old sheets and overlays from masquerading as the current review.
    output.mkdir(parents=True, exist_ok=False)
    frame_dir = output / "frames"
    frame_dir.mkdir()
    thumbnails = []
    records = []
    with av.open(str(source)) as container:
        size = None
        for index, frame in enumerate(container.decode(video=0)):
            if size is None:
                size = frame.width, frame.height
                if masks is not None:
                    masks.check_bounds(*size)
            if (frame.width, frame.height) != size:
                raise ValueError("Source frame dimensions changed")
            if frame.time is None:
                raise ValueError("Source frame has no timestamp")
            image = frame.to_image()
            if masks is not None:
                image = render_frame(image, masks, colors, index, cell_ids=set(colors), labels=True)
            path = frame_dir / f"frame_{index:03d}.png"
            image.save(path)
            records.append(FrameRecord(frame_index=index, timestamp_s=float(frame.time), file=path.name,
                                       width=frame.width, height=frame.height, sha256=hash_file(path)))
            # Retain thumbnails, rather than all native-resolution frames, for bounded memory use.
            thumbnails.append((image.resize((width, max(1, round(width * image.height / image.width))),
                                            Image.Resampling.LANCZOS), float(frame.time)))
    if size is None:
        raise ValueError("Source contains no video frames")
    if masks is not None:
        masks.check_bounds(*size, len(records))
    sheets = contact_sheets(thumbnails, output / "sheets", per_sheet=per_sheet, columns=columns, width=width)
    manifest = FramesManifest(
        source=source.name, source_sha256=hash_file(source), frames=records,
        annotation_sha256=hashlib.sha256(annotation_bytes).hexdigest() if annotation_bytes is not None else None,
        cell_colors=colors if masks is not None else None, sheets=sheets,
    )
    (output / "frames.json").write_text(manifest.model_dump_json(indent=2, exclude_none=True) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New directory for frames/, sheets/ and frames.json")
    parser.add_argument("--annotations", type=Path, help="Render these saved masks with stable colors and readable IDs")
    parser.add_argument("--per-sheet", type=int, default=20)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--width", type=int, default=480, help="Contact-sheet tile width; frame PNGs keep original pixels")
    args = parser.parse_args()
    result = export_views(args.source, args.output, annotations=args.annotations,
                          per_sheet=args.per_sheet, columns=args.columns, width=args.width)
    print(json.dumps({"frames": len(result.frames), "frame_directory": str(args.output / "frames"),
                      "sheets": [str(args.output / "sheets" / name) for name in result.sheets],
                      "manifest": str(args.output / "frames.json")}))


if __name__ == "__main__":
    main()
