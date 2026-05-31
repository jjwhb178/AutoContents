import sys, os, json, time
from datetime import datetime
import google.generativeai as genai

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
def propose_topics(data: dict) -> list:
    """뉴스를 분석하여 3개의 주제 후보를 제안합니다."""
    model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
    news = data.get("market_news", [])
    import datetime
    today_str = datetime.datetime.now().strftime("%Y년 %m월 %d일")
    
    prompt = f"""당신은 머니대디의 수석 비서입니다. 
오늘은 {today_str}입니다. 아래 실시간 뉴스 속보를 분석하여, 오늘 **미국 증시와 한국 증시에 가장 큰 영향을 미칠 핵심 뉴스 이슈** 3가지를 도출하세요.

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
        print(f"  [Proposal Error] {selected_topic if 'selected_topic' in locals() else 'Topic Proposal'} failed: {e}")
        return []

# ── 2. 기획 생성 로직 (High-Density Assets) ──────────────────────────────
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
        parts.append(f"[과거 백데이터 추이 — 반드시 기획 및 본문에 적극 반영]\n{research['back_data_trends']}")
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
    """Step 1: 전체적인 서사 구조와 슬라이드별 아키타입 및 핵심 논리를 기획합니다."""
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
    guides = load_guides()
    ppt_design_guide = guides.get('O2_PPT_Architecture.md', '')

    prompt = f"""당신은 "머니대디 경제 분석가" 페르소나를 가진 수석 전략가입니다. 주제 "{topic}"에 대한 PPT와 2,500자 블로그의 **구조 설계도**를 작성하세요.
차트 타점이나 FVG(Fair Value Gap), 지지/저항 등 기술적 분석 및 가격 기반 매수 타점 분석 명세를 프롬프트와 분석에서 완전히 배제하고, "과거 백데이터 추이 및 실시간 자금 흐름(수급)과 거시 경제 이슈"를 바탕으로 전문적이고 깊이 있는 통찰을 구조화하십시오.
더 이상 18페이지라는 제한에 얽매일 필요가 없으며, 리서치 팩트 데이터의 성격과 볼륨에 맞추어 최적의 슬라이드 수(보통 5~10장 내외)를 스스로 설계하십시오.

[시장 상황 요약]
{json.dumps(filtered_data, ensure_ascii=False)}
{pivot_inst}

{research_block}

[PPT 구조 가이드라인 및 아키타입 규칙]
{ppt_design_guide}

[현재 시점 (Current Time)]
{datetime.now().strftime('%Y-%m-%d %H:%M')}

[절대 지침]
1. **시점 인식**: 위 [현재 시점]을 절대적 현재로 간주하고, 오늘의 리서치 결과 수치를 무조건 우선하여 사용하십시오.
2. **'아키텍트' 용어 사용 금지**: 자신을 '시스템 아키텍트'라 부르지 마십시오. '머니대디 경제 분석가' 페르소나를 사용하여 작성하십시오.
3. **아키타입 매핑**: 각 슬라이드는 반드시 아래 9가지 아키타입 중 하나를 지정해야 합니다.
   - Title, Agenda, Problem, Solution, Features, Stats, Team, CTA, Closing
4. **과거 백데이터 및 수급 흐름 반영**: 리서치 리포트의 `back_data_trends` (과거 백데이터 추이) 데이터를 적극적으로 기획 구조와 슬라이드별 핵심 논리에 녹여내십시오. 실시간 자금 흐름(수급)과 거시 경제 동향을 유기적으로 연계하십시오.
5. **기술적 분석 및 타점 완전 배제**: FVG, Price Action, 지지/저항선, 가격 기반 매수 타점 분석 등의 기술적 지표 및 명세를 일절 사용하지 마십시오.
6. **팩트 인용**: 리서치 결과의 구체적 수치를 슬라이드 구성 논리에 명확하게 배치하십시오.
7. **지식 그래프 연동**: 위 [오늘 시장의 인과 관계 지식 그래프 (Graph RAG)]의 노드들과 엣지 관계(인과 관계 흐름)가 슬라이드 전체의 논리 전개(`core_logic`)에 자연스럽고 명확하게 연결되도록 구조화하십시오.
8. **지표 중복 배정 금지**: 슬라이드 구조를 기획할 때, 여러 개의 Stats 슬라이드에 동일한 지표나 수치(예: 3페이지와 6페이지 모두 Fear & Greed 지수 34를 사용하는 것)를 중복해서 사용하지 마십시오. 3페이지에는 공포/탐욕 지수(34), 6페이지에는 코스피 지수(7847.71)나 VIX(17.01)처럼 각 슬라이드마다 서로 다른 핵심 지표를 배분하십시오.



출력 JSON 스키마:
{{
  "structure_id": "unique_id",
  "theme_narrative": "이 콘텐츠가 관통하는 하나의 거대한 서사 (구체적 수치 포함)",
  "ppt_structure": [
    {{ 
      "page": 1, 
      "topic": "제목", 
      "slide_type": "Title", 
      "core_logic": "이 페이지에서 전달할 핵심 논리", 
      "visual_intent": "시각적 의도 또는 필요한 차트/이미지 묘사" 
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
    blueprint_path = "data/O_PPT_Blueprint.md"
    bp_content = f"""# 🗺️ MoneyDaddy PPT Blueprint: {topic}

## 1. 주제 서사 (Narrative)
{logic.get('theme_narrative', 'N/A')}

## 2. 슬라이드별 구성 설계 ({len(logic.get("ppt_structure", []))} Slides)
| Page | Topic | Slide Type | Core Logic / Fact to Use | Visual Intent |
|---|---|---|---|---|
"""
    for s in logic.get("ppt_structure", []):
        bp_content += f"| {s['page']} | {s['topic']} | {s.get('slide_type', 'N/A')} | {s['core_logic']} | {s.get('visual_intent', 'N/A')} |\n"
    
    bp_content += f"\n## 3. 블로그 구성 전략\n- **Intro**: {logic.get('blog_structure', {}).get('intro_logic')}\n- **Insight**: {logic.get('blog_structure', {}).get('insight_logic')}\n"
    
    with open(blueprint_path, "w", encoding="utf-8") as f:
        f.write(bp_content)
    print(f"  [Planning] Blueprint generated at {blueprint_path}")
    
    return logic

def agent_write_blog(structure: dict, data: dict, topic: str, research: dict = None) -> dict:
    """Step 2: 설계도를 바탕으로 블로그 본문을 집중적으로 작성합니다 (2,500자+)."""
    model = genai.GenerativeModel("gemini-2.5-pro", generation_config={"response_mime_type": "application/json"})
    guides = load_guides()
    research_block = _load_research_context(research or {})

    prompt = f"""당신은 머니대디의 수석 에디터입니다. [구조 설계도]와 [리서치 분석 결과]를 바탕으로 **블로그 본문**을 작성하세요.

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
6. **이미지 플레이스홀더 강제**: 블로그 본문(`blog_draft`) 내부에서 가이드라인의 이미지 4개 배치에 대응하는 논리적 문맥 위치에 각각 `[이미지1]`, `[이미지2]`, `[이미지3]`, `[이미지4]`라는 텍스트 플레이스홀더를 대괄호를 포함해 명시적으로 삽입하십시오. (예: `... 분석해 보겠습니다.\n\n[이미지1]\n\n다음으로 ...`)
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
SLIDE_LIMITS = {
    "Title":             {"title": 30, "subtitle": 35, "brand_tag": 8, "date": 15, "presenter": 10},
    "Agenda":            {"title": 20, "item": 25},
    "Problem":           {"title": 20, "bullet": 45, "label": 10, "description": 40},
    "Solution":          {"title": 20, "subtitle": 35, "point": 35, "visual_desc": 50},
    "Features":          {"title": 20, "name": 10, "description": 20},
    "Stats":             {"title": 20, "value": 10, "unit": 8, "delta": 15, "description": 45},
    "Team":              {"title": 20, "name": 8, "role": 12, "career": 15},
    "CTA":               {"title": 20, "proposal": 40, "button_text": 15, "contact": 20},
    "Closing":           {"title": 20, "message": 30, "contact": 20},
}

def enforce_field_limits(ppt_script: dict) -> dict:
    """슬라이드 각 필드 글자 수 초과 시 compress_to_fit 호출"""
    for page_key, slide in ppt_script.items():
        stype = slide.get("slide_type", "Problem").capitalize()
        # 대소문자 매핑 안정화
        if stype == "Title_only":
            stype = "Title"
        elif stype == "Big_number":
            stype = "Stats"
        elif stype == "Headline_bullets":
            stype = "Problem"
        elif stype == "Three_cards":
            stype = "Problem"
        elif stype == "Left_text_right_visual":
            stype = "Solution"
        elif stype == "Flow_steps":
            stype = "Solution"

        limits = SLIDE_LIMITS.get(stype, {})

        # 공통 title
        if "title" in slide and len(slide["title"]) > limits.get("title", 20):
            slide["title"] = compress_to_fit(slide["title"], limits["title"])

        # Title 아키타입
        if stype == "Title":
            if "subtitle" in slide and len(slide["subtitle"]) > limits.get("subtitle", 25):
                slide["subtitle"] = compress_to_fit(slide["subtitle"], limits["subtitle"])
            if "brand_tag" in slide and len(slide["brand_tag"]) > limits.get("brand_tag", 8):
                slide["brand_tag"] = compress_to_fit(slide["brand_tag"], limits["brand_tag"])
            if "date" in slide and len(slide["date"]) > limits.get("date", 15):
                slide["date"] = compress_to_fit(slide["date"], limits["date"])
            if "presenter" in slide and len(slide["presenter"]) > limits.get("presenter", 10):
                slide["presenter"] = compress_to_fit(slide["presenter"], limits["presenter"])

        # Agenda 아키타입
        elif stype == "Agenda":
            if "items" in slide:
                lim = limits.get("item", 25)
                slide["items"] = [
                    compress_to_fit(item, lim) if len(item) > lim else item
                    for item in slide["items"][:6]
                ]

        # Problem 아키타입
        elif stype == "Problem":
            if "bullets" in slide:
                lim = limits.get("bullet", 30)
                slide["bullets"] = [
                    compress_to_fit(b, lim) if len(b) > lim else b
                    for b in slide["bullets"][:3]
                ]
            if "cards" in slide:
                for card in slide["cards"][:3]:
                    if len(card.get("label", "")) > limits.get("label", 10):
                        card["label"] = compress_to_fit(card["label"], limits["label"])
                    if len(card.get("description", "")) > limits.get("description", 30):
                        card["description"] = compress_to_fit(card["description"], limits["description"])

        # Solution 아키타입
        elif stype == "Solution":
            if "subtitle" in slide and len(slide["subtitle"]) > limits.get("subtitle", 25):
                slide["subtitle"] = compress_to_fit(slide["subtitle"], limits["subtitle"])
            if "points" in slide:
                lim = limits.get("point", 25)
                slide["points"] = [
                    compress_to_fit(p, lim) if len(p) > lim else p
                    for p in slide["points"][:3]
                ]
            if "visual_desc" in slide and len(slide["visual_desc"]) > limits.get("visual_desc", 40):
                slide["visual_desc"] = compress_to_fit(slide["visual_desc"], limits["visual_desc"])

        # Features 아키타입
        elif stype == "Features":
            if "features" in slide:
                for feat in slide["features"][:6]:
                    if len(feat.get("name", "")) > limits.get("name", 10):
                        feat["name"] = compress_to_fit(feat["name"], limits["name"])
                    if len(feat.get("description", "")) > limits.get("description", 20):
                        feat["description"] = compress_to_fit(feat["description"], limits["description"])

        # Stats 아키타입
        elif stype == "Stats":
            if "value" in slide and len(str(slide["value"])) > limits.get("value", 10):
                slide["value"] = compress_to_fit(str(slide["value"]), limits["value"])
            if "unit" in slide and len(slide["unit"]) > limits.get("unit", 8):
                slide["unit"] = compress_to_fit(slide["unit"], limits["unit"])
            if "delta" in slide and len(slide["delta"]) > limits.get("delta", 10):
                slide["delta"] = compress_to_fit(slide["delta"], limits["delta"])
            if "description" in slide and len(slide["description"]) > limits.get("description", 30):
                slide["description"] = compress_to_fit(slide["description"], limits["description"])

        # Team 아키타입
        elif stype == "Team":
            if "members" in slide:
                for mem in slide["members"][:4]:
                    if len(mem.get("name", "")) > limits.get("name", 8):
                        mem["name"] = compress_to_fit(mem["name"], limits["name"])
                    if len(mem.get("role", "")) > limits.get("role", 12):
                        mem["role"] = compress_to_fit(mem["role"], limits["role"])
                    if len(mem.get("career", "")) > limits.get("career", 15):
                        mem["career"] = compress_to_fit(mem["career"], limits["career"])

        # CTA 아키타입
        elif stype == "CTA":
            if "proposal" in slide and len(slide["proposal"]) > limits.get("proposal", 40):
                slide["proposal"] = compress_to_fit(slide["proposal"], limits["proposal"])
            if "button_text" in slide and len(slide["button_text"]) > limits.get("button_text", 15):
                slide["button_text"] = compress_to_fit(slide["button_text"], limits["button_text"])
            if "contact" in slide and len(slide["contact"]) > limits.get("contact", 20):
                slide["contact"] = compress_to_fit(slide["contact"], limits["contact"])

        # Closing 아키타입
        elif stype == "Closing":
            if "message" in slide and len(slide["message"]) > limits.get("message", 30):
                slide["message"] = compress_to_fit(slide["message"], limits["message"])
            if "contact" in slide and len(slide["contact"]) > limits.get("contact", 20):
                slide["contact"] = compress_to_fit(slide["contact"], limits["contact"])

    return ppt_script


def agent_write_ppt_chunk(structure: dict, data: dict, topic: str, research: dict, start_pg: int, end_pg: int) -> dict:
    """Step 3 (Chunk): 9대 아키타입 스키마로 PPT 대본 생성"""
    model = genai.GenerativeModel("gemini-2.5-pro", generation_config={"response_mime_type": "application/json"})

    fact_sheet = ""
    if os.path.exists("data/O_FactSheet.md"):
        with open("data/O_FactSheet.md", "r", encoding="utf-8") as f:
            fact_sheet = f.read()

    full_structure = structure.get("ppt_structure", [])
    chunk_meta = [s for s in full_structure if start_pg <= int(s.get("page", 0)) <= end_pg]

    kg_block = research.get("graph_narrative", "") if research else ""
    if kg_block:
        kg_block = f"\n[오늘 시장의 인과 관계 지식 그래프 (Graph RAG)]\n{kg_block}\n"

    prompt = f"""당신은 머니대디의 PPT 대본 작가입니다. {start_pg}~{end_pg}페이지를 생성하세요.

[절대 기준: 팩트 시트 — 이 수치 외에는 사용 금지]
{fact_sheet}

{kg_block}

[현재 시점]
{datetime.now().strftime('%Y-%m-%d %H:%M')}

[구조 설계도 (해당 구간)]
{json.dumps(chunk_meta, ensure_ascii=False)}

[슬라이드 9대 아키타입별 스키마 및 규칙]
반드시 슬라이드별로 구조 설계도에 명시된 "slide_type"을 준수하고, 해당 타입에 맞는 필드 구조를 채우십시오.

1. Title (표지)
   - slide_type: "Title"
   - title: 슬라이드 메인 제목 (30자 이내)
   - subtitle: 부제 (25자 이내)
   - brand_tag: 브랜드 태그 (8자 이내, 예: "머니대디")
   - date: 날짜 (15자 이내, 예: "2026.05.16")
   - presenter: 발표자 정보 (10자 이내)
   - audio_script: 발표용 대본

2. Agenda (목차)
   - slide_type: "Agenda"
   - title: 목차 제목 (20자 이내, 예: "Agenda")
   - items: 목차 항목 리스트 (최대 6개, 각 항목 25자 이내)
   - audio_script: 발표용 대본

3. Problem (문제 정의)
   - slide_type: "Problem"
   - title: 문제 제목 (20자 이내)
   - bullets: 문제 설명 글머리 목록 (최대 3개, 각 30자 이내)
   - cards: 개별 문제 카드 목록 (선택 사항, 최대 3개, 각 카드는 {{"label": "라벨(10자)", "description": "설명(30자)"}} 구조)
   - audio_script: 발표용 대본

4. Solution (해법)
   - slide_type: "Solution"
   - title: 해법 제목 (20자 이내)
   - subtitle: 핵심 가치 한 줄 요약 (25자 이내)
   - points: 해법 포인트 리스트 (최대 3개, 각 25자 이내)
   - visual_asset: 시각 자료 매핑 정보 ({{"type": "infographic_flow" 또는 "image_issue", "fallback_text": "대체텍스트(20자)"}})
   - visual_desc: 시각 자료 요약 설명 (40자 이내)
   - audio_script: 발표용 대본

5. Features (기능/차별점)
   - slide_type: "Features"
   - title: 기능 제목 (20자 이내)
   - features: 기능 카드 목록 (최대 6개, 각 기능은 {{"name": "기능명(10자)", "description": "설명(20자)"}} 구조)
   - audio_script: 발표용 대본

6. Stats (통계 강조)
   - slide_type: "Stats"
   - title: 통계 제목 (20자 이내)
   - value: 핵심 수치 (10자 이내, 예: "7493.18" 또는 "4.59")
   - unit: 단위 (8자 이내, 예: "KOSPI" 또는 "%")
   - delta: 등락/변동 수치 (10자 이내, 예: "-6.12%" 또는 "+15%")
   - description: 통계 부연 설명 (30자 이내)
   - visual_asset: 시각 자료 매핑 정보 ({{"type": "chart_macro" 또는 "chart_sector" 또는 "chart_fear_greed", "fallback_text": "대체텍스트(20자)"}})
   - audio_script: 발표용 대본

7. Team (팀 소개)
   - slide_type: "Team"
   - title: 팀 제목 (20자 이내)
   - members: 팀원 정보 목록 (최대 4개, 각 팀원은 {{"name": "이름(8자)", "role": "직책(12자)", "career": "경력(15자)"}} 구조)
   - audio_script: 발표용 대본

8. CTA (행동 요청)
   - slide_type: "CTA"
   - title: 행동 요청 제목 (20자 이내)
   - proposal: 핵심 제안 문장 (40자 이내)
   - button_text: 버튼용 액션 문구 (15자 이내, 예: "지금 시작하기")
   - contact: 연락처 정보 (20자 이내)
   - audio_script: 발표용 대본

9. Closing (마무리)
   - slide_type: "Closing"
   - title: 감사 인사 제목 (20자 이내, 예: "감사합니다")
   - message: 맺음말 메시지 (30자 이내, 예: "Q&A를 진행합니다")
   - contact: 연락처 정보 (20자 이내)
   - audio_script: 발표용 대본

[절대 지침]
1. **팩트 시트에 없는 수치는 절대 사용하지 말며, 기재된 수치(예: KOSPI: 7847.71 등)를 본인의 이전 지식으로 교정하지 말고 100% 한 자도 틀리지 않게 그대로 사용하십시오.**
2. '시스템 아키텍트' 용어 절대 금지 → '머니대디 경제 분석가'로 지칭
3. 각 아키타입별 정의된 필드만 채우고, 지정된 글자 수 제한을 초과하면 핵심만 남기고 요약/압축하십시오.
4. `visual_asset`에 적합한 시각화 `type`을 정확하게 연결하십시오 (`chart_macro`, `chart_sector`, `chart_fear_greed`, `infographic_flow`, `infographic_compare`, `image_issue`, `none`).
5. **과거 백데이터 및 수급 흐름 반영**: 리서치 리포트의 과거 백데이터 추이 데이터 및 실시간 자금 흐름(수급)과 거시 경제 이슈에 기반하여 깊이 있는 분석을 대본(audio_script)에 담으십시오.
6. **기술적 분석 배제**: FVG, Price Action, 지지/저항선, 가격 기반 매수 타점 분석 등 기술적 분석 명세를 대본 및 필드에서 완전히 배제하십시오.
7. **필수 지표 언급**: 5대 시장 지표(코스피 지수(KOSPI), VIX, 미 국채 10년물 금리, 원/달러 환율, 공포/탐욕 지수)의 수치를 적절한 슬라이드(특히 Stats 아키타입이나 대본 audio_script)에 자연스럽고 정확하게 반드시 직접 언급하여 반영하십시오.
8. **지표 중복 작성 금지**: 여러 개의 Stats 슬라이드를 작성할 때, 다른 슬라이드에 할당된 지표와 중복되는 수치(예: Fear & Greed 34를 두 슬라이드에 동시에 사용하는 경우)가 없도록 하십시오. 3페이지가 Fear & Greed(34)였다면, 6페이지는 코스피 지수(7847.71)나 VIX(17.01) 등 반드시 서로 다른 지표 수치를 매핑해야 합니다.




출력 JSON 스키마 (page_num은 실제 숫자로 대체):
{{
  "ppt_script": {{
    "{start_pg}": {{
      "slide_type": "Title",
      "title": "슬라이드 제목",
      "subtitle": "부제목",
      "brand_tag": "머니대디",
      "date": "2026.05.16",
      "presenter": "머니대디",
      "audio_script": "브리핑 대본"
    }},
    ...
  }}
}}"""
    print(f"  [Step 3] PPT Chunk {start_pg}~{end_pg} 생성 중 (9대 아키타입 스키마)...")
    return call_gemini_with_retry(model, prompt)

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

    # [3단계] PPT 분할 생성 (동적 슬라이드 수 대응)
    full_structure = structure.get("ppt_structure", [])
    total_slides = len(full_structure)
    combined_ppt = {}
    
    # 5장 단위로 청크 처리
    chunk_size = 5
    for start_idx in range(1, total_slides + 1, chunk_size):
        end_idx = min(start_idx + chunk_size - 1, total_slides)
        chunk_data = agent_write_ppt_chunk(structure, data, selected_topic, research, start_idx, end_idx)
        if chunk_data and "ppt_script" in chunk_data:
            combined_ppt.update(chunk_data["ppt_script"])

    # [4단계] 필드 글자 수 초과 검사 및 의미 유지 압축
    print("  [Step 4] 필드 글자 수 검증 및 의미 유지 압축 실행...")
    combined_ppt = enforce_field_limits(combined_ppt)

    final_result = {
        "title": title,
        "theme_analysis": structure.get("theme_narrative", ""),
        "ppt_script": combined_ppt,
        "blog_images": blog_data.get("blog_images", []) if isinstance(blog_data, dict) else [],
        "youtube_desc": f"{title}\n\n오늘의 핵심 리포트입니다."
    }
    
    with open("data/latest_content_logic.json", "w", encoding="utf-8") as f:
        json.dump(final_result, f, indent=4, ensure_ascii=False)
    
    print(f"  [Final] Dynamic Slide Pipeline Completed: {total_slides} slides.")
    return final_result

if __name__ == "__main__":
    with open("data/raw_market_data.json", "r", encoding="utf-8") as f: data = json.load(f)
    print("Test running content generation...")
    # This block is for testing. Real execution is driven by main.py
