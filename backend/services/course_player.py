import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

COMPLETION_THRESHOLD = 1.0
MIN_COMPLETION_SECONDS = 12
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def is_valid_youtube_id(youtube_id: Optional[str]) -> bool:
    if not youtube_id:
        return False
    return bool(VIDEO_ID_PATTERN.fullmatch(str(youtube_id).strip()))


def extract_youtube_video_id(url: Optional[str]) -> Optional[str]:
    """Extract a YouTube video id from common YouTube URL formats."""
    if not url:
        return None

    cleaned = url.strip()
    if not cleaned:
        return None

    if VIDEO_ID_PATTERN.fullmatch(cleaned):
        return cleaned

    parsed = urlparse(cleaned)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").strip("/")

    if "youtube.com" in host or "youtu.be" in host or "m.youtube.com" in host:
        if "youtu.be" in host:
            video_id = path.split("/")[0]
            return video_id if VIDEO_ID_PATTERN.fullmatch(video_id) else None

        if parsed.query:
            params = parse_qs(parsed.query)
            if params.get("v"):
                video_id = params["v"][0]
                return video_id if VIDEO_ID_PATTERN.fullmatch(video_id) else None

        path_parts = [part for part in path.split("/") if part]
        if path_parts and path_parts[0] in {"embed", "shorts", "live"} and len(path_parts) > 1:
            candidate = path_parts[1]
            return candidate if VIDEO_ID_PATTERN.fullmatch(candidate) else None

    return None


def should_complete_lesson(progress_ratio: float, watched_seconds: int, ended: bool) -> bool:
    """Return True when the lesson should be marked complete."""
    if ended:
        return True

    if progress_ratio >= COMPLETION_THRESHOLD and watched_seconds >= MIN_COMPLETION_SECONDS:
        return True

    return False


def clamp_progress(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def calculate_progress(duration_seconds: Optional[float], current_seconds: Optional[float]) -> float:
    if not duration_seconds or duration_seconds <= 0:
        return 0.0
    if not current_seconds or current_seconds <= 0:
        return 0.0
    ratio = current_seconds / duration_seconds
    return clamp_progress(ratio * 100.0)


def summarize_state(progress_ratio: float, watched_seconds: int, ended: bool) -> dict:
    return {
        "progress_ratio": round(progress_ratio, 4),
        "watched_seconds": watched_seconds,
        "ended": ended,
        "should_complete": should_complete_lesson(progress_ratio, watched_seconds, ended),
    }
