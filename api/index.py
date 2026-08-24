import os
import random
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# Map base assets template directory pathways
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Mount global assets safely if directory exists
static_path = os.path.join(BASE_DIR, "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/market-data")
async def fetch_market_matrix():
    try:
        # Standard structural midpoint baseline price for XAUUSD (Gold)
        base_gold_price = 2515.00
        
        # 1. GENERATE DYNAMIC HIGH-DENSITY DEPTH DATA Snapshots
        heatmap_layers = []
        for i in range(-50, 51):
            price_offset = round(base_gold_price + (i * 0.10), 2)
            # Simulate historical institutional resting blocks
            base_vol = random.uniform(5.0, 45.0)
            if i in [-30, -15, 12, 35]:  # Inject specific massive structural Whale Walls
                base_vol += random.uniform(120.0, 200.0)
                
            heatmap_layers.append({
                "price": price_offset,
                "vol": round(base_vol, 2)
            })
            
        # 2. GENERATE COMPATIBLE MATCHED CANDLESTICK OHLC SEQUENCES
        candle_layers = []
        current_open = 2512.00
        for _ in range(40):
            change = random.uniform(-2.5, 2.5)
            current_close = current_open + change
            current_high = max(current_open, current_close) + random.uniform(0.1, 1.2)
            current_low = min(current_open, current_close) - random.uniform(0.1, 1.2)
            
            candle_layers.append({
                "open": round(current_open, 2),
                "high": round(current_high, 2),
                "low": round(current_low, 2),
                "close": round(current_close, 2)
            })
            current_open = current_close
            
        return JSONResponse(content={
            "status": "success",
            "heatmap": heatmap_layers,
            "candles": candle_layers
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
      
