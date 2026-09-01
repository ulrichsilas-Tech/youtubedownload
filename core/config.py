import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    BASE_DIR: Path = Path(__file__).parent.parent
    STATIC_DIR: Path = BASE_DIR / "static"
    
    DOWNLOAD_DIR: Path = Path(os.getenv("DOWNLOAD_DIR", BASE_DIR / "tmp" / "downloads"))
    LIBRARY_DIR: Path = DOWNLOAD_DIR / "library"
    COOKIES_DIR: Path = DOWNLOAD_DIR / "cookies"
    
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", 500 * 1024 * 1024))
    MAX_LIBRARY_SIZE: int = int(os.getenv("MAX_LIBRARY_SIZE", 500 * 1024 * 1024))
    MAX_FILE_AGE_HOURS: int = int(os.getenv("MAX_FILE_AGE_HOURS", 24))
    CLEANUP_INTERVAL_MINUTES: int = int(os.getenv("CLEANUP_INTERVAL_MINUTES", 30))
    
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", 5))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))
    
    YT_SEARCH_LIMIT: int = int(os.getenv("YT_SEARCH_LIMIT", 20))
    DOWNLOAD_TIMEOUT: int = int(os.getenv("DOWNLOAD_TIMEOUT", 180))
    
    MAX_VIDEO_HEIGHT: int = int(os.getenv("MAX_VIDEO_HEIGHT", 1080))
    MAX_AUDIO_BITRATE: int = int(os.getenv("MAX_AUDIO_BITRATE", 320))
    
    ALLOWED_DOMAINS: list[str] = None
    BLOCKED_DOMAINS: list[str] = None
    
    def __post_init__(self):
        if self.ALLOWED_DOMAINS is None:
            self.ALLOWED_DOMAINS = []
        if self.BLOCKED_DOMAINS is None:
            self.BLOCKED_DOMAINS = [
                "localhost", "127.0.0.1", "0.0.0.0", "::1",
                "10.", "172.16.", "172.17.", "172.18.", "172.19.",
                "172.20.", "172.21.", "172.22.", "172.23.",
                "172.24.", "172.25.", "172.26.", "172.27.",
                "172.28.", "172.29.", "172.30.", "172.31.",
                "192.168.", "169.254."
            ]
        
        self.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        self.COOKIES_DIR.mkdir(parents=True, exist_ok=True)


config = Config()