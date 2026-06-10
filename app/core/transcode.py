"""On-the-fly transcoding of browser-incompatible video to fragmented MP4.

Containers/codecs that HTML5 `<video>` cannot decode (AVI/Xvid, MKV, WMV, …)
are remuxed/re-encoded to H.264/AAC MP4 by ffmpeg and streamed straight to the
client, so playback works inline (notably on iOS Safari) without a download.

Live transcoding is a single forward stream: there is no seeking, and the
response carries no Content-Length. Browsers play it from the start.
"""

import asyncio
import shutil
from pathlib import Path
from typing import AsyncGenerator, Optional

# Extensions browsers generally cannot play natively and that we transcode.
# Native formats (mp4/webm/ogg/mov/m4v) are served as-is via /api/download.
TRANSCODE_EXTS = frozenset({
    "avi", "mkv", "wmv", "flv", "mpg", "mpeg", "m2ts", "mts",
    "ts", "3gp", "vob", "divx", "asf", "rm", "rmvb", "ogv",
})

_READ_CHUNK = 64 * 1024


def is_transcodable(path: Path) -> bool:
    return path.suffix.lower().lstrip(".") in TRANSCODE_EXTS


def resolve_ffmpeg(configured: str = "") -> Optional[str]:
    """Return a usable ffmpeg executable path, or None if unavailable.

    Uses the configured path when given, otherwise looks up ``ffmpeg`` on PATH.
    """
    candidate = configured.strip() or "ffmpeg"
    return shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)


async def transcode_stream(path: Path, ffmpeg: str) -> AsyncGenerator[bytes, None]:
    """Yield fragmented-MP4 bytes produced by ffmpeg from ``path``.

    The ffmpeg process is always terminated when the generator is closed
    (client disconnect, playback stopped, or normal completion).
    """
    args = [
        ffmpeg,
        "-hide_banner", "-loglevel", "error",
        "-i", str(path),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        # Fragmented MP4 so it can be streamed without a seekable output.
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "-f", "mp4",
        "pipe:1",
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        assert proc.stdout is not None
        while True:
            chunk = await proc.stdout.read(_READ_CHUNK)
            if not chunk:
                break
            yield chunk
    finally:
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
