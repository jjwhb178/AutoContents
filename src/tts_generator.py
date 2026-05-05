"""
TTS Generator Ver 3.2
- 정제된 텍스트(text_cleaner) 기반
- gTTS 생성 후 FFmpeg로 1.2배속 처리
- 슬라이드별 MP3 생성
"""
import json, os, sys, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from output_paths import get_audio_dir
from text_cleaner import clean_for_tts

TTS_SPEED = 1.4  # 1.4배속 고정 (Ver 10.0 Deep Bass 기준)


def load_ppt_script() -> list[str]:
    with open("data/latest_content_logic.json", "r", encoding="utf-8") as f:
        logic = json.load(f)
    script = logic.get("ppt_script", {})
    return [script.get(str(i), {}).get("body", "") for i in range(1, 19)]


def generate_tts_raw(text: str, output_path: str) -> bool:
    """gTTS로 원본 MP3 생성."""
    try:
        from gtts import gTTS
        gTTS(text=text, lang="ko", slow=False).save(output_path)
        return True
    except Exception as e:
        print(f"[TTS Error] {e}")
        return False


def speed_up_audio(input_path: str, output_path: str, rate: float = 1.2) -> bool:
    """
    FFmpeg atempo 필터로 배속 처리.
    atempo는 0.5~2.0 범위만 지원. 1.2는 단일 필터로 가능.
    """
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        ffmpeg = get_ffmpeg_exe()
    except Exception:
        ffmpeg = "ffmpeg"  # PATH에 있을 경우 폴백

    cmd = [
        ffmpeg, "-y", "-i", input_path,
        "-filter:a", f"atempo={rate}",
        "-vn", output_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Speed Error] {e.stderr.decode(errors='ignore')[:200]}")
        return False


def make_slide_audio(text: str, slide_num: int, audio_dir: str) -> str | None:
    """
    한 슬라이드의 음성 파일 생성 (정제 → gTTS → 1.2배속).
    반환: 최종 MP3 경로 (실패 시 None)
    """
    if not text.strip():
        return None

    clean = clean_for_tts(text)
    raw_path   = os.path.join(audio_dir, f"slide_{slide_num:02d}_raw.mp3")
    final_path = os.path.join(audio_dir, f"slide_{slide_num:02d}.mp3")

    if not generate_tts_raw(clean, raw_path):
        return None

    if speed_up_audio(raw_path, final_path, TTS_SPEED):
        os.remove(raw_path)  # 원본 정리
        return final_path
    else:
        # 배속 실패 시 원본으로 폴백
        os.rename(raw_path, final_path)
        print(f"  [Slide {slide_num:02d}] Speed-up failed, using raw speed.")
        return final_path


def main():
    audio_dir = get_audio_dir()
    lines     = load_ppt_script()

    # 전체 대본 합본 (full_narration)
    full_text  = " ".join(l for l in lines if l)
    full_clean = clean_for_tts(full_text)

    raw_full   = os.path.join(audio_dir, "full_narration_raw.mp3")
    final_full = os.path.join(audio_dir, "full_narration.mp3")
    print(f"Generating full narration ({len(full_clean)} chars after clean)...")
    if generate_tts_raw(full_clean, raw_full):
        if not speed_up_audio(raw_full, final_full, TTS_SPEED):
            os.rename(raw_full, final_full)
        elif os.path.exists(raw_full):
            os.remove(raw_full)
        print(f"  [OK] full_narration.mp3")

    # 슬라이드별
    for i, line in enumerate(lines, start=1):
        p = make_slide_audio(line, i, audio_dir)
        if p:
            print(f"  Slide {i:02d} -> {os.path.basename(p)}")

    print(f"[TTS v3.2] Complete. Speed: {TTS_SPEED}x")


if __name__ == "__main__":
    main()
