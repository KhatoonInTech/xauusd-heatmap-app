import os
import json
import requests
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from upstash_redis import Redis

app = FastAPI()

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(CURRENT_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(CURRENT_DIR, "templates"))

redis_client = None
try:
    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if url and token:
        redis_client = Redis(url=url, token=token)
except Exception:
    pass

def verify_bridge_token(request: Request):
    expected_secret = os.getenv("MT5_BRIDGE_SECRET", "DEV_DEFAULT_TOKEN")
    if request.headers.get("X-Bridge-Secret") != expected_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

@app.post("/api/update-market-data")
@app.post("/api/index.py/api/update-market-data")
async def update_market_matrix(payload: dict, authenticated: bool = Depends(verify_bridge_token)):
    if not redis_client:
        raise HTTPException(status_code=503, detail="Database offline")
    compressed_state = {
        "heatmap": payload.get("heatmap", []),
        "candles": payload.get("candles", [])
    }
    redis_client.set("XAUUSD_LIVE_STATE", json.dumps(compressed_state), ex=3600)
    return {"status": "success"}

@app.get("/api/market-data")
@app.get("/api/index.py/api/market-data")
async def fetch_market_matrix():
    # 1. TRY HOME MT5 BRIDGE
    if redis_client:
        try:
            cached_bytes = redis_client.get("XAUUSD_LIVE_STATE")
            if cached_bytes:
                parsed_data = json.loads(cached_bytes)
                if parsed_data.get("heatmap") and len(parsed_data["heatmap"]) > 0:
                    return JSONResponse(content={"source": "MT5", "heatmap": parsed_data["heatmap"], "candles": parsed_data["candles"]})
        except Exception:
            pass

    # 2. PRIMARY CLOUD: KRAKEN (Real Spot Gold - Very Reliable)
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        # Kraken Public API for XAUUSD
        book_res = requests.get("https://api.kraken.com/0/public/Depth?pair=XAUUSD&count=25", headers=headers, timeout=4)
        # Note: Kraken OHLC is heavy, so we use Bybit for candles to be fast
        kline_res = requests.get("https://api.bybit.com/v5/market/kline?category=linear&symbol=XAUUSDT&interval=5&limit=40", headers=headers, timeout=4)

        if book_res.status_code == 200:
            b_data = book_res.json()
            # Kraken format: {"result": {"XAUUSD": {"asks": [[price, vol, time], ...], "bids": ...}}}
            # The pair name might be XAUUSD or XXAUZUSD
            pair_key = list(b_data["result"].keys())[0]
            order_book = b_data["result"][pair_key]

            heatmap_layers = []
            for b in order_book.get("bids", []):
                heatmap_layers.append({"price": float(b[0]), "vol": float(b[1])})
            for a in order_book.get("asks", []):
                heatmap_layers.append({"price": float(a[0]), "vol": float(a[1])})

            # Get candles from Bybit (fallback to mock if fails)
            candle_layers = []
            if kline_res.status_code == 200:
                k_data = kline_res.json()
                if k_data["retCode"] == 0:
                     for k in reversed(k_data["result"]["list"]):
                        candle_layers.append({"open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4])})
            
            # Fallback candles if Bybit fails but Kraken works
            if not candle_layers:
                base_p = heatmap_layers[0]["price"]
                candle_layers = [{"open": base_p, "high": base_p+1, "low": base_p-1, "close": base_p} for _ in range(30)]

            return JSONResponse(content={"source": "Cloud_Kraken", "heatmap": heatmap_layers, "candles": candle_layers})

    except Exception as e:
        print(f"Kraken failed: {e}")

    # 3. BACKUP CLOUD: BYBIT (Crypto Gold)
    try:
        book_res = requests.get("https://api.bybit.com/v5/market/orderbook?category=linear&symbol=XAUUSDT&limit=25", headers=headers, timeout=3)
        if book_res.status_code == 200:
            b_data = book_res.json()
            if b_data["retCode"] == 0:
                heatmap_layers = []
                for b in b_data["result"]["b"]:
                    heatmap_layers.append({"price": float(b[0]), "vol": float(b[1])})
                for a in b_data["result"]["a"]:
                    heatmap_layers.append({"price": float(a[0]), "vol": float(a[1])})
                
                # Re-use the candle logic or use fallback
                return JSONResponse(content={"source": "Cloud_Bybit", "heatmap": heatmap_layers, "candles": []})
    except Exception:
        pass

    # 4. LAST RESORT FALLBACK (The Flat Grid)
    base_p = 2515.0
    fallback_heatmap = [{"price": base_p - 1 + (x * 0.1), "vol": 10.0} for x in range(20)]
    fallback_candles = [{"open": base_p, "high": base_p+1, "low": base_p-1, "close": base_p+0.2} for _ in range(30)]
    return JSONResponse(content={"source": "System_Offline", "heatmap": fallback_heatmap, "candles": fallback_candles})

@app.get("/", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
    
