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

REMOTION_DIR = os.getenv("REMOTION_DIR", r"D:\04_Antigravity_wp\Remotion")

# ── 1. Gemini 기반 고품격 애널리스트 대본 자동 생성 ───────────────────────────
def generate_analyst_script(report_data: dict) -> dict:
    """리서치 레포트 데이터를 기반으로 Gemini 2.5 Flash를 사용하여 5개 씬의 전문 대본을 자동 생성합니다."""
    import google.generativeai as genai
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[Orchestrator] GEMINI_API_KEY가 존재하지 않습니다. 기본 폴백 대본을 사용합니다.")
        return get_fallback_script()
        
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
    
    prompt = f"""제공된 오늘의 리서치 보고서를 바탕으로, 미국 및 한국 주식 투자자들을 위한 5개 씬의 영상 브리핑 대본을 작성해 주세요.

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
1. 5개 씬의 대본을 작성합니다:
   - scene1: 주제 소개 및 투자자 관심 환기 (인트로)
   - scene2: 핵심 팩트 1 및 글로벌 트렌드 상세 배경
   - scene3: 핵심 쟁점 2 및 수익성/위험 요인 심층 분석
   - scene4: 한국 시장 및 관련 밸류체인(반도체, HBM 등)에 미치는 명암과 리스크
   - scene5: 투자자들을 위한 실질적인 대응 전략 및 최종 요약 (아웃트로)
2. 각 씬의 대본은 생략 없이 전문가가 조목조목 설명하듯 상세하게 작성해 주십시오. (각 씬당 한글 100~150자 내외로 상세하게)
3. 출력은 반드시 아래 JSON 스키마를 따르는 JSON 포맷이어야 합니다.

출력 JSON 스키마:
{{
  "scene1": "씬1 내레이션 텍스트",
  "scene2": "씬2 내레이션 텍스트",
  "scene3": "씬3 내레이션 텍스트",
  "scene4": "씬4 내레이션 텍스트",
  "scene5": "씬5 내레이션 텍스트"
}}"""

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
        return result
    except Exception as e:
        print(f"[Orchestrator] 대본 생성 API 오류: {e}. 폴백 대본을 사용합니다.")
        return get_fallback_script()

def get_fallback_script() -> dict:
    return {
        "scene1": "머니대디 시청자 여러분, 안녕하십니까? 미국과 한국 시장의 돈의 흐름을 빠르게 분석해 드리는 머니대디입니다.",
        "scene2": "첫 번째, 시장 지황입니다. 미국 증시는 국채 금리와 환율 변동 속에 변동성이 높은 상태를 유지하고 있습니다.",
        "scene3": "두 번째, 심화되는 수익화 의구심 속에서 다음 자산 상승을 이끌 주도주를 포착하는 것이 중요합니다.",
        "scene4": "세 번째, 한국 증시입니다. 반도체 소부장과 자동차 등 대표적 강세 섹터로의 수급 이동이 돋보입니다.",
        "scene5": "마지막으로 거시경제 리스크를 관리하며 현명한 자금 이동 경로를 추적하는 전략이 유효합니다."
    }

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

def update_remotion_sources(durations: dict):
    # DURATION_IN_FRAMES 계산
    total_frames = sum(durations.values())
    
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
    with open(constants_path, "w", encoding="utf-8") as f:
        f.write(constants_content)
    print(f"[Orchestrator] constants.ts 업데이트 완료 (총 프레임: {total_frames})")

    # 2. Main.tsx 업데이트
    main_tsx_path = os.path.join(REMOTION_DIR, "src", "remotion", "MyComp", "Main.tsx")
    
    sc1 = durations["scene1"]
    sc2 = durations["scene2"]
    sc3 = durations["scene3"]
    sc4 = durations["scene4"]
    sc5 = durations["scene5"]
    
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

// Scene 1: Intro
const SceneIntro = () => {{
  const frame = useCurrentFrame();
  const {{ fps, durationInFrames }} = useVideoConfig();
  const opacity = interpolate(frame, [0, 20, durationInFrames - 20, durationInFrames], [0, 1, 1, 0], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }});
  const scale = spring({{ frame, fps, config: {{ damping: 15 }} }});
  return (
    <AbsoluteFill className="flex flex-col justify-center items-center text-white bg-slate-950 p-12" style={{{{ opacity, fontFamily }}}}>
      <Audio src={{staticFile('scene1.mp3')}} volume={{1.0}} />
      <div className="absolute inset-0 bg-radial-[circle_at_center,_var(--color-indigo-950)_0%,_var(--color-slate-950)_80%]" />
      <div className="z-10 text-center max-w-4xl">
        <span className="inline-block px-4 py-2 mb-6 text-sm font-semibold text-cyan-400 bg-cyan-950/50 border border-cyan-800 rounded-full">글로벌 IT 트렌드 분석</span>
        <h1 className="text-5xl font-bold leading-tight mb-6 text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-sky-300 to-indigo-400" style={{{{ transform: `scale(${{scale}})` }}}}>AI 투자 사이클,<br />진짜 거품일까?</h1>
        <p className="text-xl text-slate-400 font-medium leading-relaxed">미국·한국 AI 관련 주식 투자자가 반드시 알아야 할 2026 핵심 쟁점 브리핑</p>
      </div>
    </AbsoluteFill>
  );
}};

// Scene 2: CapEx Surge
const SceneCapEx = () => {{
  const frame = useCurrentFrame();
  const {{ fps, durationInFrames }} = useVideoConfig();
  const opacity = interpolate(frame, [0, 20, durationInFrames - 20, durationInFrames], [0, 1, 1, 0], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }});
  const barProgress = spring({{ frame, fps, config: {{ damping: 12 }}, delay: 20 }});
  return (
    <AbsoluteFill className="flex flex-row text-white bg-slate-950 p-16 justify-between items-center" style={{{{ opacity, fontFamily }}}}>
      <Audio src={{staticFile('scene2.mp3')}} volume={{1.0}} />
      <div className="absolute inset-0 bg-radial-[circle_at_center,_var(--color-indigo-950)_0%,_var(--color-slate-950)_80%]" />
      <div className="z-10 w-[55%] pr-8">
        <span className="text-cyan-400 font-bold text-lg mb-2 block">01. 천문학적 설비 투자 (CapEx)</span>
        <h2 className="text-4xl font-bold mb-6 text-transparent bg-clip-text bg-gradient-to-r from-white to-slate-300">빅테크의 멈추지 않는 투자 질주</h2>
        <ul className="space-y-4 text-lg text-slate-300 leading-relaxed">
          <li className="flex items-start"><span className="text-cyan-400 mr-2">✔</span><span>5대 하이퍼스케일러의 2026년 합산 CapEx가 <b>$6,800억 달러</b>로 사상 최대치 돌파</span></li>
          <li className="flex items-start"><span className="text-cyan-400 mr-2">✔</span><span>단순 AI 칩셋 구매를 넘어 <b>데이터센터 건설, 초고속 네트워킹, 전력망 확보</b>로 투자 중심 이동</span></li>
        </ul>
      </div>
      <div className="z-10 w-[40%] h-[350px] bg-slate-900/60 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between">
        <div className="text-sm font-semibold text-slate-400">빅테크 연도별 CapEx 합산 추이 (십억 달러)</div>
        <div className="flex flex-row justify-around items-end h-[240px] pt-4">
          <div className="flex flex-col items-center w-1/3">
            <div className="w-12 bg-slate-700 rounded-t-lg transition-all" style={{{{ height: `${{120 * barProgress}}px` }}}} />
            <span className="text-xs text-slate-400 mt-2">2024 (실적)</span>
            <span className="font-bold text-slate-300 text-sm">$320B</span>
          </div>
          <div className="flex flex-col items-center w-1/3">
            <div className="w-12 bg-cyan-600 rounded-t-lg transition-all" style={{{{ height: `${{180 * barProgress}}px` }}}} />
            <span className="text-xs text-slate-400 mt-2">2025 (추정)</span>
            <span className="font-bold text-cyan-300 text-sm">$480B</span>
          </div>
          <div className="flex flex-col items-center w-1/3">
            <div className="w-12 bg-gradient-to-t from-cyan-400 to-indigo-500 rounded-t-lg transition-all shadow-[0_0_15px_rgba(34,211,238,0.3)]" style={{{{ height: `${{240 * barProgress}}px` }}}} />
            <span className="text-xs text-cyan-400 mt-2 font-semibold">2026 (전망)</span>
            <span className="font-bold text-cyan-400 text-sm animate-pulse">$680B</span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}};

// Scene 3: Revenue Gap
const SceneRevenueGap = () => {{
  const frame = useCurrentFrame();
  const {{ fps, durationInFrames }} = useVideoConfig();
  const opacity = interpolate(frame, [0, 20, durationInFrames - 20, durationInFrames], [0, 1, 1, 0], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }});
  const anim = spring({{ frame, fps, config: {{ damping: 15 }} }});
  return (
    <AbsoluteFill className="flex flex-row-reverse text-white bg-slate-950 p-16 justify-between items-center" style={{{{ opacity, fontFamily }}}}>
      <Audio src={{staticFile('scene3.mp3')}} volume={{1.0}} />
      <div className="absolute inset-0 bg-radial-[circle_at_center,_var(--color-indigo-950)_0%,_var(--color-slate-950)_80%]" />
      <div className="z-10 w-[55%] pl-8">
        <span className="text-rose-400 font-bold text-lg mb-2 block">02. 실질 수익화 의구심 (Revenue Gap)</span>
        <h2 className="text-4xl font-bold mb-6 text-transparent bg-clip-text bg-gradient-to-r from-white to-slate-300">투자금 대비 부족한 AI 매출액</h2>
        <ul className="space-y-4 text-lg text-slate-300 leading-relaxed">
          <li className="flex items-start"><span className="text-rose-400 mr-2">✘</span><span>인프라 비용 회수와 최소 마진 충족을 위해 연간 약 <b>$6,000억 달러</b>의 글로벌 AI 매출 필수</span></li>
          <li className="flex items-start"><span className="text-rose-400 mr-2">✘</span><span>현재 실질 기업용 AI 유료 매출은 <b>$1,000억 달러 미만</b>으로 <b>$5,000억 달러 규모의 거대 갭</b> 상존</span></li>
        </ul>
      </div>
      <div className="z-10 w-[40%] h-[350px] bg-slate-900/60 border border-slate-800 rounded-2xl p-6 flex flex-col justify-center items-center">
        <div className="text-center mb-6"><div className="text-sm font-semibold text-slate-400">투자 회수 요구액 vs 실제 연간 매출</div></div>
        <div className="relative w-full flex flex-col items-center justify-center space-y-4">
          <div className="w-64 bg-slate-800 text-center py-3 rounded-lg border border-slate-700 text-sm font-semibold relative overflow-hidden" style={{{{ transform: `scale(${{interpolate(anim, [0, 1], [0.8, 1])}})` }}}}>필요 매출: <span className="text-cyan-400 font-bold">$600B</span></div>
          <div className="h-10 w-0.5 bg-dashed bg-rose-500/60" />
          <div className="w-48 bg-rose-950/60 text-center py-3 rounded-lg border border-rose-800 text-sm font-semibold" style={{{{ transform: `scale(${{interpolate(anim, [0, 1], [0.8, 1])}})` }}}}>실제 매출: <span className="text-rose-400 font-bold">$100B 미만</span></div>
          <div className="absolute -right-4 top-1/2 -translate-y-1/2 bg-rose-500/20 text-rose-400 border border-rose-500/40 text-xs px-3 py-1.5 rounded-full font-bold animate-pulse" style={{{{ opacity: anim }}}}>GAP: $500B+ (수익 구멍)</div>
        </div>
      </div>
    </AbsoluteFill>
  );
}};

// Scene 4: Korean/US Stock Impact
const SceneStockImpact = () => {{
  const frame = useCurrentFrame();
  const {{ fps, durationInFrames }} = useVideoConfig();
  const opacity = interpolate(frame, [0, 20, durationInFrames - 20, durationInFrames], [0, 1, 1, 0], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }});
  const arrowMove = interpolate(frame, [0, 60], [-10, 0], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }});
  return (
    <AbsoluteFill className="flex flex-row text-white bg-slate-950 p-16 justify-between items-center" style={{{{ opacity, fontFamily }}}}>
      <Audio src={{staticFile('scene4.mp3')}} volume={{1.0}} />
      <div className="absolute inset-0 bg-radial-[circle_at_center,_var(--color-indigo-950)_0%,_var(--color-slate-950)_80%]" />
      <div className="z-10 w-[55%] pr-8">
        <span className="text-amber-400 font-bold text-lg mb-2 block">03. 미·한 반도체 밸류체인 영향</span>
        <h2 className="text-4xl font-bold mb-6 text-transparent bg-clip-text bg-gradient-to-r from-white to-slate-300">한국 HBM 반도체의 명과 암</h2>
        <ul className="space-y-4 text-lg text-slate-300 leading-relaxed">
          <li className="flex items-start"><span className="text-amber-400 mr-2">💡</span><span><b>단기 호황:</b> 빅테크의 투자 가속화는 SK하이닉스 및 삼성전자의 HBM 전례 없는 실적 호재</span></li>
          <li className="flex items-start"><span className="text-amber-400 mr-2">⚠</span><span><b>구조적 리스크:</b> 빅테크의 수익성 부진에 따른 CapEx 투자 속도 조절 시 수주 실적 및 주가 급락 위험</span></li>
        </ul>
      </div>
      <div className="z-10 w-[40%] h-[350px] bg-slate-900/60 border border-slate-800 rounded-2xl p-6 flex flex-col justify-around">
        <div className="flex items-center space-x-4 bg-slate-800/40 p-4 rounded-xl border border-slate-800">
          <div className="w-12 h-12 bg-cyan-500/20 rounded-full flex items-center justify-center text-cyan-400 font-bold text-lg">💡</div>
          <div>
            <div className="font-bold text-slate-200">빅테크 인프라 투자 지속</div>
            <div className="text-xs text-slate-400 mt-0.5">HBM 수요 긍정적 (SK하이닉스, 삼성전자)</div>
          </div>
        </div>
        <div className="flex justify-center" style={{{{ transform: `translateY(${{arrowMove}}px)` }}}}>
          <span className="text-3xl text-rose-500 font-bold">⬇</span>
        </div>
        <div className="flex items-center space-x-4 bg-rose-950/20 p-4 rounded-xl border border-rose-950">
          <div className="w-12 h-12 bg-rose-500/20 rounded-full flex items-center justify-center text-rose-400 font-bold text-lg">⚠</div>
          <div>
            <div className="font-bold text-slate-200">수익 모델 지연 시 투자 조절</div>
            <div className="text-xs text-slate-400 mt-0.5">반도체 수요 급감 및 주가 변동성 확대</div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}};

// Scene 5: Outro/Summary
const SceneOutro = () => {{
  const frame = useCurrentFrame();
  const {{ fps, durationInFrames }} = useVideoConfig();
  const opacity = interpolate(frame, [0, 20, durationInFrames - 20, durationInFrames], [0, 1, 1, 0], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }});
  const scale = spring({{ frame, fps, config: {{ damping: 15 }} }});
  return (
    <AbsoluteFill className="flex flex-col justify-center items-center text-white bg-slate-950 p-12" style={{{{ opacity, fontFamily }}}}>
      <Audio src={{staticFile('scene5.mp3')}} volume={{1.0}} />
      <div className="absolute inset-0 bg-radial-[circle_at_center,_var(--color-indigo-950)_0%,_var(--color-slate-950)_80%]" />
      <div className="z-10 text-center max-w-4xl">
        <h2 className="text-4xl font-bold mb-8 text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-cyan-400" style={{{{ transform: `scale(${{scale}})` }}}}>💡 AI 투자자를 위한 3대 생존 가이드</h2>
        <div className="grid grid-cols-3 gap-6 text-left">
          <div className="bg-slate-900/80 border border-slate-800 p-6 rounded-2xl">
            <div className="text-cyan-400 font-bold text-lg mb-2">1. 맹목적 낙관·공포 금물</div>
            <p className="text-sm text-slate-300 leading-relaxed">설비투자와 실제 비즈니스 모델 수익성을 철저히 이분법적으로 분리하여 추적하십시오.</p>
          </div>
          <div className="bg-slate-900/80 border border-slate-800 p-6 rounded-2xl">
            <div className="text-cyan-400 font-bold text-lg mb-2">2. 레버리지 축소</div>
            <p className="text-sm text-slate-300 leading-relaxed">단기 변동성이 극대화될 수 있으므로, 고배율 레버리지 주식 투자는 지양하는 것이 안전합니다.</p>
          </div>
          <div className="bg-slate-900/80 border border-slate-800 p-6 rounded-2xl">
            <div className="text-cyan-400 font-bold text-lg mb-2">3. 핵심 밸류체인 압축</div>
            <p className="text-sm text-slate-300 leading-relaxed">성장세가 실제 실적 숫자로 증명되는 HBM 핵심 리더 및 실무 상용화 AI 강소기업 위주로 압축하십시오.</p>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}};

export const Main = ({{ title }}: z.infer<typeof CompositionProps>) => {{
  return (
    <AbsoluteFill className="bg-slate-950">
      <Sequence durationInFrames={{{sc1}}} layout="none">
        <SceneIntro />
      </Sequence>
      <Sequence from={{{sc1}}} durationInFrames={{{sc2}}} layout="none">
        <SceneCapEx />
      </Sequence>
      <Sequence from={{{sc1 + sc2}}} durationInFrames={{{sc3}}} layout="none">
        <SceneRevenueGap />
      </Sequence>
      <Sequence from={{{sc1 + sc2 + sc3}}} durationInFrames={{{sc4}}} layout="none">
        <SceneStockImpact />
      </Sequence>
      <Sequence from={{{sc1 + sc2 + sc3 + sc4}}} durationInFrames={{{sc5}}} layout="none">
        <SceneOutro />
      </Sequence>
    </AbsoluteFill>
  );
}};
"""
    with open(main_tsx_path, "w", encoding="utf-8") as f:
        f.write(main_content)
    print(f"[Orchestrator] Main.tsx 업데이트 완료 (각 프레임 매핑 완료)")

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
