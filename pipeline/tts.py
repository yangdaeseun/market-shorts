"""
tts.py — 내레이션 텍스트 → 음성 mp3 (+ TTS 싱크 자막 SRT).
기본 edge-tts(무료). WordBoundary로 자막 타이밍을 맞춰 narration.srt 생성(음소거 시청 대응).
"""
import sys, os, asyncio, pathlib, traceback
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, DATA

SPEAK_FIX = {  # edge-tts 발음/어색함 교정 (음성에만 적용, 슬라이드 글자는 그대로). 긴 패턴 먼저.
    "주목하세요": "눈여겨보세요", "주목해야": "눈여겨봐야", "주목할": "눈여겨볼",
    "주목받는": "관심받는", "주목받": "관심받", "주목되": "관심되", "주목": "눈여겨볼 곳",
}

def _fix_speak(t):
    for a, b in SPEAK_FIX.items():
        t = t.replace(a, b)
    return t

OUT = DATA / "narration.mp3"
SRT = DATA / "narration.srt"

def _ts(sec):
    if sec < 0: sec = 0
    h = int(sec // 3600); m = int((sec % 3600) // 60)
    s = int(sec % 60); ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _write_srt(subs):
    lines = []
    for i, (st, en, tx) in enumerate(subs, 1):
        if en <= st: en = st + 0.6
        lines += [str(i), f"{_ts(st)} --> {_ts(en)}", tx, ""]
    SRT.write_text("\n".join(lines), encoding="utf-8")

async def _edge(text, voice, rate):
    import edge_tts
    text = _fix_speak(text)
    com = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    subs = []
    cur, cur_start, cur_end = [], None, None
    with open(OUT, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                st = ch["offset"] / 1e7
                en = (ch["offset"] + ch["duration"]) / 1e7
                w = (ch.get("text") or "").strip()
                if not w:
                    continue
                if cur_start is None:
                    cur_start = st
                cur.append(w); cur_end = en
                joined = " ".join(cur)
                if len(joined) >= 13 or w[-1:] in "。.!?！？":
                    subs.append((cur_start, cur_end, joined))
                    cur, cur_start = [], None
        if cur:
            subs.append((cur_start or 0.0, cur_end or 0.0, " ".join(cur)))
    if subs:
        _write_srt(subs)
        log(f"[tts] SRT {len(subs)}컷 생성")

def _elevenlabs(text, voice_id):
    import requests
    key = os.environ["ELEVENLABS_API_KEY"]
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={"text": _fix_speak(text), "model_id": "eleven_multilingual_v2"}, timeout=60)
    r.raise_for_status()
    OUT.write_bytes(r.content)

def main():
    cfg = load_config()
    if not cfg["video"].get("voiceover", True):
        log("[tts] voiceover off, skip"); return 0
    text = read_json(DATA / "narration.json").get("text", "").strip()
    if not text:
        log("[tts] no narration text, skip"); return 0
    if SRT.exists():
        SRT.unlink()
    v = cfg["voice"]
    try:
        if v["provider"] == "elevenlabs" and os.environ.get("ELEVENLABS_API_KEY"):
            log("[tts] ElevenLabs ..."); _elevenlabs(text, v["elevenlabs_voice_id"])
        else:
            log(f"[tts] edge-tts ({v['edge_voice']}) ...")
            asyncio.run(_edge(text, v["edge_voice"], v.get("rate", "+0%")))
        log(f"[tts] wrote {OUT} ({OUT.stat().st_size//1024} KB)")
    except Exception as e:
        log(f"[tts] failed → 무음 진행 ({e})")
        if OUT.exists(): OUT.unlink()
        if SRT.exists(): SRT.unlink()
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc(); sys.exit(1)
