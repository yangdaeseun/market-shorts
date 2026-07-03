"""
images.py — 장면별 배경 이미지 생성.
1순위: 제미나이 이미지 생성(gemini-2.5-flash-image, Nano Banana) — 내용에 딱 맞는 고퀄
2순위: 무료 Pollinations/Flux — 키 없이/실패 시 폴백
텍스트는 영상에서 우리가 얹으므로 이미지엔 글자 안 넣게 함.
analysis.json 의 scenes[].v(영어 키워드)로 data/images/s{i}.png 생성.
"""
import sys, os, datetime, urllib.request, urllib.parse, pathlib, traceback
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, DATA

IMG = DATA / "images"

STYLE = (", bold editorial infographic illustration, financial news key visual, "
         "vibrant cinematic colors, dramatic lighting, deep navy background, "
         "clean vector-3d style, high detail, vertical 9:16 composition, "
         "absolutely no text, no words, no letters, no numbers, no watermark")

def _seed_base():
    d = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y%m%d")
    slot = os.environ.get("SLOT", "morning")
    return (int(d) + sum(ord(c) for c in slot) * 101) % 2_000_000

def gemini_image(prompt, out):
    """제미나이 이미지 생성. 성공 시 True. (google-genai 필요, 키에 이미지 권한 필요)"""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())
    model = os.environ.get("IMAGE_MODEL", "gemini-2.5-flash-image")
    contents = prompt + STYLE
    try:
        cfg = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="9:16"))
        r = client.models.generate_content(model=model, contents=contents, config=cfg)
    except TypeError:
        r = client.models.generate_content(model=model, contents=contents,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
    parts = getattr(r, "parts", None)
    if not parts:
        try: parts = r.candidates[0].content.parts
        except Exception: parts = []
    for p in parts or []:
        inl = getattr(p, "inline_data", None)
        if inl and getattr(inl, "data", None):
            out.write_bytes(inl.data)
            return out.stat().st_size > 5000
    return False

def pollinations(prompt, out, seed, w=1080, h=1920):
    import time
    q = urllib.parse.quote(prompt + STYLE)
    urls = [
        f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&nologo=true&enhance=true&model=flux&seed={seed}",
        f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&nologo=true&model=flux&seed={seed+37}",
        f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&nologo=true&seed={seed+91}",
    ]
    for k, url in enumerate(urls):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=150).read()
            if data and len(data) > 8000:
                out.write_bytes(data); return True
        except Exception as e:
            log(f"[images]   pollinations {k+1} 실패: {e}")
        time.sleep(3)
    return False

def main():
    cfg = load_config()
    if not cfg.get("images", {}).get("enabled", True):
        log("[images] disabled, skip"); return 0
    provider = cfg.get("images", {}).get("provider", "auto")  # auto|gemini|pollinations
    an = read_json(DATA / "analysis.json")
    scenes = an.get("scenes", [])
    mx = int(cfg.get("images", {}).get("max_images", 8))
    jobs = [(i, sc.get("v", "")) for i, sc in enumerate(scenes) if sc.get("v")][:mx]
    if not jobs:
        jobs = list(enumerate(an.get("images", {}).values()))
    if not jobs:
        log("[images] no prompts, skip"); return 0
    IMG.mkdir(exist_ok=True)
    for f in IMG.glob("*.png"):
        f.unlink()
    base = _seed_base()
    have_key = bool(os.environ.get("GEMINI_API_KEY"))
    okc = 0
    for i, prompt in jobs:
        if not prompt:
            continue
        out = IMG / f"s{i}.png"
        ok = False
        if provider in ("auto", "gemini") and have_key:
            try:
                ok = gemini_image(prompt, out)
                if ok: log(f"[images] s{i}: 제미나이 OK ({prompt[:28]})")
            except Exception as e:
                log(f"[images] s{i}: 제미나이 실패 → 폴백 ({str(e)[:80]})")
        if not ok and provider in ("auto", "pollinations"):
            ok = pollinations(prompt, out, (base + i * 1301) % 2_000_000)
            if ok: log(f"[images] s{i}: pollinations OK")
        if not ok:
            log(f"[images] s{i}: 생성 실패(스킵)")
        okc += 1 if ok else 0
    log(f"[images] 완료 {okc}/{len(jobs)}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc(); sys.exit(0)
