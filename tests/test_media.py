"""Video/audio via the bundled ffmpeg."""
import subprocess
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("imageio_ffmpeg")
from dragshift import convert, media  # noqa: E402
from dragshift.util import UserError, category  # noqa: E402


@pytest.fixture(scope="module")
def clip(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("v") / "clip.mov"
    subprocess.run([media.ffmpeg_exe(), "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30:duration=3",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                    "-c:v", "mpeg4", "-q:v", "2", "-c:a", "aac", "-shortest", str(out)], check=True)
    return out


def test_categories_and_targets():
    assert category("a.mp4") == category("b.MOV") == "video"
    assert category("c.wav") == "audio"
    assert convert.targets_for("video", ".mp4") == ["GIF", "MP3"]
    assert convert.targets_for("audio", ".mp3") == ["WAV", "M4A"]


def test_probe(clip):
    info = media.probe(clip)
    assert info["video"] and info["audio"] and (info["width"], info["height"]) == (1920, 1080)
    assert 2.5 < info["duration"] < 3.5


def test_video_to_mp4_gif_mp3_with_progress(clip):
    seen = []
    mp4 = convert.convert(clip, "video", "MP4")[0]
    assert mp4.suffix == ".mp4" and media.probe(mp4)["video"]
    gif = media.to_gif(clip, seen.append)[0]
    with Image.open(gif) as im:
        assert im.size == (640, 360) and im.n_frames > 20
    assert seen and seen[-1] == 1.0
    mp3 = convert.convert(clip, "video", "MP3")[0]
    info = media.probe(mp3)
    assert info["audio"] and not info["video"]


def test_compress_video(clip):
    out = media.compress_video(clip)[0]
    info = media.probe(out)
    assert out.name == "clip Compressed.mp4" and info["width"] == 1280
    assert out.stat().st_size < clip.stat().st_size


def test_audio_conversion(clip, tmp_path):
    wav = media.to_audio(clip, "WAV")[0]
    m4a = convert.convert(wav, "audio", "M4A")[0]
    assert media.probe(m4a)["audio"]


def test_not_media(tmp_path):
    bad = tmp_path / "x.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(UserError):
        media.probe(bad)
