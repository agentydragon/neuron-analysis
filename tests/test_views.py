import hashlib
import json
from fractions import Fraction

import av
from PIL import Image
import pytest

from cell_tracking.masks import CellMask, CellMasks
from cell_tracking.render import render_frame
from cell_tracking.views import FramesManifest, export_views, main


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "source.avi"
    with av.open(str(path), "w", format="avi") as container:
        stream = container.add_stream("ffv1", rate=Fraction(2))
        stream.width, stream.height, stream.pix_fmt = 80, 60, "bgr0"
        for index in range(5):
            frame = av.VideoFrame.from_image(Image.new("RGB", (80, 60), (index * 30,) * 3))
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def test_raw_cli_preserves_every_native_frame_and_paginates(video, tmp_path, monkeypatch, capsys):
    output = tmp_path / "raw"
    monkeypatch.setattr("sys.argv", ["cell-views", "--source", str(video), "--output", str(output),
                                     "--per-sheet", "2", "--columns", "2", "--width", "80"])
    main()
    summary = json.loads(capsys.readouterr().out)
    assert summary["frames"] == 5 and len(summary["sheets"]) == 3
    manifest = FramesManifest.model_validate_json((output / "frames.json").read_text())
    assert [f.frame_index for f in manifest.frames] == list(range(5))
    assert [f.timestamp_s for f in manifest.frames] == [0, .5, 1, 1.5, 2]
    with av.open(str(video)) as container:
        originals = [frame.to_image() for frame in container.decode(video=0)]
    for record, original in zip(manifest.frames, originals, strict=True):
        path = output / "frames" / record.file
        with Image.open(path) as exported:
            assert exported.size == original.size
            assert exported.tobytes() == original.tobytes()
        assert record.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert manifest.sheets == ["sheet_000-001.png", "sheet_002-003.png", "sheet_004-004.png"]
    # The final, partial page contains the final source frame rather than dropping it.
    with Image.open(output / "sheets" / manifest.sheets[-1]) as sheet:
        assert sheet.size == (160, 60)
        assert sheet.getpixel((5, 45)) == (120, 120, 120)


def test_overlay_matches_renderer_and_records_exact_annotation_snapshot(video, tmp_path):
    masks = CellMasks(masks=[CellMask(cell="A", frame=2, mask=[(40, 50, 56)])])
    annotations = tmp_path / "annotations.json"
    annotations.write_text(masks.model_dump_json())
    original_annotations = annotations.read_bytes()
    output = tmp_path / "review"
    manifest = export_views(video, output, annotations=annotations, width=40)
    assert manifest.annotation_sha256 == hashlib.sha256(original_annotations).hexdigest()
    assert manifest.cell_colors == masks.colors()
    with av.open(str(video)) as container:
        for index, frame in enumerate(container.decode(video=0)):
            expected = render_frame(frame.to_image(), masks, masks.colors(), index, cell_ids={"A"}, labels=True)
            with Image.open(output / "frames" / f"frame_{index:03d}.png") as image:
                assert image.size == (80, 60)  # --width changes only contact-sheet tiles
                assert image.tobytes() == expected.tobytes()
    assert annotations.read_bytes() == original_annotations
    with pytest.raises(FileExistsError):
        export_views(video, output, annotations=annotations)
    assert annotations.read_bytes() == original_annotations


def test_invalid_annotation_does_not_get_a_success_manifest(video, tmp_path):
    annotations = tmp_path / "annotations.json"
    annotations.write_text(CellMasks(masks=[CellMask(cell="A", frame=99, mask=[(40, 50, 56)])]).model_dump_json())
    with pytest.raises(ValueError, match="past the end"):
        export_views(video, tmp_path / "review", annotations=annotations)
    assert not (tmp_path / "review" / "frames.json").exists()


@pytest.mark.parametrize("option", ["per_sheet", "columns", "width"])
def test_rejects_invalid_layout_before_creating_output(video, tmp_path, option):
    with pytest.raises(ValueError, match="positive"):
        export_views(video, tmp_path / "out", **{option: 0})
    assert not (tmp_path / "out").exists()
