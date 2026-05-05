import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from main import run_step, print_footer, print_header

def resume():
    print_header()
    print("Resuming from Phase 3b...")
    
    core = [
        ("Phase 3b | 숫자 검증 루프",                  "python src/verification_loop.py"),
        ("Phase 4  | TTS 음성 1.2배속",               "python src/tts_generator.py"),
        ("Phase 5  | A/B 썸네일 2종 생성",            "python src/thumbnail_generator.py"),
        ("Phase 6  | 영상 합성 (MP4)",                "python src/video_synthesizer.py"),
    ]

    for step_name, cmd in core:
        if not run_step(step_name, cmd):
            print("  [FAIL] Pipeline aborted. Check data/history.json")
            sys.exit(1)

    optional = [
        ("Phase 7  | 네이버 블로그 포스팅",  "python src/naver_blog_poster.py"),
        ("Phase 8  | 유튜브 업로드",         "python src/youtube_uploader.py"),
    ]
    print("\n  [Optional: skipped if credentials not set]")
    for step_name, cmd in optional:
        run_step(step_name, cmd, optional=True)

    print_footer()

if __name__ == "__main__":
    resume()
