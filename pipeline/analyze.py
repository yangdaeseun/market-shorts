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
반드시 아래 JSON 형식 '하나만' 출력. 마크다운/설명/백틱 금지.
{
  "one_liner": "오늘 시장 한 문장 (18자 내외, 임팩트)",
  "headline_html": "표지 제목. 핵심 단어를 <up>..</up>(상승)/<down>..</down>(하락)으로 감쌈. 22자 내외",
  "why": [
    {"dir":"up|down|neutral","lead":"굵게 보일 핵심 한 줄(숫자 근거, 22자 내외)","body":"부연 한 줄(28자 내외)"}
  ],
  "korea": {"line":"오늘/내일 한국장 전망 한 줄(방향 명확, 24자 내외)","note":"이유+앞으로 호재 한 줄(30자 내외)"},
  "images": {
    "cover": "표지 배경용 '영어' 이미지 프롬프트. 오늘 시장을 상징하는 드라마틱한 장면(예: cracking NVIDIA AI chip, red crash arrows). 텍스트 없이.",
    "why": "'왜 움직였나'를 상징하는 영어 이미지 프롬프트(반도체/AI/차익실현 등 오늘 원인). 텍스트 없이.",
    "korea": "한국 증시 상황을 상징하는 영어 이미지 프롬프트(코스피 전광판, 서울 배경 등). 텍스트 없이."
  },
  "narration": "숏츠 아나운서 대본. 첫 문장은 아주 짧고 강한 후킹(예: '오늘, 반도체가 무너졌습니다'). 이어서 미국 왜 움직였나 → 오늘/내일 전망 → 앞으로 호재까지. 빠른 호흡, 40~55초(한국어 240~300자). 마지막 '오늘도 성투하세요'."
}
why 배열은 3~4개. 숫자는 데이터의 실제 등락률만. 과장/허위 금지. images 프롬프트는 영어로, 글자가 안 들어가게.
"""

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
        "images": {
            "cover": "dramatic cinematic illustration, glowing NVIDIA-like AI accelerator chip cracking with red fissures, shattered smaller chips, NASDAQ red crash arrows, dark blue and red neon, vertical",
            "why": "cinematic scene of semiconductor wafers and AI server racks with red downward arrows, profit-taking selloff, moody dark tech atmosphere, vertical",
            "korea": "cinematic Seoul financial district at dusk, huge KOSPI ticker board glowing red with falling arrows, tense mood, vertical"
        },
        "narration": ("밤사이 미국 증시, 정리해 드립니다. "
                      "나스닥이 1.84퍼센트 오르며 AI주가 시장을 끌어올렸습니다. "
                      "엔비디아의 칩 수요 전망이 강하게 나왔고, "
                      "약한 고용지표에 10년물 금리가 내리면서 위험자산에 우호적이었습니다. "
                      "다만 유가가 2.6퍼센트 급등하며 다우는 소폭 약세였습니다. "
                      "비트코인은 9만 8천 달러를 넘어섰습니다. "
                      "오늘 한국장은 기술주 강세에 상승 출발이 기대됩니다. "
                      "오늘 하루도 성투하세요."),
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
