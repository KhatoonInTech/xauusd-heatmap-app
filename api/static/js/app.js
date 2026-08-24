/**
 * Industrial Dual-Source Canvas Rendering Engine - MT5 & Binance Failover Matrix
 */
(function () {
    const canvas = document.getElementById('heatmapCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const footerText = document.querySelector('.main-footer p');

    // Internal memory buffers preserving live metrics
    let currentHeatmap = [];
    let currentCandles = [];
    let binanceSocket = null;
    let fallbackActive = false;

    // Configuration constraints
    const binanceSymbol = "XAUUSDT";

    // Standard structural mapping boundary projector converting price units to screen row pixels
    function renderMatrixFrame(heatmap, candles) {
        if (!heatmap || heatmap.length === 0 || !candles || candles.length === 0) return;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const prices = heatmap.map(function(item) { return item.price; });
        const maxPrice = Math.max(...prices);
        const minPrice = Math.min(...prices);
        const priceDelta = maxPrice - minPrice;

        if (priceDelta === 0) return;

        function projectPriceToY(price) {
            return canvas.height - (((price - minPrice) / priceDelta) * canvas.height);
        }

        // --- PHASE 1: BACKGROUND LIQUIDITY MATRIX COATING ---
        const volumes = heatmap.map(function(item) { return item.vol; });
        const maxVolume = Math.max(...volumes);

        for (let i = 0; i < heatmap.length; i++) {
            const layer = heatmap[i];
            const pixelY = projectPriceToY(layer.price);
            const opacityFactor = maxVolume > 0 ? Math.min(1, (layer.vol / maxVolume) * 1.5) : 0.2;
            
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

            // Render structural wick lines
            ctx.beginPath();
            ctx.moveTo(pixelX + (nodeWidth / 2), yHigh);
            ctx.lineTo(pixelX + (nodeWidth / 2), yLow);
            ctx.stroke();

            // Render structural body blocks
            const blockTop = Math.min(yOpen, yClose);
            const blockHeight = Math.max(3, Math.abs(yOpen - yClose));
            ctx.fillRect(pixelX, blockTop, nodeWidth, blockHeight);
        }
    }

    // --- PHASE 3: THE AUTOMATIC BINANCE FAILOVER WEBSOCKET LOOP ---
    function activateBinanceFallback() {
        if (fallbackActive) return;
        fallbackActive = true;
        
        if (footerText) footerText.innerHTML = "🔴 MT5 Offline • <span style='color:#eab308;'>Failing over to Live Binance WebSockets (XAUUSDT)</span>";
        console.log("Initializing core live Binance data switchover...");

        // Open direct free socket pipelines directly to Binance infrastructure
        const wsUrl = `wss://://binance.com{binanceSymbol.toLowerCase()}@depth20@100ms/${binanceSymbol.toLowerCase()}@kline_5m`;
        binanceSocket = new WebSocket(wsUrl);

        // Pre-seed baseline candlestick coordinates from public Binance REST nodes
        fetch(`https://binance.com{binanceSymbol}&interval=5m&limit=40`)
            .then(res => res.json())
            .then(rawData => {
                currentCandles = rawData.map(bar => ({
                    open: parseFloat(bar[1]), high: parseFloat(bar[2]), low: parseFloat(bar[3]), close: parseFloat(bar[4])
                }));
            });

        binanceSocket.onmessage = function (event) {
            const packet = JSON.parse(event.data);

            // Catch Order Book changes
            if (packet.bids && packet.asks) {
                currentHeatmap = [];
                packet.bids.forEach(b => currentHeatmap.push({ price: parseFloat(b[0]), vol: parseFloat(b[1]) }));
                packet.asks.forEach(a => currentHeatmap.push({ price: parseFloat(a[0]), vol: parseFloat(a[1]) }));
                renderMatrixFrame(currentHeatmap, currentCandles);
            }

            // Catch ongoing candlestick tick steps
            if (packet.e === "kline") {
                const k = packet.k;
                const activeTickCandle = {
                    open: parseFloat(k.o), high: parseFloat(k.h), low: parseFloat(k.l), close: parseFloat(k.c)
                };
                if (currentCandles.length > 0) {
                    if (!k.x) {
                        currentCandles[currentCandles.length - 1] = activeTickCandle;
                    } else {
                        currentCandles.push(activeTickCandle);
                        currentCandles.shift();
                    }
                }
            }
        };
    }

    // --- PHASE 4: INITIAL MASTER DATA AUDIT PIPELINE ---
    async function auditDataPipeline() {
        try {
            const response = await fetch('/api/market-data');
            const payload = await response.json();

            // If Upstash Redis serves a valid populated matrix pool, render it and kill fallbacks
            if (payload && payload.status === 'success' && payload.heatmap && payload.heatmap.length > 0) {
                if (fallbackActive) {
                    console.log("MT5 transmission detected. Shutting down crypto socket fallback streams.");
                    if (binanceSocket) binanceSocket.close();
                    fallbackActive = false;
                }
                if (footerText) footerText.innerText = "🟢 Status: Synchronized with Active Home MT5 Data Bridge";
                renderMatrixFrame(payload.heatmap, payload.candles);
            } else {
                // If the array drops to empty, pull the emergency break and trigger Binance immediately
                activateBinanceFallback();)
            }
        } catch (error) {
            console.error("Master check telemetry failed, defaulting to emergency loop.", error);
            activateBinanceFallback();
        }
    }

    // Continually analyze your pipeline every 4 seconds
    setInterval(auditDataPipeline, 4000);
    auditDataPipeline();
})();

          
