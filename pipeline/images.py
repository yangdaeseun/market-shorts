"""
images.py — 각 슬라이드용 배경 이미지 생성 (무료 Pollinations/Flux, 키 불필요).
analysis.json의 images{} (섹션별 영어 프롬프트)를 읽어 data/images/<key>.png 저장.
실패해도 조용히 건너뜀(영상은 이미지 없이도 정상 생성).
"""
import sys, os, urllib.request, urllib.parse, pathlib, traceback
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, DATA

IMG = DATA / "images"

STYLE = (", cinematic dramatic editorial illustration, vertical 9:16 composition, "
         "dark moody cinematic lighting, high detail, financial news key visual, "
         "no text, no words, no letters, no watermark")

def pollinations(prompt, out, seed=1, w=1080, h=1920):
    q = urllib.parse.quote(prompt + STYLE)
    url = (f"https://image.pollinations.ai/prompt/{q}"
           f"?width={w}&height={h}&nologo=true&model=flux&seed={seed}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=150).read()
    if data and len(data) > 8000:
        out.write_bytes(data)
        return True
    return False

def main():
    cfg = load_config()
    if not cfg.get("images", {}).get("enabled", True):
        log("[images] disabled in config, skip")
        return 0
    an = read_json(DATA / "analysis.json")
    imgs = an.get("images", {})
    if not imgs:
        log("[images] no image prompts, skip")
        return 0
    IMG.mkdir(exist_ok=True)
    for f in IMG.glob("*.png"):
        f.unlink()
    for i, (key, prompt) in enumerate(imgs.items(), 1):
        if not prompt:
            continue
        out = IMG / f"{key}.png"
        try:
            ok = pollinations(prompt, out, seed=i * 7)
            log(f"[images] {key}: {'생성 OK' if ok else '데이터 부족 skip'}")
        except Exception as e:
            log(f"[images] {key} 실패(건너뜀): {e}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(0)   # 이미지 실패는 파이프라인 중단 사유 아님
