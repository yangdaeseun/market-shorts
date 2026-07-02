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

def notify(cfg, text):
    """텔레그램 알림(선택). 실패해도 파이프라인 안 죽음."""
    if not cfg.get("notify", {}).get("telegram_enabled"):
        return
    try:
        import requests
        tok = os.environ.get("TELEGRAM_TOKEN", "")
        chat = os.environ.get("TELEGRAM_CHAT", "")
        if tok and chat:
            requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          json={"chat_id": chat, "text": text}, timeout=15)
    except Exception as e:
        log(f"[notify] failed: {e}")
