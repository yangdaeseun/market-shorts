"""
run.py — 전체 파이프라인 단일 실행.
  python run.py              # 실데이터 → 생성 → 업로드
  python run.py --mock       # 오프라인 목데이터로 영상까지(업로드 X)
  python run.py --no-upload  # 실데이터로 생성만, 업로드 안 함

흐름: 수집 → 분석 → [품질게이트 + 재생성] → 렌더 → 더빙 → SEO → 영상 → 업로드 → 학습로그
어느 단계가 실패해도 알림을 보내고 중단(부분 산출물은 data/ 에 남음).
"""
import sys, os, json, argparse, subprocess, pathlib
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, write_json, notify, DATA

PY = sys.executable

def step(name, args, cfg, allow_fail=False):
    log(f"\n===== {name} =====")
    r = subprocess.run([PY] + args, cwd=str(ROOT))
    if r.returncode != 0 and not allow_fail:
        notify(cfg, f"❌ 시황숏츠 실패: {name}")
        log(f"[run] STOP at {name} (rc={r.returncode})")
        sys.exit(r.returncode)
    return r.returncode

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--no-upload", action="store_true")
    a = ap.parse_args()
    cfg = load_config()
    mock = ["--mock"] if a.mock else []

    # 1) 수집
    step("수집 collect", ["pipeline/collect.py"] + mock, cfg)

    # 2) 분석 + 3) 품질 게이트(+재생성)
    step("분석 analyze", ["pipeline/analyze.py"] + mock, cfg)
    qcfg = cfg["quality"]
    held = False
    for attempt in range(qcfg["max_retries"] + 1):
        score = subprocess.run([PY, "pipeline/quality_gate.py"], cwd=str(ROOT),
                               capture_output=True, text=True)
        sys.stdout.write(score.stdout)
        pts = 0
        for ln in score.stdout.splitlines():
            if "score =" in ln:
                pts = int(ln.split("score =")[1].split("/")[0].strip())
        write_json(DATA / "score.json", {"score": pts})
        if pts >= qcfg["min_score"]:
            log(f"[run] 품질 통과 ({pts}점)")
            break
        if attempt < qcfg["max_retries"]:
            log(f"[run] {pts}점 < {qcfg['min_score']}점 → 재생성 시도 {attempt+1}")
            step("재분석 analyze", ["pipeline/analyze.py"] + mock, cfg)
        else:
            log(f"[run] 최종 {pts}점 미달")
            if qcfg["hold_on_fail"]:
                held = True
                notify(cfg, f"⚠️ 시황숏츠 품질 미달({pts}점) → 비공개 보류")

    # 4) 렌더 → 5) 더빙 → 6) SEO
    step("렌더 render", ["pipeline/render.py"], cfg)
    step("더빙 tts", ["pipeline/tts.py"], cfg, allow_fail=True)
    step("SEO meta", ["pipeline/seo.py"], cfg)

    # 보류면 메타를 비공개로 강제
    if held:
        meta = read_json(DATA / "meta.json")
        meta["privacy"] = "private"
        write_json(DATA / "meta.json", meta)

    # 7) 영상
    step("영상 make_video", ["pipeline/make_video.py"], cfg)

    # 8) 업로드
    up_args = ["pipeline/upload.py"]
    if a.no_upload or a.mock:
        up_args.append("--no-upload")
    step("업로드 upload", up_args, cfg)

    # 9) 학습 로그
    step("학습로그 learn", ["pipeline/learn.py", "log"], cfg, allow_fail=True)

    res = {}
    try: res = read_json(DATA / "upload_result.json")
    except Exception: pass
    msg = ("✅ 시황숏츠 발행 완료" + (" (비공개 보류)" if held else "")
           + (f"\n{res.get('url','')}" if res.get("url") else ""))
    notify(cfg, msg)
    log(f"\n[run] DONE. {msg}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
