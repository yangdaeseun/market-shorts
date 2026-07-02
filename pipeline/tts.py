"""
tts.py — 내레이션 텍스트 → 음성 mp3.
기본 edge-tts(무료, 키 불필요). config.voice.provider=elevenlabs 면 ElevenLabs.
voiceover=false 면 아무 것도 안 함.
"""
import sys, os, asyncio, pathlib, traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, DATA

OUT = DATA / "narration.mp3"

async def _edge(text, voice, rate):
    import edge_tts
    com = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await com.save(str(OUT))

def _elevenlabs(text, voice_id):
    import requests
    key = os.environ["ELEVENLABS_API_KEY"]
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={"text": text, "model_id": "eleven_multilingual_v2"}, timeout=60)
    r.raise_for_status()
    OUT.write_bytes(r.content)

def main():
    cfg = load_config()
    if not cfg["video"].get("voiceover", True):
        log("[tts] voiceover off, skip")
        return 0
    text = read_json(DATA / "narration.json").get("text", "").strip()
    if not text:
        log("[tts] no narration text, skip")
        return 0
    v = cfg["voice"]
    try:
        if v["provider"] == "elevenlabs" and os.environ.get("ELEVENLABS_API_KEY"):
            log("[tts] ElevenLabs ...")
            _elevenlabs(text, v["elevenlabs_voice_id"])
        else:
            log(f"[tts] edge-tts ({v['edge_voice']}) ...")
            asyncio.run(_edge(text, v["edge_voice"], v.get("rate", "+0%")))
        log(f"[tts] wrote {OUT} ({OUT.stat().st_size//1024} KB)")
    except Exception as e:
        log(f"[tts] failed → 무음 진행 ({e})")
        if OUT.exists():
            OUT.unlink()
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
