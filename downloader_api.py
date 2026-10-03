import os
import re
import hmac
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field
import yt_dlp

app = FastAPI(title="VidSprint Downloader", version="1.0.0")


class DownloadRequest(BaseModel):
    video_id: str = Field(min_length=6, max_length=32)
    mode: str = Field(pattern="^(MP4 video|MP3 audio)$")
    quality: int = Field(default=720, ge=144, le=2160)
    authorized: bool = False


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._ -]+", "", value).strip()
    return (value[:120] or "vidsprint_download")


def friendly_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "sign in to confirm" in lowered or "not a bot" in lowered:
        return (
            "YouTube blocked this server with an automated-traffic verification. "
            "Search and playback still work. For content you own, use a private "
            "local downloader or an authorized private server; VidSprint does not "
            "collect browser cookies."
        )
    if "http error 403" in lowered:
        return (
            "YouTube rejected the stream request (HTTP 403). Try again later or "
            "use a private authorized downloader for content you own."
        )
    return message


@app.get("/health")
def health():
    return {"status": "ok", "service": "vidsprint-downloader"}


@app.post("/download")
def download(request: DownloadRequest, x_vidsprint_token: str | None = Header(default=None)):
    expected_token = os.getenv("DOWNLOADER_API_TOKEN", "").strip()
    if expected_token and not hmac.compare_digest(x_vidsprint_token or "", expected_token):
        raise HTTPException(status_code=401, detail="Invalid downloader service token.")

    if not request.authorized:
        raise HTTPException(
            status_code=400,
            detail="Confirm that you own the content or have permission to download it.",
        )

    folder = Path(tempfile.mkdtemp(prefix="vidsprint_"))
    output = str(folder / "%(title).120s.%(ext)s")
    url = f"https://www.youtube.com/watch?v={request.video_id}"

    options = {
        "outtmpl": output,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 8,
        "max_filesize": 500 * 1024 * 1024,
        "js_runtimes": {"node": {}},
    }

    # Optional private deployment support. This file must be supplied by the
    # service owner as a Render Secret File; it is never accepted from users.
    cookie_file = Path(
        os.getenv("YOUTUBE_COOKIES_FILE", "/etc/secrets/youtube_cookies.txt")
    )
    if cookie_file.is_file():
        options["cookiefile"] = str(cookie_file)

    if request.mode == "MP3 audio":
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        options.update({
            "format": (
                f"bestvideo[height<={request.quality}][ext=mp4]+"
                f"bestaudio[ext=m4a]/best[height<={request.quality}][ext=mp4]/best"
            ),
            "merge_output_format": "mp4",
        })

    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
            final_path = Path(downloader.prepare_filename(info))
            if request.mode == "MP3 audio":
                final_path = final_path.with_suffix(".mp3")

            if not final_path.exists():
                candidates = [
                    p for p in folder.iterdir()
                    if p.is_file() and not p.name.endswith(".part")
                ]
                if not candidates:
                    raise RuntimeError("Download completed without an output file.")
                final_path = candidates[0]

            extension = ".mp3" if request.mode == "MP3 audio" else ".mp4"
            filename = safe_name(final_path.stem) + extension
            return FileResponse(
                final_path,
                media_type="audio/mpeg" if extension == ".mp3" else "video/mp4",
                filename=filename,
                background=BackgroundTask(shutil.rmtree, folder, ignore_errors=True),
            )
    except Exception as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(status_code=502, detail=friendly_error(exc)) from exc
