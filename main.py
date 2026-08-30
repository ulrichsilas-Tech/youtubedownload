import os
import tempfile
import shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, HttpUrl
import yt_dlp
import uvicorn

app = FastAPI(title="yt-dlp API", version="1.0.0")

DOWNLOAD_DIR = Path("/tmp/downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

SHORTCUT_FILE = Path(__file__).parent / "YouTube_Downloader.shortcut"


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


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>YouTube Downloader</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #1a1a2e; color: #fff; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
            .container { max-width: 400px; width: 90%; text-align: center; }
            h1 { font-size: 2em; margin-bottom: 10px; }
            .subtitle { color: #888; margin-bottom: 30px; }
            .btn { display: block; width: 100%; padding: 18px; margin: 15px 0; border: none; border-radius: 12px; font-size: 1.1em; font-weight: 600; cursor: pointer; text-decoration: none; color: #fff; }
            .btn-primary { background: linear-gradient(135deg, #ff0050, #ff0050); }
            .btn-secondary { background: linear-gradient(135deg, #333, #555); }
            .info { margin-top: 30px; color: #888; font-size: 0.9em; }
            .steps { text-align: left; margin-top: 20px; background: #16213e; padding: 20px; border-radius: 12px; }
            .steps li { margin: 10px 0; color: #ccc; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>YouTube Downloader</h1>
            <p class="subtitle">Téléchargez vos vidéos YouTube en MP3/MP4</p>
            <a href="/install-shortcut" class="btn btn-primary">📱 Installer le raccourci iPhone</a>
            <a href="/docs" class="btn btn-secondary">📖 API Documentation</a>
            <div class="info">
                <p>Après installation du raccourci, ouvrez l'app <strong>Raccourcis</strong> sur votre iPhone et collez une URL YouTube.</p>
            </div>
            <div class="steps">
                <strong>Comment utiliser :</strong>
                <ol>
                    <li>Installez le raccourci sur votre iPhone</li>
                    <li>Ouvrez l'app Raccourcis</li>
                    <li>Lancez "YouTube Downloader"</li>
                    <li>Collez une URL YouTube</li>
                    <li>Le fichier MP3 sera sauvegardé dans iCloud Drive</li>
                </ol>
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/install-shortcut")
async def install_shortcut():
    if not SHORTCUT_FILE.exists():
        raise HTTPException(status_code=404, detail="Shortcut file not found")
    return FileResponse(
        path=SHORTCUT_FILE,
        filename="YouTube_Downloader.shortcut",
        media_type="application/octet-stream",
    )


@app.post("/download", response_model=DownloadResponse)
async def download(request: DownloadRequest, http_request: Request, background_tasks: BackgroundTasks):
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

        download_url = f"{http_request.base_url}file/{temp_dir.name}/{filename}"

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