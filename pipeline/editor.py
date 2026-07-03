"""
editor.py — 'AI 편집장'. 발행 전 스스로 채점하고 미달이면 재생성 신호.
구조 점수(quality_gate) + AI 비평(제미나이)을 합산해 'score = N/100' 출력.
run.py 가 이 점수를 읽어 min_score 미만이면 planner/analyze부터 재생성.
키 없으면 구조 점수만 사용(안전).
"""
import sys, os, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import log, read_json, write_json, DATA
from pipeline import quality_gate

CHECK = """다음 쇼츠 기획을 유튜브 PD 관점에서 냉정하게 채점하라. JSON만 출력.
평가: (1)첫 3초 훅이 붙잡는가 (2)제목·훅이 내용과 일치 (3)같은 말 반복 없나 (4)정보 깊이 충분 (5)초보도 이해 (6)투자 판단에 쓸 구체 인사이트 (7)장면이 스토리로 이어지나 (8)말투가 단정한가(가능성/전망 남발 아님).
{"score": 0~100 정수, "issues": ["가장 큰 문제 1~4개(짧게)"]}"""

def ai_score():
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"].strip(), transport="rest")
        an = read_json(DATA / "analysis.json")
        payload = {
            "title": an.get("hook"), "scenes": [f"{s.get('t')} / {s.get('s')}" for s in an.get("scenes", [])],
            "cause": an.get("cause"), "stocks": [s.get("name") for s in an.get("stocks", [])],
            "narration": an.get("narration", "")[:600],
        }
        prompt = CHECK + "\n\n[기획]\n" + json.dumps(payload, ensure_ascii=False)
        for name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                m = genai.GenerativeModel(name)
                r = m.generate_content(prompt, generation_config={
                    "response_mime_type": "application/json", "temperature": 0.4},
                    request_options={"timeout": 40})
                j = json.loads(r.text)
                return int(j.get("score", 0)), list(j.get("issues", []))
            except Exception as e:
                log(f"[editor] {name} 실패: {e}")
    except Exception as e:
        log(f"[editor] AI 비평 생략: {e}")
    return None, []

def main():
    struct, sreasons = quality_gate.score()
    ai, issues = ai_score()
    if ai is None:
        final = struct
        log(f"[editor] 구조 {struct} (AI 비평 없음)")
    else:
        final = round(struct * 0.4 + ai * 0.6)
        log(f"[editor] 구조 {struct} + AI {ai} → 종합 {final}")
    for r in sreasons: log(f"[editor]  - (구조) {r}")
    for r in issues:   log(f"[editor]  - (비평) {r}")
    write_json(DATA / "editor.json", {"score": final, "struct": struct, "ai": ai, "issues": issues})
    log(f"[quality] score = {final}/100")
    return 0

if __name__ == "__main__":
    main()
