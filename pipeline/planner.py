"""
planner.py — '콘텐츠 기획 AI'. 매일 어떤 영상을 만들지 결정한다(가장 중요·핵심).
같은 데이터라도 앵글(관점)을 매일 바꿔서 채널이 반복되지 않게 한다.
- 오늘 데이터/뉴스 + 시간대 + 요일 + 최근 앵글 이력 → 조회수 잘 나올 앵글 1개 선택
- 최근과 겹치면 다른 앵글로 전환
결과 → data/plan.json  (analyze가 이 앵글로 깊게 분석)
"""
import sys, os, json, argparse, datetime, pathlib, traceback
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, write_json, DATA

HIST = DATA / "history.json"

# 앵글 카탈로그(유형 → 기본 제목 톤). title은 planner가 그날 맞게 다시 씀.
ANGLES = [
    ("headline",     "오늘 이 뉴스 하나만 보세요"),
    ("money_sector", "오늘 돈 되는 섹터는 여기"),
    ("risk_stock",   "지금 추격매수 위험한 종목"),
    ("schedule",     "오늘 꼭 봐야 할 일정"),
    ("misread",      "다들 오해하는 오늘 뉴스"),
    ("catalyst",     "놓치면 안 되는 오늘 호재"),
    ("leader",       "오늘 주도주 후보는?"),
    ("hidden",       "사람들이 놓친 숨은 수혜주"),
    ("overdone",     "악재가 과장된 종목"),
    ("tomorrow",     "내일까지 이어질 이슈"),
    ("hidden_link",  "시장의 숨은 연결고리"),
    ("ai_pick",      "AI가 오늘 가장 중요하다고 본 것"),
]
ANGLE_IDS = [a for a, _ in ANGLES]

# 요일/시간대 특화 앵글(있으면 우선 후보로)
def weekday_angles(dt, slot):
    wd = dt.weekday()  # 월=0 ... 일=6
    if wd == 5 or wd == 6:  # 주말
        return [("weekly_top", "이번 주 가장 중요한 변화 TOP5")]
    if wd == 0:  # 월요일
        return [("week_plan", "이번 주 시장 전략")]
    if wd == 4:  # 금요일
        return [("next_week", "다음 주 준비 포인트")]
    if slot == "close":
        return [("recap", "오늘 시장이 말해준 것"), ("tomorrow", "내일까지 이어질 이슈")]
    if slot == "uspreview":
        return [("us_variable", "오늘 미국장이 가장 민감할 변수")]
    return []

def recent_angle_ids(n=5):
    try:
        h = json.loads(HIST.read_text(encoding="utf-8"))
        return [x.get("angle") for x in h[-n:]]
    except Exception:
        return []

def append_history(entry):
    try:
        h = json.loads(HIST.read_text(encoding="utf-8")) if HIST.exists() else []
    except Exception:
        h = []
    h.append(entry)
    HIST.write_text(json.dumps(h[-60:], ensure_ascii=False, indent=1), encoding="utf-8")

def pick_rotation(dt, slot, recent):
    """키/오프라인용: 요일특화 우선, 아니면 최근과 안 겹치게 회전 선택."""
    wa = weekday_angles(dt, slot)
    if wa:
        return wa[0]
    base = dt.timetuple().tm_yday * 5 + {"morning":0,"preopen":1,"intraday":2,"close":3,"uspreview":4}.get(slot,0)
    for i in range(len(ANGLES)):
        aid, title = ANGLES[(base + i) % len(ANGLES)]
        if aid not in recent:
            return (aid, title)
    return ANGLES[base % len(ANGLES)]

def gemini_plan(data, slot, dt, recent):
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"].strip(), transport="rest")
    cat = "\n".join(f"- {a}: {t}" for a, t in ANGLES)
    wd = ["월","화","수","목","금","토","일"][dt.weekday()]
    prompt = (
        "너는 주식 유튜브 숏츠 콘텐츠 기획자다. 오늘 데이터/뉴스를 보고 "
        "'조회수가 가장 잘 나올 앵글(관점) 1개'를 골라라. 뉴스 요약이 아니라 '궁금증→답' 구조.\n"
        f"[시간대] {slot} / [요일] {wd}요일\n"
        f"[최근 사용한 앵글(겹치지 말 것)] {recent}\n"
        f"[선택 가능한 앵글 유형]\n{cat}\n"
        f"[오늘 데이터]\n{json.dumps(data, ensure_ascii=False)}\n\n"
        "아래 JSON만 출력:\n"
        '{"angle":"위 유형 id 중 하나","title":"클릭 부르는 궁금증형 제목(18자내, 물음표/후킹)",'
        '"focus":"이 앵글로 깊게 팔 핵심 한 줄","keyword":"핵심 키워드",'
        '"why_this":"왜 오늘 이 앵글이 조회수에 유리한지 한 줄"}'
    )
    for name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        try:
            m = genai.GenerativeModel(name)
            r = m.generate_content(prompt, generation_config={
                "response_mime_type": "application/json", "temperature": 0.9},
                request_options={"timeout": 45})
            j = json.loads(r.text)
            if j.get("angle"):
                log(f"[planner] gemini pick: {j['angle']} ({name})")
                return j
        except Exception as e:
            log(f"[planner] {name} 실패: {e}")
    raise RuntimeError("planner gemini 실패")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--mock", action="store_true")
    args = ap.parse_args(); load_config()
    data = read_json(DATA / "data.json")
    slot = os.environ.get("SLOT", "morning").strip() or "morning"
    dt = datetime.datetime.utcnow() + datetime.timedelta(hours=9)  # KST
    recent = recent_angle_ids()

    plan = None
    if not args.mock and os.environ.get("GEMINI_API_KEY"):
        try:
            plan = gemini_plan(data, slot, dt, recent)
        except Exception as e:
            log(f"[planner] Gemini 실패 → 회전 선택 ({e})")
    if not plan:
        aid, title = pick_rotation(dt, slot, recent)
        plan = {"angle": aid, "title": title,
                "focus": "오늘 데이터에서 가장 임팩트 있는 포인트",
                "keyword": "", "why_this": "최근과 겹치지 않는 앵글로 전환"}

    plan["slot"] = slot
    write_json(DATA / "plan.json", plan)
    append_history({"date": dt.date().isoformat(), "slot": slot,
                    "angle": plan.get("angle"), "title": plan.get("title")})
    log(f"[planner] 오늘 앵글 = {plan.get('angle')} | {plan.get('title')}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc(); sys.exit(1)
