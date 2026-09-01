from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict
import time
import logging

from core.config import config
from core.storage import storage
from core.downloader import downloader

router = APIRouter(prefix="/api/v1", tags=["health"])
logger = logging.getLogger(__name__)

_rate_limit_store: Dict[str, list] = {}


def check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    window = config.RATE_LIMIT_WINDOW_SECONDS
    max_requests = config.RATE_LIMIT_REQUESTS
    
    if client_ip not in _rate_limit_store:
        _rate_limit_store[client_ip] = []
    
    requests = _rate_limit_store[client_ip]
    requests[:] = [t for t in requests if now - t < window]
    
    if len(requests) >= max_requests:
        return False
    
    requests.append(now)
    return True


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/health")
async def health_check():
    stats = storage.get_stats()
    active_jobs = sum(1 for j in downloader._jobs.values() 
                     if j.status.value in ("pending", "downloading", "processing"))
    
    return {
        "status": "ok",
        "storage": stats,
        "active_jobs": active_jobs,
        "config": {
            "max_file_size_mb": config.MAX_FILE_SIZE // (1024 * 1024),
            "max_library_size_mb": config.MAX_LIBRARY_SIZE // (1024 * 1024),
            "max_file_age_hours": config.MAX_FILE_AGE_HOURS,
            "rate_limit": f"{config.RATE_LIMIT_REQUESTS} req / {config.RATE_LIMIT_WINDOW_SECONDS}s",
        }
    }


@router.get("/health/detailed")
async def health_detailed():
    import sys
    import psutil
    
    process = psutil.Process()
    mem = process.memory_info()
    disk = psutil.disk_usage(str(config.DOWNLOAD_DIR))
    
    return {
        "status": "ok",
        "python_version": sys.version,
        "memory": {
            "rss_mb": round(mem.rss / 1024 / 1024, 1),
            "vms_mb": round(mem.vms / 1024 / 1024, 1),
        },
        "disk": {
            "total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
            "used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
            "free_gb": round(disk.free / 1024 / 1024 / 1024, 1),
            "percent": round(disk.used / disk.total * 100, 1),
        },
        "storage": storage.get_stats(),
        "jobs": {
            "total": len(downloader._jobs),
            "active": sum(1 for j in downloader._jobs.values() 
                         if j.status.value in ("pending", "downloading", "processing")),
            "completed": sum(1 for j in downloader._jobs.values() 
                            if j.status.value == "completed"),
            "failed": sum(1 for j in downloader._jobs.values() 
                         if j.status.value == "failed"),
        }
    }


async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    # Polling du statut (GET /download/{id}) et fichiers/health ne doivent pas etre limites
    # Seul le demarrage d'un telechargement et la recherche sont limites
    should_limit = (
        (path == "/api/v1/download" and request.method == "POST")
        or (path == "/api/v1/search/download" and request.method == "POST")
        or path.startswith("/api/v1/search")
        or path.startswith("/api/v1/info")
    )
    if should_limit:
        client_ip = get_client_ip(request)
        if not check_rate_limit(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "code": "RATE_LIMITED",
                    "message": f"Rate limit exceeded for {client_ip}",
                    "user_message": "Trop de requêtes. Attendez un moment avant de réessayer.",
                    "retry_after": config.RATE_LIMIT_WINDOW_SECONDS
                },
            )

    response = await call_next(request)
    return response