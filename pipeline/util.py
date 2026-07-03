"""공용 유틸: 설정 로드, 경로, 로그, 알림."""
import os, sys, json, pathlib, datetime, yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOGS = ROOT / "logs"
TEMPLATES = ROOT / "templates"

def load_config():
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)

def log(msg):
    line = f"{datetime.datetime.now():%H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        LOGS.mkdir(exist_ok=True)
        with open(LOGS / "run.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def read_json(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))

def write_json(p, obj):
    pathlib.Path(p).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def _kakao_access_token():
    """리프레시 토큰으로 카카오 액세스 토큰 발급."""
    import requests
    rest = os.environ.get("KAKAO_REST_KEY", "").strip()
    refresh = os.environ.get("KAKAO_REFRESH_TOKEN", "").strip()
    if not (rest and refresh):
        return None
    r = requests.post("https://kauth.kakao.com/oauth/token",
        data={"grant_type": "refresh_token", "client_id": rest, "refresh_token": refresh},
        timeout=15)
    r.raise_for_status()
    return r.json().get("access_token")

def notify_kakao(text, url=""):
    """카카오톡 '나에게 보내기'. 실패해도 파이프라인 안 죽음."""
    import requests, json as _json
    try:
        tok = _kakao_access_token()
        if not tok:
            return
        link = url or "https://www.youtube.com"
        template = {"object_type": "text", "text": text[:190],
                    "link": {"web_url": link, "mobile_web_url": link}}
        if url:
            template["button_title"] = "영상 보기"
        r = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers={"Authorization": f"Bearer {tok}"},
            data={"template_object": _json.dumps(template, ensure_ascii=False)}, timeout=15)
        if r.status_code != 200:
            log(f"[notify] kakao {r.status_code}: {r.text[:120]}")
    except Exception as e:
        log(f"[notify] kakao failed: {e}")

def notify(cfg, text):
    """알림(텔레그램/카카오, 선택). 실패해도 파이프라인 안 죽음."""
    import re
    ncfg = cfg.get("notify", {})
    # 텍스트 안의 유튜브 링크 추출(카카오 버튼용)
    m = re.search(r"https?://[^\s]+", text or "")
    url = m.group(0) if m else ""
    if ncfg.get("telegram_enabled"):
        try:
            import requests
            tok = os.environ.get("TELEGRAM_TOKEN", "")
            chat = os.environ.get("TELEGRAM_CHAT", "")
            if tok and chat:
                requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                              json={"chat_id": chat, "text": text}, timeout=15)
        except Exception as e:
            log(f"[notify] telegram failed: {e}")
    if ncfg.get("kakao_enabled"):
        notify_kakao(text, url)
