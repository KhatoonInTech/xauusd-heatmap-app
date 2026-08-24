import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# Mount the static folder using a clean, deployment-agnostic path format
app.mount("/static", StaticFiles(directory="static"), name="static")

# Point templates directly to your root level templates folder
templates = Jinja2Templates(directory="templates")


# Initialize the industrial cloud database connection safely using environment variables
redis_url = os.getenv("UPSTASH_REDIS_REST_URL")
redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")

# Global production backup configuration fallback if database keys are initializing
redis_client = None
if redis_url and redis_token:
    redis_client = Redis(url=redis_url, token=redis_token)

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
        raise HTTPException(status_code=500, detail="Database credentials missing on Vercel environment.")
        
    # Serialize the authentic data matrix cleanly to a unified Redis string key
    compressed_state = {
        "heatmap": payload.get("heatmap", []),
        "candles": payload.get("candles", [])
    }
    
    # Store data point cache in Redis with an automatic expiration safety cap of 1 hour
    redis_client.set("XAUUSD_LIVE_STATE", json.dumps(compressed_state), ex=3600)
    return {"status": "success", "message": "Global data state written to database."}

# 2. THE WEBPAGE PORT: Pulls data coordinates straight out of the secure database cache layer
@app.get("/api/market-data")
async def fetch_market_matrix():
    # If database connection is offline, output clean empty fallback structure safely
    if not redis_client:
        return JSONResponse(content={"status": "success", "heatmap": [], "candles": []})
        
    # Query database string key
    cached_bytes = redis_client.get("XAUUSD_LIVE_STATE")
    
    if cached_bytes:
        # Parse compiled database string back to native client JSON arrays instantly
        parsed_data = json.loads(cached_bytes)
        return JSONResponse(content={
            "status": "success",
            "heatmap": parsed_data.get("heatmap", []),
            "candles": parsed_data.get("candles", [])
        })
        
    return JSONResponse(content={"status": "success", "heatmap": [], "candles": []})

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
    
