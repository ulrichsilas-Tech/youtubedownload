import os
import time
import threading
import logging
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass

from core.config import config

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    path: Path
    name: str
    size: int
    mtime: float
    is_temp: bool = False


class StorageManager:
    _instance: Optional['StorageManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        logger.info("Storage cleanup task started")
    
    def _cleanup_loop(self):
        while not self._stop_cleanup.is_set():
            try:
                self.cleanup_expired_files()
                self.enforce_quota()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
            self._stop_cleanup.wait(config.CLEANUP_INTERVAL_MINUTES * 60)
    
    def stop(self):
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
    
    def get_library_files(self) -> List[FileInfo]:
        files = []
        for p in config.LIBRARY_DIR.iterdir():
            if p.is_file():
                stat = p.stat()
                files.append(FileInfo(
                    path=p,
                    name=p.name,
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                    is_temp=False
                ))
        return sorted(files, key=lambda f: f.mtime, reverse=True)
    
    def get_temp_files(self) -> List[FileInfo]:
        files = []
        for p in config.DOWNLOAD_DIR.iterdir():
            if p.is_dir():
                for f in p.iterdir():
                    if f.is_file():
                        stat = f.stat()
                        files.append(FileInfo(
                            path=f,
                            name=f.name,
                            size=stat.st_size,
                            mtime=stat.st_mtime,
                            is_temp=True
                        ))
        return files
    
    def get_library_size(self) -> int:
        return sum(f.size for f in self.get_library_files())
    
    def get_library_count(self) -> int:
        return len(self.get_library_files())
    
    def cleanup_expired_files(self) -> int:
        now = time.time()
        max_age = config.MAX_FILE_AGE_HOURS * 3600
        deleted = 0
        
        for f in self.get_library_files():
            if now - f.mtime > max_age:
                try:
                    f.path.unlink(missing_ok=True)
                    deleted += 1
                    logger.info(f"Deleted expired file: {f.name}")
                except Exception as e:
                    logger.error(f"Failed to delete {f.name}: {e}")
        
        for f in self.get_temp_files():
            if now - f.mtime > 3600:
                try:
                    f.path.unlink(missing_ok=True)
                    if f.path.parent.exists() and not any(f.path.parent.iterdir()):
                        f.path.parent.rmdir()
                    deleted += 1
                except Exception as e:
                    logger.error(f"Failed to delete temp {f.name}: {e}")
        
        return deleted
    
    def enforce_quota(self) -> int:
        current_size = self.get_library_size()
        if current_size <= config.MAX_LIBRARY_SIZE:
            return 0
        
        files = self.get_library_files()
        deleted = 0
        for f in files:
            if current_size <= config.MAX_LIBRARY_SIZE * 0.8:
                break
            try:
                f.path.unlink(missing_ok=True)
                current_size -= f.size
                deleted += 1
                logger.info(f"Quota enforcement: deleted {f.name}")
            except Exception as e:
                logger.error(f"Quota delete failed {f.name}: {e}")
        
        return deleted
    
    def create_temp_dir(self) -> Path:
        import tempfile
        temp_dir = Path(tempfile.mkdtemp(dir=config.DOWNLOAD_DIR, prefix="dl_"))
        return temp_dir
    
    def cleanup_temp_dir(self, temp_dir: Path):
        try:
            for f in temp_dir.iterdir():
                if f.is_file():
                    f.unlink(missing_ok=True)
            temp_dir.rmdir()
        except Exception as e:
            logger.error(f"Failed to cleanup temp dir {temp_dir}: {e}")
    
    def generate_unique_filename(self, base_name: str, ext: str) -> Path:
        dest = config.LIBRARY_DIR / f"{base_name}.{ext}"
        if not dest.exists():
            return dest
        
        n = 2
        while True:
            dest = config.LIBRARY_DIR / f"{base_name}-{n}.{ext}"
            if not dest.exists():
                return dest
            n += 1
    
    def move_to_library(self, src: Path, base_name: str, ext: str) -> Path:
        dest = self.generate_unique_filename(base_name, ext)
        src.rename(dest)
        return dest
    
    def check_space_available(self, required: int) -> bool:
        current = self.get_library_size()
        return (current + required) <= config.MAX_LIBRARY_SIZE
    
    def get_stats(self) -> dict:
        files = self.get_library_files()
        total_size = sum(f.size for f in files)
        if files:
            oldest_age = round((time.time() - min(f.mtime for f in files)) / 3600, 1)
            newest_age = round((time.time() - max(f.mtime for f in files)) / 3600, 1)
        else:
            oldest_age = 0
            newest_age = 0
        return {
            "total_files": len(files),
            "total_size": total_size,
            "max_size": config.MAX_LIBRARY_SIZE,
            "usage_percent": round(total_size / config.MAX_LIBRARY_SIZE * 100, 1) if config.MAX_LIBRARY_SIZE > 0 else 0,
            "oldest_file_age_hours": oldest_age,
            "newest_file_age_hours": newest_age,
        }


storage = StorageManager()