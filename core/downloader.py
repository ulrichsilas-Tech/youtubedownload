import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

import yt_dlp

from core.config import config
from core.platforms import Platform, detect_platform, build_ydl_options, get_available_formats
from core.storage import storage
from core.errors import (
    DownloadError, PlatformError, AuthRequiredError, GeoBlockedError,
    DRMProtectedError, ContentUnavailableError, RateLimitedError,
    NetworkError, FormatUnavailableError, StorageError, InvalidURLError,
    FileTooLargeError, QuotaExceededError, TimeoutError, ExtractorFailedError,
    ErrorCode
)

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DownloadJob:
    id: str
    url: str
    platform: Platform
    kind: str
    height: str
    codec: str
    bitrate: str
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[DownloadError] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    _future: Optional[asyncio.Future] = field(default=None, repr=False)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "platform": self.platform.value,
            "kind": self.kind,
            "height": self.height,
            "codec": self.codec,
            "bitrate": self.bitrate,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error.to_dict() if self.error else None,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Downloader:
    def __init__(self):
        self._jobs: Dict[str, DownloadJob] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(2)
    
    async def create_job(
        self,
        url: str,
        kind: str = "video",
        height: str = "720",
        codec: str = "mp3",
        bitrate: str = "192",
        cookies: Optional[str] = None,
    ) -> DownloadJob:
        platform = detect_platform(url)
        if platform == Platform.GENERIC:
            logger.warning(f"Unknown platform for URL: {url}")
        
        job = DownloadJob(
            id=str(uuid.uuid4())[:8],
            url=url,
            platform=platform,
            kind=kind,
            height=height,
            codec=codec,
            bitrate=bitrate,
        )
        
        async with self._lock:
            self._jobs[job.id] = job
        
        job._future = asyncio.create_task(self._run_job(job, cookies))
        return job
    
    async def get_job(self, job_id: str) -> Optional[DownloadJob]:
        async with self._lock:
            return self._jobs.get(job_id)
    
    async def _run_job(self, job: DownloadJob, cookies: Optional[str]):
        async with self._semaphore:
            job.status = JobStatus.DOWNLOADING
            job.started_at = datetime.now()
            
            temp_dir = storage.create_temp_dir()
            
            try:
                await self._download(job, temp_dir, cookies)
                job.status = JobStatus.COMPLETED
                job.progress = 100.0
            except DownloadError as e:
                job.error = e
                job.status = JobStatus.FAILED
                logger.warning(f"Job {job.id} failed: {e.code.value} - {e.message}")
            except Exception as e:
                job.error = self._wrap_exception(e, job.platform)
                job.status = JobStatus.FAILED
                logger.error(f"Job {job.id} unexpected error: {e}", exc_info=True)
            finally:
                job.completed_at = datetime.now()
                storage.cleanup_temp_dir(temp_dir)
                
                async with self._lock:
                    if len(self._jobs) > 100:
                        oldest = min(self._jobs.values(), key=lambda j: j.created_at)
                        del self._jobs[oldest.id]
    
    async def _download(self, job: DownloadJob, temp_dir: Path, cookies: Optional[str]):
        opts = build_ydl_options(
            platform=job.platform,
            kind=job.kind,
            height=job.height,
            codec=job.codec,
            bitrate=job.bitrate,
            cookies=cookies,
            output_dir=str(temp_dir),
        )
        
        loop = asyncio.get_event_loop()
        
        def progress_hook(d):
            if d["status"] == "downloading":
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                if total > 0:
                    job.progress = min(90.0, (downloaded / total) * 90)
            elif d["status"] == "finished":
                job.progress = 95.0
                job.status = JobStatus.PROCESSING
        
        opts["progress_hooks"] = [progress_hook]
        
        def extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(job.url, download=True)
        
        try:
            info = await asyncio.wait_for(
                loop.run_in_executor(None, extract),
                timeout=config.DOWNLOAD_TIMEOUT
            )
        except asyncio.TimeoutError:
            raise TimeoutError(job.platform.value, config.DOWNLOAD_TIMEOUT)
        except yt_dlp.utils.DownloadError as e:
            raise self._handle_ytdlp_error(e, job.platform)
        
        if not info:
            raise ContentUnavailableError(job.platform.value, "No info extracted")
        
        formats = get_available_formats(info, job.platform)
        if formats.get("has_drm"):
            raise DRMProtectedError(job.platform.value)
        
        files = list(temp_dir.iterdir())
        if not files:
            raise StorageError("No file produced after download")
        
        src = max(files, key=lambda f: f.stat().st_size)
        size = src.stat().st_size
        
        if size > config.MAX_FILE_SIZE:
            raise FileTooLargeError(size, config.MAX_FILE_SIZE)
        
        if not storage.check_space_available(size):
            raise QuotaExceededError(storage.get_library_size(), config.MAX_LIBRARY_SIZE)
        
        vid = info.get("id") or "dl"
        title = info.get("title") or "video"
        safe_title = self._slug(title)
        ext = src.suffix[1:] or (job.codec if job.kind == "audio" else "mp4")
        base_name = f"{vid}__{safe_title}"
        
        dest = storage.move_to_library(src, base_name, ext)
        
        job.result = {
            "filename": dest.name,
            "download_url": f"/files/{dest.name}",
            "size": dest.stat().st_size,
            "metadata": {
                "id": info.get("id"),
                "title": info.get("title"),
                "channel": info.get("channel") or info.get("uploader"),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "platform": job.platform.value,
                "formats": formats,
            }
        }
    
    def _handle_ytdlp_error(self, e: yt_dlp.utils.DownloadError, platform: Platform) -> DownloadError:
        msg = str(e).lower()
        logger.error(f"yt-dlp error for {platform.value}: {e}")
        
        # TikTok specifique : extracteur casse regulierement
        if platform == Platform.TIKTOK and ("unexpected response" in msg or "webpage request" in msg):
            return ExtractorFailedError(platform.value, f"TikTok a modifié son site. L'extracteur est temporairement indisponible. Réessaie avec le lien de partage complet (vm.tiktok.com/...) ou attends la prochaine mise à jour yt-dlp. Détails: {str(e)[:200]}")
        if any(kw in msg for kw in ["sign in", "login", "authentication", "private", "members only"]):
            return AuthRequiredError(platform.value, str(e))
        if any(kw in msg for kw in ["geo", "country", "region", "not available in"]):
            return GeoBlockedError(platform.value)
        if any(kw in msg for kw in ["drm", "widevine", "protected", "encrypted"]):
            return DRMProtectedError(platform.value)
        if any(kw in msg for kw in ["removed", "deleted", "unavailable", "terminated", "banned", "copyright"]):
            return ContentUnavailableError(platform.value, str(e))
        if any(kw in msg for kw in ["rate limit", "too many requests", "429", "throttl"]):
            return RateLimitedError(platform.value)
        if any(kw in msg for kw in ["network", "connection", "timeout", "dns", "resolve"]):
            return NetworkError(str(e))
        if "format" in msg and ("not available" in msg or "unsupported" in msg):
            return FormatUnavailableError(platform.value, "", [])
        
        return ExtractorFailedError(platform.value, str(e))
    
    def _wrap_exception(self, e: Exception, platform: Platform) -> DownloadError:
        if isinstance(e, DownloadError):
            return e
        
        msg = str(e).lower()
        
        if isinstance(e, (PermissionError, OSError)) and "space" in msg:
            return StorageError(str(e))
        if isinstance(e, asyncio.TimeoutError):
            return TimeoutError(platform.value, config.DOWNLOAD_TIMEOUT)
        if "network" in msg or "connection" in msg or "dns" in msg:
            return NetworkError(str(e))
        
        return ExtractorFailedError(platform.value, str(e))
    
    def _slug(self, text: str, maxlen: int = 60) -> str:
        import re
        s = re.sub(r"[^\w\s-]", "", text or "")
        s = re.sub(r"[\s_]+", "-", s).strip("-")
        return s[:maxlen] or "video"


downloader = Downloader()