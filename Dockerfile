FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY downloader_api.py .
EXPOSE 8000
CMD ["uvicorn", "downloader_api:app", "--host", "0.0.0.0", "--port", "8000"]
