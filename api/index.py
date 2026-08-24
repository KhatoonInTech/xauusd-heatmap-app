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
async def update_market_matrix(payload: dict, authenticated: bool = Depends(verify_bridge_token)):
    if not redis_client:
        raise HTTPException(status_code=503, detail="Database offline")
    compressed_state = {
        "heatmap": payload.get("heatmap", []),
        "candles": payload.get("candles", [])
    }
    redis_client.set("XAUUSD_LIVE_STATE", json.dumps(compressed_state), ex=3600)
    return {"status": "success"}

# --- CLOUD PIPELINE SWITCH: BYPASSES PAKISTAN WEBSOCKET BLOCKS ---
@app.get("/api/market-data")
async def fetch_market_matrix():
    # 1. Attempt to read home terminal data from Upstash Cache
    if redis_client:
        try:
            cached_bytes = redis_client.get("XAUUSD_LIVE_STATE")
            if cached_bytes:
                parsed_data = json.loads(cached_bytes)
                if parsed_data.get("heatmap") and len(parsed_data["heatmap"]) > 0:
                    return JSONResponse(content={"source": "MT5", "heatmap": parsed_data["heatmap"], "candles": parsed_data["candles"]})
        except Exception:
            pass

    # 2. FAILOVER FALLBACK: Pull data cloud-to-cloud from Binance API nodes (Bypasses Local ISP blocks)
    try:
        # Query un-blocked global exchange APIs for order books and candlesticks simultaneously
        book_res = requests.get("https://binance.com", timeout=3)
        klines_res = requests.get("https://binance.com", timeout=3)
        
        if book_res.status_code == 200 and klines_res.status_code == 200:
            book_data = book_res.json()
            klines_data = klines_res.json()
            
            # Format exchange metrics to fit our existing frontend canvas properties
            heatmap_layers = []
            for b in book_data.get("bids", []):
                heatmap_layers.append({"price": float(b[0]), "vol": float(b[1])})
            for a in book_data.get("asks", []):
                heatmap_layers.append({"price": float(a[0]), "vol": float(a[1])})
                
            candle_layers = []
            for k in klines_data:
                candle_layers.append({
                    "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4])
                })
                
            return JSONResponse(content={"source": "Binance_Cloud", "heatmap": heatmap_layers, "candles": candle_layers})
            
    except Exception as e:
        print(f"Cloud fallback connection warning: {e}")
        
    return JSONResponse(content={"source": "Offline", "heatmap": [], "candles": []})

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
    
