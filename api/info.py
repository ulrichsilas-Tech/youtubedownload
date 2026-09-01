import asyncio
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import yt_dlp

from core.platforms import Platform, detect_platform, get_available_formats, get_platform_info, build_ydl_options
from core.config import config
from core.errors import ErrorCode

router = APIRouter(prefix="/api/v1", tags=["info"])


class InfoResponse(BaseModel):
    url: str
    platform: str
    id: Optional[str] = None
    title: Optional[str] = None
    channel: Optional[str] = None
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    formats: Dict[str, Any]
    supports_video: bool
    supports_audio: bool


@router.get("/info")
async def get_info(url: str = Query(..., min_length=5, max_length=2000)):
    platform = detect_platform(url)
    info_platform = get_platform_info(platform)

    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail={"code": ErrorCode.INVALID_URL.value, "user_message": "URL invalide"})

    # Bloquer SSRF
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = (parsed.netloc or "").lower()
    for blocked in config.BLOCKED_DOMAINS:
        if domain == blocked or domain.endswith("." + blocked) or domain.startswith(blocked.rstrip(".")):
            raise HTTPException(status_code=400, detail={"code": ErrorCode.INVALID_URL.value, "user_message": "Domaine bloque"})

    # Options legeres sans telechargement, avec cookies si dispo
    opts = build_ydl_options(platform, kind="video", output_dir=None)
    opts["quiet"] = True
    opts["no_warnings"] = True
    opts["skip_download"] = True
    # Pour YouTube on garde les extractor_args
    loop = asyncio.get_event_loop()

    def extract():
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        info = await asyncio.wait_for(loop.run_in_executor(None, extract), timeout=30)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail={"code": "TIMEOUT", "user_message": "Analyse trop longue, reessaye."})
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        if any(k in msg for k in ["private", "login", "sign in", "members only"]):
            raise HTTPException(status_code=403, detail={"code": "AUTH_REQUIRED", "user_message": "Contenu prive / connexion requise. Ajoute tes cookies."})
        if any(k in msg for k in ["unavailable", "removed", "deleted", "terminated"]):
            raise HTTPException(status_code=404, detail={"code": "CONTENT_UNAVAILABLE", "user_message": "Contenu indisponible."})
        raise HTTPException(status_code=502, detail={"code": "EXTRACTOR_FAILED", "user_message": f"Echec analyse: {str(e)[:200]}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "UNKNOWN", "user_message": str(e)[:200]})

    if not info:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_UNAVAILABLE", "user_message": "Aucune info trouvee."})

    # Si playlist, prendre la premiere entree
    if "entries" in info and info.get("entries"):
        # ytsearch ou playlist : on prend pas ici, on veut l'info directe -> mais pour /info on attend une URL video directe
        info = info["entries"][0] if info["entries"] else info

    formats = get_available_formats(info, platform)
    # Filtrer les qualites selon max supporte
    if info_platform.max_height and formats.get("video"):
        # garde seulement <= max_height, deja gere mais on nettoie "best"
        pass

    thumb = info.get("thumbnail")
    if not thumb:
        thumbs = info.get("thumbnails") or []
        if thumbs:
            thumb = (thumbs[-1] or {}).get("url") or (thumbs[0] or {}).get("url")
    if not thumb and info.get("id"):
        thumb = f"https://i.ytimg.com/vi/{info.get('id')}/hqdefault.jpg"

    return InfoResponse(
        url=url,
        platform=platform.value,
        id=info.get("id"),
        title=info.get("title"),
        channel=info.get("channel") or info.get("uploader"),
        duration=info.get("duration"),
        thumbnail=thumb,
        formats=formats,
        supports_video=info_platform.supports_video,
        supports_audio=info_platform.supports_audio,
    )
