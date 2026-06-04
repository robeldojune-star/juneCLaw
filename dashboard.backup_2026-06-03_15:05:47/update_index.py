import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Insert socket.io script after lightweight-charts script
pattern = r'(<script src="https://unpkg\.com/lightweight-charts@4\.0\.0/dist/lightweight-charts\.standalone\.production\.js"></script>)'
replacement = r'\1\n    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>'
content = re.sub(pattern, replacement, content)

# 2. Replace the bottom script block
parts = content.split('</body>')
if len(parts) != 2:
    raise ValueError('Unexpected content structure')
body_part = parts[0]
after_body = '</body>' + parts[1]

# Find all script tags in body_part
script_pattern = re.compile(r'<script>.*?</script>', re.DOTALL)
matches = list(script_pattern.finditer(body_part))
if len(matches) < 2:
    raise ValueError('Expected at least two script blocks')
second_match = matches[1]

new_script = '''<script>
        // Socket.io client
        const socket = io();

        // Helper functions
        function formatNumber(num) {
            return new Intl.NumberFormat('ko-KR').format(num);
        }

        function createMarketCard(title, value, change, isPositive) {
            const div = document.createElement('div');
            div.className = `glass p-4 card-hover`;
            div.innerHTML = `
                <h3 class="font-semibold mb-2">${title}</h3>
                <div class="flex justify-between items-baseline">
                    <span class="text-2xl font-bold count-up">${value}</span>
                    <span class="text-lg font-medium ${isPositive ? 'text-green-400' : 'text-red-400'}">
                        ${change >= 0 ? '▲' : '▼'} ${Math.abs(change).toFixed(2)}%
                    </span>
                </div>
            `;
            return div;
        }

        function createSignalCard(signal, type) {
            const div = document.createElement('div');
            div.className = `glass p-4 card-hover border-l-4 ${type === 'buy' ? 'border-neon-blue' : 'border-red-500'} bg-black/30`;
            div.innerHTML = `
                <h3 class="font-semibold mb-2 flex items-center gap-2">
                    ${type === 'buy' ? '🟢 매수 신호' : '🔴 매도 신호'}
                    <span>${signal.name || 'Unknown'}</span>
                </div>
                <div class="space-y-2 text-sm">
                    <div>신뢰도: <span class="font-medium">${signal.confidence || 0}%</span></div>
                    <div>예상 수익률: <span class="font-medium">${signal.expectedProfit || 0}%</span></div>
                    ${type === 'buy' ? `
                        <div>진입 가격: <span class="font-medium">${formatNumber(signal.entryPrice || 0)} 원</span></div>
                    ` : `
                        <div>위험도: <span class="font-medium">${signal.riskLevel || 'Medium'}</span></div>
                        <div>손절가: <span class="font-medium">${formatNumber(signal.stopLoss || 0)} 원</span></div>
                        <div>목표가: <span class="font-medium">${formatNumber(signal.targetPrice || 0)} 원</span></div>
                    `}
                </div>
            `;
            return div;
        }

        function createHoldingCard(holding) {
            const div = document.createElement('div');
            div.className = `glass p-4 card-hover`;
            const pl = holding.plAmt || 0;
            div.innerHTML = `
                <h3 class="font-semibold mb-2">${holding.stkNm || 'Unknown'}</h3>
                <div class="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <span class="block text-gray-400">매입가</span>
                        <span class="font-medium">${formatNumber(holding.avgPrc || 0)} 원</span>
                    </div>
                    <div>
                        <span class="block text-gray-400">보유수량</span>
                        <span class="font-medium">${formatNumber(holding.rmndQty || 0)} 주</span>
                    </div>
                    <div>
                        <span class="block text-gray-400">평가금액</span>
                        <span class="font-medium">${formatNumber(holding.evltAmt || 0)} 원</span>
                    </div>
                    <div>
                        <span class="block text-gray-400">평가손익</span>
                        <span class="font-medium ${pl >= 0 ? 'text-green-400' : 'text-red-400'}">
                            ${formatNumber(pl)} 원
                        </span>
                    </div>
                    <div>
                        <span class="block text-gray-400">수익률(%)</span>
                        <span class="font-medium ${pl >= 0 ? 'text-green-400' : 'text-red-400'}">
                            ${(holding.plRt || 0).toFixed(2)}%
                        </span>
                    </div>
                    <div>
                        <span class="block text-gray-400">종목코드</span>
                        <span class="font-mono">${holding.stkCode || '-'}</span>
                    </div>
                </div>
            `;
            return div;
        }

        function createAnalysisGauge(title, value, description) {
            const div = document.createElement('div');
            div.className = `glass p-6 text-center`;
            div.innerHTML = `
                <h3 class="font-semibold mb-4">${title}</h3>
                <div class="text-4xl font-bold count-up mb-2">${value}</div>
                <p class="text-gray-400">${description}</p>
            `;
            return div;
        }

        function createPerformanceMetric(title, value, subtitle, isPositive) {
            const div = document.createElement('div');
            div.className = `glass p-6 text-center`;
            div.innerHTML = `
                <h3 class="font-semibold mb-2">${title}</h3>
                <div class="text-3xl font-bold count-up mb-2 ${isPositive ? 'text-green-400' : 'text-red-400'}">${value}</div>
                <p class="text-gray-400 text-sm">${subtitle}</p>
            `;
            return div;
        }

        function updateDashboard(signals, accountData) {
            // Update market status (mock data for now)
            const marketStatus = document.getElementById('market-status');
            marketStatus.innerHTML = '';
            const marketData = [
                { title: 'KOSPI', value: '2,845.30', change: 1.25 },
                { title: 'KOSDAQ', value: '923.15', change: -0.85 },
                { title: 'USD/KRW', value: '1,320.50', change: 0.32 },
                { title: 'BTC', value: '68,420.00', change: 2.10 }
            ];
            marketData.forEach(data => {
                marketStatus.appendChild(createMarketCard(data.title, data.value, data.change, data.change >= 0));
            });
            // Chart for BTC (using lightweight-charts)
            const btclike = marketData.find(m => m.title === 'BTC');
            if (btclike) {
                const price = parseFloat(btclike.value.replace(/[^\\d.-]/g, ''));
                // Generate mock OHLC data for the last 60 minutes
                const now = Date.now();
                const data = [];
                let last = price;
                for (let i = 59; i >= 0; i--) {
                    const time = now - i * 60 * 1000;
                    const change = (Math.random() - 0.5) * 0.02; // +/-1%
                    const open = last * (1 + change);
                    const close = open * (1 + (Math.random() - 0.5) * 0.01);
                    const high = Math.max(open, close) * (1 + Math.random() * 0.005);
                    const low = Math.min(open, close) * (1 - Math.random() * 0.005);
                    data.push({ time: time / 1000, open, high, low, close });
                    last = close;
                }
                if (!window.btcChart) {
                    const chartContainer = document.getElementById('market-chart');
                    window.btcChart = LightweightCharts.createChart(chartContainer, { width: chartContainer.clientWidth, height: 200, timeScale: { visible: true, secondsVisible: 60 } });
                    const candleSeries = window.btcChart.addCandlestickSeries();
                    candleSeries.setData(data);
                } else {
                    // Update series with new data (shift and push)
                    const series = window.btcChart.series().find(s => s.seriesType === 'Candlestick');
                    if (series) {
                        // We'll just set new data for simplicity
                        series.setData(data);
                    }
                }
            }
            // Update AI signals
            const aiSignals = document.getElementById('ai-signals');
            aiSignals.innerHTML = '';
            // Mock buy/sell signals
            const buySignals = [
                { name: '삼성전자', confidence: 87, expectedProfit: 12.5, entryPrice: 78000 },
                { name: 'LG에너지솔루션', confidence: 82, expectedProfit: 18.3, entryPrice: 420000 }
            ];
            const sellSignals = [
                { name: '현대차', riskLevel: 'High', stopLoss: 180000, targetPrice: 220000 },
                { name: '네이버', riskLevel: 'Medium', stopLoss: 190000, targetPrice: 240000 }
            ];
            buySignals.forEach(signal => {
                aiSignals.appendChild(createSignalCard(signal, 'buy'));
            });
            sellSignals.forEach(signal => {
                aiSignals.appendChild(createSignalCard(signal, 'sell'));
            });
            // Update holdings
            const holdingsStatus = document.getElementById('holdings-status');
            holdingsStatus.innerHTML = '';
            const holdings = accountData.holdings || [];
            if (holdings.length === 0) {
                holdingsStatus.innerHTML = '<p class="text-gray-400 text-center py-8">보유 종목이 없습니다.</p>';
            } else {
                holdings.forEach(holding => {
                    holdingsStatus.appendChild(createHoldingCard(holding));
                });
            }
            // Update AI analysis
            const aiAnalysis = document.getElementById('ai-analysis');
            aiAnalysis.innerHTML = '';
            const analysisData = [
                { title: '시장 강도', value: '82%', description: '강한 상승 모멘텀' },
                { title: '상승 확률', value: '76%', description: '다음 24시간 기준' },
                { title: '변동성', value: '34%', description: '보통 수준' },
                { title: '리스크 점수', value: '28%', description: '낮은 리스크 환경' }
            ];
            analysisData.forEach(data => {
                aiAnalysis.appendChild(createAnalysisGauge(data.title, data.value, data.description));
            });
            // Update strategy performance
            const strategyPerformance = document.getElementById('strategy-performance');
            strategyPerformance.innerHTML = '';
            const performanceData = [
                { title: '누적 수익률', value: '142.8%', subtitle: '연간 수익률', isPositive: true },
                { title: '월간 수익률', value: '18.5%', subtitle: '이번 달 성과', isPositive: true },
                { title: '승률', value: '68.2%', subtitle: '전체 거래 기준', isPositive: true },
                { title: 'MDD', value: '-12.4%', subtitle: '최대 낙폭', isPositive: false }
            ];
            performanceData.forEach(data => {
                strategyPerformance.appendChild(createPerformanceMetric(data.title, data.value, data.subtitle, data.isPositive));
            });
            // Trigger count-up animation
            document.querySelectorAll('.count-up').forEach(el => {
                const target = parseFloat(el.textContent.replace(/[^\\d.-]/g, '')) || 0;
                const duration = 2000;
                const start = parseFloat(el.dataset.start || '0');
                const startTime = performance.now();
                function updateCount(now) {
                    const elapsed = now - startTime;
                    const progress = Math.min(elapsed / duration, 1);
                    const current = start + (target - start) * progress;
                    el.textContent = current.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2
                    });
                    if (progress < 1) {
                        requestAnimationFrame(updateCount);
                    }
                }
                el.dataset.start = start;
                requestAnimationFrame(updateCount);
            });
        }

        // Socket.io event handling
        socket.on('connect', () => {
            console.log('Connected to server');
        });

        socket.on('update', (data) => {
            updateDashboard(data.signals, data.accountData);
        });

        // Theme toggle functionality
        const themeToggleBtn = document.getElementById('theme-toggle');
        const themeIcon = document.getElementById('theme-icon');
        const htmlElement = document.documentElement;

        // On load, check for saved preference or system preference
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            htmlElement.classList.toggle('dark', savedTheme === 'dark');
            updateIcon(savedTheme);
        } else {
            // Respect system preference
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            htmlElement.classList.toggle('dark', prefersDark);
            updateIcon(prefersDark ? 'dark' : 'light');
        }

        function updateIcon(mode) {
            // mode: 'dark' or 'light'
            if (mode === 'dark') {
                themeIcon.innerHTML = '<path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z\"></path>';
            } else {
                themeIcon.innerHTML = '<path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z></path>';
            }
        }

        themeToggleBtn.addEventListener('click', () => {
            const isDark = htmlElement.classList.toggle('dark');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            updateIcon(isDark ? 'dark' : 'light');
        });
    </script>'''

    start, end = second_match.span()
    new_body = body_part[:start] + new_script + body_part[end:]
    content = new_body + after_body

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated index.html with socket.io')
