"""
Market Data Collector v2 — Phase 1
수집 항목:
  - VIX, US 10Y Yield, KOSPI, KOSDAQ, USD/KRW (yfinance)
  - CNN Fear & Greed (primary) → alternative.me 백업 API
  - 미국 주요 섹터 ETF 전일 수익률 (XLK, SOXX, XLF, XLV, XLE 등)
  - 한국 시장 주도 섹터 추정 (Naver Finance 간이 파싱)
"""
import json
import os
import requests
import yfinance as yf
from datetime import datetime
from bs4 import BeautifulSoup

# ── 네이버 금융 주요 뉴스 수집 ────────────────────────────────────────────────
def get_market_news():
    """
    네이버 금융의 주요 뉴스(시황) 헤드라인 및 이미지 URL 수집.
    """
    print("  Fetching market news headlines and images...")
    news_items = []
    r = None
    try:
        url = "https://finance.naver.com/news/mainnews.naver"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = "euc-kr"
        
        soup = BeautifulSoup(r.text, "html.parser")
        # 블록 단위로 파싱 (뉴스 1개당 보통 하나의 <ul>이나 <li> 구조이거나 dl > dt, dd)
        # 네이버 금융 메인 뉴스는 <div class="mainNewsList"> 혹은 <dl class="newsList"> 사용
        blocks = soup.select(".newsList")
        if not blocks:
            blocks = soup.select(".mainNewsList ul li")
            
        for dl in soup.select(".newsList"):
            # 뉴스 항목 찾기
            titles = dl.select("dd.articleSubject a")
            images = dl.select("dt.thumb img")
            
            # 매칭 로직 (단순화: 뉴스 개수만큼)
            for i, a_tag in enumerate(titles[:10]):
                title = a_tag.get_text(strip=True)
                img_url = None
                if i < len(images):
                    img_url = images[i].get("src")
                    
                news_items.append({
                    "title": title,
                    "img_url": img_url
                })
                
    except Exception as e:
        print(f"  [News] Failed to fetch headlines: {e}")
        
    # 기본 폴백: 만약 비어있다면 그냥 기존 방식 시도
    if not news_items:
        try:
            soup = BeautifulSoup(r.text, "html.parser")
            for s in soup.select("dd.articleSubject a")[:10]:
                news_items.append({"title": s.get_text(strip=True), "img_url": None})
        except:
            pass
            
    return news_items


# ── Fear & Greed: alternative.me (무료, 차단 없음) ────────────────────────
def get_fear_greed():
    try:
        r = requests.get(
            "https://api.alternative.me/fng/?limit=1",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        d = r.json()["data"][0]
        return int(d["value"]), d["value_classification"]
    except Exception as e:
        print(f"[Fear&Greed] Fallback failed: {e}")
        return None, "Unknown"


# ── 미국 섹터 ETF 수익률 ────────────────────────────────────────────────────
US_SECTOR_ETFS = {
    "반도체(SOXX)": "SOXX",
    "빅테크(QQQ)":  "QQQ",
    "금융(XLF)":    "XLF",
    "에너지(XLE)":  "XLE",
    "헬스케어(XLV)":"XLV",
    "AI/IT(XLK)":  "XLK",
}

def get_us_sector_returns():
    results = {}
    for name, ticker in US_SECTOR_ETFS.items():
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            if len(hist) >= 2:
                prev, curr = hist["Close"].iloc[-2], hist["Close"].iloc[-1]
                results[name] = round((curr - prev) / prev * 100, 2)
            else:
                results[name] = None
        except Exception:
            results[name] = None
    return results


# ── 실시간 주도 섹터 및 거래대금 1위 종목 수집 ───────────────────────────────
def get_realtime_sector_leaderboard(limit=3):
    """
    네이버 금융 테마 시세를 파싱하여 당일 주도 테마와 거래대금 1위 종목 정보를 반환합니다.
    """
    print(f"  Fetching realtime sector leaderboard (limit={limit})...")
    leaderboard = []
    try:
        url = "https://finance.naver.com/sise/theme.naver?field=change_price&ordering=desc"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4280.88 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = "euc-kr"
        
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.select_one("table.theme")
        if not table:
            print("  [Sector Leaderboard] Failed to find table.theme")
            return []
            
        rows = table.select("tr")
        count = 0
        for row in rows:
            if count >= limit:
                break
                
            a_tag = row.select_one("td.col_path a")
            if not a_tag:
                continue
                
            sector_name = a_tag.get_text(strip=True)
            href = a_tag.get("href")
            if not href:
                continue
                
            # 등락률 파싱
            change_pct = 0.0
            found_pct = False
            for td in row.select("td"):
                text = td.get_text(strip=True)
                if "%" in text:
                    try:
                        val_str = text.replace("%", "").replace("+", "").replace(",", "").strip()
                        change_pct = float(val_str)
                        found_pct = True
                        break
                    except ValueError:
                        pass
            if not found_pct:
                num_td = row.select_one("td.number")
                if num_td:
                    try:
                        val_str = num_td.get_text(strip=True).replace("+", "").replace(",", "").strip()
                        change_pct = float(val_str)
                    except ValueError:
                        pass
            
            # 상세 페이지 링크로 진입하여 거래대금 1위 종목 파싱
            detail_url = "https://finance.naver.com" + href
            try:
                dr = requests.get(detail_url, headers=headers, timeout=10)
                dr.encoding = "euc-kr"
                detail_soup = BeautifulSoup(dr.text, "html.parser")
                
                detail_rows = detail_soup.select("table.type_5 tr")
                stocks = []
                for d_row in detail_rows:
                    tds = d_row.select("td")
                    if len(tds) > 8:
                        a_stock = tds[0].select_one("a")
                        if not a_stock:
                            continue
                        stock_name = a_stock.get_text(strip=True)
                        val_str = tds[8].get_text(strip=True)
                        val_clean = val_str.replace(",", "").strip()
                        if not val_clean:
                            continue
                        try:
                            val_float = float(val_clean)
                            stocks.append({
                                "name": stock_name,
                                "value_num": val_float,
                                "value_str": val_str + "백만"
                            })
                        except ValueError:
                            pass
                
                if stocks:
                    stocks.sort(key=lambda x: x["value_num"], reverse=True)
                    top_stock = stocks[0]["name"]
                    top_stock_value = stocks[0]["value_str"]
                else:
                    top_stock = "N/A"
                    top_stock_value = "0백만"
                    
            except Exception as e:
                print(f"  [Sector Leaderboard] Failed to fetch details for {sector_name}: {e}")
                top_stock = "N/A"
                top_stock_value = "0백만"
                
            leaderboard.append({
                "sector": sector_name,
                "change_pct": change_pct,
                "top_stock": top_stock,
                "top_stock_value": top_stock_value
            })
            count += 1
            
    except Exception as e:
        print(f"  [Sector Leaderboard] Failed to fetch sector leaderboard: {e}")
        
    return leaderboard



def get_base_indicators():
    tickers = {
        "VIX":     "^VIX",
        "TNX_10Y": "^TNX",
        "USD_KRW": "KRW=X",
        "KOSPI":   "^KS11",
        "KOSDAQ":  "^KQ11",
        "NASDAQ":  "^IXIC",
        "SP500":   "^GSPC",
    }
    data = {}
    for name, t in tickers.items():
        try:
            hist = yf.Ticker(t).history(period="2d")
            if not hist.empty:
                data[name]         = round(hist["Close"].iloc[-1], 2)
                if len(hist) >= 2:
                    prev = hist["Close"].iloc[-2]
                    curr = hist["Close"].iloc[-1]
                    data[f"{name}_chg"] = round((curr - prev) / prev * 100, 2)
        except Exception as e:
            print(f"[{name}] Error: {e}")
    return data


def main():
    print("Phase 1: Collecting market data...")
    data = get_base_indicators()
    data["market_news"] = get_market_news()

    fg_val, fg_label = get_fear_greed()
    data["Fear_Greed"]        = fg_val
    data["Fear_Greed_Rating"] = fg_label
    print(f"  Fear & Greed: {fg_val} ({fg_label})")

    print("  Fetching US sector ETF returns...")
    data["us_sectors"] = get_us_sector_returns()

    print("  Fetching KR realtime sector leaderboard...")
    realtime_sectors = get_realtime_sector_leaderboard(limit=3)
    data["realtime_sectors"] = realtime_sectors

    # 하위 호환성 유지
    data["kr_sectors"] = {item["sector"]: item["change_pct"] for item in realtime_sectors}
    data["top_kr_sectors"] = [[item["sector"], item["change_pct"]] for item in realtime_sectors]
    data["bottom_kr_sectors"] = []

    data["timestamp"] = datetime.now().isoformat()

    # ── Sector Pivot: 거래량 폭증 섹터 감지 대체 (실시간 테마 매핑) ──────────────────
    print("  Mapping realtime sectors to volume surge (Sector Pivot)...")
    surges = [{"name": item["sector"], "volume_ratio": item["change_pct"]} for item in realtime_sectors]
    data["sector_volume_surge"] = surges
    if surges:
        print(f"  [PIVOT] 감지: {[s['name'] + ' x' + str(s['volume_ratio']) for s in surges]}")
    else:
        print("  [PIVOT] 해당 없음")

    # ── NaN 정제: yfinance가 반환하는 NaN/numpy 값을 None으로 변환 ──────────
    import math
    def _sanitize(obj):
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [_sanitize(i) for i in obj]
        elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        # numpy 타입을 Python 네이티브로 변환
        try:
            import numpy as np
            if isinstance(obj, (np.integer,)):
                return int(obj)
            elif isinstance(obj, (np.floating,)):
                val = float(obj)
                return None if math.isnan(val) else val
        except ImportError:
            pass
        return obj

    data = _sanitize(data)

    os.makedirs("data", exist_ok=True)
    with open("data/raw_market_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"  Saved: data/raw_market_data.json")
    print(f"  Top KR sectors: {data['top_kr_sectors']}")
    print("Phase 1 complete.")


if __name__ == "__main__":
    main()
