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
def _stars(n):
    try: n=int(n)
    except Exception: n=3
    n=max(1,min(5,n))
    return "★"*n + "☆"*(5-n)

def build_slides(cfg, data, an):
    prefix = cfg["channel"]["title_prefix"]
    date = data.get("date", "")
    label = an.get("slot_label", "오늘 대응 브리핑")
    slides = []

    # 1) 3초 훅 (표지)
    slides.append({"type": "cover", "img_key": "hook",
        "eyebrow": f"{date} · {label}",
        "hero_name": "", "hero_pct": "", "hero_dir": "flat",
        "title_html": html.escape(an.get("hook", an.get("one_liner", ""))),
        "subtitle": an.get("one_liner", ""), "foot": prefix})

    # 2) 원인 판별
    c = an.get("cause", {})
    slides.append({"type": "why", "img_key": "cause", "eyebrow": "왜 이런 일이", "page": "1",
        "title_html": "원인은 <span class='em'>이것</span>",
        "items": [
            {"cls": "is-up", "lead_html": html.escape(c.get("primary","")),
             "body": f"[{c.get('type','')}] {c.get('detail','')}"},
        ]})

    # 3) 국내 영향도 (별점)
    k = an.get("kr_impact", {})
    slides.append({"type": "impact", "eyebrow": "국내 시장 영향도", "page": "2",
        "title_html": "오늘 국내 <span class='em'>영향도</span>",
        "level": k.get("level","중"), "stars": _stars(k.get("stars",3)),
        "reason": k.get("reason","")})

    # 4) 강한 섹터 TOP3
    secs = an.get("sectors", [])[:3]
    slides.append({"type": "why", "img_key": "sectors", "eyebrow": "가장 강한 섹터", "page": "3",
        "title_html": "오늘 <span class='em'>섹터 TOP3</span>",
        "items": [{"cls": ("is-up" if x.get("dir")=="up" else "is-down"),
                   "lead_html": ("▲ " if x.get("dir")=="up" else "▼ ") + html.escape(x.get("name","")),
                   "body": x.get("reason","")} for x in secs]})

    # 5) 주목 종목 TOP5
    st = an.get("stocks", [])[:5]
    slides.append({"type": "why", "img_key": "stocks", "eyebrow": "먼저 볼 종목", "page": "4",
        "title_html": "관심 <span class='em'>종목 TOP5</span>",
        "items": [{"cls": "is-pos", "lead_html": html.escape(x.get("name","")),
                   "body": x.get("reason","")} for x in st]})

    # 6) 대응 시나리오
    pb = an.get("playbook", {})
    slides.append({"type": "rows", "img_key": "playbook", "eyebrow": "오늘 대응 전략", "page": "5",
        "title_html": "상황별 <span class='em'>대응</span>",
        "items": [
            {"name": "갭상승", "dir": "up",   "rate": "", "price": pb.get("gap_up","")},
            {"name": "갭하락", "dir": "down", "rate": "", "price": pb.get("gap_down","")},
            {"name": "횡보",   "dir": "flat", "rate": "", "price": pb.get("flat","")},
        ]})

    # 7) 리스크 & 오늘 일정
    risks = an.get("risks", [])[:3]
    events = an.get("events", [])[:3]
    items = [{"cls": "is-neg", "lead_html": "⚠ " + html.escape(r), "body": ""} for r in risks]
    items += [{"cls": "", "lead_html": "📅 " + html.escape(e), "body": ""} for e in events]
    slides.append({"type": "why", "eyebrow": "리스크 & 오늘 일정", "page": "6",
        "title_html": "조심 &amp; <span class='em'>체크</span>", "items": items})

    # 8) 10초 요약 (마무리)
    slides.append({"type": "korea", "img_key": "playbook", "eyebrow": "핵심 요약", "page": "7",
        "tag": "오늘 한 줄", "line_html": html.escape(an.get("summary","")),
        "note": an.get("one_liner",""),
        "cta_html": "도움 됐다면 <span class='q'>구독·저장</span> 👇"})
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
