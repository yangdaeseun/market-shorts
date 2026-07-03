"""
get_kakao_token.py — 카카오톡 '나에게 보내기'용 refresh_token 1회 발급 도우미.
사전: developers.kakao.com 에서 앱 생성 → REST API 키 확보,
      [카카오 로그인] 활성화 + Redirect URI 등록(예: https://localhost),
      [동의항목]에서 'talk_message'(카카오톡 메시지 전송) 사용 설정.
사용:
  python auth/get_kakao_token.py
  → REST 키/Redirect URI 입력 → 안내된 URL 열어 로그인·동의 →
     주소창의 code=... 값 붙여넣기 → refresh_token 출력.
출력된 값을 GitHub Secrets 에 KAKAO_REST_KEY, KAKAO_REFRESH_TOKEN 으로 등록.
"""
import sys, urllib.parse, urllib.request, json

def main():
    rest = input("REST API 키: ").strip()
    redirect = (input("Redirect URI [https://localhost]: ").strip() or "https://localhost")
    auth_url = ("https://kauth.kakao.com/oauth/authorize?response_type=code"
                f"&client_id={rest}&redirect_uri={urllib.parse.quote(redirect)}"
                "&scope=talk_message")
    print("\n[1] 아래 URL 을 브라우저에서 열고 로그인·동의하세요:\n")
    print(auth_url)
    print("\n[2] 동의 후 이동한 주소의 code= 뒤 값을 복사해 붙여넣으세요.")
    code = input("code: ").strip()

    data = urllib.parse.urlencode({
        "grant_type": "authorization_code", "client_id": rest,
        "redirect_uri": redirect, "code": code}).encode()
    req = urllib.request.Request("https://kauth.kakao.com/oauth/token", data=data)
    try:
        res = json.loads(urllib.request.urlopen(req, timeout=20).read())
    except Exception as e:
        print("실패:", e); sys.exit(1)
    print("\n===== GitHub Secrets 에 등록 =====")
    print("KAKAO_REST_KEY      =", rest)
    print("KAKAO_REFRESH_TOKEN =", res.get("refresh_token"))
    print("(access_token 은 자동 갱신되니 등록 안 해도 됩니다)")

if __name__ == "__main__":
    main()
