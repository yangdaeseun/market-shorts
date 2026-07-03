"""
researcher.py — '리서처'. 오늘 호재/악재 뉴스 + 앞으로의 호재·악재 일정(캘린더)을 조사.
- 규칙 기반: 옵션·선물 만기(둘째 목요일) 등 날짜로 계산되는 이벤트
- AI 조사(제미나이): 최근 뉴스+지식으로 향후 2주 실적발표·경제지표·정책 이벤트 정리
결과 → data/events.json  (analyze/seo 가 영상·설명에 반영)
키 없으면 규칙+샘플로 동작(안전).
"""
import sys, os, json, datetime, pathlib, traceback
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, write_json, DATA

def kst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)

def nth_weekday(year, month, weekday, n):
    d = datetime.date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + datetime.timedelta(days=offset + 7 * (n - 1))

def next_option_expiry(today):
    """한국 파생 만기 = 매월 둘째 목요일. 지난달이면 다음달."""
    y, m = today.year, today.month
    exp = nth_weekday(y, m, 3, 2)  # 목=3
    if exp < today:
        m2, y2 = (m % 12 + 1, y + (1 if m == 12 else 0))
        exp = nth_weekday(y2, m2, 3, 2)
    quarterly = exp.month in (3, 6, 9, 12)
    return exp, quarterly

def rule_events(today):
    ev = []
    exp, q = next_option_expiry(today)
    ev.append({"date": exp.strftime("%m/%d"),
               "name": ("분기 " if q else "") + "옵션·선물 만기(변동성 주의)",
               "kind": "악재"})
    return ev

def gemini_events(data, today):
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"].strip(), transport="rest")
    heads = data.get("headlines", [])
    prompt = (
        f"오늘은 {today:%Y-%m-%d (%A)} (한국시간). 아래 뉴스와 네 지식으로 "
        "한국 주식 투자자에게 중요한 '향후 약 2주 이벤트 캘린더'와 '오늘의 호재/악재'를 정리하라.\n"
        "실적 발표일, 미국 CPI·고용·FOMC, 한국 금통위, 대형 IPO/상장, 주요 정책 발표 등을 포함.\n"
        "날짜가 불확실하면 추측하지 말고 'kind만' 넣거나 제외하라(가짜 날짜 금지).\n"
        f"[뉴스]\n{json.dumps(heads, ensure_ascii=False)}\n\n"
        "아래 JSON만 출력:\n"
        '{"today_positive":["오늘 호재 한 줄","..."],'
        '"today_negative":["오늘 악재 한 줄","..."],'
        '"upcoming":[{"date":"MM/DD 또는 이번 주/다음 주","name":"이벤트","kind":"호재|악재|중립"}]}'
    )
    for name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        try:
            m = genai.GenerativeModel(name)
            r = m.generate_content(prompt, generation_config={
                "response_mime_type": "application/json", "temperature": 0.5},
                request_options={"timeout": 45})
            log(f"[research] gemini ok: {name}")
            return json.loads(r.text)
        except Exception as e:
            log(f"[research] {name} 실패: {e}")
    raise RuntimeError("research gemini 실패")

def mock(today):
    return {
        "today_positive": ["환율 하락에 외국인 수급 개선", "AI 밸류체인 투자 모멘텀 지속"],
        "today_negative": ["반도체 대형주 매물 소화", "한은 매파적 기조 경계"],
        "upcoming": [
            {"date": "07/07", "name": "삼성전자 2분기 잠정실적(실적장세 스타트)", "kind": "호재"},
            {"date": "07/10", "name": "SK하이닉스 나스닥 ADR 상장 추진", "kind": "호재"},
            {"date": "07/14", "name": "미국 6월 CPI 발표(금리 경로 리딩)", "kind": "악재"},
            {"date": "07/16", "name": "한국은행 금융통화위원회", "kind": "악재"},
            {"date": "07/23", "name": "SK하이닉스 2분기 실적(HBM 증명)", "kind": "호재"},
        ],
    }

def main():
    ap = __import__("argparse").ArgumentParser(); ap.add_argument("--mock", action="store_true")
    args = ap.parse_args(); load_config()
    data = read_json(DATA / "data.json")
    today = kst_now().date()
    if not args.mock and os.environ.get("GEMINI_API_KEY"):
        try:
            ev = gemini_events(data, today)
        except Exception as e:
            log(f"[research] AI 실패 → mock ({e})"); ev = mock(today)
    else:
        log("[research] MOCK/no-key"); ev = mock(today)
    # 규칙 이벤트 병합(중복 대충 방지)
    up = ev.get("upcoming", [])
    names = " ".join(x.get("name", "") for x in up)
    for r in rule_events(today):
        if "만기" not in names:
            up.append(r)
    ev["upcoming"] = up
    write_json(DATA / "events.json", ev)
    log(f"[research] 오늘 호재 {len(ev.get('today_positive',[]))} / 일정 {len(up)}건")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc(); sys.exit(1)
