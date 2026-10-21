"""Synthetic pixels exercise rendering, identity colors, and media round trips."""

import json
from fractions import Fraction
from pathlib import Path

import av
import pytest
from PIL import Image
from pydantic import ValidationError

from cell_tracking.masks import CellMask, CellMasks
from cell_tracking.render import RenderReport, hash_file, render, render_frame


def make_masks(frame_count: int) -> CellMasks:
    entries = []
    for index in range(frame_count):
        for cell, x, y in (("N001", 20 if index % 2 == 0 else 80, 30), ("N002", 80 if index % 2 == 0 else 20, 60)):
            entries.append(CellMask(cell=cell, frame=index, mask=[(y, x, x + 3), (y + 1, x, x + 4)]))
    return CellMasks(masks=entries)


@pytest.fixture
def sample(tmp_path: Path) -> tuple[Path, Path, CellMasks]:
    source = tmp_path / "source.mkv"
    with av.open(str(source), mode="w") as container:
        stream = container.add_stream("ffv1", rate=2)
        stream.width = 128
        stream.height = 96
        stream.pix_fmt = "bgr0"
        stream.time_base = Fraction(1, 1000)
        stream.codec_context.time_base = Fraction(1, 1000)
        for timestamp in (0, 400, 900):
            frame = av.VideoFrame.from_image(Image.new("RGB", (128, 96), (100, 100, 100)))
            frame.pts = timestamp
            frame.time_base = Fraction(1, 1000)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    with av.open(str(source)) as container:
        assert [frame.time for frame in container.decode(video=0)] == [0, 0.4, 0.9]
    masks = make_masks(3)
    path = tmp_path / "annotations.json"
    path.write_text(masks.model_dump_json())
    return source, path, masks


def test_pixels_and_identity_colors(sample: tuple[Path, Path, CellMasks]) -> None:
    _, _, masks = sample
    colors = masks.colors()
    raw = Image.new("RGB", (128, 96), (100, 100, 100))
    for index in (0, 1):
        both = render_frame(raw, masks, colors, index, cell_ids={"N001", "N002"}, labels=False)
        first_x, second_x = (20, 80) if index == 0 else (80, 20)
        first, second = both.getpixel((first_x, 30)), both.getpixel((second_x, 60))
        assert isinstance(first, tuple) and isinstance(second, tuple)
        assert first[0] > first[1] == first[2]  # the first id by sort order gets the red end of the palette
        assert second[1] == second[2] > second[0]
        assert both.getpixel((first_x + 3, 30)) == raw.getpixel((first_x + 3, 30))  # run ends are exclusive
        assert both.getpixel((first_x + 3, 31)) != raw.getpixel((first_x + 3, 31))
    only_first = render_frame(raw, masks, colors, 0, cell_ids={"N001"}, labels=False)
    assert only_first.getpixel((20, 30)) != raw.getpixel((20, 30))
    assert only_first.getpixel((80, 60)) == raw.getpixel((80, 60))


def test_png_matches_lossless_avi_and_timing_is_reported(sample: tuple[Path, Path, CellMasks], tmp_path: Path) -> None:
    source, path, masks = sample
    png = tmp_path / "frame.png"
    still = render(source, path, png, frame_index=1, cell_ids=None, labels=True)
    avi = tmp_path / "annotated.avi"
    report = render(source, path, avi, frame_index=None, cell_ids=None, labels=True)
    with av.open(str(avi)) as container:
        images = [frame.to_image() for frame in container.decode(video=0)]
    assert len(images) == 3
    assert all(image.size == (128, 96) for image in images)
    with Image.open(png) as image:
        assert images[1].tobytes() == image.tobytes()
    assert still.cell_colors == report.cell_colors == masks.colors()
    assert report.frame_indices == [0, 1, 2]
    assert report.source_timestamps_s == [0, 0.4, 0.9]
    assert report.output_timestamps_s == pytest.approx([0, 7 / 15, 14 / 15])
    assert report.source_duration_s == pytest.approx(1.4)
    assert report.output_duration_s == pytest.approx(1.4)
    assert report.output_sha256 == hash_file(avi)
    assert report.annotation_sha256 == hash_file(path)
    assert RenderReport.model_validate_json(avi.with_suffix(".avi.json").read_text()) == report


def test_a_sparse_file_still_exports_every_source_frame(sample: tuple[Path, Path, CellMasks], tmp_path: Path) -> None:
    source, path, _ = sample
    path.write_text(CellMasks(masks=[CellMask(cell="only", frame=1, mask=[(30, 20, 30)])]).model_dump_json())
    avi = tmp_path / "sparse.avi"
    render(source, path, avi, frame_index=None, cell_ids=None, labels=False)
    raw = Image.new("RGB", (128, 96), (100, 100, 100))
    with av.open(str(avi)) as container:
        images = [frame.to_image() for frame in container.decode(video=0)]
    assert len(images) == 3
    assert images[0].tobytes() == raw.tobytes() and images[2].tobytes() == raw.tobytes()
    assert images[1].tobytes() != raw.tobytes()


@pytest.mark.parametrize("failure", ["bounds", "unsorted", "touching", "frame", "duplicate", "empty"])
def test_invalid_annotations_are_rejected(sample: tuple[Path, Path, CellMasks], tmp_path: Path, failure: str) -> None:
    source, path, masks = sample
    data = json.loads(masks.model_dump_json())
    entry = data["masks"][0]
    match failure:
        case "bounds":
            entry["mask"] = [[30, 128, 129]]
        case "unsorted":
            entry["mask"] = [[31, 20, 23], [30, 20, 23]]
        case "touching":
            entry["mask"] = [[30, 20, 23], [30, 23, 25]]
        case "frame":
            entry["frame"] = 9
        case "duplicate":
            data["masks"].append(dict(entry))
        case "empty":
            entry["mask"] = []
    path.write_text(json.dumps(data))
    expected = ValidationError if failure in ("duplicate", "empty") else ValueError
    with pytest.raises(expected):
        render(source, path, tmp_path / "bad.png", frame_index=0, cell_ids=None, labels=True)
    assert not (tmp_path / "bad.png").exists()


def test_input_overwrite_unknown_ids_and_missing_frames_are_rejected(sample: tuple[Path, Path, CellMasks], tmp_path: Path) -> None:
    source, path, _ = sample
    with pytest.raises(ValueError, match="overwrite"):
        render(source, path, source, frame_index=None, cell_ids=None, labels=True)
    with pytest.raises(ValueError, match="Unknown cell IDs"):
        render(source, path, tmp_path / "x.png", frame_index=0, cell_ids={"nope"}, labels=True)
    with pytest.raises(ValueError, match="no frame 7"):
        render(source, path, tmp_path / "y.png", frame_index=7, cell_ids=None, labels=True)
    with pytest.raises(ValueError, match="must use .png"):
        render(source, path, tmp_path / "z.avi", frame_index=0, cell_ids=None, labels=True)
