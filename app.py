import os
import re
import tempfile
from pathlib import Path

import requests
import streamlit as st
import yt_dlp

st.set_page_config(page_title="VidSprint", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    .block-container {max-width: 1100px; padding-top: 2rem;}
    .brand {font-size: 2.7rem; font-weight: 800; letter-spacing: -0.06em; margin-bottom: 0;}
    .accent {color: #ff4d4d;}
    .muted {color: #6b7280;}
    .result-card {padding: 0.8rem; border: 1px solid #e5e7eb; border-radius: 14px; min-height: 360px;}
    .small {font-size: 0.84rem; color: #6b7280;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="brand">Vid<span class="accent">Sprint</span> ⚡</div>', unsafe_allow_html=True)
st.caption("Search. Select. Save. — for videos you own or are authorized to download.")

if "results" not in st.session_state:
    st.session_state.results = []
if "download_bytes" not in st.session_state:
    st.session_state.download_bytes = None
if "download_name" not in st.session_state:
    st.session_state.download_name = None

def get_secret(name: str) -> str:
    try:
        return str(st.secrets[name]).strip()
    except Exception:
        return os.getenv(name, "").strip()

def search_youtube(query: str, max_results: int, region: str, language: str):
    key = get_secret("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("Add YOUTUBE_API_KEY in Streamlit Secrets before searching.")

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "order": "relevance",
        "regionCode": region,
        "relevanceLanguage": language,
        "key": key,
    }
    response = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params=params,
        timeout=20,
    )
    data = response.json()
    if response.status_code != 200:
        reason = data.get("error", {}).get("errors", [{}])[0].get("reason", "API error")
        raise RuntimeError(f"YouTube search failed: {reason}")
    items = data.get("items", [])
    ids = [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]
    if not ids:
        return []

    detail_response = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "contentDetails,statistics", "id": ",".join(ids), "key": key},
        timeout=20,
    )
    details = {
        item["id"]: item
        for item in detail_response.json().get("items", [])
    }

    results = []
    for item in items:
        video_id = item.get("id", {}).get("videoId")
        if not video_id:
            continue
        detail = details.get(video_id, {})
        results.append({
            "id": video_id,
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "published": item["snippet"]["publishedAt"][:10],
            "description": item["snippet"].get("description", ""),
            "thumbnail": item["snippet"]["thumbnails"].get("high", item["snippet"]["thumbnails"]["default"])["url"],
            "duration": format_duration(detail.get("contentDetails", {}).get("duration", "")),
            "views": detail.get("statistics", {}).get("viewCount", "—"),
        })
    return results

def format_duration(value: str) -> str:
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return "—"
    hours, minutes, seconds = [int(x or 0) for x in match.groups()]
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"

def download_video(video_id: str, mode: str, quality: int, progress):
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory(prefix="vidsprint_") as folder:
        output = str(Path(folder) / "%(title).120s.%(ext)s")
        last_percent = {"value": -1}

        def hook(data):
            if data.get("status") == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                current = data.get("downloaded_bytes", 0)
                if total:
                    fraction = min(current / total, 1.0)
                    percent = int(fraction * 100)
                    if percent != last_percent["value"]:
                        last_percent["value"] = percent
                        progress.progress(fraction, text=f"Downloading… {percent}%")
            elif data.get("status") == "finished":
                progress.progress(1.0, text="Finalizing file…")

        options = {
            "outtmpl": output,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 5,
            "fragment_retries": 10,
            "concurrent_fragment_downloads": 8,
            "max_filesize": 500 * 1024 * 1024,
            "progress_hooks": [hook],
        }
        if mode == "MP3 audio":
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
                "format": f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best",
                "merge_output_format": "mp4",
            })

        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
            final_path = Path(downloader.prepare_filename(info))
            if mode == "MP3 audio":
                final_path = final_path.with_suffix(".mp3")
            elif final_path.suffix != ".mp4":
                candidates = list(Path(folder).glob("*"))
                mp4s = [p for p in candidates if p.suffix.lower() == ".mp4"]
                if mp4s:
                    final_path = mp4s[0]
            if not final_path.exists():
                candidates = [p for p in Path(folder).glob("*") if p.is_file() and not p.name.endswith(".part")]
                if not candidates:
                    raise RuntimeError("The download completed but no output file was found.")
                final_path = candidates[0]
            return final_path.read_bytes(), final_path.name

with st.form("search_form"):
    query = st.text_input("Search by keyword", placeholder="e.g. molecular dynamics tutorial")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        max_results = st.selectbox("Results", [6, 12, 18], index=1)
    with c2:
        region = st.selectbox("Region", ["TZ", "US", "GB", "IN", "KE", "ZA"], index=0)
    with c3:
        language = st.selectbox("Language", ["en", "sw", "fr", "es"], index=0)
    submitted = st.form_submit_button("🔎 Search videos", type="primary", use_container_width=True)

if submitted:
    if len(query.strip()) < 2:
        st.warning("Enter at least two characters.")
    else:
        with st.spinner("Searching YouTube…"):
            try:
                st.session_state.results = search_youtube(query.strip(), max_results, region, language)
                st.session_state.download_bytes = None
                if not st.session_state.results:
                    st.info("No matching videos were found.")
            except Exception as exc:
                st.error(str(exc))

results = st.session_state.results
if results:
    st.subheader(f"{len(results)} search results")
    options = {f"{item['title']} · {item['channel']}": item for item in results}
    selected_label = st.selectbox("Choose a video", list(options.keys()))
    selected = options[selected_label]

    left, right = st.columns([1.2, 1])
    with left:
        st.image(selected["thumbnail"], use_container_width=True)
    with right:
        st.markdown(f"### {selected['title']}")
        st.write(f"**Channel:** {selected['channel']}")
        st.write(f"**Duration:** {selected['duration']}  ·  **Views:** {selected['views']}")
        st.write(f"**Published:** {selected['published']}")
        st.link_button("Open on YouTube", f"https://www.youtube.com/watch?v={selected['id']}")

    st.divider()
    mode = st.radio("Download type", ["MP4 video", "MP3 audio"], horizontal=True)
    quality = st.select_slider("Maximum video quality", options=[360, 480, 720, 1080], value=720, disabled=mode == "MP3 audio")
    authorized = st.checkbox("I own this content or have permission to download it.")

    if st.button("⚡ Prepare fast download", type="primary", disabled=not authorized):
        progress = st.progress(0, text="Preparing…")
        try:
            st.session_state.download_bytes, st.session_state.download_name = download_video(
                selected["id"], mode, quality, progress
            )
            st.success("File ready.")
        except Exception as exc:
            st.session_state.download_bytes = None
            st.error(f"Download failed: {exc}")

if st.session_state.download_bytes and st.session_state.download_name:
    mime = "audio/mpeg" if st.session_state.download_name.lower().endswith(".mp3") else "video/mp4"
    st.download_button(
        "⬇️ Save file",
        data=st.session_state.download_bytes,
        file_name=st.session_state.download_name,
        mime=mime,
        type="primary",
        use_container_width=True,
    )

st.divider()
st.caption("VidSprint uses the YouTube Data API for search and yt-dlp/FFmpeg for authorized downloads. Temporary files are removed after processing. Respect copyright and platform terms.")
