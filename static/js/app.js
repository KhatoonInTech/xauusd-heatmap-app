/**
 * Industrial Canvas Rendering Engine - XAUUSD Spatial Matrix mapping
 */
(function () {
    const canvas = document.getElementById('heatmapCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    async function processAndRenderFrame() {
        try {
            const response = await fetch('/api/market-data');
const payload = await response.json();

// Locate this section inside your app.js loop logic
if (!payload || !payload.heatmap || payload.heatmap.length === 0) {
    // 1. Wipe the black background canvas cleanly
    ctx.fillStyle = "#020617"; // Slate 950 color match
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 2. Force text settings with explicit contrasting colors
    ctx.fillStyle = "#f97316"; // Bright Orange text
    ctx.font = "bold 24px monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("WAITING FOR DATA CONNECTION...", canvas.width / 2, canvas.height / 2);
    
    // 3. Subtext placement details
    ctx.font = "14px monospace";
    ctx.fillStyle = "#94a3b8"; // Light slate text
    ctx.fillText("Database cache active. Turn on your home MT5 data bridge to stream metrics.", canvas.width / 2, (canvas.height / 2) + 40);
    return;
}

            
            if (!payload || payload.status !== 'success') {
                console.error("Data ingestion pipeline stalled.");
                return;
            }

            const heatmap = payload.heatmap;
            const candles = payload.candles;

            // Clean previous buffer cache canvas canvas frames
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Establish structured mapping boundary parameters
            const priceMatrix = heatmap.map(function(item) { return item.price; });
            const maxPrice = Math.max(...priceMatrix);
            const minPrice = Math.min(...priceMatrix);
            const priceDelta = maxPrice - minPrice;

            if (priceDelta === 0) return;

            // Mapping calculation helper converting price units to raw screen rows
            function projectPriceToY(price) {
                return canvas.height - (((price - minPrice) / priceDelta) * canvas.height);
            }

            // --- PHASE 1: BACKGROUND GRID MATRIX COATING ---
            for (let i = 0; i < heatmap.length; i++) {
                const layer = heatmap[i];
                const pixelY = projectPriceToY(layer.price);
                
                // Transform lots volume thresholds directly into structural alpha color opacity
                const opacityFactor = Math.min(1, layer.vol / 160);
                
                ctx.fillStyle = "rgba(249, 115, 22, " + opacityFactor + ")";
                ctx.fillRect(0, Math.floor(pixelY), canvas.width, 4);
            }

            // --- PHASE 2: FOREGROUND HIGH-DENSITY CANDLESTICK OVERLAY ---
            const nodeWidth = 14;
            const nodeGap = 6;
            const horizontalPaddingLeft = 60;

            for (let j = 0; j < candles.length; j++) {
                const candle = candles[j];
                const pixelX = horizontalPaddingLeft + j * (nodeWidth + nodeGap);

                const yOpen  = projectPriceToY(candle.open);
                const yClose = projectPriceToY(candle.close);
                const yHigh  = projectPriceToY(candle.high);
                const yLow   = projectPriceToY(candle.low);

                const isBullish = candle.close >= candle.open;
                const signatureColor = isBullish ? '#22c55e' : '#ef4444';

                ctx.strokeStyle = signatureColor;
                ctx.fillStyle = signatureColor;
                ctx.lineWidth = 2;

                // Render structural wick spine lines
                ctx.beginPath();
                ctx.moveTo(pixelX + (nodeWidth / 2), yHigh);
                ctx.lineTo(pixelX + (nodeWidth / 2), yLow);
                ctx.stroke();

                // Render matching structural body blocks
                const blockTop = Math.min(yOpen, yClose);
                const blockHeight = Math.max(3, Math.abs(yOpen - yClose));
                ctx.fillRect(pixelX, blockTop, nodeWidth, blockHeight);
            }

        } catch (error) {
            console.error("Critical rendering execution collision detected:", error);
        }
    }

    // Initialize tracking interval loops continuously running frame renders every 3000ms
    setInterval(processAndRenderFrame, 3000);
    processAndRenderFrame();
})();
          
