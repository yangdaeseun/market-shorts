"""
seo.py — 업로드용 제목/설명/태그/고정댓글 자동 생성. → data/meta.json
유튜브가 금지하는 홑화살괄호(< >)는 제목·설명에서 완전히 제거한다.
"""
import sys, re, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, write_json, DATA

def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "")

def clean(s):
    # 태그 제거 + 남은 < > 완전 제거 (유튜브 설명 금지문자)
    return strip_tags(s).replace("<", "").replace(">", "").strip()

def build(cfg, data, an):
    date = data.get("date", datetime.date.today().isoformat())
    head = clean(an.get("headline_html", an.get("one_liner", "밤사이 증시 요약")))
    prefix = cfg["channel"]["title_prefix"]

    title = f"{prefix} | {head} ({date}) #shorts"
    title = title.replace("<", "").replace(">", "")[:95]

    why_lines = [f"- {clean(w.get('lead',''))}" for w in an.get("why", [])[:5]]
    ko = an.get("korea", {})
    fac = an.get("factors", {})
    neg = [f"- {clean(x)}" for x in fac.get("neg", [])[:3]]
    pos = [f"- {clean(x)}" for x in fac.get("pos", [])[:3]]

    parts = [clean(an.get("one_liner", "")), "",
             "[ 밤사이 핵심 ]"] + why_lines + [
             "", f"[ 오늘 한국장 ] {clean(ko.get('line',''))}", clean(ko.get('note',''))]
    if neg:
        parts += ["", "[ 악재 ]"] + neg
    if pos:
        parts += ["", "[ 호재 ]"] + pos
    sup = an.get("supports", [])
    if sup:
        parts += ["", "[ 지켜야 할 지지선 ]"] + [f"- {clean(x.get('name',''))} {clean(x.get('level',''))} ({clean(x.get('note',''))})" for x in sup[:4]]
    wl = an.get("watchlist", [])
    if wl:
        parts += ["", "[ 주목 종목 ]"] + [f"- {clean(w.get('name',''))}: {clean(w.get('reason',''))}" for w in wl[:3]]
    vw = an.get("views", {})
    if vw.get("short") or vw.get("long"):
        parts += ["", f"[ 관점 ] 단기 · {clean(vw.get('short',''))} / 장기 · {clean(vw.get('long',''))}"]
    parts += ["", "매일 아침, 밤사이 세계증시를 1분 안에 정리해 드립니다. 구독 부탁드려요!",
              "", "#증시 #미국증시 #나스닥 #비트코인 #주식 #코스피 #반도체 #경제 #재테크 #shorts",
              "", "본 영상은 정보 제공 목적이며 투자 권유가 아닙니다."]
    desc = "\n".join(parts)
    desc = desc.replace("<", "").replace(">", "")

    tags = ["증시", "미국증시", "나스닥", "S&P500", "비트코인", "코스피",
            "주식", "반도체", "경제뉴스", "재테크", "시황", "환율", "금리", "shorts"]
    pinned = "오늘 시장, 여러분은 어떻게 보시나요? 댓글로 알려주세요!"

    return {"title": title, "description": desc, "tags": tags,
            "pinned_comment": pinned, "privacy": cfg["publish"]["privacy"],
            "category_id": cfg["publish"]["category_id"],
            "made_for_kids": cfg["publish"]["made_for_kids"]}

def main():
    cfg = load_config()
    data = read_json(DATA / "data.json")
    an = read_json(DATA / "analysis.json")
    meta = build(cfg, data, an)
    write_json(DATA / "meta.json", meta)
    log(f"[seo] title = {meta['title']}")
    return 0

if __name__ == "__main__":
    main()
