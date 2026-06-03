"""
Step 5: YouTube Auto-Uploader (YouTube Data API v3)
생성된 영상(.mp4)과 썸네일(.png)을 유튜브에 자동 업로드합니다.

⚠️  사전 준비 (최초 1회):
  1) Google Cloud Console → 프로젝트 생성
  2) YouTube Data API v3 활성화
  3) OAuth 2.0 클라이언트 ID 생성 → client_secret.json 다운로드
  4) 파일 경로: data/client_secret.json
  최초 실행 시 브라우저 인증 창이 열리며 token.json이 생성됩니다.
"""
import os
import sys
import json
import pickle
from datetime import datetime

# sys.path 설정 추가하여 output_paths 임포트 보장
sys.path.insert(0, os.path.dirname(__file__))
from output_paths import get_path, get_dated_path

CLIENT_SECRET_PATH = os.path.join("data", "client_secret.json")
TOKEN_PATH         = os.path.join("data", "youtube_token.pickle")
SCOPES             = ["https://www.googleapis.com/auth/youtube.upload"]


def get_youtube_service():
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials  import Credentials
    from googleapiclient.discovery  import build
    import google.auth.transport.requests

    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            if not os.path.exists(CLIENT_SECRET_PATH):
                raise FileNotFoundError(
                    f"client_secret.json 이 없습니다.\n"
                    f"Google Cloud Console에서 다운로드 후 {CLIENT_SECRET_PATH} 에 배치하세요."
                )
            flow  = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, video_path: str, thumbnail_path: str,
                 title: str, description: str, tags: list[str]):
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title":       title,
            "description": description,
            "tags":        tags,
            "categoryId":  "25"  # News & Politics
        },
        "status": {
            "privacyStatus": "private"  # 확인 후 'public'으로 변경
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True,
                            mimetype="video/mp4")

    print(f"[YouTube] 영상 업로드 중: {title}")
    request  = youtube.videos().insert(part="snippet,status", body=body,
                                        media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  업로드 {int(status.progress() * 100)}%")

    video_id = response.get("id")
    print(f"[YouTube] 업로드 완료! Video ID: {video_id}")

    # 썸네일 설정
    if os.path.exists(thumbnail_path) and video_id:
        print("[YouTube] 썸네일 설정 중...")
        youtube.thumbnails().set(
            videoId   = video_id,
            media_body= MediaFileUpload(thumbnail_path)
        ).execute()
        print("[YouTube] 썸네일 적용 완료")

    return video_id


def main():
    logic_path = os.path.join("data", "latest_content_logic.json")
    if not os.path.exists(logic_path):
        print(f"[Error] {logic_path} 파일이 존재하지 않습니다. 먼저 기획안 작성을 완료하세요.")
        return
    try:
        with open(logic_path, "r", encoding="utf-8") as f:
            logic = json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"[Error] {logic_path} 파일이 유효한 JSON 형식이 아닙니다: {e}")
        return

    score = logic.get("score", 50.0)
    mood  = "공격" if score >= 50 else "방어"
    date  = datetime.now().strftime("%Y.%m.%d")

    title = f"[머니대디] {date} 스코어 {score}점 – 오늘 9시 {mood} 전략 공개"
    description = (
        f"오늘의 머니대디 스코어: {score}점 ({mood} 시장)\n\n"
        "글로벌 심리 → 미국 마감 결과 → 한국 시장 수급 흐름을 연결하는 "
        "머니대디의 아침 전략 콘텐츠입니다.\n\n"
        "#오늘주식전망 #머니대디 #KOSPI #주도주분석 #주도주수급 #거시경제"
    )
    tags = ["오늘의주식전망", "머니대디", "주식", "KOSPI", "주도주", "주도주수급", "거시경제"]

    # 경로 동적 획득
    video_path = get_dated_path("최종영상", "mp4")
    if not os.path.exists(video_path):
        video_path = get_path("daily_strategy_pro_final.mp4")
        
    thumbnail_path = get_path("thumbnail_A_rational.png")
    if not os.path.exists(thumbnail_path):
        thumbnail_path = get_path("thumbnail_B_emotional.png")

    # 파일 검출 디버깅 코드 추가
    print(f"[Debug] 비디오 경로: {video_path}")
    if os.path.exists(video_path):
        print(f"[Debug] 비디오 파일 크기: {os.path.getsize(video_path)} bytes")
    else:
        print("[Debug] 비디오 파일이 존재하지 않습니다.")

    print(f"[Debug] 썸네일 경로: {thumbnail_path}")
    if os.path.exists(thumbnail_path):
        print(f"[Debug] 썸네일 파일 크기: {os.path.getsize(thumbnail_path)} bytes")
    else:
        print("[Debug] 썸네일 파일이 존재하지 않습니다.")

    if not os.path.exists(video_path):
        print(f"[Error] 영상 파일이 없습니다: {video_path}")
        print("먼저 video_synthesizer.py를 실행하세요.")
        return

    try:
        yt = get_youtube_service()
        upload_video(yt, video_path, thumbnail_path, title, description, tags)
    except FileNotFoundError as e:
        print(f"\n[설정 필요]\n{e}")
    except Exception as e:
        print(f"[Error] {e}")


if __name__ == "__main__":
    main()
