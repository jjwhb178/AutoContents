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

# ── 1. 제안 로직 (Multi-Proposal) ──────────────────────────────────────────
def propose_topics(data: dict) -> list:
    """뉴스를 분석하여 3개의 주제 후보를 제안합니다."""
    model = genai.GenerativeModel("gemini-2.5-pro", generation_config={"response_mime_type": "application/json"})
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
        res = model.generate_content(prompt)
        return json.loads(res.text).get("proposals", [])
    except Exception as e:
        print(f"  [Proposal Error] {e}")
        return []

# ── 2. 기획 생성 로직 (High-Density Assets) ──────────────────────────────
def agent_pro_generate(data: dict, score: float, pivot: dict | None, topic: str, feedback: str = "") -> dict:
    model = genai.GenerativeModel("gemini-2.5-pro", generation_config={"response_mime_type": "application/json"})
    data_json = json.dumps(data, ensure_ascii=False)
    
    pivot_inst = f"\n[수급 집중 섹터] 오늘 '{pivot['name']}' 섹터 거래량 {pivot['volume_ratio']:.1f}배 폭증. 이 테마를 결론부 타겟으로 활용할 것." if pivot else ""

    prompt = f"""당신은 대한민국 최고의 경제 분석 전문가이자 시스템 아키텍트인 '머니대디'의 수석 비서입니다. (Antigravity Ver 13.0)

[선정된 핵심 뉴스/주제]
주제: "{topic}"
{pivot_inst}

[보조 시장 데이터]
- 전체 수치: {data_json}
- 머니대디 스코어: {score} (50 이상 공격, 미만 방어)

아래 4가지 요구사항을 완벽히 수행하여 JSON 형식으로 반환하십시오.

**[Step 1: 블로그 작성 (O1_Blog 가이드 기반)]**
1. 서사적 통찰(Narrative 80%): 단순 뉴스 요약이 아닌 시스템 아키텍트적 견해와 인과관계 분석. 거시 분석에 차트 섞지 말고 철저히 분리.
2. 최적화 5단계 구조 (순수 본문 분량 2,500자 엄수. ※프롬프트 및 캡션 글자수는 이 2,500자에 포함되지 않습니다):
   - 도입(15%): 핵심 현상/뉴스 선언적 제시 (위기감 유도)
   - 본론(20%): 발생한 거시경제적 원인과 시스템적 타격 분석
   - 시황(15%): 특정 지표(예: 환율)가 시사하는 현실적 수급 이탈 등
   - 인사이트(35%): [핵심] 단기/장기 서바이벌 모드 등 시스템 아키텍트적 관점
   - 전략(15%): Price Action과 FVG를 활용한 특정 섹터/종목 정밀 타격 제안
3. 문단 사이에 이미지 삽입 위치를 [IMAGE_1_PLACEHOLDER], [IMAGE_2_PLACEHOLDER] 형식으로 4개 삽입하세요.

**[Step 2: 블로그 및 PPT 이미지 기획 (문맥 기반)]**
1. 블로그 본문의 Placeholder에 들어갈 이미지 프롬프트 4개와 캡션을 기획하세요.
2. 캡션은 반드시 **한글(Korean)**로 구체적으로 작성하세요.
3. 이미지 기획 시 한글/영어 텍스트나 숫자 등은 화면에 절대 나타나지 않게(No Text) 시각적 메타포에만 집중하세요.

**[Step 3: PPT 대본 작성 (O2_PPT_Design 및 O3_Video_Script 가이드 기반)]**
시각적 몰입도를 높이는 18페이지 '현상-원인-현실-해법-실전' 기승전결 레이아웃으로 설계.
전체 합산 3,500자(글자 수) 수준의 1.4배속 저음(Deep Bass) 전문가용 내레이션. (페이지당 150~250자)

[18P 범용 프레임워크 준수]
* 01P: [타이틀] 주제를 관통하는 메인 타이틀
* 02P: [현상 요약] 시장 기대를 꺾은 핵심 헤드라인
* 03P: [위기의 본질] 시스템 설계도의 파기 선언 등 본질
* 04P: [삭제된 소스코드] 기존 전망이 취소된 논리
* 05P: [자본 비용의 역습] 자본 비용 상승의 치명적 영향
* 06P: [커널 업데이트] 고금리 상시화 등 새 운영체제
* 07P: [임계점 지표] 환율, 금리 등 붕괴 경고 마지노선
* 08P: [수급 이탈] 자본 효율성에 따른 프로토콜 이동
* 09P: [지표 무력화] 매크로 서사 우선 시황
* 10P: [서바이벌 모드] 단기 변동성 제어법
* 11P: [뉴 노멀 재설계] 자산 가치 결정 새 기준점
* 12P: [투자 4원칙] 무너지지 않는 종목의 조건
* 13P: [원칙 심화 1,2] 압도적 수익성과 저부채
* 14P: [원칙 심화 3,4] 현금흐름과 독점적 지배력
* 15P: [유망 섹터] 하중을 견디고 성장하는 산업군
* 16P: [정밀 타격] Price Action 및 FVG 기반 타점
* 17P: [진입 시나리오] 변동성 활용 vs 가치 축적
* 18P: [아키텍트 조언] 시스템은 변해도 원칙은 불변

출력 조건:
- 'layout_type': "visual" (이미지 중심), "data" (데이터 중심), "warning" (경고장) 중 택1
- 'visual_elements': 텍스트 최소화. 핵심 수치/문구 3개 이내.

**[Step 4: 썸네일 기획]**
1. 이성적/감성적 프롬프트 기획 및 **한글 기획 의도** 작성.
2. 유튜브 설명란 텍스트.

출력 JSON 스키마:
{{
  "theme_analysis": "서사 요약",
  "title": "강력한 제목",
  "hashtags": "#키워드",
  "blog_draft": "도입~전략까지의 2500자 전문 리포트 본문 (Placeholder 포함)",
  "blog_images": [
    {{ "id": 1, "prompt": "영문 프롬프트 (No text)", "caption_ko": "한글 캡션/설명" }}, ...
  ],
  "ppt_script": {{
    "1": {{ "title": "슬라이드 제목", "layout_type": "visual", "visual_elements": ["문구1"], "audio_script": "풍부한 대본(200자 내외)" }},
    ... "18" 까지 완벽히 채울 것
  }},
  "thumbnail_prompts": {{
    "rational_prompt_en": "영문 프롬프트",
    "emotional_prompt_en": "영문 프롬프트",
    "concept_ko": "썸네일 기획 의도 및 시각적 묘사 (한글)"
  }},
  "youtube_desc": "유튜브 업로드용 텍스트"
}}"""
    
    if feedback:
        prompt += f"\n\n[사용자 피드백 (수정 요구사항)]\n{feedback}\n이 피드백을 최우선으로 반영하여 내용을 재구성하십시오."

    print("  [Agent 1] Generating High-Density Content Assets based on News Event...")
    for i in range(3):
        try:
            res = model.generate_content(prompt)
            # JSON 마크다운 블록 제거 (Robust parsing)
            raw_text = res.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            return json.loads(raw_text.strip())
        except Exception as e:
            print(f"  [Attempt {i+1}] Error: {e}"); time.sleep(5)
    sys.exit(1)

def agent_flash_verify(draft_json: dict, data: dict) -> dict:
    return draft_json # 검증 로직 간소화

def run_content_generation(data: dict, selected_topic: str, feedback: str = ""):
    score, pivot = calculate_moneydaddy_score(data), detect_sector_pivot(data)
    
    ai_result = agent_pro_generate(data, score, pivot, selected_topic, feedback)
    ai_result = agent_flash_verify(ai_result, data)
    
    title = ai_result.get("title", "머니대디 뷰: 오늘의 핵심 뉴스 분석")
    theme = ai_result.get("theme_analysis", "")
    
    blog_content = f"# {title}\n\n{ai_result.get('blog_draft', '')}"
    blog_final = clean_for_blog(blog_content + "\n\n" + ai_result.get('hashtags', '#머니대디'))
    
    with open("data/latest_content_logic.json", "w", encoding="utf-8") as f:
        json.dump({
            "score": score,
            "mood": "Attack" if score >= 50 else "Defense",
            "title": title,
            "theme_analysis": theme,
            "ppt_script": ai_result.get("ppt_script", {}),
            "blog_images": ai_result.get("blog_images", []),
            "thumbnail_prompts": ai_result.get("thumbnail_prompts", {}),
            "youtube_desc": ai_result.get("youtube_desc", "")
        }, f, indent=4, ensure_ascii=False)
        
    with open(get_path("daily_content_draft.md"), "w", encoding="utf-8") as f: 
        f.write(blog_final)
    
    return ai_result

if __name__ == "__main__":
    with open("data/raw_market_data.json", "r", encoding="utf-8") as f: data = json.load(f)
    print("Test running content generation...")
    # This block is for testing. Real execution is driven by main.py
