# VidSprint

Search YouTube by keyword, select a result, and prepare an authorized MP4 or MP3 download.

## Features

- Keyword search using the YouTube Data API
- Region and language filters
- Video thumbnails, title, channel, duration, views, and publish date
- MP4 quality choices up to 1080p
- MP3 extraction with FFmpeg
- Concurrent fragment downloads for better throughput
- Temporary-file cleanup
- 500 MB download limit

## Run locally

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Install FFmpeg locally and make sure it is on your PATH.

## Streamlit Secrets

Create `.streamlit/secrets.toml` locally, or add the secret in Streamlit Cloud:

```toml
YOUTUBE_API_KEY = "your-youtube-data-api-key"
```

Do not commit the key to GitHub.

## Deployment

### Streamlit frontend

Deploy `app.py` on Streamlit Community Cloud. Add these secrets:

```toml
YOUTUBE_API_KEY = "your-youtube-data-api-key"
DOWNLOADER_API_URL = "https://your-downloader-service.example.com"
DOWNLOADER_API_TOKEN = "a-long-random-shared-token"
```

If `DOWNLOADER_API_URL` is not set, VidSprint uses the local Streamlit fallback. The separate downloader service is recommended because shared Streamlit Cloud IPs can receive YouTube 403 responses.

### Downloader service

The repository includes `downloader_api.py`, `Dockerfile`, and `render.yaml`. Deploy the Docker service on a server or Render. Set the service environment variable `DOWNLOADER_API_TOKEN` to a long random value, then add the same value to Streamlit Secrets. Copy the service URL into `DOWNLOADER_API_URL`.

Check that it is working by opening:

```
https://your-downloader-service.example.com/health
```

The response should contain `"status": "ok"`.

The backend uses yt-dlp, Node.js, FFmpeg, temporary files, retries, a 500 MB limit, and automatic cleanup. It does not store user cookies.

Use this application only for content you own or have permission to download, and follow YouTube's terms and applicable copyright law.
