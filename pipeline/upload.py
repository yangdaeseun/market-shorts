"""
upload.py — YouTube Data API v3 무인 업로드 (OAuth refresh token).
필요한 환경변수(GitHub Secrets):
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
영상: data/short.mp4 , 메타: data/meta.json
--no-upload : 실제 업로드 없이 메타만 출력(테스트)
"""
import sys, os, argparse, pathlib, traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, read_json, write_json, DATA

VIDEO = DATA / "short.mp4"

def get_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token")
    return build("youtube", "v3", credentials=creds)

def upload(meta):
    from googleapiclient.http import MediaFileUpload
    yt = get_service()
    body = {
        "snippet": {"title": meta["title"], "description": meta["description"],
                    "tags": meta["tags"], "categoryId": meta["category_id"]},
        "status": {"privacyStatus": meta["privacy"],
                   "selfDeclaredMadeForKids": meta["made_for_kids"]},
    }
    media = MediaFileUpload(str(VIDEO), chunksize=-1, resumable=True,
                            mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            log(f"[upload] {int(status.progress()*100)}%")
    vid = resp["id"]
    log(f"[upload] done: https://youtu.be/{vid}")

    # 고정 댓글
    try:
        yt.commentThreads().insert(part="snippet", body={"snippet": {
            "videoId": vid,
            "topLevelComment": {"snippet": {"textOriginal": meta["pinned_comment"]}}
        }}).execute()
        log("[upload] pinned comment posted")
    except Exception as e:
        log(f"[upload] comment skip ({e})")
    return vid

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-upload", action="store_true")
    args = ap.parse_args()
    meta = read_json(DATA / "meta.json")

    if args.no_upload or not os.environ.get("YT_REFRESH_TOKEN"):
        log("[upload] DRY RUN (no token / --no-upload)")
        log(f"[upload] would upload: {meta['title']} ({meta['privacy']})")
        write_json(DATA / "upload_result.json", {"dry_run": True, "title": meta["title"]})
        return 0
    vid = upload(meta)
    write_json(DATA / "upload_result.json", {"video_id": vid,
               "url": f"https://youtu.be/{vid}", "title": meta["title"]})
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
