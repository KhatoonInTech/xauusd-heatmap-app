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
    # 1. TRY HOME MT5 BRIDGE (Prioritize your local laptop data)
    if redis_client:
        try:
            cached_bytes = redis_client.get("XAUUSD_LIVE_STATE")
            if cached_bytes:
                parsed_data = json.loads(cached_bytes)
                if parsed_data.get("heatmap") and len(parsed_data["heatmap"]) > 0:
                    return JSONResponse(content={"source": "MT5", "heatmap": parsed_data["heatmap"], "candles": parsed_data["candles"]})
        except Exception:
            pass

    # 2. CLOUD FAILOVER: BYBIT API (Primary Cloud Source - Cloud Friendly)
    # Bybit V5 Public API for XAUUSDT (Linear Perpetual)
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        # Fetch Order Book (Linear Category for USDT Perps)
        book_url = "https://api.bybit.com/v5/market/orderbook?category=linear&symbol=XAUUSDT&limit=25"
        kline_url = "https://api.bybit.com/v5/market/kline?category=linear&symbol=XAUUSDT&interval=5&limit=40"
        
        book_res = requests.get(book_url, headers=headers, timeout=4)
        kline_res = requests.get(kline_url, headers=headers, timeout=4)

        if book_res.status_code == 200 and kline_res.status_code == 200:
            b_data = book_res.json()
            k_data = kline_res.json()

            if b_data["retCode"] == 0 and k_data["retCode"] == 0:
                # Parse Bybit Order Book
                # Bybit format: result.b = [["price", "size"], ...]
                heatmap_layers = []
                for b in b_data["result"]["b"]:
                    heatmap_layers.append({"price": float(b[0]), "vol": float(b[1])})
                for a in b_data["result"]["a"]:
                    heatmap_layers.append({"price": float(a[0]), "vol": float(a[1])})

                # Parse Bybit Candles
                # Bybit returns newest first, so we reverse it for the chart
                candle_layers = []
                raw_candles = k_data["result"]["list"]
                for k in reversed(raw_candles):
                    candle_layers.append({
                        "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4])
                    })

                return JSONResponse(content={"source": "Cloud_Bybit", "heatmap": heatmap_layers, "candles": candle_layers})
    except Exception as e:
        print(f"Bybit failed: {e}")

    # 3. SECONDARY CLOUD FAILOVER: BINANCE API (Backup)
    try:
        b_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        book_res = requests.get("https://api.binance.com/api/v3/depth?symbol=XAUUSDT&limit=20", headers=b_headers, timeout=3)
        klines_res = requests.get("https://api.binance.com/api/v3/klines?symbol=XAUUSDT&interval=5m&limit=40", headers=b_headers, timeout=3)
        
        if book_res.status_code == 200 and klines_res.status_code == 200:
            book_data = book_res.json()
            klines_data = klines_res.json()
            
            heatmap_layers = []
            for b in book_data.get("bids", []):
                heatmap_layers.append({"price": float(b[0]), "vol": float(b[1])})
            for a in book_data.get("asks", []):
                heatmap_layers.append({"price": float(a[0]), "vol": float(a[1])})
            
            candle_layers = []
            for k in klines_data:
                candle_layers.append({"open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4])})
                
            return JSONResponse(content={"source": "Cloud_Binance", "heatmap": heatmap_layers, "candles": candle_layers})
    except Exception:
        pass

    # 4. LAST RESORT FALLBACK (The Flat Grid you saw)
    # We create this ONLY if absolutely every API blocks us.
    base_p = 2515.0
    fallback_heatmap = [{"price": base_p - 1 + (x * 0.1), "vol": 10.0} for x in range(20)]
    fallback_candles = [{"open": base_p, "high": base_p+1, "low": base_p-1, "close": base_p+0.2} for _ in range(30)]
    return JSONResponse(content={"source": "System_Offline", "heatmap": fallback_heatmap, "candles": fallback_candles})

@app.get("/", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
    
