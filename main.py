import os, sys, json, time, subprocess
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from output_paths import get_output_dir

console = Console()

def run_step(step_name: str, command: str, optional: bool = False) -> bool:
    with console.status(f"[bold green]Running: {step_name}...", spinner="dots"):
        t0 = time.time()
        try:
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            elapsed = round(time.time() - t0, 1)
            console.print(f"[bold green][OK][/bold green] {step_name} ({elapsed}s)")
            if result.stdout:
                for line in result.stdout.strip().split('\n')[-3:]:
                    if line.strip():
                        console.print(f"[dim]    {line.strip()}[/dim]")
            return True
        except subprocess.CalledProcessError as e:
            elapsed = round(time.time() - t0, 1)
            label = "[bold yellow][SKIP][/bold yellow]" if optional else "[bold red][FAIL][/bold red]"
            console.print(f"{label} {step_name} ({elapsed}s)")
            if e.stderr:
                console.print(f"[dim]{e.stderr[-400:]}[/dim]")
            return optional

def print_dashboard_preview():
    logic_path = "data/latest_content_logic.json"
    if not os.path.exists(logic_path):
        return
    with open(logic_path, "r", encoding="utf-8") as f:
        logic = json.load(f)

    console.print("\n[bold cyan]=== Content Orchestration Preview ===[/bold cyan]")
    console.print(f"[bold]Title:[/bold] {logic.get('title', '(생성 중)')}")
    console.print(f"[bold]Theme:[/bold] {logic.get('theme_analysis', '')[:80]}")

def get_proposals():
    console.print("[bold yellow]뉴스 분석 및 주제 후보 도출 중...[/bold yellow]")
    import src.market_data_collector as mdc
    import src.content_generator as cg
    mdc.main()

    with open("data/raw_market_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    proposals = cg.propose_topics(data)
    if not proposals:
        console.print("[red]주제 제안에 실패했습니다. 기본 설정으로 진행합니다.[/red]")
        return data, "오늘의 핵심 경제 이슈 분석"

    console.print(Panel(
        "\n".join([f"[bold]{p['id']}. {p['type']} - {p['title']}[/bold]\n  └ {p['reason']}" for p in proposals]),
        title="오늘의 기획 제안 (Proposals)"
    ))
    choice = Prompt.ask("주제 번호를 선택하거나 직접 입력하세요", default="1")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(proposals):
            selected_topic = proposals[idx]["title"]
        else:
            selected_topic = choice
    except (ValueError, IndexError):
        selected_topic = choice
        
    console.print(f"\n[bold green][OK] 확정된 주제:[/bold green] {selected_topic}\n")
    return data, selected_topic

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="비대화형 자동 실행")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold blue]MoneyDaddy AI Content Factory Ver 14.0[/bold blue]\n"
        "[dim]Research-First Pipeline / Remotion Direct Render[/dim]"
    ))

    py = sys.executable

    # ── Phase 1: 시장 데이터 수집 ────────────────────────────────────────────
    if not args.auto:
        data, selected_topic = get_proposals()
    else:
        run_step("Phase 1 | 시장 데이터 수집", f'"{py}" src/market_data_collector.py')
        with open("data/raw_market_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        selected_topic = "오늘의 핵심 경제 이슈와 시스템적 결함 분석"

    # Save selected keyword for dated filenames
    import re
    cleaned = re.sub(r"[^\w가-힣]", " ", selected_topic).strip()
    words = [w for w in cleaned.split() if w]
    keyword = words[0] if words else "경제이슈"
    keyword = keyword[:10]
    os.makedirs("data", exist_ok=True)
    with open("data/selected_keyword.txt", "w", encoding="utf-8") as f:
        f.write(keyword)

    # ── Phase 2: Topic Research ───────────────────────────────────────
    console.print("\n[bold cyan]=== [RESEARCH] Topic Research Start ===[/bold cyan]")
    run_step("Phase 2 | Topic Research (뉴스/주가/서사 분석)",
             f'"{py}" src/research_agent.py "{selected_topic}"')

    # ── Phase 3: 콘텐츠 기획 및 블로그 생성 ───────────────────────────────────
    console.print("\n[bold cyan]=== [CONTENT] Content Generation Start ===[/bold cyan]")
    with console.status("[bold magenta]기획 및 블로그 본문 작성 중 (Research 기반)...[/bold magenta]", spinner="dots"):
        import src.content_generator as cg
        cg.run_content_generation(data, selected_topic)
    console.print("[bold green][OK][/bold green] Phase 3 | 블로그 기획/대본 생성 완료")
    print_dashboard_preview()

    # ── Phase 3b: Verification Loop (Gate) ───────────────────────────────────
    console.print("\n[bold cyan]=== [VERIFY] Fact-Checking Gate ===[/bold cyan]")
    with console.status("[bold yellow]생성된 콘텐츠의 팩트 정합성 검증 중...", spinner="dots"):
        import src.verification_loop as vl
        report = ""
        try:
            report = vl.verify_content()
        except Exception as e:
            report = f"FAILED: 검증 스크립트 실행 중 예외 발생: {e}"
        
    if "FAILED" in report:
        console.print(Panel(report, title="[yellow]Verification Warning[/yellow]", border_style="yellow"))
        console.print("[bold yellow]⚠️ 팩트 불일치 혹은 검증 에러가 발견되었으나 파이프라인을 계속 진행합니다.[/bold yellow]")
    else:
        console.print("[bold green][PASS][/bold green] 팩트 검증 통과")

    # ── Phase 4: 시각 자료 및 블로그 이미지 생성 (무료 생성 기능 유지) ─────────────
    console.print("\n[bold cyan]=== [DESIGN] Blog Visuals & Thumbnail Generation ===[/bold cyan]")
    run_step("Phase 4a | 블로그/소셜용 차트 및 인포그래픽 이미지 생성", f'"{py}" src/visual_generator.py')
    run_step("Phase 4b | 유튜브/소셜용 디자인 썸네일 생성", f'"{py}" src/thumbnail_generator.py')
    run_step("Phase 4c | 구글 Imagen 3 기반 인공지능 썸네일 및 블로그 이미지 생성", f'"{py}" src/imagen_generator.py')

    # ── Intermediate Approval Gate ────────────────────────────────────────────
    if not args.auto:
        out_dir = get_output_dir()
        console.print(f"\n[bold green][CHECK] 블로그 및 시각 자료 준비 완료: {out_dir}")
        if not Confirm.ask("\n[bold red][QUESTION] Remotion 기반 동영상 제작을 시작하시겠습니까? (Neural TTS 포함)[/bold red]"):
            console.print("[bold yellow]작업 종료. 영상 렌더링 모듈을 별도 실행하세요.[/bold yellow]")
            sys.exit(0)

    # ── Phase 5: Remotion 다이렉트 비디오 렌더링 ─────────────────────────────────
    console.print("\n[bold cyan]=== [MEDIA] Remotion Video Synthesis Start ===[/bold cyan]")
    run_step("Phase 5 | Remotion 비디오 다이렉트 생성 (대본 및 Neural TTS 자동 연동)", f'"{py}" src/remotion_orchestrator.py')

    console.print("\n[bold green][SUCCESS] 모든 파이프라인 완료![/bold green]")
    out_dir = get_output_dir()
    console.print(f"[FOLDER] 결과물 저장 폴더: {out_dir}")

if __name__ == "__main__":
    main()
