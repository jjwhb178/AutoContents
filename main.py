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
            console.print(f"[bold green]✓[/bold green] {step_name} ({elapsed}s)")
            return True
        except subprocess.CalledProcessError as e:
            elapsed = round(time.time() - t0, 1)
            label = "[bold yellow]⚠ SKIP[/bold yellow]" if optional else "[bold red]✗ FAIL[/bold red]"
            console.print(f"{label} {step_name} ({elapsed}s)")
            console.print(f"[dim]{e.stderr[-300:]}[/dim]")
            return optional

def print_dashboard_preview():
    logic_path = "data/latest_content_logic.json"
    if not os.path.exists(logic_path):
        return
    with open(logic_path, "r", encoding="utf-8") as f:
        logic = json.load(f)

    console.print("\n[bold cyan]=== 🔍 Content Orchestration Preview ===[/bold cyan]")
    console.print(f"[bold]Title:[/bold] {logic.get('title')}")
    console.print(f"[bold]Theme:[/bold] {logic.get('theme_analysis')}")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Page", style="dim", width=4)
    table.add_column("Visual Text (Slide)", width=30)
    table.add_column("Audio Script (TTS)", width=50)

    script = logic.get("ppt_script", {})
    for i in range(1, 19):
        p = script.get(str(i), {})
        if p:
            v_text = str(p.get("visual_text", "")).replace('\n', ' ')
            a_text = str(p.get("audio_script", ""))
            table.add_row(str(i), v_text[:40] + ("..." if len(v_text)>40 else ""), a_text[:60] + ("..." if len(a_text)>60 else ""))
            
    console.print(table)
    console.print("[dim]※ 이미지 및 썸네일 프롬프트가 동기화되어 준비 완료되었습니다.[/dim]")

def get_proposals():
    console.print("[bold yellow]뉴스 분석 및 주제 후보 도출 중...[/bold yellow]")
    import src.market_data_collector as mdc
    import src.content_generator as cg
    mdc.main() # Phase 1 실행
    
    with open("data/raw_market_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    proposals = cg.propose_topics(data)
    if not proposals:
        console.print("[red]주제 제안에 실패했습니다. 기본 설정으로 진행합니다.[/red]")
        return data, "오늘의 핵심 경제 이슈 분석"

    console.print(Panel("\n".join([f"[bold]{p['id']}. {p['type']} - {p['title']}[/bold]\n  └ {p['reason']}" for p in proposals]), title="오늘의 기획 제안 (Proposals)"))
    
    choice = Prompt.ask("주제 번호를 선택하거나, [bold cyan]직접 주제를 입력[/bold cyan]하세요 (예: 1, 2, 3, 혹은 '환율 폭등과 내 계좌 방어법')", default="1")
    
    selected_topic = ""
    if choice in ["1", "2", "3"]:
        selected_topic = proposals[int(choice)-1]["title"]
    else:
        selected_topic = choice
        
    console.print(f"\n[bold green]✅ 확정된 주제:[/bold green] {selected_topic}\n")
    return data, selected_topic

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="Skip interactive confirmation")
    args = parser.parse_args()

    console.print(Panel.fit("[bold blue]MoneyDaddy AI Content Factory Ver 12.0[/bold blue]\n[dim]Interactive Workflow & Perfect Sync Architecture[/dim]"))
    
    py = sys.executable

    # Phase 1 & 2a: Interactive Planning
    if not args.auto:
        data, selected_topic = get_proposals()
    else:
        run_step("Phase 1 | 데이터 수집", f'"{py}" src/market_data_collector.py')
        with open("data/raw_market_data.json", "r", encoding="utf-8") as f: data = json.load(f)
        selected_topic = "오늘의 핵심 경제 이슈와 시스템적 결함 분석"

    # Phase 2b: Content Orchestration
    with console.status("[bold magenta]기획 생성 및 디자인 동기화 중 (Agent 1 & 2)...[/bold magenta]", spinner="dots"):
        import src.content_generator as cg
        cg.run_content_generation(data, selected_topic)
    console.print("[bold green]✓[/bold green] Phase 2b | 기획/대본 생성 완료")

    # Phase 2c: Confirm Gate
    if not args.auto:
        print_dashboard_preview()
        if not Confirm.ask("\n[bold red]▶ 영상 및 PPT 합성을 진행하시겠습니까? (시간이 소요됩니다)[/bold red]"):
            console.print("[bold yellow]작업이 일시 정지되었습니다. 텍스트 초안을 수정 후 다시 실행하세요.[/bold yellow]")
            sys.exit(0)

    # Phase 3-6: Media Synthesis
    console.print("\n[bold cyan]=== 🎬 Media Synthesis Start ===[/bold cyan]")
    run_step("Phase 3a | 데이터 시각화 차트 렌더링", f'"{py}" src/visual_generator.py')
    run_step("Phase 3b | PPT 레이아웃 엔진 (차트 및 Visual Text 적용)", f'"{py}" src/pptx_generator.py')
    run_step("Phase 4  | 저음 보이스 TTS 합성", f'"{py}" src/tts_generator.py')
    run_step("Phase 5  | 하이브리드 썸네일 합성", f'"{py}" src/thumbnail_generator.py')
    run_step("Phase 6  | 고해상도 영상 합성 (MP4)", f'"{py}" src/video_synthesizer.py')

    console.print("\n[bold green]🎉 모든 파이프라인이 성공적으로 완료되었습니다![/bold green]")
    out_dir = get_output_dir()
    console.print(f"📁 결과물 폴더: [link file://{out_dir}]{out_dir}[/link]")

if __name__ == "__main__":
    main()
