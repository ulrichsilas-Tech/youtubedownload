import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from core.config import config
from core.storage import storage
from core.downloader import downloader
from api.download import router as download_router
from api.search import router as search_router
from api.files import router as files_router
from api.cookies import router as cookies_router
from api.health import router as health_router, rate_limit_middleware


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Universal Media Downloader")
    logger.info(f"Download dir: {config.DOWNLOAD_DIR}")
    logger.info(f"Library dir: {config.LIBRARY_DIR}")
    logger.info(f"Max file size: {config.MAX_FILE_SIZE // 1024 // 1024} MB")
    logger.info(f"Max library size: {config.MAX_LIBRARY_SIZE // 1024 // 1024} MB")
    yield
    logger.info("Shutting down...")
    storage.stop()


app = FastAPI(
    title="Universal Media Downloader",
    version="3.0.0",
    description="Téléchargeur multimédia universel avec recherche YouTube intégrée",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(rate_limit_middleware)

app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
app.mount("/icons", StaticFiles(directory=config.STATIC_DIR / "icons"), name="icons")

app.include_router(health_router)
app.include_router(download_router)
app.include_router(search_router)
app.include_router(files_router)
app.include_router(cookies_router)


@app.get("/manifest.json", response_class=FileResponse)
async def manifest():
    return FileResponse(config.STATIC_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/sw.js", response_class=FileResponse)
async def service_worker():
    return FileResponse(config.STATIC_DIR / "sw.js", media_type="application/javascript")


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(config.STATIC_DIR / "index.html")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "user_message" in exc.detail:
        return exc.detail
    return {"code": "HTTP_ERROR", "message": exc.detail, "user_message": str(exc.detail)}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return {
        "code": "INTERNAL_ERROR",
        "message": str(exc),
        "user_message": "Une erreur inattendue s'est produite. Réessayez plus tard."
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))