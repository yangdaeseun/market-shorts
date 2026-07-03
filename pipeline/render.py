"""
render.py — data.json + analysis.json → 슬라이드 PNG (1080x1920, 2x 슈퍼샘플).
HTML+CSS 고정 템플릿 → 내용이 길든 짧든 자동 정렬, 항상 같은 퀄리티.
"""
import sys, re, html, pathlib, traceback
from jinja2 import Template

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, write_json, DATA, TEMPLATES

# ---------- 포맷 헬퍼 ----------
def dir_cls(p):
    if p is None: return "flat"
    return "up" if p > 0 else ("down" if p < 0 else "flat")

def fmt_pct(p):
    if p is None: return "—"
    return f"{p:+.2f}%"

def fmt_price(name, v):
    if v is None: return "N/A"
    if "원/달러" in name: return f"{v:,.1f}원"
    if "금리" in name or "10년" in name: return f"{v:.2f}%"
    if "비트" in name or "이더" in name: return f"${v:,.0f}"
    if "유가" in name: return f"${v:,.1f}"
    return f"{v:,.2f}"

def hl(headline_html):
    """<up>..</up><down>..</down> → 색 span. 그 외 텍스트는 escape."""
    parts = re.split(r"(</?(?:up|down)>)", headline_html or "")
    out, mode = [], None
    for p in parts:
        if p == "<up>": mode = "hl-up"; continue
        if p == "<down>": mode = "hl-down"; continue
        if p in ("</up>", "</down>"): mode = None; continue
        if not p: continue
        esc = html.escape(p)
        out.append(f'<span class="{mode}">{esc}</span>' if mode else esc)
    return "".join(out)

# ---------- 슬라이드 빌더(장면 기반) ----------
def theme_palette(theme):
    t = (theme or "").lower()
    table = [
        (("반도체", "hbm", "칩", "메모리", "ai"), ("#22C55E", "#04160C")),
        (("전력", "전선", "송전", "원전", "에너지"), ("#3B82F6", "#050B1C")),
        (("비트", "코인", "암호", "크립토"), ("#F59E0B", "#160F02")),
        (("방산", "국방", "우주", "조선"), ("#9FB2C6", "#0A0E14")),
        (("전지", "배터리", "2차"), ("#10B981", "#03140E")),
        (("바이오", "제약", "헬스"), ("#2DD4BF", "#04140F")),
        (("자동차", "모빌리티"), ("#F43F5E", "#160309")),
    ]
    for keys, pal in table:
        if any(k in t for k in keys):
            return pal
    return ("#3182F6", "#0B1220")

def _chart_pts(cdir, seed=0):
    """추세 라인 포인트(viewBox 0..320 x, 0..150 y, y반전). up=상승/down=하락/flat=완만."""
    import random
    rnd = random.Random(seed or 7)
    n = 8
    if cdir == "up":
        base = [110 - i * 11 + rnd.randint(-8, 8) for i in range(n)]
    elif cdir == "down":
        base = [30 + i * 11 + rnd.randint(-8, 8) for i in range(n)]
    else:
        base = [70 + rnd.randint(-16, 16) for _ in range(n)]
    base = [max(10, min(140, v)) for v in base]
    step = 320 / (n - 1)
    pts = [(round(i * step, 1), round(v, 1)) for i, v in enumerate(base)]
    line = " ".join(f"{x},{y}" for x, y in pts)
    area = f"0,150 " + line + f" 320,150"
    return line, area

def build_slides(cfg, data, an):
    scenes = an.get("scenes", [])
    total = len(scenes)
    slides = []
    for i, sc in enumerate(scenes):
        v = sc.get("v", "")
        line, area = _chart_pts(sc.get("c", ""), seed=i + 3)
        slides.append({
            "type": "scene", "idx": i,
            "text": sc.get("t", ""), "sub": sc.get("s", ""),
            "cdir": sc.get("c", ""),
            "bar": sc.get("bar", 0) or 0,
            "n": str(sc.get("n", "") or ""),
            "unit": sc.get("u", "") or "",
            "chart_line": line, "chart_area": area,
            "img_key": (f"s{i}" if v else None),
            "kicker": data.get("date", ""),
            "page": f"{i+1} / {total}",
        })
    return slides

# ---------- 렌더 ----------
def _hex_rgb(h):
    h = (h or "#3182F6").lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    try: return f"{int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)}"
    except Exception: return "49,130,246"

def render(cfg, slides, d=None):
    css = (TEMPLATES / "base.css").read_text(encoding="utf-8")
    tmpl = Template((TEMPLATES / "slide.html").read_text(encoding="utf-8"))
    d = dict(d or cfg["design"])
    d["accent_rgb"] = _hex_rgb(d.get("accent"))
    d["up_rgb"] = _hex_rgb(d.get("up_color"))
    d["down_rgb"] = _hex_rgb(d.get("down_color"))
    out_dir = DATA / "slides"
    out_dir.mkdir(exist_ok=True)
    for f in out_dir.glob("*.png"):
        f.unlink()

    from playwright.sync_api import sync_playwright
    paths = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox", "--force-color-profile=srgb"])
        page = browser.new_page(viewport={"width": 1080, "height": 1920},
                                device_scale_factor=2)
        for i, sl in enumerate(slides):
            htmltext = tmpl.render(css=css, d=d, slide=sl)
            (DATA / "_slide.html").write_text(htmltext, encoding="utf-8")
            page.goto((DATA / "_slide.html").as_uri())
            page.wait_for_timeout(180)  # 폰트 적용 대기
            p = out_dir / f"{i:02d}.png"
            page.screenshot(path=str(p))
            paths.append(str(p))
            log(f"[render] slide {i} ({sl['type']}) -> {p.name}")
        browser.close()
    return paths

def main():
    cfg = load_config()
    data = read_json(DATA / "data.json")
    an = read_json(DATA / "analysis.json")
    slides = build_slides(cfg, data, an)
    for sl in slides:
        k = sl.get("img_key")
        if k and (DATA / "images" / f"{k}.png").exists():
            sl["bg_image"] = f"images/{k}.png"
    try:
        cards = set(read_json(DATA / "images" / "_cards.json").get("cards", []))
    except Exception:
        cards = set()
    for sl in slides:
        sl["is_card"] = sl.get("idx") in cards and bool(sl.get("bg_image"))
    write_json(DATA / "slides_meta.json", slides)
    ac, bg = theme_palette(an.get("theme", ""))
    d = dict(cfg["design"]); d["accent"] = ac; d["bg"] = bg
    log(f"[render] theme={an.get('theme')} accent={ac}")
    paths = render(cfg, slides, d)
    write_json(DATA / "narration.json", {"text": an.get("narration", "")})
    log(f"[render] {len(paths)} slides rendered")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
