"""
make_video.py — 슬라이드 PNG + 내레이션 → 1080x1920 세로 MP4.
- 슬라이드마다 줌 방향 교차(줌인/줌아웃) + 첫 슬라이드 훅 펀치 줌
- 슬라이드 사이 크로스페이드 전환(xfade). 실패하면 단순 concat으로 자동 폴백
- 내레이션 길이에 맞춰 영상 길이 자동 정렬 / (선택) 자막 번인
"""
import sys, os, json, subprocess, pathlib, glob, traceback
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, DATA

SLIDES = DATA / "slides"
NARR = DATA / "narration.mp3"
SRT = DATA / "narration.srt"
BGM = ROOT / "assets" / "bgm.mp3"
OUT = DATA / "short.mp4"
TMP = DATA / "_clips"
XFADE = 0.5  # 전환 시간(초)

def ffprobe_dur(path):
    try:
        out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=nw=1:nk=1", str(path)], text=True).strip()
        return float(out)
    except Exception:
        return 0.0

def make_clip(img, dur, W, H, fps, idx):
    """이미지 1장 → dur초 클립. idx로 줌 방향을 다르게, 0번(훅)은 강한 펀치."""
    out = TMP / f"c{idx:02d}.mp4"
    if idx == 0:
        zexpr = "min(1.18,1.0+0.0018*on)"        # 훅: 강한 줌인
    elif idx % 2 == 1:
        zexpr = "max(1.0,1.10-0.0007*on)"         # 홀수: 줌아웃
    else:
        zexpr = "min(1.10,1.0+0.0007*on)"         # 짝수: 줌인
    vf = (
        f"scale={W*2}:{H*2},"
        f"zoompan=z='{zexpr}':d={max(1,int(dur*fps))}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps},"
        f"format=yuv420p"
    )
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(img),
        "-t", f"{dur:.3f}", "-vf", vf, "-r", str(fps),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        str(out)], check=True, capture_output=True)
    return out

def _audio_args(cfg, has_audio, use_bgm, first_input_index):
    """오디오 입력/필터 구성. 반환: (extra_inputs, filter_parts, amix_labels, next_index)"""
    inputs, filt, amix = [], [], []
    ai = first_input_index
    if has_audio:
        inputs += ["-i", str(NARR)]
        filt.append(f"[{ai}:a]volume=1.0[narr]"); amix.append("[narr]"); ai += 1
    if use_bgm:
        inputs += ["-stream_loop", "-1", "-i", str(BGM)]
        filt.append(f"[{ai}:a]volume={cfg['video'].get('bgm_volume',0.12)}[bgm]"); amix.append("[bgm]"); ai += 1
    return inputs, filt, amix, ai

def build_xfade(clips, durs, cfg, has_audio, use_bgm, W, H, fps):
    """크로스페이드 전환(가변 장면 길이). 실패 시 예외."""
    n = len(clips)
    cmd = ["ffmpeg", "-y"]
    for c in clips:
        cmd += ["-i", str(c)]
    ain, afilt, amix, _ = _audio_args(cfg, has_audio, use_bgm, n)
    cmd += ain

    vf = []
    prev = "[0:v]"
    for k in range(1, n):
        off = sum(durs[:k]) - k * XFADE
        lbl = f"[vx{k}]"
        vf.append(f"{prev}[{k}:v]xfade=transition=fade:duration={XFADE}:offset={off:.3f}{lbl}")
        prev = lbl
    parts = vf + afilt
    if amix:
        parts.append(f"{''.join(amix)}amix=inputs={len(amix)}:duration=first:dropout_transition=2[aout]")
    fc = ";".join(parts)
    cmd += ["-filter_complex", fc, "-map", prev]
    if amix:
        cmd += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-r", str(fps), "-movflags", "+faststart"]
    if has_audio:
        cmd += ["-shortest"]
    cmd += [str(OUT)]
    subprocess.run(cmd, check=True, capture_output=True)

def build_concat(clips, cfg, has_audio, use_bgm, fps):
    """단순 concat + 재인코딩(폴백, 항상 동작)."""
    listfile = TMP / "list.txt"
    listfile.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    common_v = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                "-r", str(fps), "-vsync", "cfr", "-movflags", "+faststart"]
    cmd = ["ffmpeg", "-y", "-fflags", "+genpts", "-f", "concat", "-safe", "0", "-i", str(listfile)]
    ain, afilt, amix, _ = _audio_args(cfg, has_audio, use_bgm, 1)
    cmd += ain
    if amix:
        afilt.append(f"{''.join(amix)}amix=inputs={len(amix)}:duration=first:dropout_transition=2[aout]")
        cmd += ["-filter_complex", ";".join(afilt), "-map", "0:v", "-map", "[aout]"] + common_v + \
               ["-c:a", "aac", "-b:a", "192k", "-shortest", str(OUT)]
    else:
        cmd += ["-map", "0:v"] + common_v + [str(OUT)]
    subprocess.run(cmd, check=True, capture_output=True, cwd=str(TMP))

def burn_subtitles(cfg, fps):
    def has_kfont():
        try:
            out = subprocess.check_output(["fc-list"], text=True)
            return ("nanum" in out.lower()) or ("noto sans cjk" in out.lower())
        except Exception:
            return False
    if not (cfg["video"].get("subtitles", False) and SRT.exists() and has_kfont()):
        return
    try:
        subbed = DATA / "_subbed.mp4"
        style = ("FontName=NanumGothic,FontSize=44,Bold=1,PrimaryColour=&H00FFFFFF,"
                 "OutlineColour=&H00151515,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=150")
        subprocess.run(["ffmpeg", "-y", "-i", str(OUT),
            "-vf", f"subtitles={SRT.as_posix()}:original_size={cfg['video']['width']}x{cfg['video']['height']}:force_style='{style}'",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-r", str(fps), "-movflags", "+faststart", "-c:a", "copy", str(subbed)],
            check=True, capture_output=True)
        os.replace(subbed, OUT); log("[video] 자막 번인 완료")
    except Exception as e:
        log(f"[video] 자막 번인 건너뜀: {str(e)[:120]}")

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
    n = len(imgs)

    # 장면별 길이 = 글자 수 가중치로 자동 배분(고정 길이 폐지)
    try:
        meta = json.loads((DATA / "slides_meta.json").read_text(encoding="utf-8"))
        weights = [max(0.6, len(m.get("text", "")) + 0.6 * len(m.get("sub", ""))) for m in meta]
        if len(weights) != n:
            weights = [1.0] * n
    except Exception:
        weights = [1.0] * n
    if has_audio:
        target = audio_dur + 0.8 + (n - 1) * XFADE
    else:
        target = float(v["seconds_per_slide"]) * n
    wsum = sum(weights) or n
    durs = [max(1.5, target * w / wsum) for w in weights]
    log(f"[video] {n} scenes, audio={audio_dur:.1f}s, durs={[round(x,1) for x in durs]}")

    clips = [make_clip(img, durs[i], W, H, fps, i) for i, img in enumerate(imgs)]
    use_bgm = bool(v.get("bgm") and BGM.exists())

    try:
        build_xfade(clips, durs, cfg, has_audio, use_bgm, W, H, fps)
        log("[video] 크로스페이드 전환 적용")
    except subprocess.CalledProcessError as e:
        log("[video] xfade 실패 → concat 폴백: " + (e.stderr.decode()[-300:] if e.stderr else ""))
        build_concat(clips, cfg, has_audio, use_bgm, fps)

    log(f"[video] wrote {OUT} ({OUT.stat().st_size//1024} KB, {ffprobe_dur(OUT):.1f}s)")
    burn_subtitles(cfg, fps)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        log("[video] ffmpeg error:\n" + (e.stderr.decode()[-1500:] if e.stderr else str(e)))
        sys.exit(1)
    except Exception:
        traceback.print_exc(); sys.exit(1)
