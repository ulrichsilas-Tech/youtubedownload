import os
import tempfile
import shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
import yt_dlp
import uvicorn

app = FastAPI(title="yt-dlp API", version="1.0.0")

DOWNLOAD_DIR = Path("/tmp/downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


class DownloadRequest(BaseModel):
    url: HttpUrl
    format: str = "mp3"  # mp3, mp4, best
    quality: str = "192"  # for audio: 128, 192, 256, 320


class DownloadResponse(BaseModel):
    success: bool
    filename: str | None = None
    download_url: str | None = None
    error: str | None = None


def get_ydl_opts(format: str, quality: str, output_dir: Path):
    base_opts = {
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }

    if format == "mp3":
        return {
            **base_opts,
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality,
            }],
        }
    elif format == "mp4":
        return {
            **base_opts,
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        }
    else:  # best
        return {
            **base_opts,
            "format": "best",
        }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/download", response_model=DownloadResponse)
async def download(request: DownloadRequest, background_tasks: BackgroundTasks):
    temp_dir = Path(tempfile.mkdtemp(dir=DOWNLOAD_DIR))
    try:
        ydl_opts = get_ydl_opts(request.format, request.quality, temp_dir)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(str(request.url), download=True)
            if not info:
                raise HTTPException(status_code=400, detail="Could not extract video info")

            title = info.get("title", "download")
            ext = "mp3" if request.format == "mp3" else "mp4"
            filename = f"{title}.{ext}"
            filepath = temp_dir / filename

            if not filepath.exists():
                files = list(temp_dir.glob("*"))
                if files:
                    filepath = files[0]
                    filename = filepath.name
                else:
                    raise HTTPException(status_code=500, detail="Download completed but file not found")

        download_url = f"/file/{temp_dir.name}/{filename}"

        background_tasks.add_task(cleanup_dir, temp_dir)

        return DownloadResponse(
            success=True,
            filename=filename,
            download_url=download_url,
        )

    except yt_dlp.utils.DownloadError as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/file/{temp_dir_name}/{filename}")
async def serve_file(temp_dir_name: str, filename: str):
    filepath = DOWNLOAD_DIR / temp_dir_name / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found or expired")
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="audio/mpeg" if filename.endswith(".mp3") else "video/mp4",
    )


def cleanup_dir(path: Path):
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))