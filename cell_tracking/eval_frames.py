"""Extract lossless source frames and contact sheets for identity-mark labelling."""

import argparse
import json
from pathlib import Path

import av
from PIL import Image

from cell_tracking.hashing import hash_file
from cell_tracking.views import FrameRecord, FramesManifest, contact_sheets


def decode(source: Path) -> list[tuple[Image.Image, float]]:
    with av.open(str(source)) as container:
        return [(frame.to_image(), float(frame.time)) for frame in container.decode(video=0)]


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
