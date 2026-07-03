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

# 배경용(글자 없이) — 폴백/무료 이미지
STYLE_BG = (", bold editorial illustration, financial key visual, vibrant cinematic colors, "
            "deep navy background, high detail, vertical 9:16, no text, no letters, no watermark")

def card_prompt(t, s, theme):
    """제미나이 이미지 모델용: 글자·아이콘 다 넣은 완성 인포그래픽 카드 프롬프트."""
    return (f"세로 9:16 한국 주식 유튜브용 프리미엄 인포그래픽 카드 이미지. "
            f"큰 한국어 제목: '{t}'. 부제: '{s}'. 주제: {theme}. "
            f"주제에 맞는 3D 아이콘·차트·화살표(상승 초록/하락 빨강)를 배치. "
            f"짙은 네이비 배경, 선명하고 고급스러운 색감, 프로페셔널 금융 뉴스 그래픽 스타일. "
            f"한국어 글자를 또렷하고 정확하게, 오타 없이 렌더링. 워터마크 없음.")

def _seed_base():
    d = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y%m%d")
    slot = os.environ.get("SLOT", "morning")
    return (int(d) + sum(ord(c) for c in slot) * 101) % 2_000_000

def gemini_image(prompt, out):
    """제미나이 이미지 생성. 성공 시 True. 실패 시 예외(원인 로그용)."""
    from google import genai
    from google.genai import types
    import base64
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())
    model = os.environ.get("IMAGE_MODEL", "gemini-2.5-flash-image")
    last = None
    for modal in (["IMAGE"], ["TEXT", "IMAGE"]):
        try:
            r = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(response_modalities=modal))
        except Exception as e:
            last = e; continue
        cand = (getattr(r, "candidates", None) or [None])[0]
        parts = (getattr(getattr(cand, "content", None), "parts", None)
                 or getattr(r, "parts", None) or [])
        for pt in parts:
            inl = getattr(pt, "inline_data", None)
            if inl is not None and getattr(inl, "data", None):
                data = inl.data
                if isinstance(data, str):
                    data = base64.b64decode(data)
                if data and len(data) > 5000:
                    out.write_bytes(data)
                    return True
        last = RuntimeError("이미지 파트 없음(텍스트만 반환)")
    if last:
        raise last
    return False

def pollinations(prompt, out, seed, w=1080, h=1920):
    import time
    q = urllib.parse.quote(prompt + STYLE_BG)
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
    icfg = cfg.get("images", {})
    if not icfg.get("enabled", True):
        log("[images] disabled, skip"); return 0
    provider = icfg.get("provider", "auto")   # auto|gemini|pollinations
    mode = icfg.get("mode", "infographic")     # infographic|background
    mx = int(icfg.get("max_images", 8))
    an = read_json(DATA / "analysis.json")
    theme = an.get("theme", "증시")
    scenes = an.get("scenes", [])
    jobs = [(i, sc) for i, sc in enumerate(scenes) if sc.get("v") or sc.get("t")][:mx]
    if not jobs:
        log("[images] no scenes, skip"); return 0
    IMG.mkdir(exist_ok=True)
    for f in IMG.glob("*.png"):
        f.unlink()
    base = _seed_base()
    have_key = bool(os.environ.get("GEMINI_API_KEY"))
    cards, okc = [], 0
    for i, sc in jobs:
        out = IMG / f"s{i}.png"
        ok = False
        # 1순위: 제미나이 완성 카드
        if provider in ("auto", "gemini") and have_key:
            try:
                if mode == "infographic":
                    ok = gemini_image(card_prompt(sc.get("t",""), sc.get("s",""), theme), out)
                else:
                    ok = gemini_image((sc.get("v","") or sc.get("t","")) + STYLE_BG, out)
                if ok:
                    if mode == "infographic":
                        cards.append(i)
                    log(f"[images] s{i}: 제미나이 OK")
            except Exception as e:
                log(f"[images] s{i}: 제미나이 실패 → 폴백 ({str(e)[:70]})")
        # 2순위: 무료 배경(글자 없음)
        if not ok and provider in ("auto", "pollinations"):
            ok = pollinations(sc.get("v","") or sc.get("t",""), out, (base + i*1301) % 2_000_000)
            if ok: log(f"[images] s{i}: pollinations 배경 OK")
        okc += 1 if ok else 0
    # 완성 카드가 만들어진 장면 기록(render가 오버레이 글자 숨김)
    write_cards = {"cards": cards}
    (IMG / "_cards.json").write_text(__import__("json").dumps(write_cards), encoding="utf-8")
    log(f"[images] 완료 {okc}/{len(jobs)} (완성카드 {len(cards)}장)")
    return 0
