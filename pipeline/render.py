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

# ---------- 슬라이드 빌더 ----------
def build_slides(cfg, data, an):
    date = data.get("date", "")
    slides = []

    # 훅: 밤사이 가장 크게 움직인 지수를 표지 큰 숫자로 (첫 3초 임팩트)
    hero = None
    for nm, d in data.get("indices", {}).items():
        if d.get("pct") is None:
            continue
        if hero is None or abs(d["pct"]) > abs(hero[1]):
            hero = (nm, d["pct"])
    hero_name = hero[0] if hero else ""
    hero_pct = fmt_pct(hero[1]) if hero else ""
    hero_dir = dir_cls(hero[1]) if hero else "flat"

    # 1) 표지
    slides.append({
        "type": "cover",
        "eyebrow": f"{date} · 밤사이 글로벌 시황",
        "hero_name": hero_name, "hero_pct": hero_pct, "hero_dir": hero_dir,
        "title_html": hl(an.get("headline_html", an.get("one_liner", ""))),
        "subtitle": an.get("one_liner", ""),
        "foot": cfg["channel"]["title_prefix"],
    })

    # 2) 지수
    items = []
    for name, d in data.get("indices", {}).items():
        items.append({"name": name, "sub": d.get("ticker", ""),
                      "pct": fmt_pct(d.get("pct")), "dir": dir_cls(d.get("pct")),
                      "val": fmt_price(name, d.get("price"))})
    slides.append({"type": "indices", "eyebrow": "미국 증시",
                   "page": "1", "title_html": "3대 지수 <span class='em'>한눈에</span>",
                   "items": items})

    # 3) 왜? (시그니처)
    whys = []
    for w in an.get("why", [])[:4]:
        cls = {"up": "is-up", "down": "is-down"}.get(w.get("dir"), "")
        whys.append({"cls": cls, "lead_html": html.escape(w.get("lead", "")),
                     "body": w.get("body", "")})
    slides.append({"type": "why", "eyebrow": "핵심 이유",
                   "page": "2", "title_html": "왜 <span class='em'>이렇게</span> 움직였나",
                   "items": whys})

    # 4) 코인·유가·금·환율·금리
    rows = []
    order = ["비트코인", "이더리움", "WTI 유가", "금", "달러인덱스", "원/달러", "미 국채 10년"]
    src = {**data.get("crypto", {}), **data.get("macro", {})}
    for name in order:
        if name in src:
            d = src[name]
            rows.append({"name": name, "dir": dir_cls(d.get("pct")),
                         "rate": fmt_pct(d.get("pct")),
                         "price": fmt_price(name, d.get("price"))})
    slides.append({"type": "rows", "eyebrow": "코인·원자재·환율",
                   "page": "3", "title_html": "그 외 <span class='em'>시장</span>",
                   "items": rows})

    # 5) 한국장 전망 + 댓글유도
    ko = an.get("korea", {})
    slides.append({"type": "korea", "eyebrow": "오늘 한국장",
                   "page": "4", "tag": "KOSPI 전망",
                   "line_html": html.escape(ko.get("line", "")),
                   "note": ko.get("note", ""),
                   "cta_html": "오늘 시장, <span class='q'>어떻게 보시나요?</span> 👇"})

    # 6) 호재 vs 악재 (종합 변수)
    fac = an.get("factors", {})
    fitems = ([{"cls": "is-neg", "lead_html": "\U0001F534 " + html.escape(x), "body": ""} for x in fac.get("neg", [])]
              + [{"cls": "is-pos", "lead_html": "\U0001F7E2 " + html.escape(x), "body": ""} for x in fac.get("pos", [])])
    if fitems:
        slides.append({"type": "why", "eyebrow": "종합 변수", "page": "5",
                       "title_html": "<span class='em'>호재</span> vs 악재", "items": fitems})
    return slides

# ---------- 렌더 ----------
def render(cfg, slides):
    css = (TEMPLATES / "base.css").read_text(encoding="utf-8")
    tmpl = Template((TEMPLATES / "slide.html").read_text(encoding="utf-8"))
    d = cfg["design"]
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
    # 배경 이미지 연결: cover→cover, 첫 why→why, 둘째 why(호재악재)→factors, korea→korea
    seen_why = False
    for sl in slides:
        t = sl.get("type"); key = None
        if t == "cover": key = "cover"
        elif t == "korea": key = "korea"
        elif t == "why":
            key = "why" if not seen_why else "factors"; seen_why = True
        if key and (DATA / "images" / f"{key}.png").exists():
            sl["bg_image"] = f"images/{key}.png"
    write_json(DATA / "slides_meta.json", slides)
    paths = render(cfg, slides)
    write_json(DATA / "narration.json", {"text": an.get("narration", "")})
    log(f"[render] {len(paths)} slides rendered")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
