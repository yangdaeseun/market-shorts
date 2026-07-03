"""
seo.py — 업로드용 제목/설명/태그/고정댓글 자동 생성 → data/meta.json
전략 브리핑 스키마 대응. 시간대(slot) 태그로 하루 여러 편도 제목이 구분됨.
유튜브 금지문자(< >)는 제거.
"""
import sys, re, datetime, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, write_json, DATA

SLOT_TAG = {"morning":"아침브리핑","preopen":"개장직전","intraday":"장중점검",
            "close":"마감복기","uspreview":"미국장프리뷰"}

def strip_tags(s): return re.sub(r"<[^>]+>", "", s or "")
def clean(s): return strip_tags(s).replace("<","").replace(">","").strip()

def build(cfg, data, an):
    date = data.get("date", datetime.date.today().isoformat())
    prefix = cfg["channel"]["title_prefix"]
    tag = SLOT_TAG.get(an.get("slot","morning"), "브리핑")
    hook = clean(an.get("hook", an.get("one_liner", "오늘의 시장 전략")))
    tfinal = clean(an.get("title_final", ""))

    title = f"[{tag}] {tfinal or hook} | {prefix} ({date}) #shorts"
    title = clean(title)[:95]

    c = an.get("cause", {})
    k = an.get("kr_impact", {})
    secs = an.get("sectors", [])[:3]
    st = an.get("stocks", [])[:5]
    pb = an.get("playbook", {})

    P = [clean(an.get("hook","")), clean(an.get("summary","")), ""]
    P += [f"[ 원인 ] {clean(c.get('primary',''))} ({clean(c.get('type',''))})",
          f"[ 국내 영향도 ] {clean(k.get('level',''))} · {clean(k.get('reason',''))}", ""]
    if secs:
        P += ["[ 강한 섹터 ]"] + [f"- {clean(x.get('name',''))}: {clean(x.get('reason',''))}" for x in secs] + [""]
    if st:
        P += ["[ 관심 종목 ]"] + [f"- {clean(x.get('name',''))}: {clean(x.get('reason',''))}" for x in st] + [""]
    if pb:
        P += ["[ 대응 전략 ]",
              f"- 갭상승: {clean(pb.get('gap_up',''))}",
              f"- 갭하락: {clean(pb.get('gap_down',''))}",
              f"- 횡보: {clean(pb.get('flat',''))}", ""]
    cats = [clean(x) for x in an.get("catalysts", [])[:3]]
    risks = [clean(x) for x in an.get("risks", [])[:3]]
    events = [clean(x) for x in an.get("events", [])[:5]]
    if cats: P += ["[ 오늘 호재 ]"] + [f"- {c}" for c in cats] + [""]
    if risks: P += ["[ 리스크 ]"] + [f"- {r}" for r in risks] + [""]
    if events: P += ["[ 호재·악재 일정 캘린더 ]"] + [f"- {e}" for e in events] + [""]
    P += ["매일 장 전, 오늘 대응 전략을 1분으로 정리합니다. 구독하고 놓치지 마세요!",
          "", "#주식 #증시 #코스피 #미국증시 #나스닥 #반도체 #AI #종목추천 #재테크 #shorts",
          "", "본 영상은 정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단과 책임은 본인에게 있습니다."]
    desc = clean("\n".join(P)) if False else "\n".join(P).replace("<","").replace(">","")

    tags = ["주식","증시","코스피","미국증시","나스닥","반도체","AI반도체","HBM",
            "종목","섹터","시황","증시전망","재테크","경제","shorts"]
    pinned = "오늘 어떤 종목·섹터 보고 계세요? 댓글로 같이 체크해요!"
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
