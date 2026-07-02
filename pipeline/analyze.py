"""
analyze.py — 수집 데이터 + 헤드라인을 넣어 '왜 올랐나/떨어졌나' 인과 분석.
Gemini를 고정 JSON 스키마로 강제 → 매일 같은 구조/퀄리티.
오프라인:  python pipeline/analyze.py --mock
"""
import sys, os, json, argparse, pathlib, traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, write_json, DATA

SCHEMA_HINT = """
반드시 아래 JSON 하나만 출력. 마크다운/백틱/설명 금지. 숫자는 데이터의 실제 값만 사용, 없는 사실·수치는 지어내지 말 것.
말은 1.5배 빠르게 재생되므로 narration은 '많고 구체적으로' 담아라(핵심을 빼지 말 것).
{
  "one_liner": "오늘 시장 한 문장(18자내, 임팩트)",
  "headline_html": "표지 제목, 핵심어를 <up>..</up>/<down>..</down>로 감쌈(22자내)",
  "why": [
    {"dir":"up|down|neutral","lead":"핵심 한 줄(구체적 숫자·종목 포함, 24자내)","body":"원인/전망 부연 한 줄(30자내)"}
  ],
  "korea": {"line":"오늘·내일 한국장 전망 한 줄(방향 명확, 24자내)","note":"이유+수급 한 줄(30자내)"},
  "factors": {
    "neg": ["오늘/향후 악재 요인 한 줄(구체적)","...","2~3개"],
    "pos": ["오늘/향후 호재 요인 한 줄(구체적)","...","2~3개"]
  },
  "images": {
    "cover": "표지 배경 영어 프롬프트(오늘 시장 상징, 텍스트 없이)",
    "why": "'왜 움직였나' 영어 프롬프트(오늘 원인 상징, 텍스트 없이)",
    "korea": "한국 증시 영어 프롬프트(코스피/서울 상징, 텍스트 없이)",
    "factors": "호재 vs 악재 대결 영어 프롬프트(불타는 혼돈 vs 푸른 성장의 빛, 텍스트 없이)"
  },
  "narration": "아나운서 대본. 첫 문장은 아주 짧고 강한 후킹. 이어서 반드시 이 순서로 구체적으로: (1)미국-무엇이 왜 움직였나+오늘밤/내일 전망, (2)한국-원인+내일 전망, (3)비트코인-원인+지지선, (4)앞으로의 호재와 악재 종합, (5)한 줄 마무리(성투). 빠른 호흡, 숫자 포함, 400~470자."
}
why 배열은 4~5개(미국·반도체·한국·비트를 아우르게). images 프롬프트는 영어, 글자 안 들어가게."""

def build_prompt(data):
    return (
        "너는 한국 시청자용 글로벌 증시 숏츠의 시황 애널리스트다. "
        "아래 밤사이 데이터와 헤드라인을 보고 '왜 움직였는지' 인과를 짚어라.\n\n"
        f"[데이터]\n{json.dumps(data, ensure_ascii=False)}\n\n"
        + SCHEMA_HINT
    )

def call_gemini(prompt):
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"].strip(), transport="rest")
    models = [os.environ.get("GEMINI_MODEL","").strip() or None,
              "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    last = None
    for name in [m for m in models if m]:
        try:
            model = genai.GenerativeModel(name)
            resp = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json",
                                   "temperature": 0.6},
                request_options={"timeout": 45})
            log(f"[analyze] model ok: {name}")
            return json.loads(resp.text)
        except Exception as e:
            last = e
            log(f"[analyze] model {name} 실패: {e}")
    raise last if last else RuntimeError("no model")

def mock(data):
    idx = data["indices"]
    return {
        "one_liner": "AI 랠리에 3대 지수 상승",
        "headline_html": "엔비디아가 끌어올린 <up>美 증시</up>",
        "why": [
            {"dir": "up", "lead": "나스닥 +1.84%, AI주가 견인",
             "body": "엔비디아 AI 칩 수요 전망 강세"},
            {"dir": "up", "lead": "국채금리 하락이 위험자산에 우호",
             "body": "10년물 -1.8%, 약한 고용지표 영향"},
            {"dir": "down", "lead": "다우 -0.21%, 일부 경기주 약세",
             "body": "유가 급등에 항공·소비주 부담"},
            {"dir": "neutral", "lead": "유가 +2.6%, 중동 공급 우려",
             "body": "WTI 72달러대 회복"},
        ],
        "korea": {"line": "코스피 상승 출발 기대",
                  "note": "미 기술주 강세·금리 안정이 우호적"},
        "factors": {
            "neg": ["빅테크 AI 투자 속도 조절 우려로 반도체 급락",
                    "비트코인 고래 매도·현물 ETF 자금 유입 둔화",
                    "미 제조업 지표 둔화, 반도체 담합 소송 이슈"],
            "pos": ["인플레이션 둔화·국채금리 안정",
                    "AI 장기 성장성, 반도체 수요 구조적 증가",
                    "연준 금리 인하 기대로 연착륙 가능성"]
        },
        "images": {
            "cover": "dramatic cinematic illustration, glowing NVIDIA-like AI accelerator chip cracking with red fissures, shattered smaller chips, NASDAQ red crash arrows, dark blue and red neon, vertical",
            "why": "cinematic scene of semiconductor wafers and AI server racks with red downward arrows, profit-taking selloff, moody dark tech atmosphere, vertical",
            "korea": "cinematic Seoul financial district at dusk, huge KOSPI ticker board glowing red with falling arrows, foreign selloff tension, vertical",
            "factors": "epic split composition, left side fiery chaotic monster of collapsing chips and red arrows, right side serene blue-green glowing guardian of growth and rising sun, cinematic clash, vertical"
        },
        "narration": ("오늘, 반도체가 무너졌습니다. "
                      "밤사이 미국 증시는 빅테크 AI 투자 속도 조절 우려에 마이크론과 AMD 같은 반도체주가 급락하며 나스닥이 하락을 주도했습니다. "
                      "오늘 밤은 낙폭 과대 저가 매수세가 기술주로 들어오는지가 관건이고, 반도체 반등 여부가 내일 아침 금리와 비트코인 방향을 가릅니다. "
                      "한국은 이 여파로 코스피가 급락하며 매도 사이드카까지 발동됐지만, 개인과 기관이 외국인 매물을 받아내며 낙폭을 만회했습니다. "
                      "내일은 강한 반등보다 매물 소화 흐름이 예상됩니다. "
                      "비트코인은 고래 매도와 유동성 둔화로 지지선을 시험 중이라, 이 구간을 지키는지가 중요합니다. "
                      "정리하면 악재는 반도체 차익실현과 ETF 자금 둔화, 호재는 금리 안정과 AI 장기 성장성입니다. "
                      "지지선 지키는지 보며 보수적으로 접근하세요. 오늘도 성투하세요."),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    data = read_json(DATA / "data.json")

    if args.mock or not os.environ.get("GEMINI_API_KEY"):
        if not args.mock:
            log("[analyze] GEMINI_API_KEY 없음 → mock 사용")
        else:
            log("[analyze] MOCK mode")
        result = mock(data)
    else:
        log("[analyze] calling Gemini ...")
        try:
            result = call_gemini(build_prompt(data))
        except Exception as e:
            log(f"[analyze] Gemini 실패 → mock fallback ({e})")
            result = mock(data)

    write_json(DATA / "analysis.json", result)
    log("[analyze] wrote analysis.json")
    log(f"[analyze] one_liner = {result.get('one_liner')}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
