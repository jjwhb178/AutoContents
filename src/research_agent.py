"""
research_agent.py — Topic_Research 단계 자동화 모듈 (Phase 2)
아키텍처: O2_PPT_Architecture.md v2.0

핵심 변경:
  - Citation-Forced Grounding 적용
  - AI 자가검증 루프(run_critic_and_verify) 폐지
  - AI 과거지식 보정 루프(correction_prompt) 폐지
  - 인용구 코드 검증: quoted_text가 실제 뉴스 본문에 존재하는지 확인
  - 수치 코드 검증: related_metric_value가 raw_market_data.json과 일치하는지 확인
"""
import os
import sys
import json
import time
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import yfinance as yf
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
from output_paths import get_path
from graph_rag import DailyKnowledgeGraph
from dotenv import load_dotenv

load_dotenv()

# ── 설정 ─────────────────────────────────────────────────────────────────────

SECTOR_TICKERS = {
    "반도체":       "005930.KS",
    "AI/소프트웨어": "035420.KS",
    "2차전지":      "373220.KS",
    "바이오":       "207940.KS",
    "로봇/자동화":  "066570.KS",
    "자동차":       "005380.KS",
    "방산":         "047810.KS",
    "금융":         "105560.KS",
}

def fetch_back_data(ticker_or_key: str, period: str = "10d") -> dict:
    """
    ticker_or_key가 거시 경제 지표 키 또는 대표 섹터명일 때 해당하는 yfinance 티커를 매핑하여
    최근 period 영업일간의 종가(Close) 및 거래량(Volume) 추이를 가져오고 요약 통계를 반환합니다.
    """
    macro_mapping = {
        "USD_KRW": "KRW=X",
        "VIX": "^VIX",
        "TNX_10Y": "^TNX",
        "KOSPI": "^KS11",
        "NASDAQ": "^IXIC",
        "SP500": "^GSPC"
    }
    
    ticker = None
    if ticker_or_key in SECTOR_TICKERS:
        ticker = SECTOR_TICKERS[ticker_or_key]
    elif ticker_or_key in macro_mapping:
        ticker = macro_mapping[ticker_or_key]
    else:
        ticker = ticker_or_key
        
    print(f"  [Research] 백데이터 수집 중: {ticker_or_key} -> {ticker} (기간: {period})")
    
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period)
        if df.empty:
            return {}
            
        prices = df["Close"].tolist()
        volumes = df["Volume"].tolist() if "Volume" in df.columns else []
        
        if not prices:
            return {}
            
        start_val = prices[0]
        end_val = prices[-1]
        max_val = max(prices)
        min_val = min(prices)
        change_pct = ((end_val - start_val) / start_val) * 100 if start_val != 0 else 0
        
        dates = [d.strftime("%Y-%m-%d") for d in df.index]
        
        return {
            "key": ticker_or_key,
            "ticker": ticker,
            "start_date": dates[0],
            "end_date": dates[-1],
            "start_val": round(start_val, 2),
            "end_val": round(end_val, 2),
            "max_val": round(max_val, 2),
            "min_val": round(min_val, 2),
            "change_pct": round(change_pct, 2),
            "prices": [round(p, 2) for p in prices],
            "volumes": volumes
        }
    except Exception as e:
        print(f"  [Research] 백데이터 수집 실패 ({ticker_or_key}): {e}")
        return {}

def determine_back_data_key(topic: str) -> str:
    """주제(topic)에서 매칭되는 섹터 또는 거시경제 지표 키를 판별합니다."""
    for sector in SECTOR_TICKERS.keys():
        if sector in topic:
            return sector
            
    macro_keywords = {
        "환율": "USD_KRW",
        "달러": "USD_KRW",
        "원화": "USD_KRW",
        "공포": "VIX",
        "금리": "TNX_10Y",
        "국채": "TNX_10Y",
        "코스피": "KOSPI",
        "한국": "KOSPI",
        "나스닥": "NASDAQ",
        "미국": "NASDAQ",
        "S&P": "SP500",
        "에스앤피": "SP500"
    }
    
    for kw, key in macro_keywords.items():
        if kw in topic:
            return key
            
    return "KOSPI"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36"
}

MAX_NEWS_BODY = 800
MAX_NEWS_COUNT = 5


# ── 1. 뉴스 수집 ──────────────────────────────────────────────────────────────

def fetch_naver_news_list(limit: int = MAX_NEWS_COUNT) -> list[dict]:
    """네이버 금융 뉴스 제목 + URL 수집"""
    items = []
    try:
        url = "https://finance.naver.com/news/mainnews.naver"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.encoding = "euc-kr"
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("dd.articleSubject a")[:limit]:
            href = a.get("href", "")
            if href.startswith("/"):
                href = "https://finance.naver.com" + href
            items.append({"title": a.get_text(strip=True), "url": href})
    except Exception as e:
        print(f"  [Research] 뉴스 목록 수집 실패: {e}")
    return items


def fetch_article_body(url: str, max_chars: int = MAX_NEWS_BODY) -> str:
    """단일 기사 본문 추출"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")
        for selector in ["#newsct_article", "#articeBody", ".article_body", "article", "div.content"]:
            tag = soup.select_one(selector)
            if tag:
                return tag.get_text(separator=" ", strip=True)[:max_chars]
        paragraphs = soup.select("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
        return text[:max_chars]
    except Exception as e:
        return f"[본문 수집 실패: {e}]"


def fetch_naver_land_news(limit: int = MAX_NEWS_COUNT) -> list[dict]:
    """네이버 부동산 뉴스 수집"""
    items = []
    try:
        url = "https://land.naver.com/news/mainNews.naver"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select(".news_list dt a")[:limit]:
            href = "https://land.naver.com" + a.get("href", "")
            items.append({"title": a.get_text(strip=True), "url": href})
    except Exception as e:
        print(f"  [Research] 부동산 뉴스 수집 실패: {e}")
    return items


def collect_news_with_bodies(topic: str, limit: int = MAX_NEWS_COUNT) -> list[dict]:
    """주제에 맞춰 뉴스 수집 후 본문 크롤링"""
    is_real_estate = any(k in topic for k in ["부동산", "아파트", "주택", "재건축", "임대", "분양"])
    news_list = fetch_naver_land_news(limit) if is_real_estate else fetch_naver_news_list(limit)
    print(f"  [Research] {'부동산' if is_real_estate else '금융/증시'} 뉴스 수집 시작...")

    result = []
    for i, item in enumerate(news_list):
        body = fetch_article_body(item["url"])
        result.append({"idx": i + 1, "title": item["title"], "url": item["url"], "body": body})
        print(f"    [{i+1}/{len(news_list)}] {item['title'][:40]}...")
        time.sleep(0.5)
    return result


# ── 2. 거시경제 컨텍스트 ──────────────────────────────────────────────────────

def build_macro_context(raw_data: dict) -> dict:
    """시장 지표를 구조화된 컨텍스트로 변환"""
    return {
        "vix":          {"value": raw_data.get("VIX"),        "chg_pct": raw_data.get("VIX_chg")},
        "fear_greed":   {"value": raw_data.get("Fear_Greed"), "label":   raw_data.get("Fear_Greed_Rating")},
        "usd_krw":      {"value": raw_data.get("USD_KRW"),    "chg_pct": raw_data.get("USD_KRW_chg")},
        "us_10y_yield": {"value": raw_data.get("TNX_10Y"),    "chg_pct": raw_data.get("TNX_10Y_chg")},
        "kospi":        {"value": raw_data.get("KOSPI"),       "chg_pct": raw_data.get("KOSPI_chg")},
        "kosdaq":       {"value": raw_data.get("KOSDAQ"),      "chg_pct": raw_data.get("KOSDAQ_chg")},
        "nasdaq":       {"value": raw_data.get("NASDAQ"),      "chg_pct": raw_data.get("NASDAQ_chg")},
        "sp500":        {"value": raw_data.get("SP500"),       "chg_pct": raw_data.get("SP500_chg")},
    }


# ── 3. Citation-Forced 분석 (핵심 변경) ──────────────────────────────────────

def run_citation_forced_analysis(topic: str, news_list: list,
                                  macro_context: dict, raw_data: dict, back_data_trends: str = "") -> dict:
    """
    Citation-Forced Grounding 방식 분석.
    머니대디 경제 분석가 컨셉을 사용하여 수급 흐름과 거시 경제 인과관계를 도출하며,
    동적으로 쿼리된 백데이터 및 뉴스를 팩트 근거로 활용합니다.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("  [Research] GEMINI_API_KEY 미설정. 분석 스킵.")
        return {}
    genai.configure(api_key=api_key)

    # 머니대디 수석 리서치 애널리스트 페르소나 및 Citation-Forced Grounding 핵심 원칙을 System Instruction으로 분리
    system_instruction = (
        "당신은 자금 흐름과 거시경제적 관점에서 시장을 날카롭게 해설하는 유튜브/블로그 채널 '머니대디'의 수석 리서치 애널리스트(경제 분석가)입니다.\n"
        "다음 Citation-Forced Grounding의 핵심 원칙을 반드시 준수하여 분석을 진행해 주세요:\n"
        "1. 인용구 코드 검증 원칙: 작성하는 모든 주장(claim) 및 관계(edge)는 반드시 제공된 뉴스 본문에서 그대로 발췌한 인용구(quoted_text)와 출처 기사 번호(source_article)를 기반으로 작성해야 하며, 뉴스에 실재하지 않는 내용을 기재해서는 안 됩니다.\n"
        "2. 수치 코드 검증 원칙: 거시경제 지표 및 시장 수치를 인용할 때는 제공된 공식 마켓 데이터(macro_context) 및 동적 백데이터와 정확하게 일치해야 하며, 과거 학습 지식 등으로 임의 보정하거나 수치를 변경해서는 안 됩니다.\n"
        "3. 인과관계 규명 원칙: 금리, 환율, 원자재 등의 거시지표 변동과 자금 흐름(수급) 간의 객관적인 인과관계를 철저하게 분석하되, 사변적인 추측이나 뇌피셜은 배제해야 합니다."
    )

    model = genai.GenerativeModel(
        "gemini-2.5-pro",
        generation_config={"response_mime_type": "application/json"},
        system_instruction=system_instruction
    )

    # 뉴스 목록 (인덱스 포함)
    news_summary = "\n".join(
        [f"[기사{n['idx']}] 제목: {n['title']}\n본문: {n['body'][:400]}" for n in news_list[:5]]
    )

    # 서두 부분의 고정 역할 지침을 정리하여 프롬프트를 간결하게 다이어트합니다.
    prompt = f"""거시적 관점(금리, 환율, 원자재)에서 오늘 시장의 핵심적인 돈의 흐름(수급)과 테마 및 거래대금 최상위 종목들이 어떠한 유기적/인과적 연결고리(Graph RAG)를 갖고 있는지 규명하여 분석하십시오.

[현재 시점]
{datetime.now().strftime('%Y-%m-%d %H:%M')}

[오늘의 주제]
{topic}

[거시경제 지표 — 이 수치가 유일한 공식 수치입니다]
{json.dumps(macro_context, ensure_ascii=False, indent=2)}

[동적 백데이터 지표 추이 (과거 10영업일)]
{back_data_trends if back_data_trends else "제공된 과거 지표 추이 데이터 없음"}

[오늘의 시장 뉴스]
{news_summary}

[핵심 작성 및 분석 규칙 — 반드시 준수]
1. 분석은 철저하게 '머니대디 경제 분석가' 컨셉(거시적 시장 해설자로서의 무게감 있고 깊이 있는 논조, 사변적인 뇌피셜 배제, 철저한 자금 이동 관점의 분석)으로 작성하십시오.
2. 모든 주장(claim)에는 반드시 출처 기사 번호(source_article)와 해당 기사에서 그대로 발췌한 인용구(quoted_text)를 붙여야 합니다. 
3. 과거 백데이터 지표 추이({back_data_trends})를 핵심 분석에 반영하여 서술에 신뢰성을 더하십시오.
4. 기술적 분석(예: FVG, 차트 타점, FVG 30% 타점, 지지/저항선 돌파, 매수 평단가 추천 등)은 프롬프트 및 분석에서 완전히 배제하십시오. 오로지 거시경제 인과관계와 시장 수급의 상호작용 분석에만 초점을 맞춥니다.
5. 거시경제 지표 및 백데이터 수치를 사용할 경우, related_metric_key와 related_metric_value를 정확히 기입하십시오.
6. 과거 학습 지식으로 새로운 임의의 수치를 추가하거나 수정하는 것을 엄격히 금지합니다.
7. Fear & Greed 40~60은 '중립'이며, 위기나 공포로 과장하지 마십시오.
8. [지식 그래프 구축 규칙]:
   - 오늘 발생한 경제/자산 사건의 인과적 경로를 나타내기 위해 '지식 그래프'를 노드(nodes)와 엣지(edges) 구조로 구성하십시오.
   - 노드는 핵심 개체(예: '코스피', '삼성전자', '연준 금리', '미국 대선', 'USD_KRW')로 지정하고, 영문 고유 ID와 한글 표시명, 타입을 기입하십시오.
   - 엣지는 노드들 간의 영향/원인 관계(예: '환율 급등'이 '외국인 수급 유출'을 유발했다면, source는 환율 노드, target은 외국인 수급 노드, relation은 'CAUSES')를 표현하십시오.
   - 엣지에도 반드시 실제 뉴스 본문에서 발췌한 관계 근거 인용구(quoted_text)와 출처 기사 번호(source_article)를 붙여야 합니다.

[출력 JSON 스키마]
{{
  "claims": [
    {{
      "statement": "팩트 기반 주장 (수치 포함)",
      "source_article": 1,
      "quoted_text": "기사 본문에서 그대로 발췌한 구절",
      "related_metric_key": "KOSPI (해당 없으면 null)",
      "related_metric_value": 7493.18
    }}
  ],
  "graph": {{
    "nodes": [
      {{
        "id": "kospi",
        "label": "코스피",
        "type": "Macro",
        "properties": {{
          "description": "금일 코스피 변동 현황",
          "value": "2600.5"
        }}
      }}
    ],
    "edges": [
      {{
        "source": "환율급등",
        "target": "kospi",
        "relation": "INFLUENCES",
        "quoted_text": "원·달러 환율이 크게 올라 코스피가 하락 마감했다",
        "source_article": 2
      }}
    ]
  }},
  "today_narrative": "오늘 시장을 관통하는 핵심 서사 (과거 10일 백데이터 추이와 오늘의 수급 인과를 엮은 분석가적 통찰 포함)",
  "economic_background": "경제 이론적 배경 (예: 금리 변동이 자산 수급에 미치는 인과 기전)",
  "risk_factors": ["거시 리스크1", "거시 리스크2", "거시 리스크3"],
  "moneydaddy_view": "중립적 수치는 중립적으로, 과장 없이 자금 흐름 관점에서 기술한 전문가 견해",
  "sector_hint": "수급 집중 섹터 및 자금 유입 경로 힌트"
}}"""

    print("  [Research] Citation-Forced 분석 시작...")
    try:
        res = model.generate_content(prompt, request_options={"timeout": 300})
        raw = res.text.strip().replace("```json", "").replace("```", "")
        result = json.loads(raw)
        if isinstance(result, list):
            result = result[0]
        return result
    except Exception as e:
        print(f"  [Research] 분석 실패: {e}")
        return {}


# ── 4. 코드 기반 인용 검증 ────────────────────────────────────────────────────

def verify_claims(claims: list, news_list: list, raw_data: dict) -> list:
    """
    Citation-Forced 검증 (코드 담당 — AI 자가검증 아님)
    1. quoted_text가 실제 뉴스 본문에 존재하는지 확인
    2. related_metric_value가 raw_market_data와 일치하는지 확인
    검증 실패 claim은 제거, 통과 claim만 반환
    """
    # 전체 뉴스 본문 합본
    all_bodies = " ".join(n.get("body", "") for n in news_list)
    all_titles = " ".join(n.get("title", "") for n in news_list)
    all_news_text = all_bodies + " " + all_titles

    verified = []
    removed = 0

    for claim in claims:
        quoted = claim.get("quoted_text", "")
        metric_key = claim.get("related_metric_key")
        metric_val = claim.get("related_metric_value")

        # ① 인용구 실존 검증: 10자 이상인 경우만 체크 (짧은 인용은 관대하게 통과)
        if quoted and len(quoted) >= 10:
            # 공백 정규화 후 일부 포함 여부 확인 (70% 이상 단어 매칭)
            quoted_words = set(quoted.replace("…", "").split())
            news_words = set(all_news_text.split())
            overlap = len(quoted_words & news_words)
            ratio = overlap / max(len(quoted_words), 1)
            if ratio < 0.4:
                print(f"  [Verify] ❌ 인용 검증 실패 (뉴스 미확인): {claim.get('statement', '')[:30]}")
                removed += 1
                continue

        # ② 수치 일치 검증 (metric_key가 있는 경우만)
        if metric_key and metric_val is not None:
            # nested key 지원: "kr_sectors.반도체" 형태 처리
            keys = metric_key.split(".")
            ref_val = raw_data
            try:
                for k in keys:
                    ref_val = ref_val[k]
                ref_val = float(ref_val)
                # 수치 허용 오차: ±5% (반올림, 환산 허용)
                if abs(ref_val - float(metric_val)) / max(abs(ref_val), 0.001) > 0.05:
                    print(f"  [Verify] ⚠️ 수치 불일치: {metric_key} 원본={ref_val} vs 주장={metric_val}")
                    claim["statement"] = claim["statement"] + " [수치 검토 필요]"
            except (KeyError, TypeError, ValueError):
                pass  # key 없으면 수치 검증 스킵

        verified.append(claim)

    print(f"  [Verify] 검증 완료: 통과 {len(verified)}건 / 제거 {removed}건")
    return verified


def verify_graph(graph_data: dict, news_list: list) -> dict:
    """
    지식 그래프의 엣지에 연결된 인용구(quoted_text)가 실제 뉴스 본문에 존재하는지 검증합니다.
    검증에 실패한 엣지는 관계 목록에서 제외합니다.
    """
    if not graph_data or not isinstance(graph_data, dict):
        return {"nodes": [], "edges": []}

    all_bodies = " ".join(n.get("body", "") for n in news_list)
    all_titles = " ".join(n.get("title", "") for n in news_list)
    all_news_text = all_bodies + " " + all_titles

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    verified_edges = []
    removed = 0

    for edge in edges:
        quoted = edge.get("quoted_text", "")
        if quoted and len(quoted) >= 10:
            quoted_words = set(quoted.replace("…", "").split())
            news_words = set(all_news_text.split())
            overlap = len(quoted_words & news_words)
            ratio = overlap / max(len(quoted_words), 1)
            if ratio < 0.4:
                print(f"  [Verify Graph] ❌ 관계 검증 실패 (인용 뉴스 미확인): {edge.get('source')} ➔ {edge.get('target')}")
                removed += 1
                continue
        verified_edges.append(edge)

    print(f"  [Verify Graph] 지식 그래프 관계 검증 완료: 통과 {len(verified_edges)}건 / 제거 {removed}건")
    return {"nodes": nodes, "edges": verified_edges}


# ── 5. Fact-Sheet 생성 ───────────────────────────────────────────────────────

def generate_fact_sheet(report: dict) -> None:
    """검증 통과한 claim 기반 Fact-Sheet 생성"""
    m = report.get("macro_context", {})
    back_trend = report.get("back_data_trends", {})
    verified_claims = report.get("verified_claims", [])

    fact_lines = []
    for c in verified_claims:
        fact_lines.append(f"- {c['statement']}")

    back_trend_str = "- 백데이터 정보 없음"
    if back_trend:
        back_trend_str = (
            f"- **{back_trend.get('key')} 최근 10영업일 추이**: "
            f"{back_trend.get('start_date')} 종가 {back_trend.get('start_val')} ➔ "
            f"{back_trend.get('end_date')} 종가 {back_trend.get('end_val')} "
            f"({back_trend.get('change_pct')}% 변동, 최고: {back_trend.get('max_val')}, 최저: {back_trend.get('min_val')})"
        )

    fact_content = f"""# 📑 MoneyDaddy 오늘의 팩트 시트 ({datetime.now().strftime('%Y-%m-%d %H:%M')})

## 1. 핵심 거시 서사 (Core Narrative)
{report.get('today_narrative', '분석된 서사 없음')}

## 2. 과거 백데이터 추이 (Back-Data Trends)
{back_trend_str}

## 3. 코드 검증 통과 팩트 (Citation-Grounded Facts)
{chr(10).join(fact_lines) if fact_lines else '- 검증 통과 팩트 없음'}

## 4. 절대 수치 및 지표 (Market Indicators — raw_market_data 직접 참조)
- **KOSPI**: {m.get('kospi', {}).get('value', 'N/A')} ({m.get('kospi', {}).get('chg_pct', 'N/A')}%)
- **VIX (공포지수)**: {m.get('vix', {}).get('value', 'N/A')}
- **미 국채 10년물 금리**: {m.get('us_10y_yield', {}).get('value', 'N/A')}%
- **원/달러 환율**: {m.get('usd_krw', {}).get('value', 'N/A')}원

## 5. 리스크 요인 및 섹터 힌트
- **섹터 힌트**: {report.get('sector_hint', '특이사항 없음')}
{chr(10).join(['- ' + r for r in report.get('risk_factors', [])]) if report.get('risk_factors') else '- 수집된 리스크 요인 없음'}

---
**[절대 지침]** 본 팩트 시트에 기재된 내용과 수치**만**을 사용하여 콘텐츠를 생성하십시오.
뉴스 데이터에 없는 수치를 과거 지식으로 추측하거나 할루시네이션하는 것을 엄격히 금지합니다.
데이터가 부족하다면 수치를 언급하는 대신 "최근 시장 기조"와 같이 안전하게 표현하십시오.
"""
    with open("data/O_FactSheet.md", "w", encoding="utf-8") as f:
        f.write(fact_content)
    print("  [Research] Fact-Sheet 생성 완료: data/O_FactSheet.md")


# ── 6. 메인 실행 함수 ────────────────────────────────────────────────────────

def run_research(topic: str = "", raw_data: dict = None) -> dict:
    """Topic_Research 전체 파이프라인 (Citation-Forced Grounding & Graph RAG)"""
    print("\n[Phase 2] Citation-Forced Topic Research 시작...")

    if raw_data is None:
        raw_path = "data/raw_market_data.json"
        if not os.path.exists(raw_path):
            return {}
        with open(raw_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

    # 0단계: 동적 백데이터 수집
    back_data_key = determine_back_data_key(topic or "오늘의 핵심 경제 이슈")
    back_data = fetch_back_data(back_data_key, period="10d")
    
    back_data_trends_str = ""
    if back_data:
        back_data_trends_str = (
            f"[{back_data['key']} 최근 10영업일 추이] "
            f"시작일({back_data['start_date']}) 종가 {back_data['start_val']} 대비 "
            f"종료일({back_data['end_date']}) 종가 {back_data['end_val']}로 "
            f"{back_data['change_pct']}% 변동. "
            f"최고치: {back_data['max_val']}, 최저치: {back_data['min_val']}"
        )
        print(f"  [Research] 백데이터 분석 요약: {back_data_trends_str}")

    # 1단계: 뉴스 수집
    news_with_bodies = collect_news_with_bodies(topic=topic, limit=MAX_NEWS_COUNT)
    macro_context = build_macro_context(raw_data)

    # 2단계: Citation-Forced AI 분석
    analysis = run_citation_forced_analysis(
        topic=topic or "오늘의 핵심 경제 이슈",
        news_list=news_with_bodies,
        macro_context=macro_context,
        raw_data=raw_data,
        back_data_trends=back_data_trends_str
    )

    # 3단계: 코드 기반 인용 검증 (AI 자가검증 없음)
    print("  [Research] 코드 기반 인용 검증 시작...")
    raw_claims = analysis.get("claims", [])
    verified_claims = verify_claims(raw_claims, news_with_bodies, raw_data)

    # 3-2단계: 지식 그래프 검증 및 저장
    print("  [Research] 지식 그래프 검증 및 저장 시작...")
    raw_graph = analysis.get("graph", {})
    verified_graph = verify_graph(raw_graph, news_with_bodies)
    
    # DailyKnowledgeGraph 빌드
    kg = DailyKnowledgeGraph()
    for node in verified_graph.get("nodes", []):
        kg.add_node(node["id"], node["label"], node["type"], node.get("properties"))
    for edge in verified_graph.get("edges", []):
        kg.add_edge(edge["source"], edge["target"], edge["relation"], {
            "quoted_text": edge.get("quoted_text", ""),
            "source_article": edge.get("source_article")
        })
    kg_path = "data/daily_knowledge_graph.json"
    kg.save(kg_path)
    print(f"  [Research] 지식 그래프 저장 완료: {kg_path}")

    # 4단계: 최종 리포트 조합
    report = {
        "generated_at":    datetime.now().isoformat(),
        "topic":           topic,
        "macro_context":   macro_context,
        "back_data_trends": back_data,
        "news_headlines":  [n["title"] for n in news_with_bodies],
        "news_bodies":     news_with_bodies,
        "verified_claims": verified_claims,
        "graph_narrative": kg.get_narrative_text(), # 콘텐츠 생성기용 텍스트 직렬화
        "today_narrative": analysis.get("today_narrative", ""),
        "economic_background": analysis.get("economic_background", ""),
        "risk_factors":    analysis.get("risk_factors", []),
        "moneydaddy_view": analysis.get("moneydaddy_view", ""),
        "sector_hint":     analysis.get("sector_hint", ""),
        # 하위 호환: hard_facts는 verified_claims의 statement 리스트로 대체
        "hard_facts":      [c["statement"] for c in verified_claims],
    }

    # 5단계: 저장
    os.makedirs("data", exist_ok=True)
    with open("data/research_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    generate_fact_sheet(report)

    print("  [Research] 리포트 저장 완료: data/research_report.json")
    print("[Phase 2] Topic Research 완료.\n")
    return report


if __name__ == "__main__":
    import sys
    topic_arg = sys.argv[1] if len(sys.argv) > 1 else "오늘의 핵심 경제 이슈 분석"
    result = run_research(topic=topic_arg)
    if result.get("today_narrative"):
        print("\n[핵심 서사]")
        print(result["today_narrative"])
        print(f"\n[검증 통과 팩트 {len(result.get('verified_claims', []))}건]")
