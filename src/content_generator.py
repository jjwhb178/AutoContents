import sys, os, json, time
from datetime import datetime
import google.generativeai as genai

# Windows CP949 환경에서 이모지 등 유니코드 출력 시 UnicodeEncodeError 방지
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(__file__))
from output_paths import get_path, get_dated_path
from text_cleaner import clean_for_blog
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ── Metrics ───────────────────────────────────────────────────────────────────
def detect_sector_pivot(data: dict) -> dict | None:
    surges = data.get("sector_volume_surge", [])
    if surges and len(surges) > 0:
        return surges[0]
    return None

# ── 의미 유지 압축 (글자 초과 시 Flash 재압축) ──────────────────────────────────
def compress_to_fit(text: str, max_chars: int, context: str = "") -> str:
    """글자 수 초과 시 Gemini Flash로 의미 유지 압축 (2회 시도 후 단어 단위 fallback)"""
    if not text or len(text) <= max_chars:
        return text
    if not GEMINI_API_KEY:
        return text[:max_chars]

    flash = genai.GenerativeModel("gemini-2.5-flash")
    prompt = (
        f"아래 텍스트를 {max_chars}자 이내로 압축하라.\n"
        "[필수 유지] 핵심 수치, 방향성(상승/하락/급등/급락), 핵심 키워드\n"
        "[금지] 의미 반전, 수치 변경, 새로운 정보 추가\n"
        "[출력] 압축된 텍스트만 출력 (설명·부연 없이)\n"
        f"[원문] {text}"
    )
    for attempt in range(2):
        try:
            res = flash.generate_content(prompt)
            compressed = res.text.strip()
            if len(compressed) <= max_chars:
                return compressed
        except Exception:
            break
    # fallback: 단어 단위 절단
    truncated = text[:max_chars]
    last_space = truncated.rfind(' ')
    return (truncated[:last_space] if last_space > max_chars * 0.6 else truncated) + "…"


# ── API Helper with Retry ───────────────────────────────────────────────────
def call_gemini_with_retry(model, prompt, retries=3, delay=2, is_json=True):
    """Gemini API 호출 및 JSON 자동 클리닝/파싱 래퍼"""
    import re
    current_model = model
    
    for i in range(retries):
        try:
            res = current_model.generate_content(prompt)
            if not res or not res.text:
                raise ValueError("Gemini로부터 빈 응답을 받았습니다.")
            
            text = res.text.strip()
            
            if not is_json:
                return text # 텍스트 모드인 경우 그대로 반환
            
            # JSON 추출 및 클리닝
            # 1. 마크다운 블록 제거
            clean_json = re.sub(r'```json\s*(.*?)\s*```', r'\1', text, flags=re.DOTALL).strip()
            # 2. 텍스트 내에서 첫 { 와 마지막 } 사이만 추출
            start = clean_json.find('{')
            end = clean_json.rfind('}')
            if start != -1 and end != -1:
                clean_json = clean_json[start:end+1]
            
            # 3. 흔한 JSON 문법 오류 보정 (trailing commas)
            clean_json = re.sub(r',\s*}', '}', clean_json)
            clean_json = re.sub(r',\s*]', ']', clean_json)
            
            return json.loads(clean_json)
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Quota" in error_msg:
                print(f"  [Quota Alert] 모델 전환 중... (Attempt {i+1}/{retries})")
                current_model = genai.GenerativeModel("gemini-1.5-flash")
                continue
                
            if i < retries - 1:
                print(f"  [API/JSON Error] {e}. {delay}초 후 재시도... ({i+1}/{retries})")
                time.sleep(delay)
                delay *= 2
            else:
                print(f"  [Critical Error] Failed after {retries} retries: {e}")
                raise e

# ── Guide Loader ────────────────────────────────────────────────────────────
def load_guides():
    guides = {}
    target_dir = "Target"
    try:
        if os.path.exists(target_dir):
            for f in os.listdir(target_dir):
                if f.endswith(".md"):
                    with open(os.path.join(target_dir, f), "r", encoding="utf-8") as file:
                        guides[f] = file.read()
    except Exception as e:
        print(f"  [Guide Error] Failed to load Target guides: {e}")
    return guides

# ── 1. 제안 로직 (Multi-Proposal) ──────────────────────────────────────────
def propose_topics(data: dict, keyword: str = None) -> list:
    """뉴스를 분석하여 3개의 주제 후보를 제안합니다. 사용자가 입력한 수동 키워드가 있으면 이를 최우선으로 반영합니다."""
    model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
    news = data.get("market_news", [])
    import datetime
    today_str = datetime.datetime.now().strftime("%Y년 %m월 %d일")
    
    keyword_instruction = ""
    if keyword:
        keyword_instruction = f"\n[최우선 반영 요구사항]\n사용자가 입력한 관심 키워드(종목/섹터/이슈)는 **'{keyword}'**입니다. 실시간 뉴스 데이터와 더불어 이 키워드 관련 내용을 최우선적으로 다루는 주제 3가지를 제안해 주세요. 키워드의 의도를 파악하여 거시/심리/수급의 맥락에 맞춰 주제를 도출하십시오."

    prompt = f"""당신은 머니대디의 수석 비서입니다. 
오늘은 {today_str}입니다. 아래 실시간 뉴스 속보를 분석하여, 오늘 **미국 증시와 한국 증시에 가장 큰 영향을 미칠 핵심 뉴스 이슈** 3가지를 도출하세요.{keyword_instruction}

실시간 뉴스 속보: {news}

[절대 지침]
1. 단순 지표(환율 1400원, 금리, VIX) 자체를 주제로 삼지 마십시오. 수치는 보조 지표일 뿐입니다.
2. 위 뉴스에서 언급된 **'특정 기업의 실적 쇼크/서프라이즈', '정부 정책', '글로벌 지정학적 이슈', '특정 섹터의 흥망'** 등 실질적인 '사건(Event)'을 주제로 잡으세요.
3. 조건: 1. 거시경제/산업 분석 중심, 2. 시장 심리(공포/탐욕) 자극 중심, 3. 특정 섹터 수급 이동(반전) 중심으로 제안하세요.

출력 JSON 스키마:
{{
  "proposals": [
    {{ "id": 1, "type": "산업/거시", "title": "...", "reason": "이 뉴스가 미/한 증시에 미치는 영향" }},
    {{ "id": 2, "type": "시장심리", "title": "...", "reason": "..." }},
    {{ "id": 3, "type": "섹터수급", "title": "...", "reason": "..." }}
  ]
}}"""
    try:
        proposals = call_gemini_with_retry(model, prompt)
        return proposals.get("proposals", [])
    except Exception as e:
        print(f"  [Proposal Error] Topic Proposal failed: {e}")
        return []

# ── 2. 기획 생성 로직 (High-Density Assets) ──────────────────────────────
def _load_research_context(research: dict) -> str:
    """research_report에서 프롬프트 주입용 텍스트 블록 생성
    — 종목 차트, FVG, 지지/저항 등 기술적 분석 데이터 및 가격 기반 매수 타점 분석 명세는 제외하고 거시 서사 및 수급 중심으로 구성.
    """
    if not research:
        return ""
    parts = []
    if research.get("today_narrative"):
        parts.append(f"[오늘의 핵심 거시 서사 — Research Agent 분석]\n{research['today_narrative']}")
    if research.get("economic_background"):
        parts.append(f"[경제 이론적 배경]\n{research['economic_background']}")
    if research.get("back_data_trends"):
        trend = research["back_data_trends"]
        if isinstance(trend, dict) and "key" in trend:
            trend_str = (
                f"[{trend.get('key')} 최근 10영업일 추이] "
                f"시작일({trend.get('start_date')}) 종가 {trend.get('start_val')} 대비 "
                f"종료일({trend.get('end_date')}) 종가 {trend.get('end_val')}로 "
                f"{trend.get('change_pct')}% 변동. "
                f"최고치: {trend.get('max_val')}, 최저치: {trend.get('min_val')}"
            )
        else:
            trend_str = str(trend)
        parts.append(f"[과거 백데이터 추이 — 반드시 기획 및 본문에 적극 반영]\n{trend_str}")
    if research.get("key_news_summary"):
        parts.append(f"[주요 뉴스 요약]\n{research['key_news_summary']}")
    if research.get("macro_interpretation"):
        parts.append(f"[거시지표 해석]\n{research['macro_interpretation']}")
    if research.get("risk_factors"):
        risks = "\n".join(f"- {r}" for r in research["risk_factors"])
        parts.append(f"[거시 리스크 요인]\n{risks}")
    if research.get("moneydaddy_view"):
        parts.append(f"[머니대디 전략 방향성 (종목·차트 제외)]\n{research['moneydaddy_view']}")
    # 하드 팩트 (뉴스 추출 수치): 할루시네이션 방지용 최우선 데이터
    if research.get("hard_facts"):
        facts = "\n".join(f"- {f}" for f in research["hard_facts"])
        parts.append(f"[뉴스 추출 핵심 팩트 — 반드시 우선 사용]\n{facts}")

    # 경량 Graph RAG: 인과적 흐름 반영용 지식 그래프
    if research.get("graph_narrative"):
        parts.append(f"[오늘 시장의 인과 관계 지식 그래프 (Graph RAG)]\n{research['graph_narrative']}")

    # 섹터 힌트: 말미에 낮은 비중으로만 활용
    if research.get("sector_hint"):
        parts.append(f"[오늘 수급 힌트 — 콘텐츠 말미 낮은 비중으로만 언급]\n{research['sector_hint']}")
    return "\n\n".join(parts)


def agent_plan_structure(data: dict, pivot: dict | None, topic: str,
                         feedback: str = "", research: dict = None) -> dict:
    """Step 1: 전체적인 서사 구조와 비디오 씬별 핵심 논리를 기획합니다."""
    model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})

    filtered_data = {
        "Fear_Greed": data.get("Fear_Greed"),
        "top_kr_sectors": data.get("top_kr_sectors"),
        "sector_volume_surge": data.get("sector_volume_surge")
    }
    if any(k in topic for k in ["환율", "달러", "USD", "외환"]):
        filtered_data["USD_KRW"] = data.get("USD_KRW")
        filtered_data["USD_KRW_chg"] = data.get("USD_KRW_chg")

    # 주제에 따른 수급 데이터 필터링 (부동산 주제 시 주식 수급 배제)
    is_real_estate = any(k in topic for k in ["부동산", "아파트", "주택", "재건축", "임대", "분양"])
    
    pivot_inst = ""
    if pivot and not is_real_estate:
        pivot_inst = f"\n[주식 수급 집중 섹터] 오늘 '{pivot['name']}' 섹터 거래량 {pivot['volume_ratio']:.1f}배 폭증. 이 테마를 결론부 타켓으로 활용할 것."
    elif is_real_estate:
        pivot_inst = "\n[주의] 본 리포트는 부동산 중심입니다. 주식 섹터 수급(Pivot)보다는 부동산 실거래가, 금리, 규제 정책이 자산 시장 재편에 미치는 영향에 집중하세요."

    research_block = _load_research_context(research or {})

    prompt = f"""당신은 "머니대디 경제 분석가" 페르소나를 가진 수석 전략가입니다. 주제 "{topic}"에 대한 Remotion 영상(5~10씬)과 블로그의 **구조 설계도**를 작성하세요.
차트 타점이나 FVG(Fair Value Gap), 지지/저항 등 기술적 분석 및 가격 기반 매수 타점 분석 명세를 프롬프트와 분석에서 완전히 배제하고, "과거 백데이터 추이 및 실시간 자금 흐름(수급)과 거시 경제 이슈"를 바탕으로 전문적이고 깊이 있는 통찰을 구조화하십시오.
리서치 팩트 데이터의 성격과 볼륨에 맞추어 최적의 비디오 씬 수(보통 5~10씬 내외)를 스스로 설계하십시오.

[시장 상황 요약]
{json.dumps(filtered_data, ensure_ascii=False)}
{pivot_inst}

{research_block}

[현재 시점 (Current Time)]
{datetime.now().strftime('%Y-%m-%d %H:%M')}

[절대 지침]
1. **시점 인식**: 위 [현재 시점]을 절대적 현재로 간주하고, 오늘의 리서치 결과 수치를 무조건 우선하여 사용하십시오.
2. **'아키텍트' 용어 사용 금지**: 자신을 '시스템 아키텍트'라 부르지 마십시오. '머니대디 경제 분석가' 페르소나를 사용하여 작성하십시오.
3. **비디오 씬 기획**: 비디오 씬별 제목, 핵심 논리, 자막 텍스트 레이아웃을 기획하도록 지침을 지정하십시오.
4. **과거 백데이터 및 수급 흐름 반영**: 리서치 리포트의 `back_data_trends` (과거 백데이터 추이) 데이터를 적극적으로 기획 구조와 씬별 핵심 논리에 녹여내십시오. 실시간 자금 흐름(수급)과 거시 경제 동향을 유기적으로 연계하십시오.
5. **기술적 분석 및 타점 완전 배제**: FVG, Price Action, 지지/저항선, 가격 기반 매수 타점 분석 등의 기술적 지표 및 명세를 일절 사용하지 마십시오.
6. **팩트 인용**: 리서치 결과의 구체적 수치를 씬 구성 논리에 명확하게 배치하십시오.
7. **지식 그래프 연동**: 위 [오늘 시장의 인과 관계 지식 그래프 (Graph RAG)]의 노드들과 엣지 관계(인과 관계 흐름)가 영상 전체의 논리 전개(`core_logic`)에 자연스럽고 명확하게 연결되도록 구조화하십시오.
8. **인포그래픽 카드 데이터 구성**: `visual_asset`의 `type`이 `infographic_flow` 또는 `infographic_compare` 일 때는 반드시 흐름 단계 또는 비교 항목으로 표시할 핵심 요약 문구 2~4개를 `"visual_elements"` 리스트에 배열 형태로 담아주십시오. (예: `["자금 이탈", "소부장 이동"]`) 그 외의 경우에는 null 또는 빈 배열로 설정하십시오.

출력 JSON 스키마:
{{
  "structure_id": "unique_id",
  "theme_narrative": "이 콘텐츠가 관통하는 하나의 거대한 서사 (구체적 수치 포함)",
  "video_structure": [
    {{ 
      "scene": 1, 
      "title": "씬 제목 (25자 이내)", 
      "core_logic": "이 씬에서 전달할 핵심 논리 및 수치 팩트 (100자 이내)", 
      "caption_layout": "자막 텍스트 레이아웃 (예: '핵심 요약 라인1 / 라인2')",
      "visual_asset": {{
        "type": "chart_macro 또는 chart_sector 또는 chart_fear_greed 또는 infographic_flow 또는 infographic_compare 또는 image_issue 또는 none",
        "fallback_text": "대체텍스트(20자)"
      }},
      "visual_intent": "시각적 의도 또는 필요한 차트/이미지 묘사 (50자 이내)",
      "visual_elements": ["요소1(10자이내)", "요소2(10자이내)", "요소3(10자이내)"]
    }},
    ...
  ],
  "blog_structure": {{
    "intro_logic": "...", "cause_logic": "...", "market_logic": "...", "insight_logic": "...", "strategy_logic": "..."
  }}
}}"""

    print("  [Step 1] Planning Content Structure & Blueprint...")
    logic = call_gemini_with_retry(model, prompt)
    
    # Blueprint MD 생성
    blueprint_path = "data/O_Video_Blueprint.md"
    bp_content = f"""# 🗺️ MoneyDaddy Video Blueprint: {topic}

## 1. 주제 서사 (Narrative)
{logic.get('theme_narrative', 'N/A')}

## 2. 비디오 씬별 구성 설계 ({len(logic.get("video_structure", []))} Scenes)
| Scene | Title | Core Logic / Fact to Use | Caption Layout | Visual Intent |
|---|---|---|---|---|
"""
    for s in logic.get("video_structure", []):
        bp_content += f"| {s['scene']} | {s['title']} | {s['core_logic']} | {s.get('caption_layout', 'N/A')} | {s.get('visual_intent', 'N/A')} |\n"
    
    bp_content += f"\n## 3. 블로그 구성 전략\n- **Intro**: {logic.get('blog_structure', {}).get('intro_logic')}\n- **Insight**: {logic.get('blog_structure', {}).get('insight_logic')}\n"
    
    with open(blueprint_path, "w", encoding="utf-8") as f:
        f.write(bp_content)
    print(f"  [Planning] Video Blueprint generated at {blueprint_path}")
    
    return logic

def agent_write_blog(structure: dict, data: dict, topic: str, research: dict = None) -> dict:
    """Step 2: 설계도를 바탕으로 블로그 본문을 집중적으로 작성합니다 (2,500자+)."""
    # 머니대디 수석 집필 비서 페르소나 및 가독성/정제 규칙을 System Instruction으로 정의
    system_instruction = (
        "당신은 자금 흐름과 거시경제적 관점에서 시장을 날카롭게 해설하는 채널 '머니대디'의 수석 집필 비서이자 에디터입니다.\n"
        "다음 글쓰기 가독성 및 음성 합성 정제 규칙을 반드시 준수하여 블로그 본문을 작성해 주세요:\n"
        "1. 글쓰기 가독성 원칙: 문단은 독자가 읽기 편하도록 3~4줄 내외로 짧게 구성하고, 주요 키워드와 수치는 볼드 강조 처리(**텍스트**)합니다.\n"
        "2. 음성 합성용 정제 필터 규칙: 향후 TTS(내레이션) 변환 및 음성 합성을 고려하여 본문 내 괄호 ( ) 및 특수 기호를 최대한 배제하고, 자연스럽게 서술형 문장으로 풀어서 작성합니다."
    )

    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
        system_instruction=system_instruction
    )
    guides = load_guides()
    research_block = _load_research_context(research or {})

    # 사용자 프롬프트 템플릿에서 시스템 지침으로 격상된 중복 지침을 제거하여 다이어트합니다.
    prompt = f"""[구조 설계도]와 [리서치 분석 결과]를 바탕으로 **블로그 본문**을 작성하세요.

[가이드라인]
{guides.get('O1_blog.md', '')}

[구조 설계도]
{json.dumps(structure, ensure_ascii=False)}

{research_block}

[현재 시점 (Current Time)]
{datetime.now().strftime('%Y-%m-%d %H:%M')}

[절대 지침: 데이터 기반 작성]
1. **최신성 및 데이터 수치 무조건 유지 (임의 수정 절대 금지)**: 
   - 제공된 팩트 시트와 리서치 결과의 수치는 실제 수치이든, 본인의 이전 지식과 어긋나든 상관없이 **문자 그대로 100% 동일하게** 사용해야 합니다.
   - 예를 들어, 팩트 시트에 KOSPI가 7000대(예: 7847.71)로 적혀 있거나, 환율이 1500대(예: 1506.74)로 기재되어 있다면, "상식적으로 틀리다"고 판단하여 임의로 코스피를 2000대로 바꾸거나 환율을 1300대로 보정하는 등의 수치 변형을 **절대 금지**합니다. 
   - 수치를 임의로 수정하여 렌더링하면 팩트 검증기에서 자동 실패(FAIL) 처리되어 파이프라인이 중단됩니다. 제공된 KOSPI(7847.71), USD_KRW(1506.74), VIX(17.01) 등 모든 절대 수치를 한 치의 가공도 없이 그대로 본문에 명시하십시오.
2. **팩트 대조**: 
   - 제공된 데이터와 한 글자도 틀리지 않게 대조하십시오.
3. **금지 용어**: '아키텍트' 용어 사용 절대 금지.
4. **인과 관계 서사**: [오늘 시장의 인과 관계 지식 그래프 (Graph RAG)]에서 도출된 사건의 원인과 결과, 파급 효과의 흐름이 블로그 전체에 일관되게 전개되어 매끄러운 흐름을 만들도록 하십시오.

5. **필수 지표 포함**: 다음 5대 시장 지표와 수치를 본문(블로그 내용)에 자연스럽고 정확하게 반드시 직접 언급하여 기술하십시오: 코스피 지수(KOSPI), 공포지수 VIX, 미 국채 10년물 금리, 원/달러 환율, 공포/탐욕 지수. (예: "금일 코스피 지수는 XX.XX포인트를 기록했으며...", "공포지수 VIX는 XX.XX로...")
6. **이미지 플레이스홀절 강제**: 블로그 본문(`blog_draft`) 내부에서 가이드라인의 이미지 4개 배치에 대응하는 논리적 문맥 위치에 각각 `[이미지1]`, `[이미지2]`, `[이미지3]`, `[이미지4]`라는 텍스트 플레이스홀더를 대괄호를 포함해 명시적으로 삽입하십시오. (예: `... 분석해 보겠습니다.\n\n[이미지1]\n\n다음으로 ...`)
7. **해시태그 필수**: 블로그 본문(`blog_draft`)의 가장 마지막 부분에 관련성 높은 해시태그를 15개 이상(예: `#머니대디 #주식투자 #반도체 ...`) 반드시 추가하십시오.

출력 JSON 스키마:
{{
  "title": "강력한 제목 (브랜드명/머니대디 언급 금지)",
  "blog_draft": "2500자 이상의 블로그 전문",
  "blog_images": [ {{ "id": 1, "prompt": "영문", "caption_ko": "한글" }}, ... ]
}}"""

    print("  [Step 2] Writing Blog Content (2,500 chars target)...")
    return call_gemini_with_retry(model, prompt)

# ── 글자 수 제한 강제 적용 ──────────────────────────────────────────────────
def run_content_generation(data: dict, selected_topic: str, feedback: str = ""):
    pivot = detect_sector_pivot(data)

    research = {}
    research_path = "data/research_report.json"
    if os.path.exists(research_path):
        try:
            with open(research_path, "r", encoding="utf-8") as f:
                research = json.load(f)
            print(f"  [Content] Research Report 로드 완료")
        except: pass

    # [1단계] 구조 기획
    structure = agent_plan_structure(data, pivot, selected_topic, feedback, research=research)
    with open("data/latest_content_logic.json", "w", encoding="utf-8") as f:
        json.dump({"status": "planning_done", "structure": structure}, f, indent=4, ensure_ascii=False)

    # [2단계] 블로그 작성
    blog_data = agent_write_blog(structure, data, selected_topic, research=research)
    title = blog_data.get("title", "머니대디 분석 리포트") if isinstance(blog_data, dict) else "머니대디 분석 리포트"
    blog_content = f"# {title}\n\n{blog_data.get('blog_draft', '') if isinstance(blog_data, dict) else ''}"
    with open(get_dated_path("블로그초안", "md"), "w", encoding="utf-8") as f:
        f.write(clean_for_blog(blog_content))

    # 하위 호환성을 위해 verification_loop 및 대시보드에서 사용하는 daily_content_draft.md 에도 동일하게 저장
    with open(get_path("daily_content_draft.md"), "w", encoding="utf-8") as f:
        f.write(clean_for_blog(blog_content))

    final_result = {
        "title": title,
        "theme_analysis": structure.get("theme_narrative", ""),
        "video_structure": structure.get("video_structure", []),
        "blog_images": blog_data.get("blog_images", []) if isinstance(blog_data, dict) else [],
        "youtube_desc": f"{title}\n\n오늘의 핵심 리포트입니다."
    }
    
    with open("data/latest_content_logic.json", "w", encoding="utf-8") as f:
        json.dump(final_result, f, indent=4, ensure_ascii=False)
    
    print(f"  [Final] Content Pipeline Completed (Remotion Video Scene Planning).")
    return final_result

if __name__ == "__main__":
    with open("data/raw_market_data.json", "r", encoding="utf-8") as f: data = json.load(f)
    print("Test running content generation...")
    # This block is for testing. Real execution is driven by main.py
