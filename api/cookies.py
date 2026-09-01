from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from pathlib import Path

from core.config import config
from core.platforms import Platform

router = APIRouter(prefix="/api/v1", tags=["cookies"])


class CookiesRequest(BaseModel):
    platform: str = Field(..., description="Platform name (youtube, facebook, tiktok, twitter, instagram)")
    content: str = Field(..., min_length=10, description="Cookies in Netscape format")


class CookiesStatusResponse(BaseModel):
    platform: str
    configured: bool
    file_size: Optional[int] = None


class AllCookiesStatusResponse(BaseModel):
    cookies: Dict[str, bool]
    details: Dict[str, Dict]


PLATFORMS_WITH_COOKIES = [
    Platform.YOUTUBE,
    Platform.FACEBOOK,
    Platform.TIKTOK,
    Platform.TWITTER,
    Platform.INSTAGRAM,
]


@router.get("/cookies", response_model=AllCookiesStatusResponse)
async def cookies_status():
    details = {}
    configured = {}
    
    for platform in PLATFORMS_WITH_COOKIES:
        cookie_file = config.COOKIES_DIR / f"{platform.value}.txt"
        exists = cookie_file.exists()
        configured[platform.value] = exists
        details[platform.value] = {
            "configured": exists,
            "file_size": cookie_file.stat().st_size if exists else 0,
            "requires_cookies": True,
        }
    
    return AllCookiesStatusResponse(cookies=configured, details=details)


@router.get("/cookies/{platform}", response_model=CookiesStatusResponse)
async def cookie_status(platform: str):
    try:
        p = Platform(platform.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Plateforme inconnue: {platform}")
    
    cookie_file = config.COOKIES_DIR / f"{p.value}.txt"
    exists = cookie_file.exists()
    
    return CookiesStatusResponse(
        platform=p.value,
        configured=exists,
        file_size=cookie_file.stat().st_size if exists else None,
    )


@router.post("/cookies/{platform}")
async def save_cookies(platform: str, request: CookiesRequest):
    try:
        p = Platform(platform.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Plateforme inconnue: {platform}")
    
    if p not in PLATFORMS_WITH_COOKIES:
        raise HTTPException(status_code=400, detail=f"Cookies non supportés pour {platform}")
    
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Contenu vide")
    
    if not _validate_netscape_cookies(content):
        raise HTTPException(
            status_code=400,
            detail="Format de cookies invalide. Utilisez le format Netscape (export depuis extension navigateur)."
        )
    
    if not _has_platform_domain(content, p):
        raise HTTPException(
            status_code=400,
            detail=f"Les cookies ne semblent pas contenir de domaine pour {p.value}."
        )
    
    cookie_file = config.COOKIES_DIR / f"{p.value}.txt"
    cookie_file.write_text(content, encoding="utf-8")
    
    return {"success": True, "configured": True, "message": f"Cookies {p.value} enregistrés"}


@router.delete("/cookies/{platform}")
async def delete_cookies(platform: str):
    try:
        p = Platform(platform.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Plateforme inconnue: {platform}")
    
    cookie_file = config.COOKIES_DIR / f"{p.value}.txt"
    cookie_file.unlink(missing_ok=True)
    
    return {"success": True, "configured": False, "message": f"Cookies {p.value} supprimés"}


def _validate_netscape_cookies(content: str) -> bool:
    lines = content.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) >= 7:
            return True
    return False


def _has_platform_domain(content: str, platform: Platform) -> bool:
    domain_keywords = {
        Platform.YOUTUBE: ["youtube.com", ".youtube."],
        Platform.FACEBOOK: ["facebook.com", ".facebook.", "fbcdn.net"],
        Platform.TIKTOK: ["tiktok.com", ".tiktok."],
        Platform.TWITTER: ["twitter.com", "x.com", ".twitter.", ".x."],
        Platform.INSTAGRAM: ["instagram.com", ".instagram."],
    }
    
    keywords = domain_keywords.get(platform, [platform.value])
    content_lower = content.lower()
    return any(kw in content_lower for kw in keywords)