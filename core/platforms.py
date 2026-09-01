import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from urllib.parse import urlparse
from enum import Enum


class Platform(str, Enum):
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    VIMEO = "vimeo"
    TWITCH = "twitch"
    DAILYMOTION = "dailymotion"
    SOUNDCLOUD = "soundcloud"
    BANDCAMP = "bandcamp"
    REDDIT = "reddit"
    GENERIC = "generic"


@dataclass
class PlatformInfo:
    name: Platform
    domains: List[str]
    patterns: List[str] = field(default_factory=list)
    requires_cookies: bool = False
    supports_audio: bool = True
    supports_video: bool = True
    max_height: int = 1080
    default_format: str = "mp4"
    extractor_args: Dict[str, Any] = field(default_factory=dict)
    format_selector_video: str = "bestvideo+bestaudio/best"
    format_selector_audio: str = "bestaudio/best"
    postprocessors: List[Dict] = field(default_factory=list)


PLATFORMS: Dict[Platform, PlatformInfo] = {
    Platform.YOUTUBE: PlatformInfo(
        name=Platform.YOUTUBE,
        domains=["youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com", "music.youtube.com"],
        patterns=[
            r"(?:youtube\.com/(?:watch\?v=|embed/|v/|shorts/|live/)|youtu\.be/)([\w-]{11})",
            r"youtube\.com/playlist\?list=",
        ],
        requires_cookies=True,
        supports_audio=True,
        supports_video=True,
        max_height=2160,
        default_format="mp4",
        extractor_args={"youtube": {"player_client": ["tv_embedded", "android", "web"]}},
        format_selector_video="bestvideo[height<=?height]+bestaudio/best[height<=?height]/best",
        format_selector_audio="bestaudio/best",
        postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    ),
    Platform.FACEBOOK: PlatformInfo(
        name=Platform.FACEBOOK,
        domains=["facebook.com", "fb.watch", "www.facebook.com", "m.facebook.com"],
        patterns=[r"facebook\.com/.*/(?:videos|watch)/", r"fb\.watch/"],
        requires_cookies=True,
        supports_audio=True,
        supports_video=True,
        max_height=1080,
        default_format="mp4",
        format_selector_video="best[ext=mp4]/best",
        format_selector_audio="bestaudio[ext=m4a]/bestaudio",
    ),
    Platform.TIKTOK: PlatformInfo(
        name=Platform.TIKTOK,
        domains=["tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"],
        patterns=[r"tiktok\.com/@[\w.]+/video/", r"vm\.tiktok\.com/", r"vt\.tiktok\.com/"],
        requires_cookies=False,
        supports_audio=True,
        supports_video=True,
        max_height=1080,
        default_format="mp4",
        extractor_args={"tiktok": {"webpage_download": True}},
        format_selector_video="best[ext=mp4]/best",
        format_selector_audio="bestaudio[ext=m4a]/bestaudio",
    ),
    Platform.TWITTER: PlatformInfo(
        name=Platform.TWITTER,
        domains=["twitter.com", "x.com", "t.co", "www.twitter.com", "www.x.com"],
        patterns=[r"(?:twitter|x)\.com/\w+/status/", r"t\.co/"],
        requires_cookies=True,
        supports_audio=True,
        supports_video=True,
        max_height=1080,
        default_format="mp4",
        format_selector_video="best[ext=mp4]/best",
        format_selector_audio="bestaudio[ext=m4a]/bestaudio",
    ),
    Platform.INSTAGRAM: PlatformInfo(
        name=Platform.INSTAGRAM,
        domains=["instagram.com", "www.instagram.com"],
        patterns=[r"instagram\.com/(?:p|reel|tv|reels)/"],
        requires_cookies=True,
        supports_audio=True,
        supports_video=True,
        max_height=1080,
        default_format="mp4",
        format_selector_video="best[ext=mp4]/best",
        format_selector_audio="bestaudio[ext=m4a]/bestaudio",
    ),
    Platform.VIMEO: PlatformInfo(
        name=Platform.VIMEO,
        domains=["vimeo.com", "www.vimeo.com", "player.vimeo.com"],
        patterns=[r"vimeo\.com/\d+"],
        requires_cookies=False,
        supports_audio=True,
        supports_video=True,
        max_height=1080,
        default_format="mp4",
        format_selector_video="best[ext=mp4]/best",
        format_selector_audio="bestaudio[ext=m4a]/bestaudio",
    ),
    Platform.TWITCH: PlatformInfo(
        name=Platform.TWITCH,
        domains=["twitch.tv", "www.twitch.tv", "clips.twitch.tv"],
        patterns=[r"twitch\.tv/videos/", r"clips\.twitch\.tv/"],
        requires_cookies=False,
        supports_audio=True,
        supports_video=True,
        max_height=1080,
        default_format="mp4",
        format_selector_video="best[ext=mp4]/best",
        format_selector_audio="bestaudio[ext=m4a]/bestaudio",
    ),
    Platform.DAILYMOTION: PlatformInfo(
        name=Platform.DAILYMOTION,
        domains=["dailymotion.com", "www.dailymotion.com", "dai.ly"],
        patterns=[r"dailymotion\.com/video/", r"dai\.ly/"],
        requires_cookies=False,
        supports_audio=True,
        supports_video=True,
        max_height=1080,
        default_format="mp4",
        format_selector_video="best[ext=mp4]/best",
        format_selector_audio="bestaudio[ext=m4a]/bestaudio",
    ),
    Platform.SOUNDCLOUD: PlatformInfo(
        name=Platform.SOUNDCLOUD,
        domains=["soundcloud.com", "www.soundcloud.com", "on.soundcloud.com"],
        patterns=[r"soundcloud\.com/[\w-]+/[\w-]+"],
        requires_cookies=False,
        supports_audio=True,
        supports_video=False,
        max_height=0,
        default_format="mp3",
        format_selector_video="",
        format_selector_audio="bestaudio/best",
        postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}],
    ),
    Platform.BANDCAMP: PlatformInfo(
        name=Platform.BANDCAMP,
        domains=["bandcamp.com", "*.bandcamp.com"],
        patterns=[r"\.bandcamp\.com/(?:track|album)/"],
        requires_cookies=False,
        supports_audio=True,
        supports_video=False,
        max_height=0,
        default_format="mp3",
        format_selector_video="",
        format_selector_audio="bestaudio/best",
        postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}],
    ),
    Platform.REDDIT: PlatformInfo(
        name=Platform.REDDIT,
        domains=["reddit.com", "www.reddit.com", "v.redd.it"],
        patterns=[r"reddit\.com/r/.*/comments/", r"v\.redd\.it/"],
        requires_cookies=False,
        supports_audio=True,
        supports_video=True,
        max_height=1080,
        default_format="mp4",
        format_selector_video="best[ext=mp4]/best",
        format_selector_audio="bestaudio[ext=m4a]/bestaudio",
    ),
    Platform.GENERIC: PlatformInfo(
        name=Platform.GENERIC,
        domains=[],
        patterns=[],
        requires_cookies=False,
        supports_audio=True,
        supports_video=True,
        max_height=1080,
        default_format="mp4",
        format_selector_video="bestvideo+bestaudio/best",
        format_selector_audio="bestaudio/best",
    ),
}


DOMAIN_TO_PLATFORM: Dict[str, Platform] = {}
for platform, info in PLATFORMS.items():
    for domain in info.domains:
        DOMAIN_TO_PLATFORM[domain.lower()] = platform
        if domain.startswith("*."):
            DOMAIN_TO_PLATFORM[domain[2:].lower()] = platform


def detect_platform(url: str) -> Platform:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        for known_domain, platform in DOMAIN_TO_PLATFORM.items():
            if domain == known_domain or domain.endswith("." + known_domain):
                return platform
        
        for platform, info in PLATFORMS.items():
            for pattern in info.patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return platform
        
        return Platform.GENERIC
    except Exception:
        return Platform.GENERIC


def get_platform_info(platform: Platform) -> PlatformInfo:
    return PLATFORMS.get(platform, PLATFORMS[Platform.GENERIC])


def get_cookie_file(platform: Platform) -> Optional[str]:
    from core.config import config
    cookie_file = config.COOKIES_DIR / f"{platform.value}.txt"
    return str(cookie_file) if cookie_file.exists() else None


def build_ydl_options(
    platform: Platform,
    kind: str,
    height: str = "720",
    codec: str = "mp3",
    bitrate: str = "192",
    cookies: Optional[str] = None,
    output_dir: Optional[str] = None,
    extra_args: Dict = None
) -> Dict[str, Any]:
    info = get_platform_info(platform)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ignoreerrors": False,
        "retries": 3,
        "fragment_retries": 3,
        "skip_unavailable_fragments": True,
    }
    
    if cookies:
        opts["cookiefile"] = cookies
    elif info.requires_cookies:
        cookie_file = get_cookie_file(platform)
        if cookie_file:
            opts["cookiefile"] = cookie_file
    
    if output_dir:
        opts["outtmpl"] = str(Path(output_dir) / "%(id)s.%(ext)s")
    
    if extra_args:
        opts.update(extra_args)
    
    if platform == Platform.YOUTUBE:
        opts["extractor_args"] = info.extractor_args
    
    max_h = min(int(height) if height.isdigit() else info.max_height, info.max_height)
    
    if kind == "audio":
        if not info.supports_audio:
            raise ValueError(f"Platform {platform.value} does not support audio download")
        opts["format"] = info.format_selector_audio
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": codec,
            "preferredquality": str(min(int(bitrate), 320)),
        }]
        if info.postprocessors:
            opts["postprocessors"].extend(info.postprocessors)
    else:
        if not info.supports_video:
            raise ValueError(f"Platform {platform.value} does not support video download")
        fmt = info.format_selector_video.replace("?height", str(max_h))
        opts["format"] = fmt
        opts["merge_output_format"] = info.default_format
    
    return opts


def get_available_formats(info: Dict, platform: Platform) -> Dict[str, List[str]]:
    platform_info = get_platform_info(platform)
    formats = info.get("formats", [])
    
    video_qualities = set()
    audio_qualities = set()
    has_drm = False
    
    for f in formats:
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec", "none")
        height = f.get("height")
        abr = f.get("abr")
        ext = f.get("ext", "")
        
        if vcodec != "none" and height:
            video_qualities.add(f"{height}p")
        if acodec != "none" and abr:
            audio_qualities.add(f"{int(abr)}kbps")
        
        if vcodec == "none" and acodec == "none" and f.get("protocol", "").startswith("m3u8"):
            has_drm = True
    
    return {
        "video": sorted(video_qualities, key=lambda x: int(x.rstrip('p')), reverse=True) if video_qualities else ["best"],
        "audio": sorted(audio_qualities, key=lambda x: int(x.rstrip('kbps')), reverse=True) if audio_qualities else ["best"],
        "has_drm": has_drm,
        "platform_supports_video": platform_info.supports_video,
        "platform_supports_audio": platform_info.supports_audio,
        "max_height": platform_info.max_height,
    }