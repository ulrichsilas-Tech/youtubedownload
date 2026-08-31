import os
import re
import tempfile
import shutil
import urllib.parse
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yt_dlp
import uvicorn

app = FastAPI(title="YT Download", version="2.0.0")

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", BASE_DIR / "tmp" / "downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
LIBRARY_DIR = DOWNLOAD_DIR / "library"
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)

COOKIES_FILE = DOWNLOAD_DIR / "cookies.txt"

SHORTCUT_FILE = BASE_DIR / "YouTube_Downloader.shortcut"

app.mount("/icons", StaticFiles(directory=STATIC_DIR / "icons"), name="icons")


@app.get("/manifest.json", response_class=FileResponse)
async def manifest():
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/sw.js", response_class=FileResponse)
async def service_worker():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


@app.get("/health")
async def health():
    return {"status": "ok"}


_FALLBACK_CLIENTS = ["tv_embedded", "android_vr", "web_embedded", "tv"]


def _opts(with_cookies: bool = True):
    o = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    if with_cookies and COOKIES_FILE.exists():
        o["cookiefile"] = str(COOKIES_FILE)
    return o


def _extract(url: str, download: bool, output_dir: Path | None = None, req: "DownloadRequest | None" = None):
    def build(with_cookies: bool):
        base = _opts(with_cookies=with_cookies)
        if output_dir:
            base["outtmpl"] = str(output_dir / "%(id)s.%(ext)s")
        if req is not None:
            base.update(_format_opts(req))
        candidates = [dict(base)]
        for client in _FALLBACK_CLIENTS:
            candidates.append({
                **base,
                "extractor_args": {"youtube": {"player_client": [client]}},
            })
        return candidates

    candidates = list(build(with_cookies=True))
    candidates.extend(build(with_cookies=False))

    last_error = None
    for opts in candidates:
        if output_dir:
            for p in output_dir.iterdir():
                if p.is_file():
                    p.unlink(missing_ok=True)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=download)
        except yt_dlp.utils.DownloadError as e:
            last_error = e
            msg = str(e)
            if "Sign in" not in msg and "not a bot" not in msg:
                raise
    raise last_error


@app.get("/search")
def search(q: str, limit: int = 12):
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Requête vide")
    try:
        info = _extract(f"ytsearch{min(limit, 20)}:{q}", download=False)
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    results = []
    for e in (info or {}).get("entries") or []:
        if not e:
            continue
        results.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "channel": e.get("channel") or e.get("uploader") or "",
            "duration": e.get("duration"),
            "thumbnail": e.get("thumbnail"),
            "url": f"https://www.youtube.com/watch?v={e.get('id')}",
        })
    return {"results": results}


class DownloadRequest(BaseModel):
    url: str
    kind: str = "audio"        # audio | video
    codec: str = "mp3"         # mp3 | m4a (audio)
    bitrate: str = "192"       # 128 192 256 320 (audio)
    height: str = "720"        # 360 480 720 1080 1440 2160 (video)


def _dl_opts(req: DownloadRequest, output_dir: Path):
    return {
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        **{k: v for k, v in _format_opts(req).items()},
    }


def _format_opts(req: DownloadRequest):
    if req.kind == "audio":
        return {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": req.codec,
                "preferredquality": req.bitrate,
            }],
        }
    if req.height and req.height != "best":
        h = int(req.height)
        return {
            "format": (
                f"bestvideo[vcodec^=avc1][height<={h}]+bestaudio[acodec^=mp4a]"
                f"/bestvideo[vcodec^=avc1][height<={h}]+bestaudio"
                f"/bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
            ),
            "merge_output_format": "mp4",
        }
    return {
        "format": (
            "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]"
            "/bestvideo[vcodec^=avc1]+bestaudio/bestvideo+bestaudio/best"
        ),
        "merge_output_format": "mp4",
    }


def _slug(text: str, maxlen: int = 60):
    s = re.sub(r"[^\w\s-]", "", text or "")
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return s[:maxlen] or "video"


@app.post("/download")
def download(req: DownloadRequest, http_request: Request):
    if not req.url:
        raise HTTPException(status_code=400, detail="URL manquante")

    temp_dir = Path(tempfile.mkdtemp(dir=DOWNLOAD_DIR))
    try:
        info = _extract(req.url, download=True, output_dir=temp_dir, req=req) or {}
    except yt_dlp.utils.DownloadError as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))

    files = [p for p in temp_dir.iterdir() if p.is_file()]
    if not files:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Fichier introuvable après le téléchargement")

    src = files[0]
    vid = info.get("id") or "dl"
    ext = src.suffix[1:] or ("mp3" if req.kind == "audio" else "mp4")
    dest = LIBRARY_DIR / f"{vid}__{_slug(info.get('title', 'video'))}.{ext}"
    n = 2
    while dest.exists():
        dest = LIBRARY_DIR / f"{vid}__{_slug(info.get('title', 'video'))}-{n}.{ext}"
        n += 1

    shutil.move(str(src), str(dest))
    shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "success": True,
        "filename": dest.name,
        "download_url": f"/files/{urllib.parse.quote(dest.name)}",
        "size": dest.stat().st_size,
    }


@app.get("/files")
def list_files():
    items = []
    for p in sorted(LIBRARY_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file():
            items.append({
                "name": p.name,
                "size": p.stat().st_size,
                "download_url": f"/files/{urllib.parse.quote(p.name)}",
            })
    return {"files": items}


@app.get("/files/{name}")
def serve_file(name: str):
    if Path(name).name != name:
        raise HTTPException(status_code=400, detail="Nom invalide")
    filepath = LIBRARY_DIR / name
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    ext = filepath.suffix.lower()
    media = {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".webm": "audio/webm",
        ".mp4": "video/mp4",
    }.get(ext, "application/octet-stream")
    return FileResponse(path=filepath, filename=name, media_type=media)


@app.delete("/files/{name}")
def delete_file(name: str):
    if Path(name).name != name:
        raise HTTPException(status_code=400, detail="Nom invalide")
    filepath = LIBRARY_DIR / name
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    try:
        filepath.unlink()
    except PermissionError:
        raise HTTPException(status_code=500, detail="Fichier verrouillé par un autre processus. Fermez le lecteur média et réessayez.")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Erreur suppression: {e}")
    return {"success": True}


class CookiesRequest(BaseModel):
    content: str | None = None


@app.post("/cookies")
async def upload_cookies(body: CookiesRequest | None = None):
    text = None
    if body is not None and body.content:
        text = body.content

    if not text or text.strip() == "":
        raise HTTPException(status_code=400, detail="Aucun contenu reçu")

    if "youtube.com" not in text and ".youtube" not in text:
        raise HTTPException(
            status_code=400,
            detail="Ce fichier ne contient pas de cookies YouTube (.youtube.com introuvable)",
        )

    COOKIES_FILE.write_text(text, encoding="utf-8")
    return {"success": True, "configured": True}


@app.get("/cookies")
async def cookies_status():
    return {"configured": COOKIES_FILE.exists()}


@app.delete("/cookies")
async def delete_cookies():
    COOKIES_FILE.unlink(missing_ok=True)
    return {"success": True, "configured": False}


@app.get("/", response_class=HTMLResponse)
async def root():
    return """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>YT Download</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#0f0f1a">
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
  body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#0f0f1a; color:#fff; min-height:100vh; }
  .header { position:sticky; top:0; z-index:20; background:#0f0f1a; padding:calc(14px + env(safe-area-inset-top)) 16px 12px; display:flex; align-items:center; gap:10px; }
  .header h1 { font-size:1.25em; flex:1; } .header h1 span { color:#ff2d55; }
  .iconbtn { background:#1a1a2e; border:none; color:#bbb; font-size:20px; width:40px; height:40px; border-radius:12px; cursor:pointer; }
  main { padding:16px 20px calc(30px + env(safe-area-inset-bottom)); max-width:520px; margin:0 auto; }
  main input { width:100%; background:#12121f; border:1px solid #2a2a44; color:#fff; border-radius:12px; padding:13px 16px; font-size:16px; outline:none; }
  main input:focus { border-color:#ff2d55; }
  .spinner { width:34px; height:34px; border:3px solid rgba(255,255,255,.2); border-top-color:#ff2d55; border-radius:50%; margin:24px auto; animation:spin .8s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
  .overlay { position:fixed; inset:0; background:rgba(0,0,0,.82); z-index:100; display:flex; align-items:center; justify-content:center; padding:18px; }
  .panel { background:#1a1a2e; border-radius:18px; padding:20px; width:100%; max-width:460px; max-height:92vh; overflow-y:auto; }
  .panel h2 { font-size:1.2em; margin-bottom:6px; text-align:center; }
  .sub2 { color:#8a8aa3; font-size:.85em; margin-bottom:14px; text-align:center; line-height:1.5; }
  .btn { width:100%; margin-top:14px; background:linear-gradient(135deg,#ff2d55,#ff5f7e); border:none; color:#fff; border-radius:14px; padding:17px; font-size:17px; font-weight:700; cursor:pointer; }
  .btn.ghost { background:#242442; color:#c9c9e0; }
  .btn:disabled { opacity:.6; }
  .seg { display:flex; gap:8px; margin:10px 0 4px; }
  .seg div { flex:1; background:#12121f; border:2px solid #2a2a44; color:#fff; border-radius:12px; padding:13px 0; font-size:15px; font-weight:600; text-align:center; cursor:pointer; }
  .seg div.active { background:#ff2d55; border-color:#ff2d55; }
  select { width:100%; background:#12121f; border:1px solid #2a2a44; color:#fff; border-radius:12px; padding:13px 14px; font-size:16px; outline:none; margin-top:8px; }
  label { display:block; font-size:.8em; color:#8a8aa3; margin:12px 0 4px; font-weight:600; }
  #status { text-align:center; margin-top:12px; font-size:.88em; color:#8a8aa3; min-height:18px; word-break:break-word; }
  textarea { width:100%; background:#12121f; border:1px solid #2a2a44; color:#fff; border-radius:12px; padding:12px; font-size:13px; outline:none; font-family:monospace; resize:vertical; }
  #filesBox { margin-top:24px; }
  #filesBox h2 { font-size:1.05em; margin-bottom:6px; color:#c9c9e0; }
  .frow { display:flex; align-items:center; gap:12px; padding:12px 0; border-bottom:1px solid #1e1e33; }
  .ficon { font-size:26px; width:40px; text-align:center; }
  .fmeta { flex:1; min-width:0; }
  .fname { font-size:14px; font-weight:600; word-break:break-word; }
  .fsize { color:#8a8aa3; font-size:12px; margin-top:2px; }
  .fbtns { display:flex; gap:6px; }
  .fbtns button { background:#242442; border:none; color:#fff; font-size:16px; width:38px; height:38px; border-radius:10px; cursor:pointer; }
  .hint { text-align:center; color:#5a5a75; font-size:.75em; line-height:1.5; margin-top:14px; }
</style>
</head>
<body>

<div class="header">
  <h1>YT<span>Download</span></h1>
  <button class="iconbtn" onclick="openCookies()">⚙️</button>
</div>

<main>
  <label for="url">1. Colle un lien YouTube</label>
  <input id="url" placeholder="https://www.youtube.com/watch?v=…" autocomplete="off" inputmode="url" enterkeyhint="go">

  <label>2. Choisis le format</label>
  <div class="seg">
    <div id="seg-audio" class="active" onclick="setKind('audio')">🎵 Audio</div>
    <div id="seg-video" onclick="setKind('video')">🎬 Vidéo</div>
  </div>

  <div id="audioOpts">
    <label>Format audio</label>
    <div class="seg">
      <div id="cc-mp3" class="active" onclick="setCodec('mp3')">MP3</div>
      <div id="cc-m4a" onclick="setCodec('m4a')">M4A</div>
    </div>
    <label>Qualité (kbps)</label>
    <select id="bitrate">
      <option value="128">128</option>
      <option value="192" selected>192</option>
      <option value="256">256</option>
      <option value="320">320</option>
    </select>
  </div>

  <div id="videoOpts" style="display:none;">
    <label>Qualité vidéo (MP4)</label>
    <select id="height">
      <option value="360">360p</option>
      <option value="480">480p</option>
      <option value="720" selected>720p HD</option>
      <option value="1080">1080p Full HD</option>
      <option value="1440">1440p</option>
      <option value="2160">2160p 4K</option>
    </select>
  </div>

  <button class="btn" id="dlGo" onclick="startDownload()">⬇️ Télécharger</button>
  <div id="status"></div>
  <div id="successBox" style="display:none;">
    <button class="btn" onclick="saveToFiles()">💾 Enregistrer dans Fichiers (Documents)</button>
  </div>

  <div id="filesBox" style="display:none;">
    <h2>📂 Mes fichiers</h2>
    <div id="files"></div>
  </div>
</main>

<div class="overlay" id="cookiesOverlay" style="display:none;" onclick="if(event.target===this)closeCookies()">
  <div class="panel">
    <h2>Cookies YouTube</h2>
    <p class="sub2">YouTube bloque les serveurs sans connexion.<br>Colle ici les cookies de ton navigateur pour débloquer les téléchargements.</p>
    <textarea id="cookiesText" rows="8" placeholder="# Netscape HTTP Cookie File&#10;.youtube.com	TRUE	/	TRUE	0	NID	abc123..."></textarea>
    <div id="cookieStatus" style="margin:8px 0;font-size:.85em;color:#8a8aa3;"></div>
    <button class="btn" onclick="saveCookies()">💾 Enregistrer</button>
    <button class="btn ghost" onclick="clearCookies()">🗑️ Supprimer</button>
    <button class="btn ghost" onclick="closeCookies()">Fermer</button>
    <div class="hint">Où trouver les cookies ?<br>Sur ton PC, Chrome connecté à YouTube → extension "Get cookies.txt" → exporter → coller ici.</div>
  </div>
</div>

<script>
let CURFILE = null;
let kind = "audio";
let codec = "mp3";

function $(id) { return document.getElementById(id); }

function esc(s) {
  return String(s || "").replace(/[&<>"']/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
}

function setKind(k) {
  kind = k;
  $("seg-audio").classList.toggle("active", k === "audio");
  $("seg-video").classList.toggle("active", k === "video");
  $("audioOpts").style.display = k === "audio" ? "block" : "none";
  $("videoOpts").style.display = k === "video" ? "block" : "none";
}
function setCodec(c) {
  codec = c;
  $("cc-mp3").classList.toggle("active", c === "mp3");
  $("cc-m4a").classList.toggle("active", c === "m4a");
}

async function startDownload() {
  const st = $("status");
  const btn = $("dlGo");
  const url = $("url").value.trim();
  if (!url) { st.textContent = "❌ Colle d'abord un lien YouTube."; return; }
  const payload = {
    url: url,
    kind: kind,
    codec: codec,
    bitrate: $("bitrate").value,
    height: $("height").value,
  };
  btn.disabled = true;
  st.textContent = "Téléchargement en cours… (serveur froid : ~30 s)";
  try {
    const r = await fetch("/download", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erreur serveur");
    CURFILE = d;
    st.textContent = "✅ Prêt : " + d.filename;
    $("successBox").style.display = "block";
    loadFiles();
  } catch (e) {
    st.textContent = "❌ " + e.message;
    if (/bot|sign in/i.test(e.message)) {
      st.textContent = "❌ YouTube bloque le serveur. Ajoute tes cookies (⚙️) puis réessaie.";
    }
  } finally {
    btn.disabled = false;
  }
}

async function saveToFiles() {
  if (!CURFILE) return;
  const u = $("status");
  u.textContent = "Préparation du partage…";
  try {
    const res = await fetch(CURFILE.download_url);
    const blob = await res.blob();
    const f = new File([blob], CURFILE.filename.split("/").pop(), {type: blob.type || "application/octet-stream"});
    if (navigator.share && navigator.canShare && navigator.canShare({files: [f]})) {
      await navigator.share({files: [f]});
      u.textContent = "✅ Choisis « Enregistrer dans Fichiers » puis Documents → Inbox.";
    } else {
      const a = document.createElement("a");
      a.href = CURFILE.download_url;
      a.download = CURFILE.filename.split("/").pop();
      document.body.appendChild(a);
      a.click();
      a.remove();
      u.textContent = "✅ Téléchargement lancé — dans Safari, appuie sur le fichier → Enregistrer dans Fichiers.";
    }
  } catch (e) {
    if (e.name !== "AbortError") u.textContent = "❌ " + e.message;
  }
}

async function loadFiles() {
  try {
    const r = await fetch("/files");
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail);
    const box = $("filesBox");
    if (!d.files.length) { box.style.display = "none"; return; }
    box.style.display = "block";
    $("files").innerHTML = d.files.map(f => {
      const audio = /[.](mp3|m4a|webm)$/i.test(f.name);
      const icon = audio ? "🎵" : "🎬";
      return `<div class="frow"><div class="ficon">${icon}</div>` +
        `<div class="fmeta"><div class="fname">${esc(f.name)}</div><div class="fsize">${fmtSize(f.size)}</div></div>` +
        `<div class="fbtns">` +
        `<button title="Enregistrer dans Fichiers" onclick="saveFileByName('${esc(f.name)}','${f.download_url}')">💾</button>` +
        `<button title="Ouvrir" onclick="window.open('${f.download_url}')">▶️</button>` +
        `<button title="Supprimer" onclick="delFile('${esc(f.name)}')">🗑️</button>` +
        `</div></div>`;
    }).join("");
  } catch (e) { /* silencieux */ }
}

function fmtSize(b) {
  b = b || 0;
  if (b < 1024) return b + " o";
  if (b < 1048576) return (b / 1024).toFixed(1) + " Ko";
  return (b / 1048576).toFixed(1) + " Mo";
}

async function saveFileByName(name, url) {
  const res = await fetch(url);
  const blob = await res.blob();
  const f = new File([blob], name, {type: blob.type || "application/octet-stream"});
  if (navigator.share && navigator.canShare && navigator.canShare({files: [f]})) {
    await navigator.share({files: [f]});
  } else {
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }
}

async function delFile(name) {
  if (!confirm("Supprimer " + name + " ?")) return;
  await fetch("/files/" + encodeURIComponent(name), {method: "DELETE"});
  loadFiles();
}

function openCookies() {
  $("cookiesOverlay").style.display = "flex";
  refreshCookieStatus();
}
function closeCookies() { $("cookiesOverlay").style.display = "none"; }

async function refreshCookieStatus() {
  const el = $("cookieStatus");
  try {
    const r = await fetch("/cookies");
    const d = await r.json();
    el.textContent = d.configured ? "✅ Cookies enregistrés" : "ℹ️ Aucun cookie pour l'instant";
  } catch (e) { el.textContent = ""; }
}
async function saveCookies() {
  const el = $("cookieStatus");
  const txt = $("cookiesText").value;
  if (!txt.trim()) { el.textContent = "Le champ est vide."; return; }
  el.textContent = "Enregistrement…";
  try {
    const r = await fetch("/cookies", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({content: txt})});
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail);
    el.textContent = "✅ Cookies enregistrés ! Relance un téléchargement.";
  } catch (e) { el.textContent = "❌ " + e.message; }
}
async function clearCookies() {
  await fetch("/cookies", {method: "DELETE"});
  $("cookiesText").value = "";
  $("cookieStatus").textContent = "✅ Cookies supprimés";
}

$("url").addEventListener("keydown", e => { if (e.key === "Enter") startDownload(); });
loadFiles();

if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/sw.js').catch(function() {});
  });
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))