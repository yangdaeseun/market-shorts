"""
seo.py — 업로드용 제목/설명/태그/고정댓글 자동 생성. → data/meta.json
"""
import sys, re, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, write_json, DATA

def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "")

def build(cfg, data, an):
    date = data.get("date", datetime.date.today().isoformat())
    head = strip_tags(an.get("headline_html", an.get("one_liner", "밤사이 증시 요약")))
    prefix = cfg["channel"]["title_prefix"]

    title = f"{prefix} | {head} ({date}) #shorts"
    title = title[:95]

    why_lines = [f"• {strip_tags(w.get('lead',''))}" for w in an.get("why", [])[:4]]
    ko = an.get("korea", {})
    desc = (
        f"{an.get('one_liner','')}\n\n"
        f"📊 밤사이 핵심\n" + "\n".join(why_lines) + "\n\n"
        f"🇰🇷 오늘 한국장: {ko.get('line','')}\n{ko.get('note','')}\n\n"
        "매일 아침, 밤사이 세계증시를 1분 안에 정리해 드립니다. 구독 부탁드려요!\n\n"
        "#증시 #미국증시 #나스닥 #비트코인 #주식 #코스피 #경제 #재테크 #shorts\n\n"
        "※ 본 영상은 정보 제공 목적이며 투자 권유가 아닙니다."
    )

    tags = ["증시", "미국증시", "나스닥", "S&P500", "비트코인", "코스피",
            "주식", "경제뉴스", "재테크", "시황", "환율", "금리", "shorts"]

    pinned = f"오늘 시장, 여러분은 어떻게 보시나요? 👇 댓글로 알려주세요!"

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
