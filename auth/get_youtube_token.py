"""
get_youtube_token.py — YouTube 무인 업로드용 refresh token 1회 발급.
PC에서 딱 한 번만 실행하면 됩니다.

준비:
1) Google Cloud Console → 프로젝트 → YouTube Data API v3 '사용 설정'
2) OAuth 동의화면 구성(외부, 테스트 사용자에 본인 계정 추가)
3) 사용자 인증 정보 → OAuth 클라이언트 ID → '데스크톱 앱' 생성
   → client_secret.json 다운로드해서 이 파일과 같은 폴더에 둠
4) pip install google-auth-oauthlib
5) python auth/get_youtube_token.py

실행하면 브라우저가 열리고 로그인 → 동의하면 아래 3개 값이 출력됩니다:
  YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN
→ 이 값들을 GitHub 저장소 Settings → Secrets and variables → Actions 에 등록.
"""
import json, pathlib
from google_auth_oauthlib.flow import InstalledAppFlow

HERE = pathlib.Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]

def main():
    cs = HERE / "client_secret.json"
    if not cs.exists():
        print("❌ client_secret.json 을 auth/ 폴더에 두세요. (위 주석 3번 참고)")
        return
    flow = InstalledAppFlow.from_client_secrets_file(str(cs), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    info = json.loads(cs.read_text())
    key = "installed" if "installed" in info else "web"
    print("\n================ GitHub Secrets 에 등록 ================")
    print("YT_CLIENT_ID    =", info[key]["client_id"])
    print("YT_CLIENT_SECRET=", info[key]["client_secret"])
    print("YT_REFRESH_TOKEN=", creds.refresh_token)
    print("======================================================")

if __name__ == "__main__":
    main()
