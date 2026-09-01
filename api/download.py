from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict, Any
import urllib.parse

from core.config import config
from core.downloader import downloader, DownloadJob, JobStatus
from core.platforms import Platform, detect_platform, get_available_formats, get_platform_info
from core.errors import DownloadError, InvalidURLError, ErrorCode
from core.storage import storage

router = APIRouter(prefix="/api/v1", tags=["download"])


class DownloadRequest(BaseModel):
    url: HttpUrl
    kind: str = Field(default="video", pattern="^(video|audio)$")
    height: str = Field(default="720", pattern="^(360|480|720|1080|best)$")
    codec: str = Field(default="mp3", pattern="^(mp3|m4a|opus|flac)$")
    bitrate: str = Field(default="192", pattern="^(128|192|256|320)$")
    cookies: Optional[str] = None


class DownloadResponse(BaseModel):
    job_id: str
    status: str
    status_url: str
    message: str


class JobStatusResponse(BaseModel):
    id: str
    url: str
    platform: str
    kind: str
    status: str
    progress: float
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class FormatsResponse(BaseModel):
    platform: str
    video: List[str]
    audio: List[str]
    has_drm: bool
    supports_video: bool
    supports_audio: bool
    max_height: int


@router.post("/download", response_model=DownloadResponse)
async def create_download(request: DownloadRequest, http_request: Request):
    url = str(request.url)
    
    if not _is_url_allowed(url):
        raise HTTPException(
            status_code=400,
            detail={
                "code": ErrorCode.INVALID_URL.value,
                "message": "URL not allowed",
                "user_message": "Ce domaine n'est pas autorisé ou est bloqué pour des raisons de sécurité."
            }
        )
    
    platform = detect_platform(url)
    platform_info = get_platform_info(platform)
    
    if request.kind == "video" and not platform_info.supports_video:
        raise HTTPException(
            status_code=400,
            detail={
                "code": ErrorCode.FORMAT_UNAVAILABLE.value,
                "message": f"Platform {platform.value} does not support video",
                "user_message": f"Cette plateforme ({platform.value}) ne supporte pas le téléchargement vidéo."
            }
        )
    
    if request.kind == "audio" and not platform_info.supports_audio:
        raise HTTPException(
            status_code=400,
            detail={
                "code": ErrorCode.FORMAT_UNAVAILABLE.value,
                "message": f"Platform {platform.value} does not support audio",
                "user_message": f"Cette plateforme ({platform.value}) ne supporte pas le téléchargement audio."
            }
        )
    
    job = await downloader.create_job(
        url=url,
        kind=request.kind,
        height=request.height,
        codec=request.codec,
        bitrate=request.bitrate,
        cookies=request.cookies,
    )
    
    return DownloadResponse(
        job_id=job.id,
        status=job.status.value,
        status_url=f"/api/v1/download/{job.id}",
        message="Téléchargement démarré. Consultez le statut via l'URL fournie."
    )


@router.get("/download/{job_id}", response_model=JobStatusResponse)
async def get_download_status(job_id: str):
    job = await downloader.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={
                "code": ErrorCode.UNKNOWN_ERROR.value,
                "message": "Job not found",
                "user_message": "Téléchargement introuvable ou expiré."
            }
        )
    
    return JobStatusResponse(**job.to_dict())


@router.get("/download/{job_id}/formats", response_model=FormatsResponse)
async def get_available_formats_endpoint(job_id: str):
    job = await downloader.get_job(job_id)
    if not job or not job.result:
        raise HTTPException(
            status_code=404,
            detail={
                "code": ErrorCode.UNKNOWN_ERROR.value,
                "message": "Job not found or not completed",
                "user_message": "Téléchargement non terminé ou introuvable."
            }
        )
    
    formats = job.result.get("metadata", {}).get("formats", {})
    return FormatsResponse(
        platform=job.platform.value,
        video=formats.get("video", []),
        audio=formats.get("audio", []),
        has_drm=formats.get("has_drm", False),
        supports_video=formats.get("platform_supports_video", True),
        supports_audio=formats.get("platform_supports_audio", True),
        max_height=formats.get("max_height", 1080),
    )


@router.post("/download/estimate")
async def estimate_download(request: DownloadRequest):
    url = str(request.url)
    
    if not _is_url_allowed(url):
        raise HTTPException(
            status_code=400,
            detail={
                "code": ErrorCode.INVALID_URL.value,
                "message": "URL not allowed",
                "user_message": "Ce domaine n'est pas autorisé."
            }
        )
    
    platform = detect_platform(url)
    platform_info = get_platform_info(platform)
    
    return {
        "platform": platform.value,
        "supports_video": platform_info.supports_video,
        "supports_audio": platform_info.supports_audio,
        "max_height": platform_info.max_height,
        "requires_cookies": platform_info.requires_cookies,
        "estimated": True,
    }


def _is_url_allowed(url: str) -> bool:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    for blocked in config.BLOCKED_DOMAINS:
        if domain == blocked or domain.startswith(blocked.rstrip('.')) or domain.endswith('.' + blocked):
            return False
    
    if config.ALLOWED_DOMAINS:
        allowed = False
        for allowed_domain in config.ALLOWED_DOMAINS:
            if domain == allowed_domain or domain.endswith('.' + allowed_domain):
                allowed = True
                break
        if not allowed:
            return False
    
    return True