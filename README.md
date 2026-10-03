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

Deploy `app.py` from this repository on Streamlit Community Cloud. The platform reads `requirements.txt` for Python dependencies and `packages.txt` for FFmpeg.

Use this application only for content you own or have permission to download, and follow YouTube's terms and applicable copyright law.
