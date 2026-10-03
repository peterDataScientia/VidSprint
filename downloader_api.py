import os
import re
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
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


@app.get("/health")
def health():
    return {"status": "ok", "service": "vidsprint-downloader"}


@app.post("/download")
def download(request: DownloadRequest):
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
                background=None,
            )
    except Exception as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
