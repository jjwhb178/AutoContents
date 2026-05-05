"""
Shared output path resolver.
모든 스크립트가 이 모듈을 import하여 당일 날짜 폴더를 일관되게 사용합니다.

예시 경로: outputs/2026-04-30/
"""
import os
from datetime import datetime


def get_output_dir(base: str = "outputs") -> str:
    """Return (and create) today's dated output directory."""
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(base, today)
    os.makedirs(path, exist_ok=True)
    return path


def get_path(*parts: str) -> str:
    """Shortcut: get_path('thumbnail.png') → outputs/2026-04-30/thumbnail.png"""
    return os.path.join(get_output_dir(), *parts)


def get_audio_dir() -> str:
    d = os.path.join(get_output_dir(), "audio")
    os.makedirs(d, exist_ok=True)
    return d


def get_slides_dir() -> str:
    d = os.path.join(get_output_dir(), "slides")
    os.makedirs(d, exist_ok=True)
    return d
