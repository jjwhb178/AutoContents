# -*- coding: utf-8 -*-
import os
import sys
import json
import re
import asyncio
import subprocess
import shutil
from datetime import datetime

# 윈도우 ProactorEventLoop 호환성 보정
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.dirname(__file__))
from output_paths import get_path, get_output_dir, get_dated_path

from dotenv import load_dotenv
load_dotenv()

raw_dir = os.getenv("REMOTION_DIR")
if raw_dir and raw_dir.strip():
    REMOTION_DIR = raw_dir.strip()
else:
    REMOTION_DIR = r"D:\04_Antigravity_wp\Remotion"

if not os.path.isdir(REMOTION_DIR):
    print(f"[Orchestrator] Warning: REMOTION_DIR ({REMOTION_DIR}) 경로가 올바른 디렉토리가 아닙니다.")

# ── 1. Gemini 기반 고품격 애널리스트 대본 자동 생성 ───────────────────────────
def generate_analyst_script(report_data: dict) -> dict:
    """리서치 레포트 데이터를 기반으로 Gemini 2.5 Flash를 사용하여 동적 N개 씬의 전문 대본을 자동 생성합니다."""
    import google.generativeai as genai
    
    logic_path = "data/latest_content_logic.json"
    video_structure = []
    if os.path.exists(logic_path):
        try:
            with open(logic_path, "r", encoding="utf-8") as f:
                logic_data = json.load(f)
                video_structure = logic_data.get("video_structure", [])
        except Exception as e:
            print(f"[Orchestrator] 대본 생성용 latest_content_logic.json 로드 에러: {e}")

    if not video_structure or not isinstance(video_structure, list):
        video_structure = [
            {"scene": 1, "title": "주제 소개 및 투자자 관심 환기 (인트로)", "core_logic": "리서치 레포트 기반 인트로 및 주제 환기"},
            {"scene": 2, "title": "핵심 팩트 1 및 글로벌 트렌드 상세 배경", "core_logic": "보고서의 주요 팩트 분석 및 배경 설명"},
            {"scene": 3, "title": "핵심 쟁점 2 및 수익성/위험 요인 심층 분석", "core_logic": "보고서의 핵심 쟁점 및 위험 요인 심층 설명"},
            {"scene": 4, "title": "한국 시장 및 관련 밸류체인(반도체, HBM 등)에 미치는 명암과 리스크", "core_logic": "국내 시장의 영향 및 반도체 밸류체인 분석"},
            {"scene": 5, "title": "투자자들을 위한 실질적인 대응 전략 및 최종 요약 (아웃트로)", "core_logic": "머니대디 관점에서의 핵심 투자 전략 요약"}
        ]
        
    N = len(video_structure)
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[Orchestrator] GEMINI_API_KEY가 존재하지 않습니다. 기본 폴백 대본을 사용합니다.")
        return get_fallback_script(video_structure)
        
    genai.configure(api_key=api_key)
    
    # 머니대디의 수석 리서치 애널리스트 및 앵커 페르소나와 음성 합성용 정제 필터 규칙을 System Instruction으로 정의
    system_instruction = (
        "당신은 자금 흐름과 거시경제적 관점에서 시장을 날카롭게 해설하는 채널 '머니대디'의 수석 리서치 애널리스트이자 앵커입니다.\n"
        "다음 음성 합성 및 톤 규칙을 반드시 준수하여 영상 브리핑 대본을 작성해 주세요:\n"
        "1. 톤앤매너: 금융 전문가가 친근하면서도 매우 정교하고 전문성 있게 설명하는 구어체 톤이어야 합니다.\n"
        "2. 음성 합성용 정제 필터 규칙: 숫자는 발음하기 좋게 한글로 적고(예: '2026년' -> '이천이십육년', '6,800억 달러' -> '육천팔백억 달러', 'HBM' -> '에이치비엠'), "
        "본문 내 괄호 ( ) 및 기호를 배제하여 말로 자연스럽게 풀어 서술합니다."
    )
    
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
        system_instruction=system_instruction
    )
    
    # 씬 정보를 프롬프트에 담기 위해 문자열로 빌드
    scenes_desc = ""
    json_schema_dict = {}
    for i, s in enumerate(video_structure, start=1):
        title = s.get("title", f"씬 {i}")
        core_logic = s.get("core_logic", "")
        scenes_desc += f"- scene{i}: 제목: {title} / 핵심 논리: {core_logic}\n"
        json_schema_dict[f"scene{i}"] = f"씬{i} 내레이션 텍스트"
        
    json_schema_str = json.dumps(json_schema_dict, ensure_ascii=False, indent=2)
    
    prompt = f"""제공된 오늘의 리서치 보고서를 바탕으로, 미국 및 한국 주식 투자자들을 위한 {N}개 씬의 영상 브리핑 대본을 작성해 주세요.

[오늘의 주제]
{report_data.get("topic", "오늘의 핵심 경제 이슈 분석")}

[핵심 서사]
{report_data.get("today_narrative", "")}

[이론적 배경]
{report_data.get("economic_background", "")}

[리스크 요인]
{report_data.get("risk_factors", [])}

[투자 전문가 견해]
{report_data.get("moneydaddy_view", "")}

[뉴스 추출 핵심 팩트]
{report_data.get("hard_facts", [])}

[작성 규칙]
1. {N}개 씬의 대본을 작성합니다:
{scenes_desc}
2. 각 씬의 대본은 생략 없이 전문가가 조목조목 설명하듯 상세하게 작성해 주십시오. (각 씬당 한글 100~150자 내외로 상세하게)
3. 출력은 반드시 아래 JSON 스키마를 따르는 JSON 포맷이어야 합니다.

출력 JSON 스키마:
{json_schema_str}"""

    try:
        res = model.generate_content(prompt)
        raw = res.text.strip()
        # JSON 클리닝
        clean_json = re.sub(r'```json\s*(.*?)\s*```', r'\1', raw, flags=re.DOTALL).strip()
        start = clean_json.find('{')
        end = clean_json.rfind('}')
        if start != -1 and end != -1:
            clean_json = clean_json[start:end+1]
        
        result = json.loads(clean_json)
        # 생성된 대본의 키 검증 및 타입 안전성 보완
        fallback_data = get_fallback_script(video_structure)
        for i in range(1, N + 1):
            key = f"scene{i}"
            if key not in result or not result[key] or not str(result[key]).strip():
                print(f"[Orchestrator] Warning: 생성 대본에 {key}가 누락되었거나 비어 있어 폴백 문구를 적용합니다.")
                result[key] = fallback_data[key]
            else:
                result[key] = str(result[key]).strip()
        return result
    except Exception as e:
        print(f"[Orchestrator] 대본 생성 API 오류: {e}. 폴백 대본을 사용합니다.")
        return get_fallback_script(video_structure)

def get_fallback_script(video_structure: list = None) -> dict:
    """가변 씬 수에 맞춰 폴백 대본 딕셔너리를 리턴합니다."""
    if not video_structure:
        video_structure = [
            {"scene": 1, "title": "주제 소개 및 투자자 관심 환기 (인트로)", "core_logic": "리서치 레포트 기반 인트로 및 주제 환기"},
            {"scene": 2, "title": "핵심 팩트 1 및 글로벌 트렌드 상세 배경", "core_logic": "보고서의 주요 팩트 분석 및 배경 설명"},
            {"scene": 3, "title": "핵심 쟁점 2 및 수익성/위험 요인 심층 분석", "core_logic": "보고서의 핵심 쟁점 및 위험 요인 심층 설명"},
            {"scene": 4, "title": "한국 시장 및 관련 밸류체인(반도체, HBM 등)에 미치는 명암과 리스크", "core_logic": "국내 시장의 영향 및 반도체 밸류체인 분석"},
            {"scene": 5, "title": "투자자들을 위한 실질적인 대응 전략 및 최종 요약 (아웃트로)", "core_logic": "머니대디 관점에서의 핵심 투자 전략 요약"}
        ]
    fallback = {}
    for i, s in enumerate(video_structure, start=1):
        title = s.get("title", f"씬 {i}")
        core_logic = s.get("core_logic", "")
        if i == 1:
            fallback[f"scene{i}"] = f"머니대디 브리핑을 시작합니다. 오늘 설명드릴 첫 번째 주제는 {title}입니다. {core_logic}"
        elif i == len(video_structure):
            fallback[f"scene{i}"] = f"마지막으로 요약해 드리겠습니다. {title}과 관련하여, {core_logic} 관점으로 시장에 대응하시기 바랍니다."
        else:
            fallback[f"scene{i}"] = f"다음으로 {title}에 대해 알아보겠습니다. {core_logic}"
    return fallback

async def generate_tts_with_retry(name: str, text: str, final_path: str, voice: str, rate: str, retries: int = 3) -> bool:
    import edge_tts
    import asyncio
    for i in range(retries):
        try:
            print(f"  [TTS] {name} 생성 중... (시도 {i+1}/{retries})")
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(final_path)
            if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                return True
        except Exception as e:
            print(f"  [TTS Error] {name} 실패: {e}")
            await asyncio.sleep(1)
    return False

def get_audio_duration(ffmpeg_bin: str, file_path: str) -> float:
    import subprocess
    import re
    try:
        cmd = [ffmpeg_bin, "-i", file_path]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
        output = res.stderr
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", output)
        if match:
            h, m, s = match.groups()
            return float(h) * 3600 + float(m) * 60 + float(s)
    except Exception as e:
        print(f"  [Duration Error] {e}")
    return 5.0

def escape_js(text: str) -> str:
    """JS/TSX 구문 에러를 예방하기 위해 백슬래시와 큰따옴표 등을 이스케이프 처리합니다."""
    if not text:
        return ""
    # 백슬래시와 큰따옴표 이스케이프
    text = text.replace('\\', '\\\\')
    text = text.replace('"', '\\"')
    text = text.replace('\n', ' ')
    return text

def update_remotion_sources(durations: dict):
    # DURATION_IN_FRAMES 계산
    # 0. latest_content_logic.json 로드하여 N 및 video_structure 파악
    logic_path = "data/latest_content_logic.json"
    video_structure = []
    if os.path.exists(logic_path):
        try:
            with open(logic_path, "r", encoding="utf-8") as f:
                logic_data = json.load(f)
                video_structure = logic_data.get("video_structure", [])
        except Exception as e:
            print(f"[Orchestrator] update_remotion_sources에서 {logic_path} 로드 중 에러: {e}")

    # video_structure가 비어있거나 올바른 리스트가 아니면 기본 5개 씬 정의
    if not video_structure or not isinstance(video_structure, list):
        video_structure = [
            {"scene": 1, "title": "주제 소개 및 투자자 관심 환기 (인트로)", "core_logic": "리서치 레포트 기반 인트로 및 주제 환기"},
            {"scene": 2, "title": "핵심 팩트 1 및 글로벌 트렌드 상세 배경", "core_logic": "보고서의 주요 팩트 분석 및 배경 설명"},
            {"scene": 3, "title": "핵심 쟁점 2 및 수익성/위험 요인 심층 분석", "core_logic": "보고서의 핵심 쟁점 및 위험 요인 심층 설명"},
            {"scene": 4, "title": "한국 시장 및 관련 밸류체인(반도체, HBM 등)에 미치는 명암과 리스크", "core_logic": "국내 시장의 영향 및 반도체 밸류체인 분석"},
            {"scene": 5, "title": "투자자들을 위한 실질적인 대응 전략 및 최종 요약 (아웃트로)", "core_logic": "머니대디 관점에서의 핵심 투자 전략 요약"}
        ]
        
    N = len(video_structure)
    scene_frames = []
    for i in range(1, N + 1):
        key = f"scene{i}"
        frames = durations.get(key, 150) # 폴백 150프레임 (5초)
        scene_frames.append(frames)
    
    total_frames = sum(scene_frames)
    
    # 1. constants.ts 업데이트
    constants_path = os.path.join(REMOTION_DIR, "types", "constants.ts")
    constants_content = f"""import {{ z }} from "zod";
export const COMP_NAME = "MyComp";

export const CompositionProps = z.object({{
  title: z.string(),
}});

export const defaultMyCompProps: z.infer<typeof CompositionProps> = {{
  title: "Next.js and Remotion",
}};

export const DURATION_IN_FRAMES = {total_frames};
export const VIDEO_WIDTH = 1280;
export const VIDEO_HEIGHT = 720;
export const VIDEO_FPS = 30;
"""
    # 디렉토리 존재 보장
    os.makedirs(os.path.dirname(constants_path), exist_ok=True)
    with open(constants_path, "w", encoding="utf-8") as f:
        f.write(constants_content)
    print(f"[Orchestrator] constants.ts 업데이트 완료 (총 프레임: {total_frames})")

    # 2. Main.tsx 업데이트
    main_tsx_path = os.path.join(REMOTION_DIR, "src", "remotion", "MyComp", "Main.tsx")
    os.makedirs(os.path.dirname(main_tsx_path), exist_ok=True)
    
    # Scene 컴포넌트 소스코드 동적 생성
    scene_components = []
    for i, s in enumerate(video_structure, start=1):
        title = s.get("title", f"씬 {i}")
        title = str(title) if title is not None else f"씬 {i}"
        title_escaped = escape_js(title)
        
        caption_layout = s.get("caption_layout", title)
        caption_layout = str(caption_layout) if caption_layout is not None else title
        caption_parts = [p.strip() for p in caption_layout.split('/')]
        caption_jsx = " <br /> ".join([f'{{"{escape_js(p)}"}}' for p in caption_parts])
        
        visual_asset = s.get("visual_asset", "none")
        has_visual = False
        if visual_asset and visual_asset != "none":
            if isinstance(visual_asset, dict):
                if visual_asset.get("type", "none") != "none":
                    has_visual = True
            else:
                has_visual = True
        
        image_file = f"슬라이드_시각자료_{i}.png"
        image_path = os.path.join(REMOTION_DIR, "public", image_file)
        
        use_image = has_visual and os.path.exists(image_path)
        
        # 씬 컴포넌트 템플릿
        if use_image:
            comp_src = f"""// Scene {i}: {title_escaped} (이미지 포함)
const Scene{i} = () => {{
  const frame = useCurrentFrame();
  const {{ fps, durationInFrames }} = useVideoConfig();
  const opacity = interpolate(frame, [0, 20, durationInFrames - 20, durationInFrames], [0, 1, 1, 0], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }});
  const scale = spring({{ frame, fps, config: {{ damping: 15 }} }});
  
  return (
    <AbsoluteFill className="flex flex-col justify-center items-center text-white bg-slate-950 p-12" style={{{{ opacity, fontFamily }}}}>
      <Audio src={{staticFile('scene{i}.mp3')}} volume={{1.0}} />
      <div className="absolute inset-0 bg-radial-[circle_at_center,_var(--color-indigo-950)_0%,_var(--color-slate-950)_80%]" />
      
      <div className="z-10 flex flex-row items-center justify-between w-full max-w-5xl gap-8">
        <div className="flex flex-col w-[50%] text-left">
          <span className="inline-block px-4 py-2 mb-6 text-sm font-semibold text-cyan-400 bg-cyan-950/50 border border-cyan-800 rounded-full w-fit">
            씬 {i}: {{"{title_escaped}"}}
          </span>
          <h1 className="text-4xl font-bold leading-tight mb-6 text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-sky-300 to-indigo-400">
            {caption_jsx}
          </h1>
        </div>
        <div className="w-[50%] flex justify-center items-center">
          <div className="relative border border-slate-800 rounded-2xl overflow-hidden bg-slate-900/60 p-4 shadow-[0_0_20px_rgba(0,0,0,0.5)]">
            <img 
              src={{staticFile('슬라이드_시각자료_{i}.png')}} 
              alt="시각 자료"
              style={{{{
                maxWidth: '100%',
                maxHeight: '400px',
                objectFit: 'contain',
                borderRadius: '12px',
                transform: `scale(${{scale}})`
              }}}}
            />
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}};
"""
        else:
            comp_src = f"""// Scene {i}: {title_escaped} (텍스트 전용)
const Scene{i} = () => {{
  const frame = useCurrentFrame();
  const {{ fps, durationInFrames }} = useVideoConfig();
  const opacity = interpolate(frame, [0, 20, durationInFrames - 20, durationInFrames], [0, 1, 1, 0], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }});
  const scale = spring({{ frame, fps, config: {{ damping: 15 }} }});
  
  return (
    <AbsoluteFill className="flex flex-col justify-center items-center text-white bg-slate-950 p-12" style={{{{ opacity, fontFamily }}}}>
      <Audio src={{staticFile('scene{i}.mp3')}} volume={{1.0}} />
      <div className="absolute inset-0 bg-radial-[circle_at_center,_var(--color-indigo-950)_0%,_var(--color-slate-950)_80%]" />
      
      <div className="z-10 text-center max-w-4xl">
        <span className="inline-block px-4 py-2 mb-6 text-sm font-semibold text-cyan-400 bg-cyan-950/50 border border-cyan-800 rounded-full">
          씬 {i}: {{"{title_escaped}"}}
        </span>
        <h1 className="text-5xl font-bold leading-tight mb-6 text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-sky-300 to-indigo-400" style={{{{ transform: `scale(${{scale}})` }}}}>
          {caption_jsx}
        </h1>
      </div>
    </AbsoluteFill>
  );
}};
"""
        scene_components.append(comp_src)
        
    scene_components_code = "\n".join(scene_components)
    
    # Sequence JSX 블록 생성
    sequence_blocks = []
    cumulative = 0
    for i in range(1, N + 1):
        frames = scene_frames[i - 1]
        if i == 1:
            block = f"""      <Sequence durationInFrames={{{frames}}} layout="none">
        <Scene{i} />
      </Sequence>"""
        else:
            block = f"""      <Sequence from={{{cumulative}}} durationInFrames={{{frames}}} layout="none">
        <Scene{i} />
      </Sequence>"""
        cumulative += frames
        sequence_blocks.append(block)
    
    sequences_jsx = "\n".join(sequence_blocks)
    
    main_content = f"""import {{ fontFamily, loadFont }} from "@remotion/google-fonts/NotoSansKR";
import {{
  AbsoluteFill,
  Sequence,
  spring,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Audio,
  staticFile,
}} from "remotion";
import {{ z }} from "zod";
import {{ CompositionProps }} from "../../../types/constants";

loadFont("normal", {{
  subsets: ["korean"],
  weights: ["400", "700"],
}});

{scene_components_code}

export const Main = ({{ title }}: z.infer<typeof CompositionProps>) => {{
  return (
    <AbsoluteFill className="bg-slate-950">
{sequences_jsx}
    </AbsoluteFill>
  );
}};
"""

    with open(main_tsx_path, "w", encoding="utf-8") as f:
        f.write(main_content)
    print(f"[Orchestrator] Main.tsx 업데이트 완료 (총 {N}개 씬 동적 매핑 완료)")

# ── 4. 메인 파이프라인 연동 ───────────────────────────────────────────────────
def run_remotion_pipeline() -> bool:
    print("[Orchestrator] Remotion 파이프라인 작동 시작...")
    
    # 1. 리서치 리포트 로드
    report_path = "data/research_report.json"
    if not os.path.exists(report_path):
        print(f"[Orchestrator] 에러: {report_path} 파일이 존재하지 않습니다.")
        return False
        
    with open(report_path, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    # 2. 고품격 애널리스트 대본 생성
    print("[Orchestrator] 최신 팩트 기반 전문가 대본 생성 중...")
    script_data = generate_analyst_script(report_data)
    
    # 생성된 대본을 latest_content_logic.json에 백업
    logic_path = "data/latest_content_logic.json"
    if os.path.exists(logic_path):
        with open(logic_path, "r", encoding="utf-8") as f:
            logic = json.load(f)
    else:
        logic = {}
    
    logic["video_script"] = script_data
    with open(logic_path, "w", encoding="utf-8") as f:
        json.dump(logic, f, ensure_ascii=False, indent=4)

    # 3. Neural TTS 생성 (edge-tts)
    voice = "ko-KR-InJoonNeural"
    rate = "+15%"
    fps = 30
    durations = {}
    
    # imageio-ffmpeg에서 ffmpeg 바이너리 확보
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        ffmpeg_bin = get_ffmpeg_exe()
    except Exception:
        ffmpeg_bin = "ffmpeg"

    public_dir = os.path.join(REMOTION_DIR, "public")
    os.makedirs(public_dir, exist_ok=True)

    print("[Orchestrator] Neural TTS 음성 연동 중...")
    
    # 비동기 실행 루프
    async def make_tts():
        for name, text in script_data.items():
            final_path = os.path.join(public_dir, f"{name}.mp3")
            success = await generate_tts_with_retry(name, text, final_path, voice, rate)
            if not success:
                raise RuntimeError(f"오디오 {name} 생성 최종 실패")
            
            # 길이 측정
            duration_sec = get_audio_duration(ffmpeg_bin, final_path)
            durations[name] = int(duration_sec * fps) + 15  # 여유 오프셋 추가

    asyncio.run(make_tts())
    print("[Orchestrator] 모든 Neural TTS 음성 렌더링 완료.")

    # 4. Remotion 소스 파일 동적 빌드
    update_remotion_sources(durations)

    # 5. Remotion Render 실행
    print("[Orchestrator] Remotion Studio Render 프로세스 시작...")
    output_mp4 = os.path.join(public_dir, "ai_investment_guide.mp4")
    
    cmd = ["npx", "remotion", "render", "MyComp", "public/ai_investment_guide.mp4"]
    try:
        process = subprocess.Popen(
            cmd,
            cwd=REMOTION_DIR,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                sys.stdout.write(line)
                sys.stdout.flush()
        rc = process.wait()
        if rc != 0:
            raise subprocess.CalledProcessError(rc, cmd)
        print("[Orchestrator] Remotion MP4 비디오 렌더링 완료!")
    except subprocess.CalledProcessError as e:
        print(f"[Orchestrator] 렌더링 중 에러 발생: {e}")
        return False

    # 6. outputs 디렉토리에 복사
    out_dir = get_output_dir()
    os.makedirs(out_dir, exist_ok=True)
    
    # 날짜와 키워드가 적용된 저장파일명
    final_dest = get_dated_path("최종영상", "mp4")
    
    # GUI나 CLI에서 바로 확인하도록 고정 파일명으로도 복사
    standard_dest = os.path.join(out_dir, "daily_strategy_pro_final.mp4")
    
    try:
        shutil.copy2(output_mp4, final_dest)
        shutil.copy2(output_mp4, standard_dest)
        print(f"[Orchestrator] 최종 영상 파일이 outputs 폴더에 복사되었습니다: {final_dest}")
        return True
    except Exception as e:
        print(f"[Orchestrator] 파일 복사 중 에러: {e}")
        return False

if __name__ == "__main__":
    run_remotion_pipeline()
