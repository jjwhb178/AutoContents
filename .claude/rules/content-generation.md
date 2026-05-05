# Rule: Content Generation (MoneyDaddy Voice & SEO)

## Context
This rule defines the linguistic and structural standards for all generated content (Blog, PPT, Video Scripts).

## 1. The MoneyDaddy Voice
- **Tone**: Aggressive but logical, authoritative but humble (expert humility), "Sexy Logic".
- **Key Phrases**: 
  - "이건 제 분석이 틀릴 시나리오입니다." (Expert humility)
  - "지금은 공격할 때입니다." (Aggressive)
  - "숫자는 거짓말을 하지 않습니다." (Data-driven)
- **Formatting**: Use bold text for key conclusions. Use bullet points for "Today's Action Items".

## 2. Naver Blog SEO
- **Keywords**: Place primary keywords (e.g., '오늘의 주식전망', '머니대디') in the first 100 words.
- **Images**: Always specify at least 3 chart placeholders.
- **Hooking Title**: Start with a controversial or high-impact statement. 
  - *Example*: "미국 국채 금리 폭등, 그런데 이 섹터만 살아남는 이유"

## 3. PPT Scripting
- **One Slide, One Idea**: Keep text per slide minimal.
- **Visual Description**: Every slide must have a [Visual Description] tag indicating what the background image or chart should be.
- **The Score Page**: Slide 15 MUST explain exactly how the MoneyDaddy Score was calculated today.

## 4. Hallucination Prevention
- Cross-check all numbers (VIX, KOSPI levels) against `data/raw_market_data.json`.
- If a number is missing or `null`, explicitly state "데이터 수집 중" or use a conservative estimate with a warning.
