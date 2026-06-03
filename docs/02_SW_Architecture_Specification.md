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
       ├─ Phase 2 : content_generator.py       (AI 콘텐츠 생성 — Dual-Agent)
       ├─ Phase 3 : verification_loop.py       (수치 검증)
       ├─ Phase 4 : visual/thumbnail/imagen_generator.py (시각 자료 및 썸네일 생성)
       ├─ Phase 5 : remotion_orchestrator.py   (TTS 생성 및 Remotion 비디오 생성)
       ├─ [Optional] Phase 6: naver_blog_poster.py
       └─ [Optional] Phase 7: youtube_uploader.py
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
│  remotion_orchestrator / thumbnail_generator        │
│  visual_generator                                   │
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
  - Core Phase(1~5): 실패 시 즉시 파이프라인 중단 + history.json 에러 기록
  - Optional Phase(6~7): 실패 시 SKIP + 파이프라인 계속
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

### 3.3 Phase 2 — content_generator.py (신규 아키텍처: Fact-Grounding)

#### Fact-Blueprint 파이프라인
```
raw_market_data.json
        │
    [O_FactSheet.md 생성] ── 리서치 기반 절대적 팩트 고정
        │
    [Step 1: Blueprint Planning] ── Gemini 2.5 Flash
    ├─ 팩트 시트 기반 18p 논리 설계 (Blueprint MD)
    └─ 레이아웃 제약 없는 자유 구조 기획
        │
    [Step 2: Blog & PPT Script] ── Gemini 2.5 Pro
    ├─ 블루프린트 기반 고밀도 대본 집필
    └─ [Dynamic Canvas Engine]으로 데이터 전달
```

### 3.4 Phase 3 — verification_loop.py
- **역할:** VIX, US10Y 수치가 블로그 초안에 정확히 언급되었는지 텍스트 검증
- **출력:** outputs/YYYY-MM-DD/verification_report.md

### 3.5 Phase 4 — visual_generator.py, thumbnail_generator.py & imagen_generator.py
- **역할:** 시각 자료(히트맵/QR/차트), 하이브리드 방식의 썸네일 2종 및 AI 배경 이미지 생성
- **로직:**
  - `visual_generator.py`: 섹터 히트맵 이미지 및 블로그용 QR 코드 생성
  - `thumbnail_generator.py`: assets/ 내 AI 생성 배경을 로드하여 PIL로 제목 및 강조 텍스트 합성 (썸네일 A/B 생성)
  - `imagen_generator.py`: 구글 Imagen 3 API를 활용하여 인공지능 썸네일 및 블로그 본문용 이미지 생성
- **출력:** outputs/YYYY-MM-DD/market_heatmap.png, thumbnail_A_rational.png, thumbnail_B_emotional.png

### 3.6 Phase 5 — remotion_orchestrator.py
- **역할:** TTS 생성, 오디오 길이 기반 씽크 연동 및 동적 렌더링 일괄 처리
- **핵심 로직:**
  - **TTS 생성:** 대본 텍스트를 기반으로 나레이션 음성 파일 자동 생성 (Neural TTS)
  - **오디오 길이 기반 씽크 연동:** 각 슬라이드/씬의 오디오 길이를 측정하여 Remotion 프로젝트의 비디오 타임라인 프레임 길이를 동적으로 계산 및 매핑
  - **동적 렌더링:** React 기반 Remotion 프레임워크를 구동하여 비디오 에셋과 자막, 나레이션을 합성한 후 최종 MP4 동영상 파일로 다이렉트 렌더링
- **출력:** outputs/YYYY-MM-DD/daily_video.mp4

### 3.7 Phase 6 — naver_blog_poster.py (Optional)
- **역할:** session_data.json 기반 자동 로그인 → 블로그 포스팅
- **자격증명:** .env 또는 data/session_data.json

### 3.8 Phase 7 — youtube_uploader.py (Optional)
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
    visual/thumbnail/imagen_generator
    heatmap.png / thumbnail_A/B.png
         │
    remotion_orchestrator
    daily_video.mp4
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
| Node.js & Remotion | React 기반 비디오 컴포지션 및 렌더링 프레임워크 | 무료 |
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
│   ├── verification_loop.py
│   ├── thumbnail_generator.py
│   ├── imagen_generator.py
│   ├── remotion_orchestrator.py
│   ├── naver_blog_poster.py
│   ├── youtube_uploader.py
│   ├── output_paths.py
│   └── text_cleaner.py
└── outputs/
    └── YYYY-MM-DD/
        ├── daily_content_draft.md
        ├── daily_video.mp4
        ├── thumbnail_A_rational.png
        ├── thumbnail_B_emotional.png
        ├── verification_report.md
        └── market_heatmap.png
```

### 7.2 환경 변수 (.env)
```
GEMINI_API_KEY=...
NAVER_ID=...
NAVER_PW=...
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
```
