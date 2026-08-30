import os
import tempfile
import shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
import yt_dlp
import uvicorn

app = FastAPI(title="yt-dlp API", version="1.0.0")

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

DOWNLOAD_DIR = Path("/tmp/downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

SHORTCUT_FILE = BASE_DIR / "YouTube_Downloader.shortcut"

app.mount("/icons", StaticFiles(directory=STATIC_DIR / "icons"), name="icons")


@app.get("/manifest.json", response_class=FileResponse)
async def manifest():
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/sw.js", response_class=FileResponse)
async def service_worker():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


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
    return """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>YouTube Downloader</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#ff2d55">
<meta name="mobile-web-app-capable" content="yes">
<meta name="application-name" content="YT Download">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="YT Download">
<link rel="apple-touch-icon" sizes="180x180" href="/icons/icon-180.png">
<link rel="apple-touch-icon" sizes="152x152" href="/icons/icon-152.png">
<link rel="apple-touch-icon" sizes="120x120" href="/icons/icon-120.png">
<style>
  * { margin:0; padding:0; box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#0f0f1a; color:#fff; min-height:100vh; display:flex; align-items:center; justify-content:center; padding:20px; }
  .card { background:#1a1a2e; border-radius:20px; padding:28px 22px; max-width:420px; width:100%; box-shadow:0 20px 60px rgba(0,0,0,.5); }
  .logo { text-align:center; margin-bottom:6px; font-size:44px; }
  h1 { text-align:center; font-size:1.6em; margin-bottom:4px; }
  .sub { text-align:center; color:#8a8aa3; font-size:.9em; margin-bottom:22px; }
  label { display:block; font-size:.8em; color:#8a8aa3; margin:14px 0 6px; font-weight:600; letter-spacing:.3px; }
  input[type="url"], input[type="text"] { width:100%; background:#12121f; border:1px solid #2a2a44; color:#fff; border-radius:12px; padding:14px 16px; font-size:16px; outline:none; }
  input:focus { border-color:#ff2d55; }
  .fmt-grid { display:flex; gap:10px; margin-top:8px; }
  .fmt-btn { flex:1; background:#12121f; border:2px solid #2a2a44; color:#fff; border-radius:12px; padding:14px 0; font-size:16px; font-weight:600; cursor:pointer; text-align:center; }
  .fmt-btn.active { background:#ff2d55; border-color:#ff2d55; color:#fff; }
  select { width:100%; background:#12121f; border:1px solid #2a2a44; color:#fff; border-radius:12px; padding:14px 16px; font-size:16px; outline:none; }
  .btn { width:100%; margin-top:22px; background:linear-gradient(135deg,#ff2d55,#ff5f7e); border:none; color:#fff; border-radius:14px; padding:18px; font-size:18px; font-weight:700; cursor:pointer; transition:transform .1s; }
  .btn:active { transform:scale(.97); }
  .btn:disabled { opacity:.6; }
  #status { text-align:center; margin-top:16px; font-size:.9em; color:#8a8aa3; min-height:20px; word-break:break-word; }
  .spinner { display:none; width:26px; height:26px; border:3px solid rgba(255,255,255,.3); border-top-color:#fff; border-radius:50%; margin:0 auto 8px; animation:spin .8s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
  .hint { margin-top:20px; text-align:center; color:#5a5a75; font-size:.75em; line-height:1.5; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">🎵</div>
  <h1>YouTube Downloader</h1>
  <p class="sub">Collez un lien YouTube pour télécharger</p>

  <label>Lien YouTube</label>
  <input type="url" id="url" placeholder="https://youtube.com/..." autocomplete="off">
  <div style="margin-top:4px; text-align:right;"><button onclick="paste()" style="background:none;border:none;color:#ff5f7e;font-size:.8em;cursor:pointer;">📋 Coller</button></div>

  <label>Format</label>
  <div class="fmt-grid">
    <div class="fmt-btn active" id="fmt-mp3" onclick="setFmt('mp3')">MP3</div>
    <div class="fmt-btn" id="fmt-mp4" onclick="setFmt('mp4')">MP4</div>
  </div>

  <div id="qualityBlock">
    <label>Qualité audio</label>
    <select id="quality">
      <option value="128">128 kbps (petit)</option>
      <option value="192" selected>192 kbps (standard)</option>
      <option value="256">256 kbps (bon)</option>
      <option value="320">320 kbps (max)</option>
    </select>
  </div>

  <button class="btn" id="go" onclick="download()">Télécharger</button>
  <div class="spinner" id="spinner"></div>
  <div id="status"></div>
  <div class="hint">⏱️ Le serveur gratuit redémarre après inactivité :<br>la première requête peut prendre ~30 s.</div>
</div>

<script>
let fmt = "mp3";
function setFmt(f) {
  fmt = f;
  document.getElementById("fmt-mp3").classList.toggle("active", f === "mp3");
  document.getElementById("fmt-mp4").classList.toggle("active", f === "mp4");
  document.getElementById("qualityBlock").style.display = f === "mp3" ? "block" : "none";
}
function paste() {
  const u = document.getElementById("url");
  if (navigator.clipboard && navigator.clipboard.readText) {
    navigator.clipboard.readText().then(t => { u.value = t; }).catch(() => {});
  }
}
async function download() {
  const u = document.getElementById("url").value.trim();
  const q = document.getElementById("quality").value;
  const st = document.getElementById("status");
  const sp = document.getElementById("spinner");
  const btn = document.getElementById("go");
  if (!u) { st.textContent = "Collez d'abord un lien YouTube."; return; }
  btn.disabled = true; st.textContent = "Téléchargement en cours… (patiente, le serveur peut être en veille)"; sp.style.display = "block";
  try {
    const res = await fetch("/download", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({url: u, format: fmt, quality: q})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Erreur serveur");
    st.textContent = "Fichier prêt ! Ouverture du téléchargement…";
    window.location.href = data.download_url;
  } catch (e) {
    st.textContent = "Erreur : " + e.message;
    btn.disabled = false; sp.style.display = "none";
  }
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/sw.js').catch(function() {});
  });
}
</script>
</body>
</html>"""


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