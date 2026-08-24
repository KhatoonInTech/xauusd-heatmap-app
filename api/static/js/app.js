/**
 * Clean UI Canvas Renderer - Pulls Verified Cloud-Side Data Streams
 */
(function () {
    const canvas = document.getElementById('heatmapCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const footerText = document.querySelector('.main-footer p');
    const fallbackLabel = document.getElementById('canvasLoaderFallback');

    function renderMatrixFrame(heatmap, candles) {
        if (!heatmap || heatmap.length === 0 || !candles || candles.length === 0) return;

        // Instantly hide the initialization text overlay frame when genuine metrics load
        if (fallbackLabel) fallbackLabel.style.display = "none";

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const prices = heatmap.map(item => item.price);
        const maxPrice = Math.max(...prices);
        const minPrice = Math.min(...prices);
        const priceDelta = maxPrice - minPrice;

        if (priceDelta === 0) return;

        function projectPriceToY(price) {
            return canvas.height - (((price - minPrice) / priceDelta) * canvas.height);
        }

        // 1. BACKGROUND METRIC MATRIX MAPPING
        const volumes = heatmap.map(item => item.vol);
        const maxVolume = Math.max(...volumes);

        for (let i = 0; i < heatmap.length; i++) {
            const layer = heatmap[i];
            const pixelY = projectPriceToY(layer.price);
            const opacity = maxVolume > 0 ? Math.min(1, (layer.vol / maxVolume) * 2.0) : 0.2;
            
            ctx.fillStyle = "rgba(249, 115, 22, " + opacity + ")";
            ctx.fillRect(0, Math.floor(pixelY), canvas.width, 4);
        }

        // 2. FOREGROUND HIGH-DENSITY CANDLESTICK CHART OVERLAY
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
            const themeColor = isBullish ? '#22c55e' : '#ef4444';

            ctx.strokeStyle = themeColor;
            ctx.fillStyle = themeColor;
            ctx.lineWidth = 2;

            ctx.beginPath();
            ctx.moveTo(pixelX + (nodeWidth / 2), yHigh);
            ctx.lineTo(pixelX + (nodeWidth / 2), yLow);
            ctx.stroke();

            const blockTop = Math.min(yOpen, yClose);
            const blockHeight = Math.max(3, Math.abs(yOpen - yClose));
            ctx.fillRect(pixelX, blockTop, nodeWidth, blockHeight);
        }
    }

    async function pullCloudMarketState() {
        try {
            // Pull standard JSON outputs directly generated from un-blocked server nodes
            const response = await fetch('/api/market-data');
            const data = await response.json();

            if (data && data.heatmap && data.heatmap.length > 0) {
                if (footerText) {
                    if (data.source === "MT5") {
                        footerText.innerText = "🟢 Status: Linked with Active Home MT5 Data Bridge";
                    } else {
                        footerText.innerHTML = "🟡 Status: MT5 Standby • <span style='color:#eab308;'>Streaming Secure Serverless Binance Feed</span>";
                    }
                }
                renderMatrixFrame(data.heatmap, data.candles);
            }
        } catch (error) {
            console.error("Cloud synchronization polling loop delayed:", error);
        }
    }

    // Poll your Vercel endpoint every 3 seconds for continuous updates
    setInterval(pullCloudMarketState, 3000);
    pullCloudMarketState();
})();
