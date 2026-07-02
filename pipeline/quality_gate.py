"""
quality_gate.py — 발행 전 자동 채점 (마스터프롬프트 '90점 미만 재생성' 자동화).
데이터 완성도 / 인과 분석 충실도 / 내레이션 길이 / 첫 슬라이드 훅 등을 점수화.
미달이면 run.py 가 1회 재생성 시도, 그래도 미달이면 비공개 보류.
"""
import sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import log, read_json, DATA

def score():
    data = read_json(DATA / "data.json")
    an = read_json(DATA / "analysis.json")
    pts, reasons = 0, []

    # 1) 지수 데이터 완성도 (25)
    idx = data.get("indices", {})
    ok = sum(1 for d in idx.values() if d.get("pct") is not None)
    s = int(25 * ok / max(1, len(idx)))
    pts += s
    if ok < len(idx): reasons.append(f"지수 일부 결측({ok}/{len(idx)})")

    # 2) 인과 분석 개수·근거 (30)
    whys = an.get("why", [])
    if len(whys) >= 3: pts += 18
    else: reasons.append(f"인과 분석 {len(whys)}개(3개 권장)")
    if sum(any(c.isdigit() for c in w.get("lead", "")) for w in whys) >= 2:
        pts += 12
    else: reasons.append("인과에 숫자 근거 부족")

    # 3) 표지 훅 (15)
    if an.get("headline_html") and ("<up>" in an["headline_html"] or "<down>" in an["headline_html"]):
        pts += 15
    else: reasons.append("표지 헤드라인 강조 약함")

    # 4) 한국장 전망 (10)
    if an.get("korea", {}).get("line"): pts += 10
    else: reasons.append("한국장 전망 없음")

    # 5) 내레이션 길이 (20) — 25~40초 분량 ≈ 120~330자
    n = len(an.get("narration", ""))
    if 120 <= n <= 360: pts += 20
    elif n >= 80: pts += 12; reasons.append(f"내레이션 길이 비표준({n}자)")
    else: reasons.append(f"내레이션 너무 짧음({n}자)")

    return pts, reasons

def main():
    pts, reasons = score()
    log(f"[quality] score = {pts}/100")
    for r in reasons: log(f"[quality]  - {r}")
    return pts

if __name__ == "__main__":
    main()
