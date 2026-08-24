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
          
