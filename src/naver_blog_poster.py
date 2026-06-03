"""
Step 4: Naver Blog Auto-Poster (Selenium)
생성된 블로그 초안을 네이버 블로그에 자동으로 업로드합니다.

⚠️  사전 준비:
  1) Chrome 브라우저 설치
  2) 환경변수 설정:
       NAVER_ID=아이디
       NAVER_PW=비밀번호
  3) 네이버 2단계 인증 → 미사용 또는 앱 비밀번호 활용 권장
"""
import os
import sys
import json
import time
from datetime import datetime
from dotenv import load_dotenv

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.output_paths import get_output_dir, get_topic_keyword

# .env 로드
load_dotenv()


def get_credentials() -> tuple[str, str, str]:
    """로그인 ID/PW 및 블로그 ID를 반환합니다.
    NAVER_BLOG_ID가 설정된 경우 해당 값 사용, 없으면 NAVER_ID로 폴백."""
    nid = os.environ.get("NAVER_ID", "")
    npw = os.environ.get("NAVER_PW", "")
    # 블로그 ID는 로그인 ID와 다를 수 있음 (예: jjwhb178 로그인 → jasonmoneylogin 블로그)
    blog_id = os.environ.get("NAVER_BLOG_ID", "") or nid
    if not nid or not npw:
        raise EnvironmentError(
            "NAVER_ID / NAVER_PW 환경변수가 설정되지 않았습니다.\n"
            "  .env 파일에 NAVER_ID, NAVER_PW, NAVER_BLOG_ID를 설정하세요."
        )
    return nid, npw, blog_id


def load_blog_draft() -> dict:
    """날짜 기반 경로에서 블로그 초안을 읽어 {title, body_html, tags}를 반환합니다."""
    out_dir = get_output_dir()
    today_str = datetime.now().strftime("%Y%m%d")
    keyword = get_topic_keyword()
    
    # 날짜 기반 파일명으로 초안 탐색
    draft_filename = f"{today_str}_{keyword}_블로그초안.md"
    draft_path = os.path.join(out_dir, draft_filename)
    
    # 파일이 없으면 폴백: 디렉토리 내 블로그초안.md 검색
    if not os.path.exists(draft_path):
        candidates = [f for f in os.listdir(out_dir) if "블로그초안" in f and f.endswith(".md")]
        if candidates:
            draft_path = os.path.join(out_dir, sorted(candidates)[-1])
        else:
            raise FileNotFoundError(f"블로그 초안 파일을 찾을 수 없습니다: {out_dir}")
    
    logic_path = os.path.join("data", "latest_content_logic.json")
    
    if not os.path.exists(draft_path):
        print(f"[Blog] Error: 초안 파일이 존재하지 않습니다: {draft_path}")
        return {"title": "", "body_text": "", "tags": ""}

    with open(draft_path, "r", encoding="utf-8") as f:
        raw = f.read()
    print(f"[Blog] 초안 파일 로드: {draft_path}")

    # logic.json 파일 유무 검증 추가
    blog_title = ""
    if os.path.exists(logic_path):
        try:
            with open(logic_path, "r", encoding="utf-8") as f:
                logic = json.load(f)
            blog_title = logic.get("title", "")
        except Exception as e:
            print(f"[Blog] Warning: logic.json 로드 실패 ({e})")
            
    if not blog_title:
        date = datetime.now().strftime("%Y.%m.%d")
        blog_title = f"[머니대디] {date} 오늘의 핵심 경제 이슈 분석"

    # insertText 사용을 위해 <br> 대신 개행 문자가 유지된 원본 텍스트를 그대로 사용
    body_text = raw
    tags = "오늘의주식전망,머니대디,주식,KOSPI,주도주분석,주도주수급,경제동향,한국증시,ETF,코스피"

    return {"title": blog_title, "body_text": body_text, "tags": tags}


def post_to_naver_blog(title: str, body_text: str, tags: str):
    """Selenium으로 네이버 블로그에 포스트."""
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options

    nid, npw, blog_id = get_credentials()
    print(f"[Blog] 로그인 ID: {nid}, 블로그 ID: {blog_id}")

    options = Options()
    # options.add_argument("--headless")  # 화면 숨기려면 주석 해제
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)
    wait   = WebDriverWait(driver, 20)

    try:
        # 1) 네이버 로그인
        print("[Blog] 네이버 로그인 중...")
        driver.get("https://nid.naver.com/nidlogin.login")
        time.sleep(1)

        driver.execute_script(
            "document.getElementById('id').value=arguments[0]", nid)
        driver.execute_script(
            "document.getElementById('pw').value=arguments[0]", npw)
        driver.find_element(By.ID, "log.login").click()
        
        print("[Blog] 2단계 인증 또는 보안 해제를 기다립니다 (최대 60초 대기)...")
        # 로그인이 완료되어 메인 화면 등으로 넘어갈 때까지 대기 (url이 로그인 페이지가 아니게 될 때)
        try:
            WebDriverWait(driver, 60).until(
                lambda d: "nidlogin.login" not in d.current_url
            )
            print("[Blog] 로그인 성공 확인됨.")
        except Exception:
            print("[Blog] 시간 초과: 로그인이 진행되지 않았을 수 있습니다.")

        # 2) 블로그 글쓰기 에디터 열기
        print(f"[Blog] 블로그 글쓰기 페이지 이동... (blogId={blog_id})")
        driver.get(f"https://blog.naver.com/PostWriteForm.naver?blogId={blog_id}")
        time.sleep(6)  # 에디터 로딩 대기

        # SmartEditor ONE: iframe 없음 (직접 접근)
        # 3) 제목 입력
        print("[Blog] 제목 입력 중...")
        try:
            title_el = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                    ".se-title-input, .tit_area textarea, [placeholder*='제목'], .se-placeholder"))
            )
            title_el.click()
            time.sleep(0.5)
            title_el.send_keys(title)
        except Exception as e:
            print(f"[Blog] 제목 입력 실패 (CSS 폴백 시도): {e}")
            # JS 직접 주입 폴백
            driver.execute_script("""
                var el = document.querySelector('.se-title-input, .tit_area textarea');
                if(el){ el.focus(); el.value = arguments[0]; }
            """, title)
        time.sleep(0.5)

        # 4) 본문 클릭 후 텍스트 입력
        print("[Blog] 본문 입력 중...")
        try:
            body_el = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR,
                    ".se-content, .se-main-container, p.se-text-paragraph"))
            )
            body_el.click()
            time.sleep(0.5)
            # 긴 텍스트는 clipboard 방식으로 주입 (send_keys 속도 문제 방지)
            driver.execute_script("""
                var el = document.querySelector('.se-content, .se-main-container');
                if(el){ el.focus(); }
                document.execCommand('selectAll');
                document.execCommand('insertText', false, arguments[0]);
            """, body_text)
        except Exception as e:
            print(f"[Blog] 본문 입력 실패: {e}")
        time.sleep(2)

        # 5) 발행 버튼 클릭
        print("[Blog] 발행 버튼 클릭...")
        try:
            publish_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR,
                    ".publish_btn, .btn_publish, button.publish, [class*='publish']"))
            )
            publish_btn.click()
            time.sleep(3)
            # 공개 발행 확인 팝업 처리
            try:
                confirm_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR,
                        ".btn_ok, .btn_confirm, [class*='confirm'], button[type='submit']"))
                )
                confirm_btn.click()
                time.sleep(2)
            except Exception:
                pass  # 확인 팝업 없는 경우 무시
        except Exception as e:
            print(f"[Blog] 발행 버튼 오류: {e}")

        print(f"[Blog] 포스팅 완료: '{title}'")

    except Exception as e:
        print(f"[Blog Error] {e}")
    finally:
        driver.quit()



def main():
    # 1) 초안 데이터 로드
    draft_data = load_blog_draft()
    if not draft_data["body_text"]:
        print("[Blog] Error: 포스팅할 초안 본문 내용이 없습니다. 업로드를 중단합니다.")
        sys.exit(1)

    # 2) 블로그 포스팅 실행
    try:
        post_to_naver_blog(
            title=draft_data["title"],
            body_text=draft_data["body_text"],
            tags=draft_data["tags"]
        )
    except EnvironmentError as e:
        print(f"\n[설정 필요]\n{e}")
    except Exception as e:
        print(f"[Error] {e}")


if __name__ == "__main__":
    main()
