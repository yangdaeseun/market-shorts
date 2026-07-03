"""
copywriter.py — 훅·제목을 여러 개 만들고 CTR 예측으로 베스트 선택.
analysis.json 의 내용으로 훅 10개·제목 10개를 생성→점수화→최고점 채택.
- 첫 장면(scene[0].t)을 최적 훅으로 교체
- result['title_final'] 에 최적 제목 저장(seo가 사용)
- 최근 제목과 겹치면 회피
키 없으면 아무것도 안 바꿈(안전).
"""
import sys, os, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import log, read_json, write_json, DATA

HIST = DATA / "history.json"

def recent_titles(n=15):
    try:
        h = json.loads(HIST.read_text(encoding="utf-8"))
        return [x.get("title") for x in h[-n:] if x.get("title")]
    except Exception:
        return []

def gen():
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"].strip(), transport="rest")
    an = read_json(DATA / "analysis.json")
    ctx = {"theme": an.get("theme"), "hook": an.get("hook"),
           "cause": an.get("cause"), "stocks": [s.get("name") for s in an.get("stocks", [])],
           "summary": an.get("summary"), "scenes": [s.get("t") for s in an.get("scenes", [])[:6]]}
    prompt = (
        "너는 주식 유튜브 쇼츠 카피라이터다. 아래 내용으로 시청자가 '클릭·끝까지'하게 만드는 "
        "훅 10개와 제목 10개를 만들고, 각 CTR 가능성을 0~100으로 예측하라. 낚시성 과장/허위 금지.\n"
        f"[최근 제목(겹치지 말 것)] {recent_titles()}\n"
        f"[내용]\n{json.dumps(ctx, ensure_ascii=False)}\n\n"
        "아래 JSON만 출력:\n"
        '{"hooks":[{"t":"훅(12자내,강하게)","ctr":0~100}],'
        '"titles":[{"t":"제목(28자내,궁금증형)","ctr":0~100}]}'
    )
    for name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        try:
            m = genai.GenerativeModel(name)
            r = m.generate_content(prompt, generation_config={
                "response_mime_type": "application/json", "temperature": 0.9},
                request_options={"timeout": 45})
            return json.loads(r.text)
        except Exception as e:
            log(f"[copy] {name} 실패: {e}")
    raise RuntimeError("copywriter gemini 실패")

def best(cands):
    cands = [c for c in cands if c.get("t")]
    if not cands:
        return None
    return sorted(cands, key=lambda c: -int(c.get("ctr", 0)))[0]

def main():
    if not os.environ.get("GEMINI_API_KEY"):
        log("[copy] no key, skip"); return 0
    try:
        out = gen()
    except Exception as e:
        log(f"[copy] 실패 → 원본 유지 ({e})"); return 0
    an = read_json(DATA / "analysis.json")
    bh, bt = best(out.get("hooks", [])), best(out.get("titles", []))
    if bh and an.get("scenes"):
        log(f"[copy] 훅 채택: {bh['t']} (CTR {bh.get('ctr')})")
        an["scenes"][0]["t"] = bh["t"]
        an["hook"] = bh["t"]
    if bt:
        log(f"[copy] 제목 채택: {bt['t']} (CTR {bt.get('ctr')})")
        an["title_final"] = bt["t"]
    write_json(DATA / "analysis.json", an)
    return 0

if __name__ == "__main__":
    main()
