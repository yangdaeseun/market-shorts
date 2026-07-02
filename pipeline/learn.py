"""
learn.py — 성과 학습 루프(가벼운 버전).
- log: 발행 결과를 logs/history.jsonl 에 누적
- report: 누적된 영상들의 조회수를 YouTube API로 받아 베스트 패턴 출력
analyze.py 가 history 의 베스트 헤드라인을 '잘 먹힌 표현' 힌트로 참고할 수 있음.
"""
import sys, os, json, datetime, argparse, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import log, read_json, LOGS, DATA

HIST = LOGS / "history.jsonl"

def log_publish():
    meta = read_json(DATA / "meta.json")
    res = {}
    try: res = read_json(DATA / "upload_result.json")
    except Exception: pass
    rec = {"date": datetime.date.today().isoformat(),
           "title": meta.get("title"), "video_id": res.get("video_id"),
           "score": json.loads((DATA / "score.json").read_text())["score"]
                    if (DATA / "score.json").exists() else None}
    LOGS.mkdir(exist_ok=True)
    with open(HIST, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log(f"[learn] logged: {rec['title']}")

def report():
    if not HIST.exists():
        log("[learn] no history yet"); return
    ids = []
    for line in HIST.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("video_id"): ids.append((r["video_id"], r["title"]))
    if not ids or not os.environ.get("YT_REFRESH_TOKEN"):
        log("[learn] need video ids + token for stats"); return
    from pipeline.upload import get_service
    yt = get_service()
    stats = []
    for i in range(0, len(ids), 50):
        chunk = ids[i:i+50]
        resp = yt.videos().list(part="statistics",
                                id=",".join(c[0] for c in chunk)).execute()
        vmap = {it["id"]: int(it["statistics"].get("viewCount", 0))
                for it in resp["items"]}
        for vid, title in chunk:
            stats.append((vmap.get(vid, 0), title))
    stats.sort(reverse=True)
    log("[learn] === TOP 5 by views ===")
    for v, t in stats[:5]:
        log(f"[learn]  {v:>8,}  {t}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["log", "report"])
    a = ap.parse_args()
    if a.mode == "log": log_publish()
    else: report()

if __name__ == "__main__":
    main()
