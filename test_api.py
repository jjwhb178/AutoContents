"""Diagnose content_generator prompt size and API call"""
from dotenv import load_dotenv
load_dotenv()
import os, sys, json
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
sys.path.insert(0, "src")
from content_generator import (
    detect_sector_pivot,
    calculate_moneydaddy_score
)

with open("data/raw_market_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Fix NaN values
import math
def clean_nan(d):
    if isinstance(d, dict):
        return {k: clean_nan(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [clean_nan(i) for i in d]
    elif isinstance(d, float) and math.isnan(d):
        return None
    return d

data = clean_nan(data)

score = calculate_moneydaddy_score(data)
pivot = detect_sector_pivot(data)

print(f"Score: {score}")
print(f"Pivot: {pivot}")

# Check prompt size
data_json = json.dumps(data, ensure_ascii=False)
print(f"\nData JSON size: {len(data_json)} chars")

# Try using the new Gemini 3 Flash model
model = genai.GenerativeModel(
    "gemini-3-pro-preview",
    generation_config={"response_mime_type": "application/json"}
)

simple_prompt = f"""
당신은 금융 콘텐츠 생성 AI입니다.

시장 데이터: {data_json}
머니대디 스코어: {score}점

아래 JSON 형식으로 블로그 초안과 PPT 대본(18페이지)을 생성하세요.
블로그는 거시 경제 서사 70%, FVG 타점 30%로 구성하세요.
대본은 구어체 라이브 해설가 모드이고, 괄호와 기호를 모두 제거하세요.

JSON:
{{
  "blog_draft": "블로그 본문 (2000자 이상, 이미지 플레이스홀더 4개 포함)",
  "ppt_script": {{
    "1": {{"title": "제목", "body": "대본", "visual": "시각자료 설명"}},
    "2": {{"title": "...", "body": "...", "visual": "..."}},
    ...
    "18": {{"title": "...", "body": "...", "visual": "..."}}
  }}
}}
"""

print(f"Prompt size: {len(simple_prompt)} chars")
print("\nCalling API...")

try:
    response = model.generate_content(simple_prompt)
    text = response.text
    print(f"Response length: {len(text)} chars")
    result = json.loads(text)
    print(f"Keys: {list(result.keys())}")
    if "ppt_script" in result:
        print(f"PPT pages: {list(result['ppt_script'].keys())}")
    if "blog_draft" in result:
        print(f"Blog length: {len(result['blog_draft'])} chars")
    print("\n[SUCCESS] Content generation works!")
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")
