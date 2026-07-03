"""
images.py — 각 슬라이드 배경 이미지 생성 (무료 Pollinations/Flux, 키 불필요).
analysis.json의 images{} 프롬프트(그날 실제 주제 반영)를 읽어 data/images/<key>.png 저장.
- seed를 '날짜+시간대+슬라이드'로 매번 다르게 → 매 영상 새 그림
- 실패해도 조용히 건너뜀(영상은 이미지 없이도 정상)
"""
import sys, os, datetime, urllib.request, urllib.parse, pathlib, traceback
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, DATA

IMG = DATA / "images"

STYLE = (", cinematic editorial key visual, ultra detailed, hyper realistic, "
         "dramatic volumetric lighting, rich cinematic color grade, depth of field, "
         "8k, sharp focus, trending on artstation, professional financial news poster, "
         "vertical 9:16 composition, no text, no words, no letters, no logo, no watermark")

def _seed_base():
    # 날짜 + 시간대(slot) → 매 영상마다 다른 seed
    d = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y%m%d")
    slot = os.environ.get("SLOT", "morning")
    return (int(d) + sum(ord(c) for c in slot) * 101) % 2_000_000

def pollinations(prompt, out, seed, w=1080, h=1920):
    import time
    q = urllib.parse.quote(prompt + STYLE)
    attempts = [
        f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&nologo=true&enhance=true&model=flux&seed={seed}",
        f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&nologo=true&model=flux&seed={seed+37}",
        f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&nologo=true&seed={seed+91}",
    ]
    for k, url in enumerate(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=150).read()
            if data and len(data) > 8000:
                out.write_bytes(data); return True
        except Exception as e:
            log(f"[images]   시도 {k+1} 실패: {e}")
        time.sleep(3)
    return False

def main():
    cfg = load_config()
    if not cfg.get("images", {}).get("enabled", True):
        log("[images] disabled in config, skip"); return 0
    an = read_json(DATA / "analysis.json")
    imgs = an.get("images", {})
    if not imgs:
        log("[images] no image prompts, skip"); return 0
    IMG.mkdir(exist_ok=True)
    for f in IMG.glob("*.png"):
        f.unlink()
    base = _seed_base()
    for i, (key, prompt) in enumerate(imgs.items(), 1):
        if not prompt:
            continue
        seed = (base + i * 1301) % 2_000_000
        ok = pollinations(prompt, IMG / f"{key}.png", seed=seed)
        log(f"[images] {key}: {'생성 OK' if ok else 'skip'} (seed={seed})")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc(); sys.exit(0)  # 이미지 실패는 파이프라인 중단 사유 아님
