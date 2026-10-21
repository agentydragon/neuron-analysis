import json
from fractions import Fraction

import av
from PIL import Image
import pytest

from cell_tracking import eval_frames
from cell_tracking.eval_frames import FramesManifest


def write_clip(path, count=4):
    with av.open(str(path), mode="w", format="avi") as container:
        stream = container.add_stream("ffv1", rate=Fraction(2))
        stream.width, stream.height, stream.pix_fmt = 64, 48, "bgr0"
        for index in range(count):
            image = Image.new("RGB", (64, 48), (index * 40,) * 3)
            for packet in stream.encode(av.VideoFrame.from_image(image)):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def test_extracts_selected_frames_with_manifest(tmp_path, monkeypatch):
    clip = tmp_path / "clip.avi"
    write_clip(clip)
    monkeypatch.setattr(
        "sys.argv", ["x", "--source", str(clip), "--output", str(tmp_path / "out"), "--frame", "2", "--frame", "0", "--sheets"]
    )
    eval_frames.main()
    manifest = FramesManifest.model_validate_json((tmp_path / "out" / "frames.json").read_text())
    assert [record.frame_index for record in manifest.frames] == [0, 2]
    assert manifest.frames[1].timestamp_s == pytest.approx(1.0)
    assert (tmp_path / "out" / "frames" / "frame_002.png").exists()
    assert list((tmp_path / "out" / "sheets").glob("sheet_*.png"))


def test_rejects_missing_frame(tmp_path, monkeypatch):
    clip = tmp_path / "clip.avi"
    write_clip(clip)
    monkeypatch.setattr("sys.argv", ["x", "--source", str(clip), "--output", str(tmp_path / "out"), "--frame", "9"])
    with pytest.raises(ValueError, match="no frame"):
        eval_frames.main()
