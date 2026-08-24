import os
import json
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from upstash_redis import Redis

app = FastAPI()

# Mount static folder securely using relative path declarations
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize the industrial cloud database client within a safe execution sandbox
redis_client = None
try:
    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    
    # Only establish the socket if both credentials are validly populated strings
    if url and token:
        redis_client = Redis(url=url, token=token)
    else:
        print("⚠️ Warning: Upstash Redis keys are missing. Running in standby mode.")
except Exception as init_err:
    print(f"❌ Database connection initialization failed: {init_err}")

# Secure verification middleware
def verify_bridge_token(request: Request):
    expected_secret = os.getenv("MT5_BRIDGE_SECRET", "DEV_DEFAULT_TOKEN")
    client_token = request.headers.get("X-Bridge-Secret")
    if client_token != expected_secret:
        raise HTTPException(status_code=401, detail="Unauthorized Bridge Access")
    return True

# 1. THE DATA PORT: Permanently locks incoming authentic terminal metrics to your database cache
@app.post("/api/update-market-data")
async def update_market_matrix(payload: dict, authenticated: bool = Depends(verify_bridge_token)):
    if not redis_client:
        raise HTTPException(status_code=503, detail="Database cache client is currently offline.")
        
    try:
        compressed_state = {
            "heatmap": payload.get("heatmap", []),
            "candles": payload.get("candles", [])
        }
        
        # Save snapshot with a 1-hour automatic expiration safety cap
        redis_client.set("XAUUSD_LIVE_STATE", json.dumps(compressed_state), ex=3600)
        return {"status": "success", "message": "Global data state written to database."}
    except Exception as db_err:
        raise HTTPException(status_code=500, detail=f"Database write execution failed: {db_err}")

# 2. THE WEBPAGE PORT: Pulls data coordinates straight out of the secure database cache layer
@app.get("/api/market-data")
async def fetch_market_matrix():
    # If the database client is offline, drop out into empty arrays to prevent frontend screen crashes
    if not redis_client:
        return JSONResponse(content={"status": "success", "heatmap": [], "candles": []})
        
    try:
        cached_bytes = redis_client.get("XAUUSD_LIVE_STATE")
        
        if cached_bytes:
            parsed_data = json.loads(cached_bytes)
            return JSONResponse(content={
                "status": "success",
                "heatmap": parsed_data.get("heatmap", []),
                "candles": parsed_data.get("candles", [])
            })
    except Exception as fetch_err:
        print(f"Database query warning: {fetch_err}")
        
    return JSONResponse(content={"status": "success", "heatmap": [], "candles": []})

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
