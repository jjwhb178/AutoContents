"""
Shared output path resolver.
모든 스크립트가 이 모듈을 import하여 당일 날짜 폴더를 일관되게 사용합니다.

예시 경로: outputs/2026-04-30/
"""
import os
import json
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


def get_topic_keyword() -> str:
    """data/selected_keyword.txt 또는 latest_content_logic.json에서 주제 키워드를 추출합니다."""
    keyword_file = "data/selected_keyword.txt"
    if os.path.exists(keyword_file):
        with open(keyword_file, "r", encoding="utf-8") as f:
            val = f.read().strip()
            if val:
                return val

    # 폴백: latest_content_logic.json 파싱
    logic_path = "data/latest_content_logic.json"
    if os.path.exists(logic_path):
        try:
            with open(logic_path, "r", encoding="utf-8") as f:
                logic = json.load(f)
                title = logic.get("title", "")
                import re
                cleaned = re.sub(r"[^\w가-힣]", " ", title).strip()
                words = [w for w in cleaned.split() if w]
                if words:
                    return words[0][:10]
        except Exception:
            pass

    return "경제이슈"


def get_dated_filename(suffix: str, ext: str) -> str:
    """날짜(YYYYMMDD)와 키워드가 결합된 파일명을 생성합니다. 예: 20260530_ai투자_블로그초안.md"""
    today_str = datetime.now().strftime("%Y%m%d")
    keyword = get_topic_keyword()
    import re
    keyword = re.sub(r'[\\/*?:"<>|]', "", keyword)
    return f"{today_str}_{keyword}_{suffix}.{ext}"


def get_dated_path(suffix: str, ext: str) -> str:
    """날짜(YYYYMMDD)와 키워드를 결합한 전체 저장 경로를 반환합니다."""
    filename = get_dated_filename(suffix, ext)
    return os.path.join(get_output_dir(), filename)



def get_audio_dir() -> str:
    d = os.path.join(get_output_dir(), "audio")
    os.makedirs(d, exist_ok=True)
    return d


def get_slides_dir() -> str:
    d = os.path.join(get_output_dir(), "slides")
    os.makedirs(d, exist_ok=True)
    return d
