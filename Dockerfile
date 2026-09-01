FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY core/ core/
COPY api/ api/
COPY models/ models/
COPY static/ static/

ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV DOWNLOAD_DIR=/tmp/downloads
ENV MAX_FILE_SIZE=524288000
ENV MAX_LIBRARY_SIZE=524288000
ENV MAX_FILE_AGE_HOURS=24
ENV CLEANUP_INTERVAL_MINUTES=30
ENV RATE_LIMIT_REQUESTS=5
ENV RATE_LIMIT_WINDOW_SECONDS=60
ENV YT_SEARCH_LIMIT=20
ENV DOWNLOAD_TIMEOUT=180
ENV MAX_VIDEO_HEIGHT=1080
ENV MAX_AUDIO_BITRATE=320

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]