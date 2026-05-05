# SW 구현사양서 (Software Implementation Specification)
**프로젝트명:** MoneyDaddy AI Content Factory  
**기준 문서:** 02_SW_Architecture_Specification.md  
**문서 버전:** 1.0  
**작성일:** 2026-05-01  

---

## 1. 개요

본 문서는 아키텍처 사양서에 정의된 컴포넌트를 실제 코드로 구현하기 위한 상세 스펙을 기술한다. 각 모듈의 함수 시그니처, 알고리즘, 데이터 변환 규칙, GAP 분석 및 구현 우선순위를 정의한다.

---

## 2. 모듈별 구현 상세

### 2.1 market_data_collector.py

#### 현황 및 GAP
| 기능 | 구현 상태 | GAP |
|------|----------|-----|
| 글로벌 지수 수집 (yfinance) | 구현 완료 | - |
| 미국 섹터 ETF 6종 수집 | 구현 완료 | - |
| KR 섹터 대표주 수익률 | 구현 완료 | - |
| Fear & Greed (alternative.me) | 구현 완료 | - |
| **Sector Pivot 감지** | **미구현** | sector_volume_surge 키 생성 로직 추가 필요 |

#### 구현 필요: detect_volume_surge()

```python
def detect_volume_surge(threshold: float = 1.5) -> list[dict]:
    """
    전일 대비 거래량이 threshold배 이상인 KR 섹터를 감지.
    yfinance의 Volume 컬럼을 활용.
    반환: [{"name": "로봇/자동화", "volume_ratio": 2.1}, ...]
    """
    surges = []
    for name, ticker in KR_SECTOR_TICKERS.items():
        try:
            hist = yf.Ticker(ticker).history(period="3d")
            if len(hist) >= 2:
                prev_vol = hist["Volume"].iloc[-2]
                curr_vol = hist["Volume"].iloc[-1]
                if prev_vol > 0:
                    ratio = round(curr_vol / prev_vol, 2)
                    if ratio >= threshold:
                        surges.append({"name": name, "volume_ratio": ratio})
        except Exception:
            pass
    return sorted(surges, key=lambda x: x["volume_ratio"], reverse=True)
```

main() 함수 내 아래 라인 추가:
```python
data["sector_volume_surge"] = detect_volume_surge(threshold=1.5)
```

---

### 2.2 content_generator.py

#### 현황 및 GAP
| 기능 | 구현 상태 | GAP |
|------|----------|-----|
| detect_anchor() | 구현 완료 | - |
| calculate_moneydaddy_score() | 구현 완료 | - |
| detect_sector_pivot() | 구현 완료 | market_data_collector의 sector_volume_surge 데이터 필요 |
| build_title() with Pivot | 구현 완료 | - |
| agent_pro_generate() | 구현 완료 | 모델 ID 최신 확인 필요 |
| agent_flash_verify() | 구현 완료 | - |
| clean_for_blog() 이미지 보호 | 구현 완료 | - |

#### 핵심 함수 스펙

**detect_anchor(data: dict) -> dict**
- 후보: NASDAQ_chg, VIX_chg, USD_KRW_chg, top_kr_sector 수익률
- 선정 기준: abs() 값이 가장 큰 수치
- 반환: {label, value, abs, direction, stats_line}

**calculate_moneydaddy_score(data: dict) -> float**
```
Score = (100 - Fear_Greed) × 0.40
      + max(0, 40 - VIX) × 2.5 × 0.20
      + k_flow_normalized × 5 × 0.30
      + tech_align × 100 × 0.10

k_flow = avg(top_kr_returns) × 2, clamp(-10, 10)
tech_align = (SOXX_chg + 5) / 10, clamp(0.0, 1.0)
```

**agent_pro_generate() 프롬프트 구조**
```text
[역할 선언]: Antigravity Ver 10.0 에이전트 (머니대디 수석 비서/시스템 아키텍트 페르소나)
[입력 데이터]: score, anchor, pivot, title, raw_json
[Sector Pivot 지시] (pivot 감지 시 조건부 삽입)
[Ver 10.0 가이드라인]:
  - Macro 80% + FVG 20% (단, 섹터/종목 분석용 렌즈 분리일 뿐 투자 비중 이원화 의도 아님)
  - 블로그: 3~4줄 단락 분리, 핵심 통찰 볼드, 텍스트/숫자 없는 순수 이미지 4종 플레이스홀더 (Slate Blue 톤)
  - 대본: 기승전결 18p 구조 (기 1~3, 승 4~9, 전 10~15, 결 16~18), [轉] 구간에 분량 50% 집중
  - 대본 페르소나: 라이브 해설가 모드, 3000자 이상, 1:1 슬라이드 동기화([Slide XX]), 1.4배속 단호한 어투, 괄호 제거
[JSON 스키마]: {blog_draft, ppt_script: {1~18: {title, body, visual}}}
```

**agent_flash_verify() 검증 항목**
- 검증 수치: VIX, NASDAQ_chg, SP500_chg, TNX_10Y, USD_KRW, Fear_Greed, KOSPI
- 검증 방식: 원본 수치가 블로그 초안 텍스트에 정확히 반영되었는지 LLM 판단
- 반환: {is_clean: bool, issues_found: list, blog_draft: str}

---

### 2.3 text_cleaner.py

#### 현황 및 GAP
| 기능 | 구현 상태 | 비고 |
|------|----------|------|
| bracket_purge() | 구현 완료 | TTS 전용 |
| phonetic_convert() | 구현 완료 | TTS 전용 |
| staccato_split() | 구현 완료 | TTS 전용 |
| clean_for_tts() | 구현 완료 | - |
| clean_for_blog() | 개선 완료 | 이미지 플레이스홀더 보호 추가 |

#### clean_for_blog() 처리 순서
```
1. re.sub(r'\[이미지\d[^\]]*\]', protect)  ← 플레이스홀더 토큰화 보호
2. re.sub(r'\([^)]*\)', '')               ← 소괄호 제거
3. deduplication()                        ← 중복 단어 제거
4. 기호 변환 (↑→상승, ↓→하락)
5. 플레이스홀더 복원
```

---

### 2.4 pptx_generator.py

#### 현황 및 GAP
| 기능 | 구현 상태 | GAP |
|------|----------|-----|
| 18페이지 생성 | 구현 완료 | - |
| 검정 배경 + 흰 제목 | 구현 완료 | - |
| 14p 히트맵 삽입 | 구현 완료 | - |
| **슬레이트 블루 & 골드 컬러 팔레트** | **미구현** | 제목 색상을 골드로, 배경 그라데이션 적용 필요 |
| **핵심 수치 거대 배치 (Anchor)** | **미구현** | 1p에 오늘의 Anchor 수치를 초대형 폰트로 배치 필요 |

#### 구현 필요: 1p 썸네일 슬라이드 Anchor 수치 거대 배치
```python
# 1p 처리 시 Anchor 수치를 별도 텍스트박스로 초대형 배치
from pptx.util import Pt, Emu
GOLD = RGBColor(212, 175, 55)  # 골드 컬러

if page_num == 1:
    # Anchor 수치 거대 텍스트 (오른쪽 하단)
    anchor_val = logic.get("anchor", {}).get("value", "")
    txBox = slide.shapes.add_textbox(Inches(5), Inches(3), Inches(4), Inches(2))
    tf = txBox.text_frame
    tf.text = anchor_val
    tf.paragraphs[0].font.size = Pt(72)
    tf.paragraphs[0].font.color.rgb = GOLD
    tf.paragraphs[0].font.bold = True
```

---

### 2.5 tts_generator.py

#### 현황 및 GAP
| 기능 | 구현 상태 | 비고 |
|------|----------|------|
| gTTS 한국어 생성 | 구현 완료 | - |
| FFmpeg atempo 1.4배속 | **수정 완료** | 1.2 → 1.4 수정됨 |
| 슬라이드별 MP3 | 구현 완료 | - |
| full_narration.mp3 | 구현 완료 | - |

#### atempo 제약 사항
- FFmpeg atempo 필터는 단일 필터로 0.5~2.0 범위만 지원
- 1.4배속은 단일 atempo=1.4로 처리 가능 (범위 내)
- 2.0 초과 필요 시 체인 방식 필요: atempo=2.0,atempo=X

---

### 2.6 verification_loop.py

#### 현황 및 GAP
| 기능 | 구현 상태 | GAP |
|------|----------|-----|
| VIX, TNX_10Y 텍스트 검증 | 구현 완료 | - |
| **확장 검증 항목** | **미구현** | NASDAQ_chg, USD_KRW, top_kr_sectors 추가 필요 |
| **Dual-Agent 검증과 연계** | **미구현** | Agent 2의 issues_found를 리포트에 포함 필요 |

#### 구현 필요: 확장 검증 항목
```python
# 현재: VIX, TNX_10Y만 검증
# 추가 필요:
VERIFY_KEYS = [
    ("VIX", "VIX"),
    ("TNX_10Y", "US 10Y Yield"),
    ("USD_KRW", "달러-원 환율"),
    ("NASDAQ_chg", "나스닥"),
    ("Fear_Greed", "공포/탐욕"),
]
```

---

### 2.7 visual_generator.py / thumbnail_generator.py / video_synthesizer.py

#### 현황 및 GAP
| 모듈 | 기능 | 구현 상태 |
|------|------|----------|
| visual_generator | 히트맵, QR 생성 | 구현 완료 |
| thumbnail_generator | A/B 2종 썸네일 | 구현 완료 |
| video_synthesizer | PPTX→PNG→MP4 Dynamic Sync | 구현 완료 |

---

## 3. 구현 GAP 요약 및 우선순위

| 우선순위 | 모듈 | GAP 항목 | 예상 공수 |
|---------|------|----------|----------|
| **P1 (즉시)** | market_data_collector | sector_volume_surge 거래량 수집 추가 | 30분 |
| **P1 (즉시)** | verification_loop | 검증 항목 확장 (NASDAQ, USD/KRW, Fear&Greed) | 20분 |
| **P2 (단기)** | pptx_generator | 슬레이트 블루 & 골드 컬러 팔레트 적용 | 1시간 |
| **P2 (단기)** | pptx_generator | 1p Anchor 수치 초대형 배치 | 30분 |
| **P3 (중기)** | 전체 | .gitignore 설정, docs/ 폴더 정리 | 10분 |

---

## 4. 텍스트 변환 규칙 (No-Bracket Filter + Phonetic)

### 4.1 대본용 (clean_for_tts)
| 원본 | 변환 |
|------|------|
| S&P500 | 에스앤피 오백 |
| SOXX | 에스오엑스엑스 |
| VIX | 빅스 |
| XLK | 엑스엘케이 |
| FVG | 에프브이지 |
| % | 퍼센트 |
| +3.5 | 플러스 3.5 |
| -1.2 | 마이너스 1.2 |
| ↑ | 상승 |
| ↓ | 하락 |
| () 내용 | 전체 삭제 |

### 4.2 블로그용 (clean_for_blog)
| 처리 항목 | 규칙 |
|----------|------|
| [이미지N: ...] | 보호 (삭제 금지) |
| () 소괄호 내용 | 삭제 |
| MD 기호 (#, -, *) | AI 프롬프트로 생성 단계에서 배제 (post-process 아님) |
| ↑↓ 기호 | 상승/하락 치환 |

---

## 5. API 호출 스펙

### 5.1 Gemini Agent 1 (생성)
```
모델: gemini-2.5-pro-preview-05-06
response_mime_type: application/json
입력 토큰 예상: ~2,000 tokens (raw_data JSON + 프롬프트)
출력 토큰 예상: ~4,000 tokens (blog_draft + 18p 대본)
```

### 5.2 Gemini Agent 2 (검증)
```
모델: gemini-1.5-flash
response_mime_type: application/json
입력 토큰 예상: ~1,500 tokens
출력 토큰 예상: ~300 tokens
```

### 5.3 일일 호출량 및 무료 한도
| 항목 | 일일 호출 | 무료 한도 |
|------|---------|----------|
| Agent 1 (Pro) | 1~2회 | 50회/일 |
| Agent 2 (Flash) | 1~2회 | 1,500회/일 |
| 여유율 | 97% 이상 | 안전 |

---

## 6. 에러 처리 규칙

| 상황 | 처리 방법 |
|------|----------|
| yfinance 수집 실패 | None으로 저장, 수치 표시 시 "N/A" 출력 |
| Gemini API 호출 실패 | sys.exit(1)으로 파이프라인 즉시 중단 + history.json 기록 |
| Agent 2 검증 실패 | 경고 출력 + 원본 콘텐츠 유지 (파이프라인 계속) |
| gTTS 실패 | 해당 슬라이드 음성 Skip (None 반환) |
| FFmpeg 배속 실패 | 원본 속도(1.0x) 파일로 폴백 |
| 네이버/유튜브 발행 실패 | Skip + history.json SKIPPED 기록 |

---

## 7. 테스트 시나리오

| 테스트 | 방법 | 성공 기준 |
|--------|------|----------|
| Phase 1 단독 실행 | python src/market_data_collector.py | data/raw_market_data.json 생성 |
| Phase 2b 단독 실행 | python src/content_generator.py | daily_content_draft.md 생성, 대본 3500자+ |
| Sector Pivot 발동 | raw_market_data.json에 sector_volume_surge 수동 삽입 후 Phase 2b 실행 | 제목과 서사가 해당 섹터 중심으로 전환됨 확인 |
| 이미지 플레이스홀더 보존 | clean_for_blog() 단독 테스트 | [이미지N: ...] 4개 모두 보존 |
| TTS 배속 확인 | Phase 4 실행 후 MP3 재생 | 1.4배속으로 재생됨 |
| 전체 파이프라인 | python main.py | Phase 1~6 모두 [OK], outputs 폴더에 산출물 생성 |
