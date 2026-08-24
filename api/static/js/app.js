/**
 * Industrial Dual-Source Canvas Rendering Engine - Defensively Guarded
 */
(function () {
    const canvas = document.getElementById('heatmapCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const footerText = document.querySelector('.main-footer p');
    const fallbackLabel = document.getElementById('canvasLoaderFallback');
    const toggleBtn = document.getElementById('sourceToggleBtn');

    // Safe hardcoded structural fallback data to prevent an empty screen under any network condition
    const backupPrice = 2515.00;
    const mockHeatmap = Array.from({length: 30}, (_, i) => ({ price: backupPrice - 1.5 + (i * 0.1), vol: Math.random() * 50 }));
    const mockCandles = Array.from({length: 40}, (_, i) => ({ open: backupPrice, high: backupPrice + 1, low: backupPrice - 1, close: backupPrice + 0.2 }));

    let currentHeatmap = [];
    let currentCandles = [];
    let binanceSocket = null;
    let fallbackActive = false;
    let forceBinance = false;

    if (toggleBtn) {
        toggleBtn.onclick = function() {
            forceBinance = !forceBinance;
            if (forceBinance) {
                toggleBtn.innerText = "MODE: FORCED BINANCE (CRYPTO)";
                toggleBtn.style.borderColor = "#eab308";
                activateBinanceFallback();
            } else {
                toggleBtn.innerText = "MODE: AUTO-SWITCHING";
                toggleBtn.style.borderColor = "#334155";
                if (binanceSocket) { binanceSocket.close(); binanceSocket = null; }
                fallbackActive = false;
                auditDataPipeline();
            }
        };
    }

    function renderMatrixFrame(heatmap, candles) {
        // Core Guard: If arrays are empty or corrupted, fall back to safe data structures to keep screen active
        if (!heatmap || heatmap.length === 0 || !candles || candles.length === 0) {
            heatmap = mockHeatmap;
            candles = mockCandles;
        }

        // Hide the backing loader watermark text when rendering
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

        // 1. BACKGROUND LIQUIDITY COATING
        const volumes = heatmap.map(item => item.vol);
        const maxVolume = Math.max(...volumes);

        for (let i = 0; i < heatmap.length; i++) {
            const layer = heatmap[i];
            const pixelY = projectPriceToY(layer.price);
            const opacity = maxVolume > 0 ? Math.min(1, (layer.vol / maxVolume) * 1.5) : 0.2;
            
            ctx.fillStyle = "rgba(249, 115, 22, " + opacity + ")";
            ctx.fillRect(0, Math.floor(pixelY), canvas.width, 4);
        }

        // 2. FOREGROUND CANDLESTICK OVERLAY
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

            ctx.beginPath();
            ctx.moveTo(pixelX + (nodeWidth / 2), yHigh);
            ctx.lineTo(pixelX + (nodeWidth / 2), yLow);
            ctx.stroke();

            const blockTop = Math.min(yOpen, yClose);
            const blockHeight = Math.max(3, Math.abs(yOpen - yClose));
            ctx.fillRect(pixelX, blockTop, nodeWidth, blockHeight);
        }
    }

    function activateBinanceFallback() {
        if (fallbackActive) return;
        fallbackActive = true;
        
        if (footerText) footerText.innerHTML = "🟡 MT5 Standby • <span style='color:#eab308;'>Streaming direct Binance public WebSockets (XAUUSDT)</span>";

        if (binanceSocket) { binanceSocket.close(); }
        binanceSocket = new WebSocket(`wss://://binance.com`);

        // Load baseline candles and render immediately using fallbacks if the network delays
        fetch(`https://binance.com`)
            .then(res => res.json())
            .then(rawData => {
                currentCandles = rawData.map(bar => ({
                    open: parseFloat(bar[1]), high: parseFloat(bar[2]), low: parseFloat(bar[3]), close: parseFloat(bar[4])
                }));
                renderMatrixFrame(currentHeatmap, currentCandles);
            })
            .catch(() => {
                currentCandles = mockCandles;
                renderMatrixFrame(currentHeatmap, currentCandles);
            });

        binanceSocket.onmessage = function (event) {
            const packet = JSON.parse(event.data);

            if (packet.bids && packet.asks) {
                currentHeatmap = [];
                packet.bids.forEach(b => currentHeatmap.push({ price: parseFloat(b[0]), vol: parseFloat(b[1]) }));
                packet.asks.forEach(a => currentHeatmap.push({ price: parseFloat(a[0]), vol: parseFloat(a[1]) }));
                renderMatrixFrame(currentHeatmap, currentCandles);
            }

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

    async function auditDataPipeline() {
        if (forceBinance) return;

        try {
            const response = await fetch('/api/market-data');
            const payload = await response.json();

            if (payload && payload.status === 'success' && payload.heatmap && payload.heatmap.length > 0) {
                if (fallbackActive) {
                    if (binanceSocket) binanceSocket.close();
                    fallbackActive = false;
                }
                if (footerText) footerText.innerText = "🟢 Status: Linked with Active Home MT5 Data Bridge";
                renderMatrixFrame(payload.heatmap, payload.candles);
            } else {
                activateBinanceFallback();
            }
        } catch (error) {
            activateBinanceFallback();
        }
    }

    setInterval(auditDataPipeline, 4000);
    auditDataPipeline();
})();
            
