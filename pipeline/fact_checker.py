"""
fact_checker.py — AI가 '확인 안 된 수치'를 지어내지 못하게 검수/정정.
무료로 알 수 없는 것(실시간 기관·외국인·프로그램 순매수 '금액', 정확한 수급 숫자)은
구체 숫자를 빼고 일반 표현으로 바꾼다. analysis.json 을 제자리 수정.
규칙 기반이라 키 없이도 동작(파이프라인 안전).
"""
import sys, re, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import log, read_json, write_json, DATA

# '외국인 3천억 순매수' 처럼 수급 주체 + 금액이 붙은 표현 → 금액 제거
FLOW = r"(외국인|기관|연기금|프로그램)\s*[이가]?\s*"
AMOUNT = r"(약\s*)?[\d,\.]+\s*(조|억|천억|백억|만주|주|달러|억원|조원)"
PATS = [
    (re.compile(FLOW + AMOUNT + r"\s*(순매수|순매도|매수|매도|유입|유출)"), r"\1 \4"),
    (re.compile(AMOUNT + r"\s*(순매수|순매도)\s*(유입|유출)?"), r"\2"),
]

def scrub(text):
    if not text:
        return text, 0
    n = 0
    for pat, rep in PATS:
        text, c = pat.subn(rep, text)
        n += c
    # 이중 공백 정리
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text, n

def walk(obj):
    """문자열 필드 전체를 재귀적으로 스크럽. 정정 횟수 반환."""
    total = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                nv, c = scrub(v); obj[k] = nv; total += c
            else:
                total += walk(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, str):
                nv, c = scrub(v); obj[i] = nv; total += c
            else:
                total += walk(v)
    return total

def main():
    an = read_json(DATA / "analysis.json")
    fixed = walk(an)
    if fixed:
        write_json(DATA / "analysis.json", an)
        log(f"[fact] 확인 안 된 수급 수치 {fixed}건 정정")
    else:
        log("[fact] 정정 없음(깨끗)")
    return 0

if __name__ == "__main__":
    main()
