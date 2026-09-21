document.addEventListener('DOMContentLoaded', function () {
    const scanBtn = document.getElementById('scanBtn');
    const limitSelect = document.getElementById('coinLimit');
    const tbody = document.getElementById('resultsBody');
    const spinner = document.getElementById('loadingSpinner');

    const totalCount = document.getElementById('totalCount');
    const longCount = document.getElementById('longCount');
    const shortCount = document.getElementById('shortCount');
    const avgConf = document.getElementById('avgConf');

    const originalBtnHTML = scanBtn.innerHTML;

    // Fixed scan settings — full confirmation (indicators + candles + chart patterns), relaxed entry zone.
    const MODE = 'full';
    const ENTRY_TYPE = 'relaxed';

    async function performScan() {
        const limit = limitSelect.value;

        scanBtn.disabled = true;
        scanBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Scanning...';

        spinner.style.display = 'block';
        tbody.innerHTML = '';

        try {
            const url = `/api/scan?limit=${limit}&mode=${MODE}&entry_type=${ENTRY_TYPE}`;
            const response = await fetch(url);
            const result = await response.json();

            if (result.status === 'redirect' && result.redirect_url) {
                window.location.href = result.redirect_url;
                return;
            }

            if (result.status === 'success' && result.data.length > 0) {
                renderTable(result.data);
                updateStats(result.data);
            } else {
                tbody.innerHTML = `
                    <tr><td colspan="12">
                        <div class="empty-state">
                            <i class="fas fa-frown"></i>
                            <p>No signals found right now. Try again in a few minutes.</p>
                        </div>
                    </td></tr>
                `;
                updateStats([]);
            }
        } catch (error) {
            console.error(error);
            tbody.innerHTML = `
                <tr><td colspan="12">
                    <div class="empty-state" style="color: var(--sell);">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>Error connecting to the scanner backend. Please try again shortly.</p>
                    </div>
                </td></tr>
            `;
        } finally {
            spinner.style.display = 'none';
            scanBtn.disabled = false;
            scanBtn.innerHTML = originalBtnHTML;
        }
    }

    scanBtn.addEventListener('click', performScan);

    function renderTable(data) {
        if (!data || data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="12"><div class="empty-state"><i class="fas fa-inbox"></i><p>No signals</p></div></td></tr>`;
            return;
        }

        let html = '';
        data.forEach((item, index) => {
            const isLong = item.signal === 'LONG';
            const badgeClass = isLong ? 'badge-long' : 'badge-short';
            const trendClass = item.trend === 'Bullish' ? 'badge-bull' : 'badge-bear';
            const trendIcon = item.trend === 'Bullish' ? 'fa-arrow-up' : 'fa-arrow-down';

            let fillClass = 'fill-low';
            if (item.confidence >= 70) fillClass = 'fill-high';
            else if (item.confidence >= 45) fillClass = 'fill-mid';

            let risk, reward;
            if (isLong) { risk = item.price - item.stop_loss; reward = item.take_profit - item.price; }
            else { risk = item.stop_loss - item.price; reward = item.price - item.take_profit; }
            const rr = risk > 0 ? (reward / risk).toFixed(2) : '0';

            let patternDisplay = '';
            if (item.pattern && item.pattern.length > 0) {
                if (item.pattern.includes(' | ')) {
                    const parts = item.pattern.split(' | ');
                    patternDisplay = `<span class="pattern-tag"><i class="fas fa-square"></i> ${parts[0]}</span>`;
                    if (parts[1]) patternDisplay += ` <span class="chart-tag"><i class="fas fa-chart-line"></i> ${parts[1]}</span>`;
                } else {
                    patternDisplay = `<span class="pattern-tag"><i class="fas fa-square"></i> ${item.pattern}</span>`;
                }
            } else {
                patternDisplay = `<span style="color: var(--text-faint); font-size: 11px;">—</span>`;
            }

            let chartDisplay = '';
            if (item.chart_pattern && item.chart_pattern.length > 0) {
                chartDisplay = `<span class="chart-tag"><i class="fas fa-chart-line"></i> ${item.chart_pattern}</span>`;
            } else {
                chartDisplay = `<span style="color: var(--text-faint); font-size: 11px;">—</span>`;
            }

            html += `
                <tr class="main-row" data-index="${index}">
                    <td data-label="#">${index + 1}</td>
                    <td data-label="Coin"><strong>${item.symbol}</strong></td>
                    <td data-label="Trend (4H)"><span class="${trendClass}"><i class="fas ${trendIcon}"></i> ${item.trend}</span></td>
                    <td data-label="Action"><span class="badge ${badgeClass}">${item.signal}</span></td>
                    <td data-label="Entry Price" style="color: var(--buy);">$${item.price}</td>
                    <td data-label="Stop Loss" style="color: var(--sell);">$${item.stop_loss}</td>
                    <td data-label="Take Profit" style="color: var(--buy);">$${item.take_profit}</td>
                    <td data-label="Leverage">${item.leverage}</td>
                    <td data-label="Confidence">
                        <div class="conf-bar"><div class="fill ${fillClass}" style="width: ${item.confidence}%;"></div></div>
                        ${item.confidence}%
                    </td>
                    <td data-label="Candle Pattern">${patternDisplay}</td>
                    <td data-label="Chart Pattern">${chartDisplay}</td>
                    <td data-label=""><button onclick="toggleDetail(${index})" style="background: none; border: none; color: var(--text-faint); cursor: pointer;"><i class="fas fa-plus-circle"></i> <span class="detail-toggle-label">Details</span></button></td>
                </tr>
                <tr class="detail-row" id="detail-${index}">
                    <td colspan="12">
                        <div class="detail-content">
                            <div class="detail-item"><span class="label">Risk / Reward</span><span class="val">1 : ${rr}</span></div>
                            <div class="detail-item"><span class="label">Risk %</span><span class="val">${(risk / item.price * 100).toFixed(2)}%</span></div>
                            <div class="detail-item"><span class="label">Reward %</span><span class="val">${(reward / item.price * 100).toFixed(2)}%</span></div>
                            <div class="detail-item"><span class="label">Strategy Rule</span><span class="val" style="font-size: 13px; font-weight: 400;">${isLong ? 'Price>MA20, RSI>30, MACD Cross Up' : 'Price<MA20, RSI<70, MACD Cross Down'}</span></div>
                            <div class="detail-item"><span class="label">Chart Patterns</span><span class="val" style="font-size: 13px; font-weight: 400;">${item.chart_pattern || '—'}</span></div>
                        </div>
                    </td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
    }

    window.toggleDetail = function (index) {
        const row = document.getElementById(`detail-${index}`);
        if (row) {
            row.classList.toggle('active');
            const btn = document.querySelector(`.main-row[data-index="${index}"] button i`);
            if (btn) {
                btn.classList.toggle('fa-plus-circle');
                btn.classList.toggle('fa-minus-circle');
            }
        }
    };

    function updateStats(data) {
        totalCount.textContent = data.length;
        const longs = data.filter(d => d.signal === 'LONG').length;
        const shorts = data.filter(d => d.signal === 'SHORT').length;
        longCount.textContent = longs;
        shortCount.textContent = shorts;
        if (data.length > 0) {
            const avg = data.reduce((sum, d) => sum + d.confidence, 0) / data.length;
            avgConf.textContent = avg.toFixed(1) + '%';
        } else {
            avgConf.textContent = '0%';
        }
    }
});
