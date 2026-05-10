import sys, os, json, time
import google.generativeai as genai

sys.path.insert(0, os.path.dirname(__file__))
from output_paths import get_path
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

def calculate_moneydaddy_score(data: dict) -> float:
    fear_greed = data.get("Fear_Greed", 50)
    vix = data.get("VIX", 15)
    k_flow = data.get("kr_sectors", {}).get("반도체", 0) or 0
    soxx = data.get("us_sectors", {}).get("반도체(SOXX)", 0) or 0
    return round((100 - fear_greed) * 0.4 + max(0, 40 - vix) * 0.5 + (k_flow + 5) * 2 + (soxx + 5) * 1.5, 1)

# ── API Helper with Retry ───────────────────────────────────────────────────
def call_gemini_with_retry(model, prompt, retries=3, delay=10):
    """API 호출 실패 시 지수 백오프를 사용하며, 429 오류 시 Flash 모델로 자동 전환합니다."""
    current_model = model
    # 응답 형식을 유지하기 위한 설정 보존
    is_json = "application/json" in str(getattr(model, "_generation_config", ""))
    
    for i in range(retries):
        try:
            response = current_model.generate_content(prompt, request_options={"timeout": 1200})
            return response
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Quota exceeded" in error_msg:
                print(f"  [Quota Alert] Switching to Flash model... (Attempt {i+1}/{retries})")
                # 안전한 설정을 사용하여 Flash 모델로 교체
                config = {"response_mime_type": "application/json"} if is_json else {}
                current_model = genai.GenerativeModel("gemini-1.5-flash", generation_config=config)
                continue

            if i < retries - 1:
                print(f"  [API Error] {e}. Retrying in {delay}s... ({i+1}/{retries})")
                time.sleep(delay)
                delay *= 2
            else:
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
    model = genai.GenerativeModel("gemini-3-flash-preview", generation_config={"response_mime_type": "application/json"})
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
        res = call_gemini_with_retry(model, prompt)
        return json.loads(res.text).get("proposals", [])
    except Exception as e:
        print(f"  [Proposal Error] {selected_topic if 'selected_topic' in locals() else 'Topic Proposal'} failed: {e}")
        return []

# ── 2. 기획 생성 로직 (High-Density Assets) ──────────────────────────────
# ── 2. 기획 생성 로직 (High-Density Assets) ──────────────────────────────
def agent_plan_structure(data: dict, score: float, pivot: dict | None, topic: str, feedback: str = "") -> dict:
    """Step 1: 전체적인 서사 구조와 슬라이드별 핵심 논리를 기획합니다."""
    model = genai.GenerativeModel("gemini-3-flash-preview", generation_config={"response_mime_type": "application/json"})
    
    # [데이터 필터링] 주제와 관련이 적은 데이터는 제거하거나 비중을 낮춤
    filtered_data = {
        "Fear_Greed": data.get("Fear_Greed"),
        "top_kr_sectors": data.get("top_kr_sectors"),
        "sector_volume_surge": data.get("sector_volume_surge")
    }
    # 주제에 '환율'이나 '달러'가 포함된 경우에만 환율 데이터를 비중 있게 포함
    if any(k in topic for k in ["환율", "달러", "USD", "외환"]):
        filtered_data["USD_KRW"] = data.get("USD_KRW")
        filtered_data["USD_KRW_chg"] = data.get("USD_KRW_chg")

    pivot_inst = f"\n[수급 집중 섹터] 오늘 '{pivot['name']}' 섹터 거래량 {pivot['volume_ratio']:.1f}배 폭증. 이 테마를 결론부 타켓으로 활용할 것." if pivot else ""

    prompt = f"""당신은 머니대디의 수석 전략가입니다. 주제 "{topic}"에 대한 18페이지 PPT와 2,500자 블로그의 **구조 설계도**를 작성하세요.
    
[시장 상황 요약]
{json.dumps(filtered_data, ensure_ascii=False)}
머니대디 점수: {score}
{pivot_inst}

[임무]
1. 18페이지 PPT의 페이지별 '핵심 메시지'와 '시각적 의도'를 정의하세요.
2. 블로그의 5단계(도입-원인-현상-인사이트-전략)별 핵심 논리를 설계하세요.
3. 지표(환율 등)는 주제와 직접 연관이 있을 때만 언급하고, 아니면 철저히 배제하세요.

출력 JSON 스키마:
{{
  "structure_id": "unique_id",
  "theme_narrative": "이 콘텐츠가 관통하는 하나의 거대한 서사",
  "ppt_structure": [
    {{ "page": 1, "topic": "제목", "core_logic": "이 페이지에서 반드시 전달해야 할 논리" }},
    ... (18페이지까지)
  ],
  "blog_structure": {{
    "intro_logic": "...", "cause_logic": "...", "market_logic": "...", "insight_logic": "...", "strategy_logic": "..."
  }}
}}"""

    print("  [Step 1] Planning Content Structure...")
    res = call_gemini_with_retry(model, prompt)
    return json.loads(res.text.strip().replace("```json", "").replace("```", ""))

def agent_write_blog(structure: dict, data: dict, topic: str) -> dict:
    """Step 2: 설계도를 바탕으로 블로그 본문을 집중적으로 작성합니다 (2,500자+)."""
    model = genai.GenerativeModel("gemini-3-pro-preview", generation_config={"response_mime_type": "application/json"})
    guides = load_guides()
    
    prompt = f"""당신은 머니대디의 수석 에디터입니다. [구조 설계도]를 바탕으로 **블로그 본문**을 작성하세요.
    
[가이드라인]
{guides.get('O1_blog.md', '')}

[구조 설계도]
{json.dumps(structure, ensure_ascii=False)}

[제작 지침]
1. **분량**: 순수 본문만 **2,500자 이상**으로 작성하세요.
2. **구성**: 도입-원인-현상-인사이트-전략 5단계를 심도 있게 다룹니다.
3. **이미지**: [IMAGE_1_PLACEHOLDER] ~ [IMAGE_4_PLACEHOLDER] 토큰을 문맥에 맞게 배치하세요.

출력 JSON 스키마:
{{
  "title": "강력한 제목 (브랜드명/머니대디 언급 금지)",
  "blog_draft": "2500자 이상의 블로그 전문",
  "blog_images": [ {{ "id": 1, "prompt": "영문", "caption_ko": "한글" }}, ... ]
}}"""

    print("  [Step 2] Writing Blog Content (2,500 chars target)...")
    res = call_gemini_with_retry(model, prompt)
    return json.loads(res.text.strip().replace("```json", "").replace("```", ""))

def agent_write_ppt(structure: dict, data: dict, topic: str) -> dict:
    """Step 3: 설계도를 바탕으로 18페이지 PPT 대본 및 디자인 설계를 수행합니다 (3,500자+)."""
    model = genai.GenerativeModel("gemini-3-pro-preview", generation_config={"response_mime_type": "application/json"})
    guides = load_guides()
    
    prompt = f"""당신은 머니대디 시스템의 수석 프레젠테이션 디자이너이자 에디터입니다. [구조 설계도]를 바탕으로 **18페이지 PPT 대본**을 작성하세요.
    
[디자인 및 대본 가이드라인]
{guides.get('O2_PPT_VisionDesign.md', '')}
{guides.get('O3_Video_Script.md', '')}

[구조 설계도]
{json.dumps(structure, ensure_ascii=False)}

[제작 지침]
1. **분량**: 18페이지 전체 합산 **3,500자 이상**의 고밀도 대본을 작성하세요.
2. **태그 삽입**: 각 슬라이드 시작 전 반드시 `[Slide XX]` 태그를 삽입하세요.
3. **가중치**: 가이드라인에 따라 Slide 10~14(인사이트 구간)에 약 1,000자 이상을 집중 배치합니다.
4. **디자인 제안**: 각 슬라이드별로 가이드라인의 6가지 레이아웃 중 하나를 선택하고 시각적 계층을 정의하세요.

출력 JSON 스키마:
{{
  "ppt_script": {{
    "1": {{ 
      "title": "슬라이드 제목", 
      "layout_type": "레이아웃 번호(1~6)", 
      "visual_elements": ["요소1", "요소2"], 
      "audio_script": "상세 대본 (구어체, 괄호 제거)" 
    }},
    ... (18번까지)
  }},
  "thumbnail_prompts": {{ "rational_prompt_en": "...", "emotional_prompt_en": "...", "concept_ko": "..." }},
  "youtube_desc": "..."
}}"""

    print("  [Step 3] Writing PPT Script (3,500 chars target)...")
    res = call_gemini_with_retry(model, prompt)
    return json.loads(res.text.strip().replace("```json", "").replace("```", ""))

def agent_pro_generate(data: dict, score: float, pivot: dict | None, topic: str, feedback: str = "") -> dict:
    # 3-Step Hybrid Generation (Stability Patch)
    structure = agent_plan_structure(data, score, pivot, topic, feedback)
    
    # 블로그와 PPT 생성을 분리하여 API 부하 분산
    blog_data = agent_write_blog(structure, data, topic)
    ppt_data  = agent_write_ppt(structure, data, topic)
    
    # 최종 결과 합치기
    result = {**blog_data, **ppt_data}
    result["theme_analysis"] = structure.get("theme_narrative", "")
    return result

def agent_flash_verify(draft_json: dict, data: dict) -> dict:
    return draft_json # 검증 로직 간소화

def run_content_generation(data: dict, selected_topic: str, feedback: str = ""):
    score, pivot = calculate_moneydaddy_score(data), detect_sector_pivot(data)
    
    # [1단계] 구조 기획 및 즉시 저장
    structure = agent_plan_structure(data, score, pivot, selected_topic, feedback)
    with open("data/latest_content_logic.json", "w", encoding="utf-8") as f:
        json.dump({"status": "planning_done", "structure": structure}, f, indent=4, ensure_ascii=False)
    print("  [Checkpoint] Structure planning saved.")

    # [2단계] 블로그 작성 및 즉시 저장
    blog_data = agent_write_blog(structure, data, selected_topic)
    title = blog_data.get("title", "머니대디 분석 리포트")
    blog_content = f"# {title}\n\n{blog_data.get('blog_draft', '')}"
    blog_final = clean_for_blog(blog_content)
    
    with open(get_path("daily_content_draft.md"), "w", encoding="utf-8") as f:
        f.write(blog_final)
    print("  [Checkpoint] Blog draft saved to outputs.")

    # [3단계] PPT 작성 및 최종 통합 저장
    ppt_data = agent_write_ppt(structure, data, selected_topic)
    
    final_result = {
        "score": score,
        "mood": "Attack" if score >= 50 else "Defense",
        "title": title,
        "theme_analysis": structure.get("theme_narrative", ""),
        "ppt_script": ppt_data.get("ppt_script", {}),
        "blog_images": blog_data.get("blog_images", []),
        "thumbnail_prompts": ppt_data.get("thumbnail_prompts", {}),
        "youtube_desc": ppt_data.get("youtube_desc", "")
    }
    
    with open("data/latest_content_logic.json", "w", encoding="utf-8") as f:
        json.dump(final_result, f, indent=4, ensure_ascii=False)
    
    print("  [Final] All content logic successfully integrated and saved.")
    return final_result

if __name__ == "__main__":
    with open("data/raw_market_data.json", "r", encoding="utf-8") as f: data = json.load(f)
    print("Test running content generation...")
    # This block is for testing. Real execution is driven by main.py
