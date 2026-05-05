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
import json
import time
from datetime import datetime


def get_credentials() -> tuple[str, str]:
    nid = os.environ.get("NAVER_ID", "")
    npw = os.environ.get("NAVER_PW", "")
    if not nid or not npw:
        raise EnvironmentError(
            "NAVER_ID / NAVER_PW 환경변수가 설정되지 않았습니다.\n"
            "  PowerShell: $Env:NAVER_ID='your_id'; $Env:NAVER_PW='your_pw'"
        )
    return nid, npw


def load_blog_draft() -> dict:
    """returns {title, body, tags}"""
    draft_path = os.path.join("outputs", "daily_content_draft.md")
    logic_path = os.path.join("data",    "latest_content_logic.json")

    with open(draft_path, "r", encoding="utf-8") as f:
        raw = f.read()

    with open(logic_path, "r", encoding="utf-8") as f:
        logic = json.load(f)

    score = logic.get("score", 50)
    date  = datetime.now().strftime("%Y.%m.%d")
    title = f"[머니대디] {date} 스코어 {score}점, 오늘 9시 당신이 해야 할 것"

    # 줄바꿈 → <br> 변환 (Naver 에디터 호환)
    body_html = raw.replace("\n", "<br>")
    tags = "오늘의주식전망,머니대디,주식,KOSPI,주도주분석,FVG"

    return {"title": title, "body_html": body_html, "tags": tags}


def post_to_naver_blog(title: str, body_html: str, tags: str):
    """Selenium으로 네이버 블로그에 포스트."""
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options

    nid, npw = get_credentials()

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
        print("[Blog] 블로그 글쓰기 페이지 이동...")
        driver.get("https://blog.naver.com/PostWriteForm.naver")
        time.sleep(4)

        # iframe 전환
        wait.until(EC.frame_to_be_available_and_switch_to_it(
            (By.CSS_SELECTOR, "iframe#mainFrame")))

        # 3) 제목 입력
        title_el = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "textarea.se-input-title")))
        title_el.clear()
        title_el.send_keys(title)
        time.sleep(0.5)

        # 4) 본문 입력 (SmartEditor 4 기준)
        body_el = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".se-content")))
        body_el.click()
        body_el.send_keys(body_html)
        time.sleep(1)

        # 5) 발행 버튼
        publish_btn = driver.find_element(By.CSS_SELECTOR, ".btn_publish")
        publish_btn.click()
        time.sleep(3)

        print(f"[Blog] 포스팅 완료: '{title}'")

    except Exception as e:
        print(f"[Blog Error] {e}")
    finally:
        driver.quit()


def main():
    try:
        draft = load_blog_draft()
        post_to_naver_blog(
            title     = draft["title"],
            body_html = draft["body_html"],
            tags      = draft["tags"]
        )
    except EnvironmentError as e:
        print(f"\n[설정 필요]\n{e}")
    except Exception as e:
        print(f"[Error] {e}")


if __name__ == "__main__":
    main()
