# Pipeline Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 버그 수정, 이식성 확보, 팩트체크 경고 우회(소프트 게이트), AI 품질 정제 및 Remotion 가변 동적 TSX 생성을 구현하여 자동화 파이프라인의 완성도를 극대화합니다.

**Architecture:** 
1. `sys.exit(1)` 방식을 무조건 무시하지 않고 GUI/로그상에 경고(⚠️)만 내보내며 발행까지 흘려주는 소프트 게이트 제어.
2. `remotion_orchestrator.py`가 오늘의 대본 데이터(`latest_content_logic.json`)를 바탕으로 씬 개수에 상관없이 `Scene1` ~ `SceneN` 컴포넌트 구조의 `Main.tsx`를 동적으로 빌드하는 템플릿 생성 엔진 탑재.
3. 런타임 NameError 및 레이아웃 오류 등의 잔여 마이너 버그 일괄 수정.

**Tech Stack:** Python 3.x, React, Remotion, Tkinter, Selenium

---

### Task 1: NameError 및 마이너 버그 수정 (1단계 - 버그 수정)

**Files:**
- Modify: `src/market_data_collector.py`
- Modify: `src/content_generator.py`

- [ ] **Step 1: `market_data_collector.py` NameError 수정**
  - `src/market_data_collector.py`의 `r` 변수 미정의 참조 오류 예방을 위해 try문 이전에 `r = None` 선언을 추가합니다.
  ```python
  # src/market_data_collector.py
  r = None
  try:
      r = requests.get(url, headers=HEADERS, timeout=10)
  ```
- [ ] **Step 2: `content_generator.py` NameError 및 중복 주석 수정**
  - `propose_topics` 함수 내 except 블록의 미정의 변수 `selected_topic` 참조를 수정합니다.
  - L163-164 근처의 중복 주석(`#  2. 기획 생성 로직...`)을 제거합니다.
  ```python
  # src/content_generator.py L147 수정
  except Exception as e:
      print(f"  [Proposal Error] Topic Proposal failed: {e}")
      return []
  ```
- [ ] **Step 3: 구문 검사**
  - Run: `.venv\Scripts\python -m py_compile src/market_data_collector.py src/content_generator.py`
  - Expected: 정상 컴파일 (아무 에러 출력 없음)
- [ ] **Step 4: Commit**
  ```bash
  git add src/market_data_collector.py src/content_generator.py
  git commit -m "fix(pipeline): resolve NameError in collector & generator and clean comments"
  ```

---

### Task 2: REMOTION_DIR 환경변수화 및 .env 명세 (1단계 - 환경설정)

**Files:**
- Modify: `src/remotion_orchestrator.py`
- Modify: `.env`

- [ ] **Step 1: `remotion_orchestrator.py` 상수 정의 수정**
  - 하드코딩된 절대 경로를 `os.getenv`로 대체합니다.
  ```python
  # src/remotion_orchestrator.py L18 수정
  REMOTION_DIR = os.getenv("REMOTION_DIR", r"D:\04_Antigravity_wp\Remotion")
  ```
- [ ] **Step 2: `.env` 환경 변수 추가**
  - `.env` 파일 맨 아래에 `REMOTION_DIR` 키값을 기본 경로와 함께 추가합니다.
  ```env
  REMOTION_DIR=D:\04_Antigravity_wp\Remotion
  ```
- [ ] **Step 3: 구문 검사**
  - Run: `.venv\Scripts\python -m py_compile src/remotion_orchestrator.py`
  - Expected: PASS
- [ ] **Step 4: Commit**
  ```bash
  git add src/remotion_orchestrator.py .env
  git commit -m "feat(remotion): support REMOTION_DIR from env config"
  ```

---

### Task 3: 팩트체크 소프트 게이트 전환 및 본문 절단 제한 해제 (1단계 - 제어/발행)

**Files:**
- Modify: `src/generation_pipeline.py`
- Modify: `main.py`
- Modify: `src/naver_blog_poster.py`

- [ ] **Step 1: `generation_pipeline.py` 소프트 게이트 처리**
  - 팩트 검증 실패(`FAILED`)를 감지해도 즉시 프로그램이 강제 종료되지 않고 경고만 출력하도록 예외 흐름을 완화합니다.
  ```python
  # src/generation_pipeline.py L73-77 수정
  report = vl.verify_content()
  if "FAILED" in report:
      print("⚠️ [경고] 팩트 불일치 항목이 발견되었습니다. 결과를 확인 후 수정을 권장합니다.")
      print(report)
      # sys.exit(1) 제거하여 파이프라인 계속 진행
  else:
      print("✅ 팩트 검증 통과.")
  ```
- [ ] **Step 2: `main.py` 소프트 게이트 처리**
  - `main.py` 내의 팩트체크 게이트 구문을 `generation_pipeline.py`와 동일하게 소프트 게이트로 변경합니다.
  ```python
  # main.py L119-123 수정
  if "FAILED" in report:
      console.print(Panel(report, title="[yellow]Verification Warning[/yellow]", border_style="yellow"))
      console.print("[bold yellow]⚠️ 팩트 불일치가 발견되었으나 파이프라인을 계속 진행합니다.[/bold yellow]")
  else:
      console.print("[bold green][PASS][/bold green] 팩트 검증 통과")
  ```
- [ ] **Step 3: `naver_blog_poster.py` 3,000자 절단 제한 완화**
  - 3,000자 슬라이싱 제약을 50,000자로 완화하여 긴 본문이 온전히 작성되도록 합니다.
  ```python
  # src/naver_blog_poster.py L164 수정
  """, body_html[:50000])
  ```
- [ ] **Step 4: 구문 검사**
  - Run: `.venv\Scripts\python -m py_compile src/generation_pipeline.py main.py src/naver_blog_poster.py`
  - Expected: PASS
- [ ] **Step 5: Commit**
  ```bash
  git add src/generation_pipeline.py main.py src/naver_blog_poster.py
  git commit -m "fix(pipeline): change fact-check gate to soft-gate and expand blog text limit"
  ```

---

### Task 4: back_data_trends 자연어 포맷터 구현 (2단계 - AI 품질)

**Files:**
- Modify: `src/content_generator.py`

- [ ] **Step 1: 자연어 포맷팅 유틸리티 함수 구현 및 프롬프트 주입**
  - `_load_research_context` 함수 내부에서 `back_data_trends` dict를 자연어로 이쁘게 풀어서 주입합니다.
  ```python
  # src/content_generator.py _load_research_context 수정
  if research.get("back_data_trends"):
      trend = research["back_data_trends"]
      if isinstance(trend, dict) and "key" in trend:
          trend_str = (
              f"[{trend.get('key')} 최근 10영업일 추이] "
              f"시작일({trend.get('start_date')}) 종가 {trend.get('start_val')} 대비 "
              f"종료일({trend.get('end_date')}) 종가 {trend.get('end_val')}로 "
              f"{trend.get('change_pct')}% 변동. "
              f"최고치: {trend.get('max_val')}, 최저치: {trend.get('min_val')}"
          )
      else:
          trend_str = str(trend)
      parts.append(f"[과거 백데이터 추이 — 반드시 기획 및 본문에 적극 반영]\n{trend_str}")
  ```
- [ ] **Step 2: 구문 및 테스트 실행**
  - Run: `.venv\Scripts\python -m py_compile src/content_generator.py`
  - Expected: PASS
- [ ] **Step 3: Commit**
  ```bash
  git add src/content_generator.py
  git commit -m "refactor(content): format back_data_trends dict to natural language in prompt"
  ```

---

### Task 5: gui_main.py 레이아웃 버그 수정 (2단계 - UI)

**Files:**
- Modify: `gui_main.py`

- [ ] **Step 1: `lbl_topic_status` 배치 방식 수정**
  - grid/pack 배치가 충돌하여 옆으로 찌그러지거나 줄바꿈 오류가 생기던 레이블 위젯 배치를 Grid 방식으로 안전하게 정렬시킵니다.
  ```python
  # gui_main.py L169-170 근처 수정
  self.lbl_topic_status = ttk.Label(gen_ctrl_frame, text="주제를 선택해 주세요", foreground="#AAAAAA")
  self.lbl_topic_status.grid(row=2, column=0, columnspan=3, sticky="w", pady=2)
  ```
- [ ] **Step 2: GUI 실행 검사**
  - Run: `.venv\Scripts\python gui_main.py`
  - Expected: GUI 창이 열리고, 주제 상태 레이블이 주제 콤보박스 아래에 깨지지 않고 한글로 이쁘게 정렬되어 있어야 함. (정상 실행 후 창 닫기)
- [ ] **Step 3: Commit**
  ```bash
  git add gui_main.py
  git commit -m "fix(gui): correct lbl_topic_status layout positioning"
  ```

---

### Task 6: Remotion 가변 동적 TSX 생성 엔진 구현 (3단계 - 핵심 기능)

**Files:**
- Modify: `src/remotion_orchestrator.py`

- [ ] **Step 1: `update_remotion_sources()` 함수 내에 dynamic TSX 생성 로직 구현**
  - `data/latest_content_logic.json`에서 읽어온 `video_structure` 씬 데이터의 개수(N)를 토대로 `Scene1` ~ `SceneN` 컴포넌트를 빌드합니다.
  - 슬래시`/` 문자로 구성된 `caption_layout`을 분리하여 `<br />` 혹은 멀티 텍스트 요소를 빌드합니다.
  - 따옴표, 백틱, 중괄호 등 한국어 텍스트 이스케이프 함수(`escape_js`)를 작성하여 문자열 대입 오류를 방지합니다.
  - 생성된 TSX 텍스트를 `REMOTION_DIR/src/Main.tsx` 파일에 통째로 덮어쓰도록 수정합니다.
  ```python
  # src/remotion_orchestrator.py 내 dynamic code block 빌더 구현
  def escape_js(text):
      if not text: return ""
      return text.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace("\n", " ").replace("{", "\\{").replace("}", "\\}")
  ```
- [ ] **Step 2: 렌더러 검증 테스트 실행**
  - Run: `.venv\Scripts\python src/remotion_orchestrator.py`
  - Expected: `Main.tsx` 파일이 가변 씬 형태로 정상 재생성되어야 함. (실제 비디오 렌더러 동작 시도 후 `outputs/`에 `.mp4` 영상이 정상 추출되는지 확인)
- [ ] **Step 3: Commit**
  ```bash
  git add src/remotion_orchestrator.py
  git commit -m "feat(remotion): implement dynamic TSX script generator for variable scenes"
  ```
