// formatting helpers
        const pct = v => (v * 100).toFixed(2) + '%';
        const fp = v => v.toFixed(4);
        const DRIFT_CONTEXTS = [
            "Post-COVID recovery - new bull regime",
            "Post rate-hike cycle stabilisation",
            "2025 volatility - PSO trusted oldest regime"
        ];
        
        // initialize summary
        if(SUMMARY.static_accuracy) { // ensure we have data
            document.getElementById('val-static-acc').innerText = pct(SUMMARY.static_accuracy);
            document.getElementById('val-adapt-acc').innerText = pct(SUMMARY.adaptive_accuracy);
            document.getElementById('val-delta').innerText = '+' + pct(SUMMARY.delta);
            document.getElementById('val-drifts').innerText = SUMMARY.drift_count;
            document.getElementById('val-days').innerText = SUMMARY.total_days;
            document.getElementById('val-preds').innerText = SUMMARY.resolved_predictions;
        }
        
        // initialize overview drift table
        const tbody = document.getElementById('overview-drift-tbody');
        DRIFT_EVENTS.forEach((e, i) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${i+1}</td>
                <td>${e.date}</td>
                <td><span class="badge" style="background:var(--surface2)">${e.row_index}</span></td>
                <td style="color:var(--text)">${DRIFT_CONTEXTS[i] || ''}</td>
                <td>${fp(e.w_old_before)} -> <b style="color:var(--accent)">${fp(e.w_old_after)}</b></td>
                <td>${fp(e.w_medium_before)} -> <b style="color:var(--amber)">${fp(e.w_medium_after)}</b></td>
                <td>${fp(e.w_recent_before)} -> <b style="color:var(--green)">${fp(e.w_recent_after)}</b></td>
            `;
            tbody.appendChild(tr);
        });
        
        // build drift detail cards for PSO tab
        const psoDetailCards = document.getElementById('pso-detail-cards');
        DRIFT_EVENTS.forEach((e, i) => {
            const div = document.createElement('div');
            // drift-card adds padding and border
            div.className = 'drift-card';
            div.style.marginBottom = '0';
            div.innerHTML = `
                <div class="drift-header">EVENT ${i+1} | ${e.date}</div>
                <div class="card-title">${DRIFT_CONTEXTS[i] || ''}</div>
                <div class="flex-between" style="margin-top:16px;">
                    <div class="w-half">
                        <div class="card-title">BEFORE (Row ${e.row_index})</div>
                        <div class="weight-bars">
                            <div class="weight-row">
                                <span class="weight-label">w_old</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${e.w_old_before*100}%; background:var(--accent);"></div></div>
                                <span class="weight-value">${fp(e.w_old_before)}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_medium</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${e.w_medium_before*100}%; background:var(--amber);"></div></div>
                                <span class="weight-value">${fp(e.w_medium_before)}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_recent</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${e.w_recent_before*100}%; background:var(--green);"></div></div>
                                <span class="weight-value">${fp(e.w_recent_before)}</span>
                            </div>
                        </div>
                    </div>
                    <div class="w-half">
                        <div class="card-title">AFTER</div>
                        <div class="weight-bars">
                            <div class="weight-row">
                                <span class="weight-label">w_old</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${e.w_old_after*100}%; background:var(--accent);"></div></div>
                                <span class="weight-value">${fp(e.w_old_after)}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_medium</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${e.w_medium_after*100}%; background:var(--amber);"></div></div>
                                <span class="weight-value">${fp(e.w_medium_after)}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_recent</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${e.w_recent_after*100}%; background:var(--green);"></div></div>
                                <span class="weight-value">${fp(e.w_recent_after)}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            psoDetailCards.appendChild(div);
        });
        
        // build drift events tab cards
        const driftEventsContainer = document.getElementById('drift-events-container');
        const driftLongContexts = [
            "ADWIN detected regime change in August 2020 corresponding to NIFTY50's recovery from COVID-19 crash lows. PSO collapsed w_recent to 0.018 and elevated w_medium to 0.541. Counterintuitive but sound - Model_MEDIUM (2016-18) captured the 2018 correction+recovery cycle, a closer analogue to post-COVID dynamics than the steady 2017-19 bull run embedded in Model_RECENT.",
            "Post rate-hike stabilisation. RBI paused hikes, inflation cooling. PSO rehabilitated w_recent from 0.018 to 0.330, recognising that 2017-19 pre-hike bull conditions were partially re-emerging.",
            "Most dramatic PSO decision: w_old surged to 0.851, placing 85% trust in the model trained on 2015-17. PSO discovered empirically that January 2025 market patterns most closely resembled early bull-market behaviour from that era - a non-obvious finding from pure optimisation on 60 resolved trading days."
        ];
        DRIFT_EVENTS.forEach((e, i) => {
            const div = document.createElement('div');
            div.className = 'drift-card';
            div.innerHTML = `
                <div class="drift-header" style="font-size:1rem;">DRIFT EVENT ${i+1} | ${e.date} <span class="badge" style="background:var(--surface2); color:var(--text); margin-left:12px;">Row ${e.row_index}</span></div>
                <p style="margin-bottom:24px; color:var(--text); font-size:0.875rem;">${driftLongContexts[i] || ''}</p>
                <div class="flex-between">
                    <div class="w-half">
                        <div class="card-title">BEFORE DRIFT</div>
                        <div class="weight-bars">
                            <div class="weight-row">
                                <span class="weight-label">w_old</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${e.w_old_before*100}%; background:var(--accent);"></div></div>
                                <span class="weight-value">${fp(e.w_old_before)}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_medium</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${e.w_medium_before*100}%; background:var(--amber);"></div></div>
                                <span class="weight-value">${fp(e.w_medium_before)}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_recent</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${e.w_recent_before*100}%; background:var(--green);"></div></div>
                                <span class="weight-value">${fp(e.w_recent_before)}</span>
                            </div>
                        </div>
                    </div>
                    <div class="w-half">
                        <div class="card-title">AFTER PSO SHIFT</div>
                        <div class="weight-bars">
                            <div class="weight-row">
                                <span class="weight-label">w_old</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${e.w_old_after*100}%; background:var(--accent);"></div></div>
                                <span class="weight-value">${fp(e.w_old_after)}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_medium</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${e.w_medium_after*100}%; background:var(--amber);"></div></div>
                                <span class="weight-value">${fp(e.w_medium_after)}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_recent</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${e.w_recent_after*100}%; background:var(--green);"></div></div>
                                <span class="weight-value">${fp(e.w_recent_after)}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            driftEventsContainer.appendChild(div);
        });
        
        // Raw Data table
        const pageSize = 25;
        let currentPage = 1;
        const maxPages = Math.ceil(RAW_TABLE.length / pageSize);
        
        function renderTable() {
            const tbody = document.getElementById('raw-tbody');
            tbody.innerHTML = '';
            const start = (currentPage - 1) * pageSize;
            const end = start + pageSize;
            const rows = RAW_TABLE.slice(start, end);
            
            rows.forEach(r => {
                // 1 if UP, 0 if DOWN
                const predBadge = r.prediction === 1 ? '<span class="badge green">UP</span>' : '<span class="badge red">DOWN</span>';
                const truthBadge = r.truth === 1 ? '<span class="badge green">UP</span>' : '<span class="badge red">DOWN</span>';
                const errBadge = r.error === 0 ? '<span class="badge green">CORRECT</span>' : '<span class="badge red">WRONG</span>';
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${r.date}</td>
                    <td>${predBadge}</td>
                    <td>${truthBadge}</td>
                    <td>${errBadge}</td>
                    <td>${fp(r.ensemble_probability)}</td>
                    <td>${fp(r.w_old)}</td>
                    <td>${fp(r.w_medium)}</td>
                    <td>${fp(r.w_recent)}</td>
                `;
                tbody.appendChild(tr);
            });
            
            document.getElementById('page-info').innerText = `page ${currentPage} of ${maxPages} - rows ${start+1}-${Math.min(end, RAW_TABLE.length)}`;
            document.getElementById('btn-prev').disabled = currentPage === 1;
            document.getElementById('btn-next').disabled = currentPage === maxPages;
        }
        if(RAW_TABLE.length > 0) renderTable();
        document.getElementById('btn-prev').addEventListener('click', () => { if(currentPage > 1) { currentPage--; renderTable(); } });
        document.getElementById('btn-next').addEventListener('click', () => { if(currentPage < maxPages) { currentPage++; renderTable(); } });

        // CHARTS
        Chart.defaults.color = '#7a7f94';
        Chart.defaults.borderColor = 'rgba(255,255,255,0.04)';
        Chart.defaults.font.family = "'IBM Plex Mono', monospace";
        
        const chartsBuilt = {};
        
        function getDriftAnnotations() {
            return DRIFT_EVENTS.map(d => {
                // Find nearest index in DATES
                let minDiff = Infinity;
                let idx = 0;
                let targetTime = new Date(d.date).getTime();
                DATES.forEach((cDate, i) => {
                    let diff = Math.abs(new Date(cDate).getTime() - targetTime);
                    if (diff < minDiff) { minDiff = diff; idx = i; }
                });
                return { type: 'line', xMin: idx, xMax: idx, borderColor: '#f0b429', borderDash: [4,4], borderWidth: 1 };
            });
        }
        // In Chart.js 4, without annotation plugin, we draw vertical lines manually via plugin
        const driftPlugin = {
            id: 'driftLines',
            beforeDraw: (chart) => {
                const ctx = chart.ctx;
                const xAxis = chart.scales.x;
                const yAxis = chart.scales.y;
                
                DRIFT_EVENTS.forEach(d => {
                    // find index in chart data labels
                    const labels = chart.data.labels;
                    let idx = labels.indexOf(d.date);
                    if (idx === -1) {
                        let minDiff = Infinity;
                        let targetTime = new Date(d.date).getTime();
                        labels.forEach((lbl, i) => {
                            let diff = Math.abs(new Date(lbl).getTime() - targetTime);
                            if (diff < minDiff) { minDiff = diff; idx = i; }
                        });
                    }
                    
                    if (idx !== -1) {
                        const x = xAxis.getPixelForValue(idx);
                        ctx.save();
                        ctx.beginPath();
                        ctx.moveTo(x, yAxis.top);
                        ctx.lineTo(x, yAxis.bottom);
                        ctx.lineWidth = 1;
                        ctx.strokeStyle = '#f0b429';
                        ctx.setLineDash([4, 4]);
                        ctx.stroke();
                        // Optional text annotation
                        ctx.fillStyle = '#f0b429';
                        ctx.font = "10px 'IBM Plex Mono'";
                        ctx.fillText(d.date, x + 4, yAxis.top + 10);
                        ctx.restore();
                    }
                });
            }
        };

        function buildOverviewCharts() {
            if (chartsBuilt['overview']) return;
            
            new Chart(document.getElementById('overview-acc-chart'), {
                type: 'line',
                data: {
                    labels: DATES,
                    datasets: [
                        { label: 'Static', data: ROLLING_STATIC, borderColor: '#f26d6d', borderWidth: 1.5, pointRadius: 0, tension: 0.3 },
                        { label: 'Adaptive', data: ROLLING_ADAPTIVE, borderColor: '#3ecf8e', borderWidth: 1.5, pointRadius: 0, tension: 0.3 }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { min: 0.3, max: 0.8, ticks: { callback: function(value) { return (value*100).toFixed(0) + '%'; } } },
                        x: { ticks: { maxTicksLimit: 4 } }
                    }
                },
                plugins: [driftPlugin]
            });
            
            new Chart(document.getElementById('overview-weights-chart'), {
                type: 'line',
                data: {
                    labels: DATES,
                    datasets: [
                        { label: 'w_old', data: W_OLD, borderColor: '#4f9cf9', borderWidth: 1.5, pointRadius: 0, tension: 0, stepped: true },
                        { label: 'w_medium', data: W_MEDIUM, borderColor: '#f0b429', borderWidth: 1.5, pointRadius: 0, tension: 0, stepped: true },
                        { label: 'w_recent', data: W_RECENT, borderColor: '#3ecf8e', borderWidth: 1.5, pointRadius: 0, tension: 0, stepped: true }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { min: 0, max: 1 },
                        x: { ticks: { maxTicksLimit: 4 } }
                    }
                },
                plugins: [driftPlugin]
            });
            
            chartsBuilt['overview'] = true;
        }
        
        function buildAccuracyChart() {
            if (chartsBuilt['accuracy']) return;
            new Chart(document.getElementById('accuracy-chart'), {
                type: 'line',
                data: {
                    labels: DATES,
                    datasets: [
                        { label: 'Static', data: ROLLING_STATIC, borderColor: '#f26d6d', backgroundColor: 'rgba(242,109,109,0.1)', fill: true, borderWidth: 1.5, pointRadius: 0, tension: 0.3 },
                        { label: 'Adaptive', data: ROLLING_ADAPTIVE, borderColor: '#3ecf8e', backgroundColor: 'rgba(62,207,142,0.1)', fill: true, borderWidth: 1.5, pointRadius: 0, tension: 0.3 }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: { 
                        legend: { display: false },
                        tooltip: { backgroundColor: '#1e2230', titleColor: '#7a7f94', bodyColor: '#e8eaf0', borderColor: 'rgba(255,255,255,0.07)', borderWidth: 1 }
                    },
                    scales: {
                        y: { min: 0.3, max: 0.8, ticks: { callback: function(value) { return (value*100).toFixed(0) + '%'; } } },
                        x: { ticks: { maxTicksLimit: 8 } }
                    }
                },
                plugins: [driftPlugin]
            });
            chartsBuilt['accuracy'] = true;
        }
        
        function buildWeightsChart() {
            if (chartsBuilt['weights']) return;
            new Chart(document.getElementById('weights-chart'), {
                type: 'line',
                data: {
                    labels: DATES,
                    datasets: [
                        { label: 'w_old', data: W_OLD, borderColor: '#4f9cf9', borderWidth: 1.5, pointRadius: 0, tension: 0, stepped: true },
                        { label: 'w_medium', data: W_MEDIUM, borderColor: '#f0b429', borderWidth: 1.5, pointRadius: 0, tension: 0, stepped: true },
                        { label: 'w_recent', data: W_RECENT, borderColor: '#3ecf8e', borderWidth: 1.5, pointRadius: 0, tension: 0, stepped: true }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: { 
                        legend: { display: false }, 
                        tooltip: { backgroundColor: '#1e2230', titleColor: '#7a7f94', bodyColor: '#e8eaf0', borderColor: 'rgba(255,255,255,0.07)', borderWidth: 1 } 
                    },
                    scales: {
                        y: { min: 0, max: 1 },
                        x: { ticks: { maxTicksLimit: 8 } }
                    }
                },
                plugins: [driftPlugin]
            });
            chartsBuilt['weights'] = true;
        }
        
        function buildNiftyChart() {
            if (chartsBuilt['nifty']) return;
            
            // For shaded COVID region (Jan-2020 to Sep-2020)
            const covidData = CLOSE_DATES.map((d, i) => {
                if (d >= '2020-01-01' && d <= '2020-09-30') return Math.max(...CLOSE); // arbitrary high to fill rect
                return null;
            });

            new Chart(document.getElementById('nifty-chart'), {
                type: 'line',
                data: {
                    labels: CLOSE_DATES,
                    datasets: [
                        { 
                            label: 'NIFTY50 Close', 
                            data: CLOSE, 
                            borderColor: '#e8eaf0', 
                            borderWidth: 1.5, 
                            pointRadius: 0, 
                            tension: 0.1,
                            zIndex: 2
                        },
                        {
                            label: 'COVID-19 Volatility',
                            data: covidData,
                            backgroundColor: 'rgba(242,109,109,0.1)',
                            borderWidth: 0,
                            pointRadius: 0,
                            fill: 'start',
                            zIndex: 1
                        }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: { 
                        legend: { display: false }, 
                        tooltip: { backgroundColor: '#1e2230', titleColor: '#7a7f94', bodyColor: '#e8eaf0', borderColor: 'rgba(255,255,255,0.07)', borderWidth: 1 } 
                    },
                    scales: {
                        y: { 
                            ticks: { 
                                callback: function(value) { return 'INR ' + value.toLocaleString('en-IN'); }
                            }
                        },
                        x: { ticks: { maxTicksLimit: 8 } }
                    }
                },
                // Reuse driftPlugin logic but with close_dates map
                plugins: [{
                    id: 'driftLinesNifty',
                    beforeDraw: (chart) => {
                        const ctx = chart.ctx;
                        const xAxis = chart.scales.x;
                        const yAxis = chart.scales.y;
                        
                        DRIFT_EVENTS.forEach(d => {
                            const labels = chart.data.labels;
                            let idx = labels.indexOf(d.date);
                            if (idx === -1) {
                                let minDiff = Infinity;
                                let targetTime = new Date(d.date).getTime();
                                labels.forEach((lbl, i) => {
                                    let diff = Math.abs(new Date(lbl).getTime() - targetTime);
                                    if (diff < minDiff) { minDiff = diff; idx = i; }
                                }  );
                            }
                            
                            if (idx !== -1) {
                                const x = xAxis.getPixelForValue(idx);
                                ctx.save();
                                ctx.beginPath();
                                ctx.moveTo(x, yAxis.top);
                                ctx.lineTo(x, yAxis.bottom);
                                ctx.lineWidth = 1;
                                ctx.strokeStyle = '#f0b429';
                                ctx.setLineDash([4, 4]);
                                ctx.stroke();
                                ctx.fillStyle = '#f0b429';
                                ctx.font = "10px 'IBM Plex Mono'";
                                ctx.fillText(d.date, x + 4, yAxis.top + 10);
                                ctx.restore();
                            }
                        });
                    }
                }]
            });
            chartsBuilt['nifty'] = true;
        }
        
        function buildPsoChart() {
            if (chartsBuilt['pso']) return;
            // X-axis names
            let psoLabels = ["Aug 2020", "Jun 2023", "Jan 2025"];
            if (DRIFT_EVENTS.length !== 3) {
                psoLabels = DRIFT_EVENTS.map(d => d.date);
            }
            
            const datasets = [
                { label: 'w_old (before)', data: DRIFT_EVENTS.map(d => d.w_old_before), backgroundColor: 'rgba(79,156,249,0.4)', borderWidth: 0 },
                { label: 'w_old (after)', data: DRIFT_EVENTS.map(d => d.w_old_after), backgroundColor: 'rgba(79,156,249,0.9)', borderWidth: 0 },
                { label: 'w_medium (before)', data: DRIFT_EVENTS.map(d => d.w_medium_before), backgroundColor: 'rgba(240,180,41,0.4)', borderWidth: 0 },
                { label: 'w_medium (after)', data: DRIFT_EVENTS.map(d => d.w_medium_after), backgroundColor: 'rgba(240,180,41,0.9)', borderWidth: 0 },
                { label: 'w_recent (before)', data: DRIFT_EVENTS.map(d => d.w_recent_before), backgroundColor: 'rgba(62,207,142,0.4)', borderWidth: 0 },
                { label: 'w_recent (after)', data: DRIFT_EVENTS.map(d => d.w_recent_after), backgroundColor: 'rgba(62,207,142,0.9)', borderWidth: 0 },
            ];
            
            new Chart(document.getElementById('pso-chart'), {
                type: 'bar',
                data: { labels: psoLabels, datasets: datasets },
                options: {
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: { 
                        legend: { display: true, position: 'bottom', labels: { color: '#7a7f94', font: { family: "'IBM Plex Mono', monospace", size: 10 }, usePointStyle: true, boxWidth: 6 } },
                        tooltip: { backgroundColor: '#1e2230', titleColor: '#7a7f94', bodyColor: '#e8eaf0', borderColor: 'rgba(255,255,255,0.07)', borderWidth: 1 }
                    },
                    scales: { y: { min: 0, max: 1 } }
                }
            });
            chartsBuilt['pso'] = true;
        }
        
        // Tab switching logic
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                
                btn.classList.add('active');
                const target = btn.getAttribute('data-target');
                document.getElementById(target).classList.add('active');
                
                // trigger charts inside active tab
                if (target === 'tab-overview') buildOverviewCharts();
                if (target === 'tab-accuracy') buildAccuracyChart();
                if (target === 'tab-weights') buildWeightsChart();
                if (target === 'tab-nifty') buildNiftyChart();
                if (target === 'tab-pso') buildPsoChart();
            });
        });
        
        // build default charts
        buildOverviewCharts();
