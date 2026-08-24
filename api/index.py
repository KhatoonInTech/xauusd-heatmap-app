import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Global shared storage layer holding the authentic market state
AUTHENTIC_MARKET_STATE = {
    "heatmap": [],
    "candles": []
}

# Secure token validation dependency framework
def verify_bridge_token(request: Request):
    expected_secret = os.getenv("MT5_BRIDGE_SECRET", "DEV_DEFAULT_TOKEN")
    client_token = request.headers.get("X-Bridge-Secret")
    if client_token != expected_secret:
        raise HTTPException(status_code=401, detail="Unauthorized Bridge Access Attempt")
    return True

# 1. THE DATA PORT: Accepts authentic data straight from your home laptop terminal
@app.post("/api/update-market-data")
async def update_market_matrix(payload: dict, authenticated: bool = Depends(verify_bridge_token)):
    global AUTHENTIC_MARKET_STATE
    
    # Store incoming authentic broker order book updates
    AUTHENTIC_MARKET_STATE["heatmap"] = payload.get("heatmap", [])
    AUTHENTIC_MARKET_STATE["candles"] = payload.get("candles", [])
    
    return {"status": "success", "message": "State synchronized successfully"}

# 2. THE WEBPAGE PORT: Feeds the data array straight into your HTML5 canvas
@app.get("/api/market-data")
async def fetch_market_matrix():
    global AUTHENTIC_MARKET_STATE
    return JSONResponse(content={
        "status": "success",
        "heatmap": AUTHENTIC_MARKET_STATE["heatmap"],
        "candles": AUTHENTIC_MARKET_STATE["candles"]
    })

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
