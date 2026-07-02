"""
make_video.py — 슬라이드 PNG + 내레이션 → 1080x1920 세로 MP4.
- 슬라이드별 부드러운 줌(Ken Burns) + 페이드
- 내레이션 길이에 맞춰 영상 길이 자동 정렬
- BGM(assets/bgm.mp3 있으면) 자동 믹스
ffmpeg만 사용. CapCut 불필요.
"""
import sys, os, json, subprocess, pathlib, glob, traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, DATA

SLIDES = DATA / "slides"
NARR = DATA / "narration.mp3"
BGM = ROOT / "assets" / "bgm.mp3"
OUT = DATA / "short.mp4"
TMP = DATA / "_clips"

def ffprobe_dur(path):
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(path)], text=True).strip()
        return float(out)
    except Exception:
        return 0.0

def make_clip(img, dur, W, H, fps, idx):
    """이미지 1장 → dur초 클립 (느린 줌 + 페이드)."""
    out = TMP / f"c{idx:02d}.mp4"
    frames = max(1, int(dur * fps))
    # 스케일 업 후 zoompan 으로 1.0→1.06 천천히 줌, 페이드 인/아웃
    zoom = (
        f"scale={W*2}:{H*2},"
        f"zoompan=z='min(zoom+0.0006,1.06)':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps},"
        f"fade=t=in:st=0:d=0.3,fade=t=out:st={max(0,dur-0.3):.2f}:d=0.3,"
        f"format=yuv420p"
    )
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(img),
        "-t", f"{dur:.3f}", "-vf", zoom, "-r", str(fps),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)
    ], check=True, capture_output=True)
    return out

def main():
    cfg = load_config()
    v = cfg["video"]
    W, H, fps = v["width"], v["height"], v["fps"]
    imgs = sorted(glob.glob(str(SLIDES / "*.png")))
    if not imgs:
        log("[video] no slides!"); return 1

    TMP.mkdir(exist_ok=True)
    for f in TMP.glob("*.mp4"):
        f.unlink()

    has_audio = NARR.exists() and ffprobe_dur(NARR) > 0.5
    audio_dur = ffprobe_dur(NARR) if has_audio else 0.0

    # 슬라이드별 노출 시간: 내레이션 있으면 거기에 맞춤, 없으면 설정값
    if has_audio:
        total = audio_dur + 0.8
        per = max(2.0, total / len(imgs))
    else:
        per = float(v["seconds_per_slide"])
        total = per * len(imgs)
    log(f"[video] {len(imgs)} slides, per={per:.2f}s, total≈{per*len(imgs):.1f}s, audio={audio_dur:.1f}s")

    clips = [make_clip(img, per, W, H, fps, i) for i, img in enumerate(imgs)]

    # 클립 이어붙이기 (concat demuxer)
    listfile = TMP / "list.txt"
    listfile.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    silent = DATA / "_silent.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
        "-c", "copy", str(silent)
    ], check=True, capture_output=True, cwd=str(TMP))

    # 오디오 믹스
    use_bgm = v.get("bgm") and BGM.exists()
    if not has_audio and not use_bgm:
        os.replace(silent, OUT)
        log(f"[video] (무음) wrote {OUT}"); return 0

    cmd = ["ffmpeg", "-y", "-i", str(silent)]
    filt, amix = [], []
    ai = 1
    if has_audio:
        cmd += ["-i", str(NARR)]
        filt.append(f"[{ai}:a]volume=1.0[narr]"); amix.append("[narr]"); ai += 1
    if use_bgm:
        cmd += ["-stream_loop", "-1", "-i", str(BGM)]
        filt.append(f"[{ai}:a]volume={v.get('bgm_volume',0.12)}[bgm]"); amix.append("[bgm]"); ai += 1
    filt.append(f"{''.join(amix)}amix=inputs={len(amix)}:duration=first:dropout_transition=2[aout]")
    cmd += ["-filter_complex", ";".join(filt),
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(OUT)]
    subprocess.run(cmd, check=True, capture_output=True)
    log(f"[video] wrote {OUT} ({OUT.stat().st_size//1024} KB, {ffprobe_dur(OUT):.1f}s)")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        log("[video] ffmpeg error:\n" + (e.stderr.decode()[-1500:] if e.stderr else str(e)))
        sys.exit(1)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
