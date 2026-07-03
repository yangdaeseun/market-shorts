"""
quality_gate.py — 발행 전 자동 채점(전략 스키마). 미달이면 재생성/보류.
데이터 완성도 / 원인·섹터·종목 충실도 / 훅 / 대응 시나리오 / 내레이션 길이.
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import log, read_json, DATA

def score():
    data = read_json(DATA / "data.json")
    an = read_json(DATA / "analysis.json")
    pts, reasons = 0, []

    # 1) 지수 데이터 완성도 (20)
    idx = data.get("indices", {})
    ok = sum(1 for d in idx.values() if d.get("pct") is not None)
    pts += int(20 * ok / max(1, len(idx)))
    if ok < len(idx): reasons.append(f"지수 일부 결측({ok}/{len(idx)})")

    # 2) 훅 (15)
    if (an.get("hook") or "").strip(): pts += 15
    else: reasons.append("훅 없음")

    # 3) 원인 판별 (15)
    c = an.get("cause", {})
    if c.get("primary") and c.get("type"): pts += 15
    else: reasons.append("원인 판별 부족")

    # 4) 섹터 TOP3 (15)
    if len(an.get("sectors", [])) >= 3: pts += 15
    else: reasons.append(f"섹터 {len(an.get('sectors',[]))}개(3개 권장)")

    # 5) 종목 (15)
    if len(an.get("stocks", [])) >= 4: pts += 15
    else: reasons.append(f"종목 {len(an.get('stocks',[]))}개(5개 권장)")

    # 6) 대응 시나리오 (10)
    pb = an.get("playbook", {})
    if pb.get("gap_up") and pb.get("gap_down"): pts += 10
    else: reasons.append("대응 시나리오 부족")

    # 7) 내레이션 길이 (10) — 200~600자
    n = len(an.get("narration", ""))
    if 200 <= n <= 600: pts += 10
    elif n >= 120: pts += 6; reasons.append(f"내레이션 길이 비표준({n}자)")
    else: reasons.append(f"내레이션 너무 짧음({n}자)")

    return pts, reasons

def main():
    pts, reasons = score()
    log(f"[quality] score = {pts}/100")
    for r in reasons: log(f"[quality]  - {r}")
    return pts

if __name__ == "__main__":
    main()
