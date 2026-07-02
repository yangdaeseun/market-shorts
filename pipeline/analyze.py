"""
analyze.py — 수집 데이터+헤드라인 → 종합 시황 브리핑(JSON). Gemini 고정 스키마.
미국/한국/비트 동향·왜·지지선·주목종목·호재/악재·단기·장기 관점 + 슬라이드별 이미지 프롬프트.
오프라인: python pipeline/analyze.py --mock
"""
import sys, os, json, argparse, pathlib, traceback
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, write_json, DATA

SCHEMA_HINT = """
반드시 아래 JSON 하나만 출력. 마크다운/백틱/설명 금지. 숫자는 데이터의 실제 값만, 없는 사실은 지어내지 말 것.
말은 1.5배 빠르게 재생되니 narration은 '많고 구체적으로'(핵심 빼지 말 것). 지지선은 현재가 기준 합리적 기술적 레벨로 제시.
{
  "one_liner": "오늘 시장 한 문장(18자내, 임팩트)",
  "headline_html": "표지 제목, 핵심어 <up>..</up>/<down>..</down> 감쌈(22자내)",
  "why": [
    {"dir":"up|down|neutral","lead":"핵심 한 줄(구체적 숫자·종목, 24자내)","body":"원인/전망 부연(30자내)"}
  ],
  "supports": [
    {"name":"나스닥","level":"레벨(예: 20,000)","note":"지지/저항 관건 한 줄(16자내)"},
    {"name":"코스피","level":"레벨","note":"..."},
    {"name":"코스닥","level":"레벨","note":"..."},
    {"name":"비트코인","level":"$레벨","note":"..."}
  ],
  "watchlist": [
    {"name":"종목/섹터","reason":"호재·주목 이유 한 줄(구체적, 26자내)"}
  ],
  "factors": {"neg":["악재 한 줄","2~3개"], "pos":["호재 한 줄","2~3개"]},
  "views": {"short":"단기 관점 한 줄(24자내)","long":"장기 관점 한 줄(24자내)"},
  "korea": {"line":"오늘·내일 한국장 전망(24자내)","note":"이유·수급 한 줄(30자내)"},
  "images": {
    "cover":"표지 배경 영어 프롬프트(오늘 시장 상징, 글자 없이)",
    "why":"'왜 움직였나' 영어 프롬프트(원인 상징)",
    "supports":"지지선/차트 영어 프롬프트(캔들차트, 지지선, 상승/하락 화살표)",
    "watch":"주목 종목 영어 프롬프트(spotlight on rising stocks/sector)",
    "factors":"호재 vs 악재 대결 영어 프롬프트(불타는 혼돈 vs 푸른 성장의 빛)",
    "korea":"한국 증시 영어 프롬프트(코스피/서울 상징)"
  },
  "narration": "아나운서 대본. 첫 문장 아주 짧고 강하게. 이어 구체적으로: (1)미국-무엇이 왜+단기전망, (2)한국-코스피/코스닥 원인+내일, (3)비트코인 원인, (4)지지선-지켜야 할 레벨, (5)주목 종목/호재, (6)호재와 악재 종합, (7)단기·장기 관점+주요 일정(고용지표 등), (8)한 줄 마무리. 빠른 호흡, 숫자 포함, 460~520자."
}
why 4~5개, supports 3~4개, watchlist 2~3개. images는 영어, 글자 안 들어가게.
"""

def build_prompt(data):
    return ("너는 한국 시청자용 글로벌 증시 숏츠의 시황 애널리스트다. "
            "아래 밤사이 데이터와 헤드라인으로 미국/한국/비트코인의 '왜 움직였는지'와 "
            "지지선·주목 종목·호재/악재·단기·장기 관점을 종합하라.\n\n"
            f"[데이터]\n{json.dumps(data, ensure_ascii=False)}\n\n" + SCHEMA_HINT)

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

def mock(data):
    return {
        "one_liner": "AI·반도체 차익실현에 조정",
        "headline_html": "반도체가 끌어내린 <down>글로벌 증시</down>",
        "why": [
            {"dir":"down","lead":"나스닥 하락, 반도체가 주도","body":"빅테크 AI 투자 속도조절 우려"},
            {"dir":"down","lead":"마이크론·AMD 급락","body":"차익실현 매물 집중"},
            {"dir":"down","lead":"코스피·코스닥 동반 약세","body":"미 반도체 여파+외국인 매도"},
            {"dir":"neutral","lead":"국채금리는 안정","body":"물가 둔화로 하방 압력"},
        ],
        "supports": [
            {"name":"나스닥","level":"20,000","note":"이 선 지지 관건"},
            {"name":"코스피","level":"2,550","note":"단기 지지선"},
            {"name":"코스닥","level":"720","note":"수급 분수령"},
            {"name":"비트코인","level":"$58,000","note":"지지 실패 시 조정 확대"},
        ],
        "watchlist": [
            {"name":"HBM 메모리주","reason":"AI 수요 장기 성장 지속"},
            {"name":"전력기기·원전","reason":"AI 인프라 전력수요 수혜"},
            {"name":"방산","reason":"지정학 리스크 수혜 기대"},
        ],
        "factors": {
            "neg":["빅테크 AI 투자 속도조절·반도체 급락","비트코인 고래 매도·ETF 유입 둔화","미 제조업 지표 둔화"],
            "pos":["인플레이션 둔화·금리 안정","AI·반도체 장기 성장성","연준 금리 인하 기대"]
        },
        "views": {"short":"단기 변동성 큰 조정 국면","long":"AI 장기 사이클은 유효"},
        "korea": {"line":"내일 매물 소화 후 반등 시도","note":"외국인 매도 진정 여부가 관건"},
        "images": {
            "cover":"dramatic cinematic illustration, glowing AI accelerator chip cracking with red fissures, NASDAQ red crash arrows, dark blue red neon, vertical",
            "why":"cinematic semiconductor wafers and AI server racks with red downward arrows, profit-taking selloff, moody dark tech, vertical",
            "supports":"cinematic glowing candlestick stock chart with clear horizontal support line and red down arrows, financial trading screen, vertical",
            "watch":"cinematic spotlight on a few rising green stock tickers, HBM memory chip and power grid and defense icons glowing, hopeful, vertical",
            "factors":"epic split composition, left fiery chaotic monster of collapsing chips and red arrows, right serene blue-green guardian of growth and rising sun, vertical",
            "korea":"cinematic Seoul financial district at dusk, huge KOSPI ticker board red with falling arrows, foreign selloff tension, vertical"
        },
        "narration": ("오늘, 반도체가 무너졌습니다. "
            "밤사이 미국은 빅테크 AI 투자 속도조절 우려에 마이크론과 AMD 등 반도체주가 급락하며 나스닥이 하락을 주도했습니다. "
            "단기적으론 낙폭 과대 저가매수가 들어오는지가 관건입니다. "
            "한국도 여파로 코스피와 코스닥이 동반 약세, 외국인 매도가 컸지만 개인·기관이 받아냈습니다. 내일은 매물 소화 흐름이 예상됩니다. "
            "비트코인은 고래 매도와 유동성 둔화로 지지선을 시험 중입니다. "
            "지켜야 할 선은 나스닥 2만, 코스피 2천5백50, 코스닥 720, 비트코인 5만8천 달러입니다. "
            "주목할 곳은 HBM 메모리, 전력기기·원전, 방산입니다. "
            "악재는 반도체 차익실현과 ETF 유입 둔화, 호재는 금리 안정과 AI 장기 성장성입니다. "
            "단기는 변동성 조정, 장기는 AI 사이클 유효. 이번 주 미국 고용지표를 주목하세요. "
            "지지선 지키는지 보며 성투하세요.")
    }

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--mock", action="store_true")
    args = ap.parse_args(); cfg = load_config()
    data = read_json(DATA / "data.json")
    if args.mock or not os.environ.get("GEMINI_API_KEY"):
        log("[analyze] MOCK/no-key mode"); result = mock(data)
    else:
        try:
            result = call_gemini(build_prompt(data))
        except Exception as e:
            log(f"[analyze] Gemini 실패 → mock ({e})"); result = mock(data)
    write_json(DATA / "analysis.json", result)
    log(f"[analyze] one_liner = {result.get('one_liner')}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc(); sys.exit(1)
