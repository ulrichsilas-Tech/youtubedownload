from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import yt_dlp

from core.config import config
from core.platforms import Platform, build_ydl_options
from core.errors import DownloadError, NetworkError, ExtractorFailedError

router = APIRouter(prefix="/api/v1", tags=["search"])


class SearchResult(BaseModel):
    id: str
    title: str
    channel: str
    duration: Optional[int] = None
    duration_str: Optional[str] = None
    thumbnail: Optional[str] = None
    url: str
    view_count: Optional[int] = None
    upload_date: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    page: int
    per_page: int
    total: Optional[int] = None


class SearchDownloadRequest(BaseModel):
    video_id: str
    kind: str = Field(default="video", pattern="^(video|audio)$")
    height: str = Field(default="720", pattern="^(360|480|720|1080|best)$")
    codec: str = Field(default="mp3", pattern="^(mp3|m4a|opus|flac)$")
    bitrate: str = Field(default="192", pattern="^(128|192|256|320)$")


@router.get("/search", response_model=SearchResponse)
async def search_youtube(
    q: str = Query(..., min_length=1, max_length=200, description="Requête de recherche"),
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(20, ge=1, le=50, description="Résultats par page"),
):
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Requête vide")
    
    # +5 pour compenser le filtrage des chaines/playlists
    limit = min(per_page * page + 5, config.YT_SEARCH_LIMIT)
    
    opts = build_ydl_options(
        platform=Platform.YOUTUBE,
        kind="video",
        output_dir=None,
    )
    opts["quiet"] = True
    opts["no_warnings"] = True
    opts["extract_flat"] = "in_playlist"
    
    search_query = f"ytsearch{limit}:{query}"
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "SEARCH_FAILED",
                "message": str(e),
                "user_message": "Échec de la recherche YouTube. Réessayez plus tard."
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "SEARCH_ERROR",
                "message": str(e),
                "user_message": "Erreur interne lors de la recherche."
            }
        )
    
    entries = (info or {}).get("entries") or []
    if not entries:
        return SearchResponse(query=query, results=[], page=page, per_page=per_page, total=0)
    
    # Filtrer d'abord (chaines/playlists), puis paginer pour garantir per_page resultats
    filtered = []
    for e in entries:
        if not e:
            continue
        if e.get("ie_key") and e.get("ie_key") != "Youtube":
            continue
        vid = e.get("id", "")
        if not vid:
            continue
        if len(vid) == 24 and vid.startswith(("UC", "UU", "PL", "RD", "OL")):
            if e.get("ie_key") != "Youtube":
                continue
        filtered.append(e)
    
    start = (page - 1) * per_page
    end = start + per_page
    page_entries = filtered[start:end]
    
    results = []
    for e in page_entries:
        vid = e.get("id", "")
        # yt-dlp en mode flat ne renvoie pas toujours thumbnail → fallback i.ytimg.com
        thumb = e.get("thumbnail")
        if not thumb:
            thumbs = e.get("thumbnails") or []
            if thumbs:
                # prendre la meilleure miniature disponible
                thumb = (thumbs[-1] or {}).get("url") or (thumbs[0] or {}).get("url")
        if not thumb and vid:
            thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
        results.append(SearchResult(
            id=vid,
            title=e.get("title", "Sans titre"),
            channel=e.get("channel") or e.get("uploader") or "Inconnu",
            duration=e.get("duration"),
            duration_str=_format_duration(e.get("duration")) if e.get("duration") else None,
            thumbnail=thumb,
            url=f"https://www.youtube.com/watch?v={vid}",
            view_count=e.get("view_count"),
            upload_date=_format_upload_date(e.get("upload_date")) if e.get("upload_date") else None,
        ))
    
    return SearchResponse(
        query=query,
        results=results,
        page=page,
        per_page=per_page,
        total=len(entries) if len(entries) < limit else None
    )


@router.post("/search/download")
async def download_from_search(request: SearchDownloadRequest):
    from core.downloader import downloader
    
    if not request.video_id:
        raise HTTPException(status_code=400, detail="video_id requis")
    
    url = f"https://www.youtube.com/watch?v={request.video_id}"
    
    job = await downloader.create_job(
        url=url,
        kind=request.kind,
        height=request.height,
        codec=request.codec,
        bitrate=request.bitrate,
    )
    
    return {
        "job_id": job.id,
        "status": job.status.value,
        "status_url": f"/api/v1/download/{job.id}",
        "message": "Téléchargement démarré depuis la recherche."
    }


def _format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return ""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_upload_date(date_str: Optional[str]) -> str:
    if not date_str or len(date_str) != 8:
        return ""
    return f"{date_str[6:8]}/{date_str[4:6]}/{date_str[0:4]}"