from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import urllib.parse
from pathlib import Path

from core.config import config
from core.storage import storage, FileInfo

router = APIRouter(prefix="/api/v1", tags=["files"])


class FileListItem(BaseModel):
    name: str
    size: int
    size_str: str
    download_url: str
    is_audio: bool
    is_video: bool


class FileListResponse(BaseModel):
    files: List[FileListItem]
    total: int
    total_size: int
    total_size_str: str
    max_size: int
    usage_percent: float


class DeleteResponse(BaseModel):
    success: bool
    message: str


@router.get("/files", response_model=FileListResponse)
async def list_files():
    files = storage.get_library_files()
    
    items = []
    for f in files:
        items.append(FileListItem(
            name=f.name,
            size=f.size,
            size_str=_format_size(f.size),
            download_url=f"/api/v1/files/{urllib.parse.quote(f.name)}",
            is_audio=f.name.lower().endswith(('.mp3', '.m4a', '.opus', '.flac', '.webm', '.ogg')),
            is_video=f.name.lower().endswith(('.mp4', '.webm', '.mkv', '.mov')),
        ))
    
    stats = storage.get_stats()
    
    return FileListResponse(
        files=items,
        total=len(items),
        total_size=stats["total_size"],
        total_size_str=_format_size(stats["total_size"]),
        max_size=config.MAX_LIBRARY_SIZE,
        usage_percent=stats["usage_percent"],
    )


@router.get("/files/{name}")
async def serve_file(name: str, download: int = 0, inline: int = 0):
    if Path(name).name != name:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")
    
    filepath = config.LIBRARY_DIR / name
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    
    ext = filepath.suffix.lower()
    media_type = {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".opus": "audio/opus",
        ".flac": "audio/flac",
        ".webm": "audio/webm",
        ".ogg": "audio/ogg",
        ".mp4": "video/mp4",
        ".mkv": "video/x-matroska",
        ".mov": "video/quicktime",
    }.get(ext, "application/octet-stream")
    
    # inline=1 => lecture dans le navigateur (Ouvrir), sinon attachment pour Enregistrer
    if inline:
        disposition = f'inline; filename="{name}"'
    else:
        disposition = f'attachment; filename="{name}"'
    # compat: ?download=1 force attachment, ?inline=1 force inline
    if download:
        disposition = f'attachment; filename="{name}"'
    
    return FileResponse(
        path=filepath,
        filename=name,
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": disposition,
        }
    )


@router.head("/files/{name}")
async def head_file(name: str):
    if Path(name).name != name:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")
    
    filepath = config.LIBRARY_DIR / name
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    
    return Response(
        headers={
            "Content-Length": str(filepath.stat().st_size),
            "Accept-Ranges": "bytes",
        }
    )


@router.delete("/files/{name}", response_model=DeleteResponse)
async def delete_file(name: str):
    if Path(name).name != name:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")
    
    filepath = config.LIBRARY_DIR / name
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    
    try:
        filepath.unlink()
        return DeleteResponse(success=True, message="Fichier supprimé")
    except PermissionError:
        raise HTTPException(
            status_code=500,
            detail="Fichier verrouillé par un autre processus. Fermez le lecteur et réessayez."
        )
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Erreur suppression: {e}")


@router.post("/files/cleanup")
async def cleanup_files():
    deleted_expired = storage.cleanup_expired_files()
    deleted_quota = storage.enforce_quota()
    stats = storage.get_stats()
    
    return {
        "success": True,
        "deleted_expired": deleted_expired,
        "deleted_quota": deleted_quota,
        "stats": stats,
        "message": f"Nettoyage terminé: {deleted_expired} expirés, {deleted_quota} pour quota"
    }


@router.get("/files/stats")
async def get_storage_stats():
    return storage.get_stats()


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} o"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} Ko"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} Mo"
    return f"{size / (1024 * 1024 * 1024):.1f} Go"