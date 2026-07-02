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
    idx = data.get("indices", {})
    crypto = data.get("crypto", {})
    slides = []

    hero = None
    for nm, d in idx.items():
        if d.get("pct") is None:
            continue
        if hero is None or abs(d["pct"]) > abs(hero[1]):
            hero = (nm, d["pct"])
    hn = hero[0] if hero else ""
    hp = fmt_pct(hero[1]) if hero else ""
    hd = dir_cls(hero[1]) if hero else "flat"
    date = data.get("date", "")
    prefix = cfg["channel"]["title_prefix"]

    # 1) 표지
    slides.append({"type": "cover", "img_key": "cover",
        "eyebrow": f"{date} · 밤사이 글로벌 시황",
        "hero_name": hn, "hero_pct": hp, "hero_dir": hd,
        "title_html": hl(an.get("headline_html", "")),
        "subtitle": an.get("one_liner", ""), "foot": prefix})

    # 2) 지수 한눈에 (미국+한국+비트)
    items = []
    for nm in ["나스닥", "S&P 500", "코스피", "코스닥"]:
        d = idx.get(nm)
        if d and d.get("pct") is not None:
            items.append({"name": nm, "sub": d.get("ticker", ""),
                          "pct": fmt_pct(d["pct"]), "dir": dir_cls(d["pct"]),
                          "val": fmt_price(nm, d.get("price"))})
    bt = crypto.get("비트코인")
    if bt and bt.get("pct") is not None:
        items.append({"name": "비트코인", "sub": "BTC", "pct": fmt_pct(bt["pct"]),
                      "dir": dir_cls(bt["pct"]), "val": fmt_price("비트코인", bt.get("price"))})
    slides.append({"type": "indices", "eyebrow": "오늘 한눈에", "page": "1",
                   "title_html": "지수 <span class='em'>한눈에</span>", "items": items[:5]})

    # 3) 왜 움직였나
    slides.append({"type": "why", "img_key": "why", "eyebrow": "핵심 이유", "page": "2",
                   "title_html": "왜 <span class='em'>이렇게</span> 움직였나",
                   "items": [{"cls": ("is-up" if w.get("dir") == "up" else "is-down" if w.get("dir") == "down" else ""),
                              "lead_html": html.escape(w.get("lead", "")), "body": w.get("body", "")}
                             for w in an.get("why", [])[:4]]})

    # 4) 지지선
    sup = an.get("supports", [])
    if sup:
        slides.append({"type": "rows", "img_key": "supports", "eyebrow": "지지선 체크", "page": "3",
                       "title_html": "지켜야 할 <span class='em'>지지선</span>",
                       "items": [{"name": x.get("name", ""), "dir": "flat",
                                  "rate": x.get("level", ""), "price": x.get("note", "")} for x in sup[:4]]})

    # 5) 주목 종목
    wl = an.get("watchlist", [])
    if wl:
        slides.append({"type": "why", "img_key": "watch", "eyebrow": "주목 종목", "page": "4",
                       "title_html": "눈여겨볼 <span class='em'>종목·섹터</span>",
                       "items": [{"cls": "is-pos", "lead_html": html.escape(w.get("name", "")),
                                  "body": w.get("reason", "")} for w in wl[:3]]})

    # 6) 호재 vs 악재
    fac = an.get("factors", {})
    fitems = ([{"cls": "is-neg", "lead_html": "\U0001F534 " + html.escape(x), "body": ""} for x in fac.get("neg", [])[:3]]
              + [{"cls": "is-pos", "lead_html": "\U0001F7E2 " + html.escape(x), "body": ""} for x in fac.get("pos", [])[:3]])
    if fitems:
        slides.append({"type": "why", "img_key": "factors", "eyebrow": "종합 변수", "page": "5",
                       "title_html": "<span class='em'>호재</span> vs 악재", "items": fitems})

    # 7) 한국장 + 단기/장기 관점
    ko = an.get("korea", {})
    vw = an.get("views", {})
    note = ko.get("note", "")
    if vw.get("short") or vw.get("long"):
        note = f"단기 · {vw.get('short','')}   /   장기 · {vw.get('long','')}"
    slides.append({"type": "korea", "img_key": "korea", "eyebrow": "오늘 한국장 · 관점", "page": "6",
                   "tag": "KOSPI 전망", "line_html": html.escape(ko.get("line", "")),
                   "note": note, "cta_html": "오늘 시장, <span class='q'>어떻게 보시나요?</span> 👇"})
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
    for sl in slides:
        k = sl.get("img_key")
        if k and (DATA / "images" / f"{k}.png").exists():
            sl["bg_image"] = f"images/{k}.png"
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
