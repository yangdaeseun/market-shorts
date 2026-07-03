"""
collect.py — 밤사이 글로벌 시장 데이터 수집
- yfinance: 지수/유가/금/환율/금리
- CoinGecko 무료 API: 코인
- RSS: 헤드라인
각 항목 독립 수집. 하나 실패해도 'N/A'로 두고 나머지 진행.
오프라인 테스트:  python pipeline/collect.py --mock
"""
import sys, json, datetime, argparse, pathlib, traceback

def kst_date():
    # GitHub Actions는 UTC로 돌기 때문에 한국시간(UTC+9) 기준 날짜로 고정
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date().isoformat()

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.util import load_config, log, DATA

def _pct(cur, prev):
    if prev in (None, 0) or cur is None:
        return None
    return (cur - prev) / prev * 100.0

def fetch_yf(tickers: dict):
    import yfinance as yf
    out = {}
    for name, tk in tickers.items():
        try:
            h = yf.Ticker(tk).history(period="5d", interval="1d")
            if h is None or h.empty or len(h) < 2:
                raise ValueError("no data")
            close = float(h["Close"].iloc[-1])
            prev = float(h["Close"].iloc[-2])
            out[name] = {"ticker": tk, "price": close, "pct": _pct(close, prev)}
            log(f"  yf  {name:10s} {close:>12.2f}  {out[name]['pct']:+.2f}%")
        except Exception as e:
            out[name] = {"ticker": tk, "price": None, "pct": None}
            log(f"  yf  {name:10s} FAILED ({e})")
    return out

def fetch_crypto(ids: dict):
    import requests
    out = {}
    try:
        idlist = ",".join(ids.values())
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": idlist, "vs_currencies": "usd",
                    "include_24hr_change": "true"},
            timeout=20)
        j = r.json()
        for name, cid in ids.items():
            d = j.get(cid, {})
            out[name] = {"price": d.get("usd"), "pct": d.get("usd_24h_change")}
            log(f"  cg  {name:10s} {str(d.get('usd')):>12}  {d.get('usd_24h_change')}")
    except Exception as e:
        log(f"  cg  FAILED ({e})")
        for name in ids:
            out[name] = {"price": None, "pct": None}
    return out

def fetch_news(feeds: list, limit=12):
    import feedparser
    KEY = ("fed", "rate", "inflation", "war", "oil", "tariff", "jobs",
           "cpi", "earnings", "nvidia", "trump", "yield", "recession",
           "china", "powell", "gdp")
    items = []
    for url in feeds:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:20]:
                title = getattr(e, "title", "").strip()
                if not title:
                    continue
                score = sum(k in title.lower() for k in KEY)
                items.append((score, title))
        except Exception as e:
            log(f"  rss FAILED {url} ({e})")
    items.sort(key=lambda x: -x[0])
    heads = [t for _, t in items][:limit]
    log(f"  rss collected {len(heads)} headlines")
    return heads

def mock():
    return {
        "date": kst_date(),
        "indices": {
            "S&P 500": {"ticker": "^GSPC", "price": 6321.4, "pct": 1.12},
            "나스닥": {"ticker": "^IXIC", "price": 20890.3, "pct": 1.84},
            "다우": {"ticker": "^DJI", "price": 43210.7, "pct": -0.21},
            "코스피": {"ticker": "^KS11", "price": 2555.3, "pct": -1.2},
            "코스닥": {"ticker": "^KQ11", "price": 728.4, "pct": -0.9},
        },
        "macro": {
            "나스닥선물": {"ticker": "NQ=F", "price": 25990.0, "pct": 0.42},
            "S&P선물": {"ticker": "ES=F", "price": 7510.0, "pct": 0.31},
            "WTI 유가": {"ticker": "CL=F", "price": 72.4, "pct": 2.6},
            "금": {"ticker": "GC=F", "price": 2655.1, "pct": 0.4},
            "달러인덱스": {"ticker": "DX-Y.NYB", "price": 104.8, "pct": -0.3},
            "원/달러": {"ticker": "KRW=X", "price": 1382.5, "pct": 0.5},
            "미 국채 10년": {"ticker": "^TNX", "price": 4.31, "pct": -1.8},
        },
        "crypto": {
            "비트코인": {"price": 98230.0, "pct": 3.1},
            "이더리움": {"price": 3420.0, "pct": 4.7},
        },
        "headlines": [
            "Nvidia jumps as AI chip demand outlook stays strong",
            "Fed officials signal patience on rate cuts amid sticky inflation",
            "Oil rallies on Middle East supply fears",
            "Bitcoin tops $98K as risk appetite returns",
            "10-year Treasury yield slips after soft jobs data",
        ],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    DATA.mkdir(exist_ok=True)

    if args.mock:
        log("[collect] MOCK mode")
        data = mock()
    else:
        log("[collect] fetching live data ...")
        data = {
            "date": kst_date(),
            "indices": fetch_yf(cfg["markets"]["indices"]),
            "macro": fetch_yf(cfg["markets"]["macro"]),
            "crypto": fetch_crypto(cfg["markets"]["crypto"]),
            "headlines": fetch_news(cfg["news_rss"]),
        }

    out = DATA / "data.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[collect] wrote {out}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
