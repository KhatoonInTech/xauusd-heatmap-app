import os
import json
import requests
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from upstash_redis import Redis

# INDUSTRIAL CORE FIX: Explicitly define the top-level app handler for Vercel
app = FastAPI()

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Mount assets securely inside the serverless package wrapper
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
    # 1. Attempt to serve live MT5 data from your home laptop cache
    if redis_client:
        try:
            cached_bytes = redis_client.get("XAUUSD_LIVE_STATE")
            if cached_bytes:
                parsed_data = json.loads(cached_bytes)
                if parsed_data.get("heatmap") and len(parsed_data["heatmap"]) > 0:
                    return JSONResponse(content={"source": "MT5", "heatmap": parsed_data["heatmap"], "candles": parsed_data["candles"]})
        except Exception:
            pass

    # 2. BINANCE CLOUD PIPELINE (PIPELINE B INTEGRATION)
    # This spoofs a desktop browser to ensure Binance does not block the request
    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    try:
        # Fetch fresh data from global Binance nodes
        book_res = requests.get("https://api.binance.com/api/v3/depth?symbol=XAUUSDT&limit=30", headers=browser_headers, timeout=5)
        klines_res = requests.get("https://api.binance.com/api/v3/klines?symbol=XAUUSDT&interval=5m&limit=40", headers=browser_headers, timeout=5)
        
        if book_res.status_code == 200 and klines_res.status_code == 200:
            book_data = book_res.json()
            klines_data = klines_res.json()
            
            heatmap_layers = []
            # PARSING FIX: Binance returns strings ["2500.00", "5.00"]. 
            # We must convert them to floats explicitly.
            for b in book_data.get("bids", []):
                heatmap_layers.append({"price": float(b[0]), "vol": float(b[1])})
            for a in book_data.get("asks", []):
                heatmap_layers.append({"price": float(a[0]), "vol": float(a[1])})
                
            candle_layers = []
            # PARSING FIX: Map indices 1-4 (Open, High, Low, Close) to float
            for k in klines_data:
                candle_layers.append({
                    "open": float(k[1]), 
                    "high": float(k[2]), 
                    "low": float(k[3]), 
                    "close": float(k[4])
                })
            
            # Sort heatmap by price for cleaner rendering (optional but recommended)
            heatmap_layers.sort(key=lambda x: x["price"], reverse=True)

            return JSONResponse(content={"source": "Binance_Cloud", "heatmap": heatmap_layers, "candles": candle_layers})
            
        else:
            print(f"Binance Error: {book_res.status_code} | {klines_res.status_code}")

    except Exception as e:
        print(f"Cloud pipeline failed: {e}")
        
    # 3. SAFETY FALLBACK (The Flat Grid)
    # This only triggers if BOTH Redis and Binance fail completely
    base_p = 2515.0
    fallback_heatmap = [{"price": base_p - 1 + (x * 0.1), "vol": 10.0} for x in range(20)]
    fallback_candles = [{"open": base_p, "high": base_p+1, "low": base_p-1, "close": base_p+0.2} for _ in range(30)]
    return JSONResponse(content={"source": "Local_Fallback", "heatmap": fallback_heatmap, "candles": fallback_candles})

@app.get("/", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
            
