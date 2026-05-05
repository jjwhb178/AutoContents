# SW 아키텍처 사양서 (Software Architecture Specification)
**프로젝트명:** MoneyDaddy AI Content Factory  
**기준 문서:** 01_SW_Requirements_Specification.md  
**문서 버전:** 1.0  
**작성일:** 2026-05-01  

---

## 1. 아키텍처 개요

본 시스템은 **순차적 단계(Phase) 파이프라인** 아키텍처를 채택한다. 각 Phase는 독립적인 Python 모듈로 구현되며, `main.py`가 오케스트레이터(Orchestrator) 역할을 담당한다.

```
[main.py: Orchestrator]
       │
       ├─ Phase 1 : market_data_collector.py   (데이터 수집)
       ├─ Phase 2a: visual_generator.py        (히트맵·QR 생성)
       ├─ Phase 2b: content_generator.py       (AI 콘텐츠 생성 — Dual-Agent)
       ├─ Phase 3a: pptx_generator.py          (PPT 합성)
       ├─ Phase 3b: verification_loop.py       (수치 검증)
       ├─ Phase 4 : tts_generator.py           (TTS 1.4배속)
       ├─ Phase 5 : thumbnail_generator.py     (A/B 썸네일)
       ├─ Phase 6 : video_synthesizer.py       (영상 합성 MP4)
       ├─ [Optional] Phase 7: naver_blog_poster.py
       └─ [Optional] Phase 8: youtube_uploader.py
```

---

## 2. 레이어 구조

```
┌─────────────────────────────────────────────────────┐
│  Presentation Layer  (outputs/YYYY-MM-DD/)          │
│  .md / .pptx / .mp4 / .png / .mp3                  │
├─────────────────────────────────────────────────────┤
│  Application Layer  (src/)                          │
│  content_generator ← Dual-Agent 핵심               │
│  pptx_generator / tts_generator / video_synthesizer│
│  thumbnail_generator / visual_generator             │
├─────────────────────────────────────────────────────┤
│  Domain Layer  (src/)                               │
│  market_data_collector / verification_loop          │
│  text_cleaner / output_paths                        │
├─────────────────────────────────────────────────────┤
│  Infrastructure Layer                               │
│  Google Gemini API / yfinance / gTTS / FFmpeg       │
│  Naver Blog Session / YouTube Data API v3           │
└─────────────────────────────────────────────────────┘
```

---

## 3. 컴포넌트 상세 설계

### 3.1 Orchestrator (main.py)
- **역할:** Phase별 subprocess 호출, 성공/실패 판단, 히스토리 로깅
- **실패 정책:**
  - Core Phase(1~6): 실패 시 즉시 파이프라인 중단 + history.json 에러 기록
  - Optional Phase(7~8): 실패 시 SKIP + 파이프라인 계속
- **출력:** 콘솔 진행 상황, data/history.json

### 3.2 Phase 1 — market_data_collector.py
- **역할:** 외부 API 수집 → raw_market_data.json 저장
- **데이터 소스:**
  - yfinance: VIX(^VIX), US10Y(^TNX), USD/KRW(KRW=X), KOSPI(^KS11), KOSDAQ(^KQ11), NASDAQ(^IXIC), S&P500(^GSPC)
  - yfinance: US 섹터 ETF 6종 (SOXX, QQQ, XLK, XLF, XLE, XLV)
  - yfinance: KR 섹터 대표주 8종 (대리 지수 활용)
  - alternative.me API: CNN Fear & Greed 지수
- **Sector Pivot 감지:** sector_volume_surge 키에 거래량 비율 1.5배 이상 섹터 기록
- **출력:** data/raw_market_data.json

### 3.3 Phase 2a — visual_generator.py
- **역할:** 섹터 히트맵 이미지 생성, QR 코드 생성
- **출력:** outputs/YYYY-MM-DD/market_heatmap.png, qr_blog.png

### 3.4 Phase 2b — content_generator.py (핵심 AI 엔진)

#### Dual-Agent 흐름
```
raw_market_data.json
        │
   [Pre-processing]
   ├─ detect_anchor()       : 최대 변동성 수치 선정
   ├─ detect_sector_pivot() : 거래량 1.5배 폭증 섹터 감지
   ├─ calculate_score()     : 머니대디 스코어 산출
   └─ build_title()         : Pivot 유무에 따른 제목 생성
        │
   [Agent 1: Gemini 2.5 Pro] ── 생성 에이전트
   ├─ 입력: score, anchor, pivot, title, raw_data
   ├─ 처리: 거시 서사 80% + FVG 20%(투자 비중 이원화 아님) + 기승전결 18p 대본(전 10~15p 50% 비중) + 블로그 이미지 제약(텍스트 배제)
   └─ 출력: {blog_draft, ppt_script{1~18}}
        │
   [Agent 2: Gemini 1.5 Flash] ── 검증 에이전트
   ├─ 입력: Agent 1 결과 + key_figures(VIX, NASDAQ 등)
   ├─ 처리: 수치 교차 검증, 오류 수정
   └─ 출력: {is_clean, issues_found, blog_draft(수정본)}
        │
   [Post-processing]
   ├─ clean_for_blog()     : 이미지 플레이스홀더 보호 + 소괄호 제거
   └─ 해시태그 15개 자동 삽입
        │
   [저장]
   ├─ data/latest_content_logic.json  (PPT 대본, 스코어 등)
   └─ outputs/YYYY-MM-DD/daily_content_draft.md
```

#### 머니대디 스코어 산출 공식
```
Score = (100 - Fear_Greed) × 0.40
      + max(0, 40 - VIX) × 2.5 × 0.20
      + k_flow_normalized × 0.30
      + tech_align × 0.10

k_flow     = avg(top_kr_sector_returns) × 2  [범위 -10~+10]
tech_align = (SOXX_chg + 5) / 10             [범위 0.0~1.0]
```

### 3.5 Phase 3a — pptx_generator.py
- **역할:** latest_content_logic.json의 ppt_script 기반 18페이지 PPTX 생성
- **디자인:** 검정 배경(0F0F0F), 흰색 제목, 회색 본문(C8C8C8), 24pt
- **특이사항:** 14p에 market_heatmap.png 자동 삽입
- **출력:** outputs/YYYY-MM-DD/daily_strategy_v2_5.pptx

### 3.6 Phase 3b — verification_loop.py
- **역할:** VIX, US10Y 수치가 블로그 초안에 정확히 언급되었는지 텍스트 검증
- **출력:** outputs/YYYY-MM-DD/verification_report.md

### 3.7 Phase 4 — tts_generator.py
- **역할:** PPT 대본 텍스트 → gTTS → FFmpeg 1.4배속 처리
- **처리 순서:** clean_for_tts() → gTTS(ko) → atempo=1.4 → 슬라이드별 MP3 + full_narration.mp3
- **출력:** outputs/YYYY-MM-DD/audio/

### 3.8 Phase 5 — thumbnail_generator.py
- **역할:** 오늘의 핵심 수치/키워드로 썸네일 2종 생성
- **출력:** thumbnail_A_rational.png, thumbnail_B_emotional.png

### 3.9 Phase 6 — video_synthesizer.py
- **역할:** PPTX 슬라이드 → PNG 변환 → 슬라이드별 오디오 길이에 맞춰 Dynamic Sync → FFmpeg MP4 합성
- **Sync 정밀도:** 0.1초 단위
- **출력:** outputs/YYYY-MM-DD/daily_video.mp4

### 3.10 Phase 7 — naver_blog_poster.py (Optional)
- **역할:** session_data.json 기반 자동 로그인 → 블로그 포스팅
- **자격증명:** .env 또는 data/session_data.json

### 3.11 Phase 8 — youtube_uploader.py (Optional)
- **역할:** YouTube Data API v3로 MP4 업로드
- **자격증명:** .env의 YouTube OAuth 토큰

---

## 4. 데이터 흐름 다이어그램

```
[yfinance / alternative.me]
          │
          ▼
  raw_market_data.json
          │
    ┌─────┴──────┐
    ▼            ▼
heatmap.png   content_generator
qr_blog.png       │
    │         [Agent 1: Pro]
    │             │ blog_draft + ppt_script
    │         [Agent 2: Flash]
    │             │ 수치 검증
    │         latest_content_logic.json
    │         daily_content_draft.md
    │             │
    └────┬────────┘
         ▼
    pptx_generator
    daily_strategy_v2_5.pptx
         │
    tts_generator
    audio/*.mp3
         │
    video_synthesizer
    daily_video.mp4
         │
    thumbnail_generator
    thumbnail_A/B.png
         │
    [Optional]
    naver_blog_poster → 네이버 블로그
    youtube_uploader  → YouTube
```

---

## 5. 공유 유틸리티 모듈

| 모듈 | 역할 |
|------|------|
| output_paths.py | 날짜 기반 출력 경로 일관 관리 (outputs/YYYY-MM-DD/) |
| text_cleaner.py | bracket_purge / phonetic_convert / staccato_split / clean_for_tts / clean_for_blog |

---

## 6. 외부 의존성

| 의존성 | 용도 | 비용 |
|--------|------|------|
| google-generativeai | Gemini 2.5 Pro / 1.5 Flash API | 무료 티어 |
| yfinance | 글로벌 시장 데이터 수집 | 무료 |
| alternative.me API | Fear & Greed 지수 | 무료 |
| gTTS | 한국어 TTS 음성 생성 | 무료 |
| FFmpeg / imageio-ffmpeg | 음성 배속 처리, 영상 합성 | 무료 |
| python-pptx | PPTX 파일 생성 | 무료 |
| opencv-python | 이미지 처리, 슬라이드 PNG 변환 | 무료 |
| python-dotenv | .env 환경 변수 로드 | 무료 |

---

## 7. 환경 설정

### 7.1 디렉토리 구조
```
AutoContents/
├── main.py                    # 오케스트레이터
├── .env                       # API 키 (gitignore)
├── data/
│   ├── raw_market_data.json   # Phase 1 출력
│   ├── latest_content_logic.json  # Phase 2b 출력
│   └── history.json           # 파이프라인 실행 이력
├── src/
│   ├── market_data_collector.py
│   ├── visual_generator.py
│   ├── content_generator.py
│   ├── pptx_generator.py
│   ├── verification_loop.py
│   ├── tts_generator.py
│   ├── thumbnail_generator.py
│   ├── video_synthesizer.py
│   ├── naver_blog_poster.py
│   ├── youtube_uploader.py
│   ├── output_paths.py
│   └── text_cleaner.py
└── outputs/
    └── YYYY-MM-DD/
        ├── daily_content_draft.md
        ├── daily_strategy_v2_5.pptx
        ├── daily_video.mp4
        ├── thumbnail_A_rational.png
        ├── thumbnail_B_emotional.png
        ├── verification_report.md
        ├── market_heatmap.png
        └── audio/
            ├── slide_01.mp3 ~ slide_18.mp3
            └── full_narration.mp3
```

### 7.2 환경 변수 (.env)
```
GEMINI_API_KEY=...
NAVER_ID=...
NAVER_PW=...
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
```
