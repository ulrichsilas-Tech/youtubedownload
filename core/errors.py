from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    PLATFORM_UNSUPPORTED = "PLATFORM_UNSUPPORTED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    GEO_BLOCKED = "GEO_BLOCKED"
    DRM_PROTECTED = "DRM_PROTECTED"
    CONTENT_UNAVAILABLE = "CONTENT_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_ERROR = "NETWORK_ERROR"
    FORMAT_UNAVAILABLE = "FORMAT_UNAVAILABLE"
    STORAGE_ERROR = "STORAGE_ERROR"
    INVALID_URL = "INVALID_URL"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    TIMEOUT = "TIMEOUT"
    EXTRACTOR_FAILED = "EXTRACTOR_FAILED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass
class DownloadError(Exception):
    code: ErrorCode
    message: str
    user_message: str
    retryable: bool = False
    details: Optional[Dict[str, Any]] = None
    platform: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "user_message": self.user_message,
            "retryable": self.retryable,
            "details": self.details or {},
            "platform": self.platform
        }


class PlatformError(DownloadError):
    def __init__(self, platform: str, message: str, details: Dict = None):
        super().__init__(
            code=ErrorCode.PLATFORM_UNSUPPORTED,
            message=f"Platform {platform}: {message}",
            user_message=f"Cette plateforme ({platform}) n'est pas supportée ou l'extracteur a échoué.",
            retryable=False,
            details=details,
            platform=platform
        )


class AuthRequiredError(DownloadError):
    def __init__(self, platform: str, message: str = "", details: Dict = None):
        super().__init__(
            code=ErrorCode.AUTH_REQUIRED,
            message=f"Auth required for {platform}: {message}",
            user_message="Ce contenu est privé ou nécessite une connexion. Ajoutez vos cookies pour cette plateforme.",
            retryable=True,
            details=details,
            platform=platform
        )


class GeoBlockedError(DownloadError):
    def __init__(self, platform: str, countries: list = None, details: Dict = None):
        super().__init__(
            code=ErrorCode.GEO_BLOCKED,
            message=f"Geo-blocked on {platform}: {countries}",
            user_message="Ce contenu n'est pas disponible dans votre pays. Utilisez un VPN ou proxy.",
            retryable=False,
            details={"countries": countries} if countries else details,
            platform=platform
        )


class DRMProtectedError(DownloadError):
    def __init__(self, platform: str, details: Dict = None):
        super().__init__(
            code=ErrorCode.DRM_PROTECTED,
            message=f"DRM protected content on {platform}",
            user_message="Ce contenu est protégé par des droits numériques (DRM) et ne peut pas être téléchargé.",
            retryable=False,
            details=details,
            platform=platform
        )


class ContentUnavailableError(DownloadError):
    def __init__(self, platform: str, reason: str = "", details: Dict = None):
        super().__init__(
            code=ErrorCode.CONTENT_UNAVAILABLE,
            message=f"Content unavailable on {platform}: {reason}",
            user_message="Cette vidéo n'est plus disponible (supprimée, privée, ou bannie).",
            retryable=False,
            details=details,
            platform=platform
        )


class RateLimitedError(DownloadError):
    def __init__(self, platform: str, retry_after: int = None, details: Dict = None):
        super().__init__(
            code=ErrorCode.RATE_LIMITED,
            message=f"Rate limited by {platform}",
            user_message="Trop de requêtes vers cette plateforme. Attendez quelques minutes avant de réessayer.",
            retryable=True,
            details={"retry_after": retry_after} if retry_after else details,
            platform=platform
        )


class NetworkError(DownloadError):
    def __init__(self, message: str, details: Dict = None):
        super().__init__(
            code=ErrorCode.NETWORK_ERROR,
            message=f"Network error: {message}",
            user_message="Erreur de connexion. Vérifiez votre réseau et réessayez.",
            retryable=True,
            details=details
        )


class FormatUnavailableError(DownloadError):
    def __init__(self, platform: str, requested: str, available: list = None, details: Dict = None):
        super().__init__(
            code=ErrorCode.FORMAT_UNAVAILABLE,
            message=f"Format {requested} unavailable on {platform}. Available: {available}",
            user_message=f"La qualité demandée n'est pas disponible. Qualités disponibles : {', '.join(available) if available else 'inconnues'}.",
            retryable=False,
            details={"requested": requested, "available": available} if available else details,
            platform=platform
        )


class StorageError(DownloadError):
    def __init__(self, message: str, details: Dict = None):
        super().__init__(
            code=ErrorCode.STORAGE_ERROR,
            message=f"Storage error: {message}",
            user_message="Espace de stockage insuffisant. Supprimez d'anciens fichiers ou réessayez plus tard.",
            retryable=True,
            details=details
        )


class InvalidURLError(DownloadError):
    def __init__(self, url: str, reason: str = ""):
        super().__init__(
            code=ErrorCode.INVALID_URL,
            message=f"Invalid URL: {url} - {reason}",
            user_message="Lien invalide ou non supporté. Vérifiez l'URL et réessayez.",
            retryable=False,
            details={"url": url, "reason": reason}
        )


class FileTooLargeError(DownloadError):
    def __init__(self, size: int, max_size: int):
        super().__init__(
            code=ErrorCode.FILE_TOO_LARGE,
            message=f"File too large: {size} bytes (max: {max_size})",
            user_message=f"Le fichier est trop volumineux ({size // 1024 // 1024} MB). Taille max : {max_size // 1024 // 1024} MB.",
            retryable=False,
            details={"size": size, "max_size": max_size}
        )


class QuotaExceededError(DownloadError):
    def __init__(self, current: int, max_quota: int):
        super().__init__(
            code=ErrorCode.QUOTA_EXCEEDED,
            message=f"Quota exceeded: {current} / {max_quota}",
            user_message="Quota de stockage dépassé. Supprimez d'anciens fichiers pour libérer de l'espace.",
            retryable=True,
            details={"current": current, "max_quota": max_quota}
        )


class TimeoutError(DownloadError):
    def __init__(self, platform: str, timeout: int):
        super().__init__(
            code=ErrorCode.TIMEOUT,
            message=f"Timeout on {platform} after {timeout}s",
            user_message="Le téléchargement a pris trop de temps. Réessayez avec une qualité inférieure.",
            retryable=True,
            details={"timeout": timeout},
            platform=platform
        )


class ExtractorFailedError(DownloadError):
    def __init__(self, platform: str, message: str, details: Dict = None):
        super().__init__(
            code=ErrorCode.EXTRACTOR_FAILED,
            message=f"Extractor failed for {platform}: {message}",
            user_message="Échec de l'extraction. La plateforme a peut-être changé. Réessayez plus tard.",
            retryable=True,
            details=details,
            platform=platform
        )


ERROR_MESSAGES_FR = {
    ErrorCode.PLATFORM_UNSUPPORTED: "Plateforme non supportée",
    ErrorCode.AUTH_REQUIRED: "Connexion requise",
    ErrorCode.GEO_BLOCKED: "Blocage géographique",
    ErrorCode.DRM_PROTECTED: "Contenu protégé (DRM)",
    ErrorCode.CONTENT_UNAVAILABLE: "Contenu indisponible",
    ErrorCode.RATE_LIMITED: "Trop de requêtes",
    ErrorCode.NETWORK_ERROR: "Erreur réseau",
    ErrorCode.FORMAT_UNAVAILABLE: "Qualité indisponible",
    ErrorCode.STORAGE_ERROR: "Erreur stockage",
    ErrorCode.INVALID_URL: "URL invalide",
    ErrorCode.FILE_TOO_LARGE: "Fichier trop volumineux",
    ErrorCode.QUOTA_EXCEEDED: "Quota dépassé",
    ErrorCode.TIMEOUT: "Délai dépassé",
    ErrorCode.EXTRACTOR_FAILED: "Échec extraction",
    ErrorCode.UNKNOWN_ERROR: "Erreur inconnue",
}


def get_user_message(code: ErrorCode, default: str = "") -> str:
    return ERROR_MESSAGES_FR.get(code, default)