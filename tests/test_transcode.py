"""Testes dos helpers de transcodificação de vídeo."""

import sys
from pathlib import Path

root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from app.core.transcode import is_transcodable, resolve_ffmpeg, TRANSCODE_EXTS  # noqa: E402


def test_transcodable_formats():
    assert is_transcodable(Path("/x/movie.avi"))
    assert is_transcodable(Path("/x/movie.MKV"))  # case-insensitive
    assert is_transcodable(Path("/x/clip.wmv"))


def test_native_formats_not_transcoded():
    for name in ("video.mp4", "video.webm", "video.ogg", "video.mov", "video.m4v"):
        assert not is_transcodable(Path("/x/" + name))


def test_non_video_not_transcoded():
    assert not is_transcodable(Path("/x/doc.pdf"))
    assert not is_transcodable(Path("/x/photo.jpg"))
    assert not is_transcodable(Path("/x/noext"))


def test_transcode_exts_lowercase_no_dot():
    assert all(e == e.lower() and not e.startswith(".") for e in TRANSCODE_EXTS)


def test_resolve_ffmpeg_missing_returns_none():
    assert resolve_ffmpeg("definitely-not-a-real-ffmpeg-binary-xyz") is None
