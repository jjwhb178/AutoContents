import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from main import run_step

def print_header():
    print("\n" + "=" * 60)
    print("  MoneyDaddy AI Content Factory - Resume Pipeline")
    print("=" * 60)

def print_footer():
    print("=" * 60)
    print("  Pipeline resumed successfully.")
    print("=" * 60 + "\n")

def resume():
    print_header()
    print("Resuming from Phase 3b...")
    
    py = sys.executable
    core = [
        ("Phase 3  | 숫자 검증 루프",                  f'"{py}" src/verification_loop.py'),
        ("Phase 4a | 시각 자료 및 차트 생성",          f'"{py}" src/visual_generator.py'),
        ("Phase 4b | 유튜브 디자인 썸네일 생성",       f'"{py}" src/thumbnail_generator.py'),
        ("Phase 4c | Google Imagen 3 AI 이미지 생성",  f'"{py}" src/imagen_generator.py'),
        ("Phase 5  | Remotion 비디오 다이렉트 생성",   f'"{py}" src/remotion_orchestrator.py'),
    ]

    for step_name, cmd in core:
        if not run_step(step_name, cmd):
            print("  [FAIL] Pipeline aborted. Check data/history.json")
            sys.exit(1)

    optional = [
        ("Phase 6  | 네이버 블로그 포스팅",  f'"{py}" src/naver_blog_poster.py'),
        ("Phase 7  | 유튜브 업로드",         f'"{py}" src/youtube_uploader.py'),
    ]
    print("\n  [Optional: skipped if credentials not set]")
    for step_name, cmd in optional:
        run_step(step_name, cmd, optional=True)

    print_footer()

if __name__ == "__main__":
    resume()
