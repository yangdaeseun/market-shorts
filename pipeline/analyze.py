"""
analyze.py — 시장 데이터+뉴스 → 'AI 시장 전략 브리핑'(JSON).
뉴스 요약이 아니라: 원인 판별 → 국내 영향도 → 섹터/종목 → 대응 시나리오 → 리스크 → 이벤트 → 요약.
시간대(SLOT)에 따라 역할/대본이 바뀜. 실시간 수급 등 무료로 알 수 없는 수치는 지어내지 않는다.
오프라인: python pipeline/analyze.py --mock
"""
import sys, os, json, argparse, pathlib, traceback
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, write_json, DATA, current_slot
from pipeline import kr_themes

SLOTS = {
    "morning":   "장 시작 전 · 오늘 대응 브리핑",
    "preopen":   "개장 직전 · 최종 점검",
    "intraday":  "장중 · 현재 흐름 점검",
    "close":     "마감 복기 · 내일 준비",
    "uspreview": "밤 · 미국장 프리뷰",
}

def slot_now():
    return current_slot()

SCHEMA_HINT = """
아래 JSON 하나만 출력(마크다운/백틱/설명 금지). 숫자는 제공된 실제 데이터만 사용.
핵심 원칙: 시청자가 "그래서 오늘 뭘 봐야 하는가"를 얻게 하라. 뉴스 나열 금지, '해석과 대응' 중심.
종목은 제공된 '테마→국내종목 관계도'에서 뉴스와 연관성 높은 것을 우선 선택(관계도 밖이어도 명백히 관련되면 허용).
장중(intraday) 슬롯이라도 실시간 기관/외국인 수급 '금액'은 알 수 없으니 지어내지 말 것(가격 흐름·뉴스 근거로만 서술).
매수 권유가 아니라 '정보 제공'. 단정 대신 '가능성/체크'로 표현. narration에서 '주목' 단어 대신 '눈여겨' 또는 '관심'을 쓸 것.
시청자 관점: 오늘 시청자가 가장 궁금해하고 클릭할 '핫한 종목·뉴스·시황'을 골라 구체적으로 설명하라(막연한 섹터 나열 금지).
{
  "hook": "3초 훅 — 오늘 가장 중요한 한 가지(16자내, 강렬하게)",
  "headline_html": "표지 제목, 핵심어 <up>..</up>/<down>..</down>(20자내)",
  "one_liner": "한 문장 요약(18자내)",
  "cause": {"primary":"가장 큰 원인(예: AI 투자 확대)","type":"AI투자|실적|금리|정책|옵션만기|숏커버|기관매수|유가|환율|기타","detail":"부연 한 줄(28자내)"},
  "kr_impact": {"level":"상|중|하","stars":4,"reason":"그 영향도인 이유 한 줄(26자내)"},
  "sectors": [{"name":"섹터명","dir":"up|down","reason":"이유 한 줄(22자내)"}],
  "stocks":  [{"name":"실제 상장 종목명(정확히)","tag":"대장주|수혜주|테마주|턴어라운드 중 1","reason":"지금 왜 핫한지 촉매+한줄 설명(구체적,38자내)"}],
  "hot_stock": {"name":"오늘 가장 핫한 종목 1개(실제 종목명)","tag":"대장주|수혜주|테마주|턴어라운드","catalyst":"핵심 촉매·뉴스 근거(구체적,32자내)","why_now":"왜 하필 지금 뜨는지(30자내)","watch":"체크포인트/주의할 점(28자내)"},
  "playbook": {"gap_up":"갭상승 시 대응(22자내)","gap_down":"갭하락 시 대응(22자내)","flat":"횡보 시 대응(22자내)"},
  "catalysts": ["오늘의 호재/모멘텀 한 줄(구체적 뉴스근거)","2~3개"],
  "risks":  ["오늘 조심할 리스크 한 줄","2~3개"],
  "events": ["오늘 확인할 이벤트(지표/실적/정책) 한 줄","2~3개"],
  "summary": "10초 핵심 요약(한 문장, 기억에 남게, 26자내)",
  "images": {
    "hook":"표지 배경 영어 프롬프트 — 오늘의 실제 주제를 구체적 사물로 묘사(예: 반도체=glowing silicon wafer/GPU, 전선=power transmission towers and cables, 원전=nuclear reactor, 조선=huge shipyard, 방산=missiles/defense). 글자 없이",
    "cause":"오늘 원인을 상징하는 구체적 장면 영어 프롬프트(그 산업/사건을 실제로 묘사)",
    "sectors":"오늘 가장 강한 섹터를 실제 사물로 묘사한 영어 프롬프트(막연한 차트 금지)",
    "stocks":"오늘 핵심 종목이 속한 산업을 구체적으로 묘사한 영어 프롬프트(예: HBM 메모리칩 클로즈업)",
    "playbook":"대응 전략/갈림길/화살표 상징 영어 프롬프트"
  },
  "theme": "오늘 핵심 테마 한 단어(예: 반도체/전력/원전/비트코인/방산/조선/2차전지/바이오/증시)",
  "scenes": [
    {"t":"한 화면 한 메시지(큰 글씨, 12자내, 단정형)","s":"보조 한 줄(없으면 \"\", 18자내)","v":"이 장면 영어 이미지 키워드(없으면 \"\")","c":"up|down|","bar":0,"n":"카운트업할 숫자(예: 6, 25832; 없으면 \"\")","u":"단위(%|$|없음)"}
  ],
  "narration": "아나운서 대본. 1.5배속 재생 고려해 빠르고 구체적으로. 순서: (1)3초 훅 강하게 (2)무슨 일+원인 판별 (3)국내 영향도와 이유 (4)오늘 강한 섹터 (5)먼저 볼 종목: 실제 종목명 3~5개를 또박또박 말하고 각 종목이 지금 왜 핫한지 촉매를 한 마디씩 설명 (5.5)그중 오늘 가장 핫한 1개는 촉매·왜 지금·체크포인트까지 2~3문장으로 깊게 설명 (6)갭상승/갭하락/횡보 대응 (7)오늘의 호재와 조심할 리스크 (8)오늘 이벤트/일정 (9)한 문장 요약. 440~520자."
}
sectors 3개, stocks 5개, risks/events 2~3개.
scenes 규칙(가장 중요): 12~15개. '한 장면=한 메시지'. 슬라이드가 아니라 쇼츠 컷처럼. 순서는 (0~3초)강한 훅 → 핵심 한 방 → 왜(누가·규모·근거) → 국내 파급 → 핵심 종목 하나씩 → 대응 → 한 줄 요약/CTA. 말투는 단정하게('~입니다','딱 하나입니다'), '가능성/전망/예상' 남발 금지. 각 t는 짧고 강하게. 스토리가 이어지게(엔비디아→GPU→데이터센터→HBM→SK하이닉스 식 연결). 향후 중요한 호재/악재 일정(실적발표일·CPI·금통위·만기 등, 날짜 포함)을 최소 1~2개 장면에 꼭 넣어라. 구체 수치(등락률·급등폭 등)가 있는 장면엔 bar(0~1, 그 수치의 강도)를 넣어 막대가 차오르게 하고, n(숫자)·u(단위)도 넣어 숫자가 0부터 올라가게 하라(예: 6% 급등이면 bar 0.6, n "6", u "%").
narration은 scenes의 t(+s)를 자연스럽게 이어 말하는 대본으로(장면과 음성이 일치하도록).
images 5개는 서로 다른 장면이며 반드시 오늘의 실제 주제(종목/섹터/사건)를 구체적 사물로 묘사할 것. 막연한 주식차트·도시야경 반복 금지.
"""

def build_prompt(data, slot, plan, events=None):
    heads = data.get("headlines", [])
    themap = kr_themes.context_block(heads)
    evtxt = ("\n[리서치: 오늘 호재/악재 + 향후 일정]\n" + json.dumps(events, ensure_ascii=False)) if events else ""
    label = SLOTS.get(slot, SLOTS["morning"])
    angle = (f"오늘 이 영상의 앵글(관점): 「{plan.get('title','')}」 (유형 {plan.get('angle','')}).\n"
             f"이 앵글로 영상 전체를 관통시켜라 — hook은 이 제목의 '궁금증'을 던지고, narration은 그 질문을 먼저 제시한 뒤 답하는 구조로. "
             f"모든 섹션(원인/섹터/종목/대응)은 이 앵글에 맞게 취사선택·강조하라. 초점: {plan.get('focus','')}\n") if plan else ""
    return (f"너는 한국 주식 시청자용 '전략 숏츠'의 애널리스트다. 지금 시간대 역할: [{label}].\n"
            + angle +
            "밤사이/최근 글로벌·국내 데이터와 뉴스로 오늘의 '대응 전략'을 만든다. 뉴스 나열 금지, 앵글 중심.\n"
            "특히 '지금 시청자가 가장 관심 가질 종목과 그 이유'를 구체적으로 짚어라.\n"
            f"데이터 기준: {data.get('captured_at','')} · {data.get('market_phase','')}. "
            "제공된 수치만 사용하고, 데이터에 없는 실시간 급등락(예: 장중 +10%)은 단정하지 말 것. "
            "수치를 말할 땐 이 '기준 시점'에 맞게 표현하라(밤사이/장중/마감).\n\n"
            f"[데이터]\n{json.dumps(data, ensure_ascii=False)}\n\n"
            f"[{themap}]\n" + evtxt + "\n\n" + SCHEMA_HINT)

def call_gemini(prompt):
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"].strip(), transport="rest")
    last = None
    for name in [os.environ.get("GEMINI_MODEL","").strip() or None,
                 "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        if not name: continue
        try:
            m = genai.GenerativeModel(name)
            r = m.generate_content(prompt, generation_config={
                "response_mime_type": "application/json", "temperature": 0.6},
                request_options={"timeout": 60})
            log(f"[analyze] model ok: {name}")
            return json.loads(r.text)
        except Exception as e:
            last = e; log(f"[analyze] model {name} 실패: {e}")
    raise last if last else RuntimeError("no model")

def mock(data, slot, plan=None):
    plan = plan or {}
    return {
        "hook": plan.get("title") or "AI 반도체, 오늘 국내가 받는다",
        "headline_html": "엔비디아 급등에 <up>반도체 순환</up>",
        "one_liner": "밤사이 AI 수요 재확인",
        "cause": {"primary":"AI 데이터센터 투자 확대", "type":"AI투자",
                  "detail":"엔비디아 대형 계약+ETF 자금 유입"},
        "kr_impact": {"level":"상","stars":5,"reason":"HBM·전력 국내 밸류체인 직접 수혜"},
        "sectors": [
            {"name":"AI반도체","dir":"up","reason":"엔비디아 계약에 수요 재확인"},
            {"name":"전력기기","dir":"up","reason":"데이터센터 전력수요 급증"},
            {"name":"PCB·기판","dir":"up","reason":"AI 가속기 고다층 기판 수혜"},
        ],
        "stocks": [
            {"name":"SK하이닉스","reason":"HBM 공급 사실상 독점적 지위"},
            {"name":"한미반도체","reason":"HBM 본딩 장비 핵심 수혜"},
            {"name":"이수페타시스","reason":"AI용 고다층 PCB 수요 급증"},
            {"name":"제룡전기","reason":"데이터센터·전력망 투자 수혜"},
            {"name":"두산에너빌리티","reason":"AI 전력원 원전·SMR 기대"},
        ],
        "hot_stock": {"name":"한미반도체","tag":"수혜주",
            "catalyst":"HBM 본딩장비 대형 수주 기대+엔비디아 공급망 편입",
            "why_now":"AI 투자 재확대로 HBM 증설 사이클 진입",
            "watch":"단기 급등 시 눌림목, 실적 발표 전후 변동성"},
        "playbook": {
            "gap_up":"4% 이상 갭상승 시 추격보다 눌림목 확인",
            "gap_down":"갭하락은 대장주 위주 분할 관점",
            "flat":"횡보 시 거래량 실린 주도주만 대응",
        },
        "catalysts": ["엔비디아 대형 데이터센터 계약 발표", "HBM 증설 사이클 재개 기대", "미 금리 인하 기대감 지속"],
        "risks": ["환율 급등 시 외국인 매도 부담", "옵션만기 주간 변동성 확대", "단기 급등 종목 차익실현"],
        "events": ["밤 미국 고용지표 발표", "SK하이닉스 실적 시즌 임박", "원/달러 환율 방향"],
        "summary": "오늘 키워드는 AI 반도체 순환매",
        "images": {
            "hook":"cinematic glowing AI GPU chip with green up arrows exploding, Korean semiconductor city skyline behind, dramatic, vertical",
            "cause":"cinematic massive AI data center servers glowing, capital flowing in as light streams, vertical",
            "sectors":"cinematic three glowing pillars labeled by light: chips, power grid, circuit board, rising, vertical",
            "stocks":"cinematic spotlight on rising Korean tech stock tickers, HBM chip and transformer icons glowing green, vertical",
            "playbook":"cinematic crossroads with three glowing arrows up steep, down, flat, strategy map, vertical",
        },
        "theme": "반도체",
        "scenes": [
            {"t":"오늘, 반도체입니다","s":"딱 하나만 보세요","v":"glowing silicon wafer macro, green neon","c":""},
            {"t":"밤사이 엔비디아 급등","s":"AI 투자가 다시 붙었다","v":"nvidia style gpu chip glowing, green up arrow","c":"up","bar":0.75,"n":"6","u":"%"},
            {"t":"이유는 딱 하나","s":"대형 데이터센터 계약","v":"massive AI data center servers glowing","c":""},
            {"t":"실적이 아니다","s":"AI 투자 확대다","v":"streams of capital light into servers","c":""},
            {"t":"한국이 먼저 받는다","s":"HBM·전력 밸류체인","v":"korean semiconductor factory at night","c":"up"},
            {"t":"1번 SK하이닉스","s":"HBM 사실상 독점","v":"HBM memory chip stack macro, green","c":"up","bar":0.6,"n":"3","u":"%"},
            {"t":"2번 한미반도체","s":"HBM 장비 핵심","v":"semiconductor bonding equipment closeup","c":"up"},
            {"t":"3번 이수페타시스","s":"AI 기판 수요 폭발","v":"high layer PCB circuit board macro","c":"up"},
            {"t":"전력도 같이 간다","s":"제룡전기·LS ELECTRIC","v":"power transmission towers with lightning","c":"up"},
            {"t":"단, 갭상승 4%면","s":"추격 말고 눌림목","v":"stock candlestick chart pullback","c":""},
            {"t":"조심할 건 환율","s":"급등 시 외국인 매도","v":"won dollar exchange board red","c":"down","bar":0.5,"n":"1300","u":""},
            {"t":"오늘 밤 고용지표","s":"미국 지표 체크","v":"economic data calendar and clock","c":""},
            {"t":"오늘 결론","s":"AI 반도체 순환매","v":"","c":"up"},
            {"t":"저장하고 내일 확인","s":"구독하면 매일 옵니다","v":"","c":""}
        ],
        "narration": ("오늘, AI 반도체가 국내로 넘어옵니다. "
            "밤사이 엔비디아가 대형 데이터센터 계약 발표 이후 급등했고, 관련 ETF에 기관 자금이 대거 유입됐습니다. 원인은 실적이 아니라 AI 투자 확대입니다. "
            "국내 영향도는 별 다섯. HBM과 전력 밸류체인이 직접 수혜기 때문입니다. "
            "오늘 강한 섹터는 AI 반도체, 전력기기, PCB 기판. "
            "먼저 볼 종목은 SK하이닉스, 한미반도체, 이수페타시스, 제룡전기, 두산에너빌리티입니다. HBM 독점과 전력 수요가 이유입니다. "
            "대응은, 4퍼센트 이상 갭상승이면 추격보다 눌림목 확인, 갭하락이면 대장주 분할 관점, 횡보면 거래량 실린 주도주만. "
            "조심할 건 환율 급등과 옵션만기 변동성입니다. "
            "오늘은 미국 고용지표와 환율 방향을 체크하세요. "
            "한 줄 요약, 오늘은 AI 반도체 순환매입니다.")
    }

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--mock", action="store_true")
    args = ap.parse_args(); cfg = load_config()
    data = read_json(DATA / "data.json")
    slot = slot_now()
    try: plan = read_json(DATA / "plan.json")
    except Exception: plan = {}
    try: events = read_json(DATA / "events.json")
    except Exception: events = {}
    log(f"[analyze] SLOT = {slot} | 앵글 = {plan.get('angle')} ({plan.get('title')})")
    if args.mock or not os.environ.get("GEMINI_API_KEY"):
        log("[analyze] MOCK/no-key mode"); result = mock(data, slot, plan)
    else:
        try:
            result = call_gemini(build_prompt(data, slot, plan, events))
        except Exception as e:
            log(f"[analyze] Gemini 실패 → mock ({e})"); result = mock(data, slot)
    # 리서치 캘린더를 권위값으로 반영(호재/악재 일정)
    if events:
        up = events.get("upcoming", [])[:4]
        if up:
            result["events"] = [f"{x.get('date','')} {x.get('name','')}".strip() for x in up]
        pos = events.get("today_positive", [])[:3]
        if pos: result["catalysts"] = pos
        neg = events.get("today_negative", [])[:2]
        if neg:
            result["risks"] = (neg + result.get("risks", []))[:3]
    result["slot"] = slot
    result["slot_label"] = SLOTS.get(slot, SLOTS["morning"])
    write_json(DATA / "analysis.json", result)
    log(f"[analyze] hook = {result.get('hook')}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc(); sys.exit(1)
