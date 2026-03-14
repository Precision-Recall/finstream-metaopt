HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADAPTIVE ML // NIFTY50 CONCEPT DRIFT PIPELINE</title>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
    <style>
        :root {{
            --bg: #0d0f14;
            --surface: #161920;
            --surface2: #1e2230;
            --border: rgba(255,255,255,0.07);
            --text: #e8eaf0;
            --muted: #7a7f94;
            --accent: #4f9cf9;
            --green: #3ecf8e;
            --red: #f26d6d;
            --amber: #f0b429;
            --font-mono: 'IBM Plex Mono', monospace;
            --font-sans: 'IBM Plex Sans', sans-serif;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: var(--font-sans);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px 32px;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
        }}
        .header-title {{
            font-family: var(--font-mono);
            color: var(--accent);
            font-size: 1.25rem;
            font-weight: 600;
        }}
        .header-subtitle {{
            color: var(--muted);
            font-size: 0.875rem;
            font-family: var(--font-mono);
        }}
        nav {{
            display: flex;
            gap: 16px;
            margin-bottom: 32px;
            border-bottom: 1px solid var(--border);
            overflow-x: auto;
        }}
        .tab-btn {{
            background: transparent;
            border: none;
            color: var(--muted);
            font-family: var(--font-mono);
            font-size: 0.875rem;
            padding: 12px 16px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            white-space: nowrap;
            transition: all 0.2s;
        }}
        .tab-btn:hover {{ color: var(--text); }}
        .tab-btn.active {{
            color: var(--accent);
            border-bottom-color: var(--accent);
        }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        
        .grid-6 {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
        }}
        .card-title {{
            font-family: var(--font-mono);
            font-size: 0.75rem;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }}
        .card-value {{
            font-size: 2rem;
            font-weight: 600;
            font-family: var(--font-mono);
        }}
        .text-red {{ color: var(--red); }}
        .text-green {{ color: var(--green); }}
        .text-amber {{ color: var(--amber); }}
        .text-accent {{ color: var(--accent); }}
        
        .chart-container {{ position: relative; width: 100%; }}
        .chart-container.h-220 {{ height: 220px; }}
        .chart-container.h-300 {{ height: 300px; }}
        .chart-container.h-340 {{ height: 340px; }}
        .chart-container.h-360 {{ height: 360px; }}
        
        .custom-legend {{
            display: flex;
            gap: 16px;
            margin-bottom: 16px;
            font-family: var(--font-mono);
            font-size: 0.75rem;
            color: var(--muted);
            flex-wrap: wrap;
        }}
        .legend-item {{ display: flex; align-items: center; gap: 8px; }}
        .legend-color {{ width: 12px; height: 12px; border-radius: 2px; }}
        .legend-dashed {{ width: 16px; height: 2px; border-top: 2px dashed var(--amber); margin-top: 5px; }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-family: var(--font-mono);
            font-size: 0.875rem;
            text-align: left;
        }}
        th, td {{
            padding: 12px;
            border-bottom: 1px solid var(--border);
        }}
        th {{ color: var(--muted); font-weight: 500; font-size: 0.75rem; text-transform: uppercase; }}
        .badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge.green {{ background: rgba(62,207,142,0.15); color: var(--green); }}
        .badge.red {{ background: rgba(242,109,109,0.15); color: var(--red); }}
        
        .drift-card {{
            border-left: 4px solid var(--amber);
            margin-bottom: 16px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            border-left-width: 4px;
        }}
        .drift-header {{
            color: var(--amber);
            font-family: var(--font-mono);
            font-size: 0.875rem;
            margin-bottom: 12px;
        }}
        .weight-bars {{ margin-top: 16px; }}
        .weight-row {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
            font-family: var(--font-mono);
            font-size: 0.75rem;
        }}
        .weight-label {{ width: 80px; color: var(--muted); }}
        .weight-bar-bg {{
            flex: 1;
            height: 8px;
            background: var(--surface2);
            border-radius: 4px;
            margin: 0 12px;
            overflow: hidden;
        }}
        .weight-bar-fill {{ height: 100%; border-radius: 4px; }}
        .weight-value {{ width: 60px; text-align: right; }}
        
        .inference-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 24px;
            margin-bottom: 16px;
            border-left-width: 4px;
        }}
        .inference-card.border-accent {{ border-left-color: var(--accent); }}
        .inference-card.border-amber {{ border-left-color: var(--amber); }}
        .inference-card.border-green {{ border-left-color: var(--green); }}
        .inference-title {{
            font-family: var(--font-mono);
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text);
            margin-bottom: 12px;
            text-transform: uppercase;
        }}
        
        .pagination {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 16px;
            font-family: var(--font-mono);
            font-size: 0.875rem;
        }}
        .page-btn {{
            background: var(--surface2);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-family: var(--font-mono);
            transition: all 0.2s;
        }}
        .page-btn:hover:not(:disabled) {{ background: var(--border); }}
        .page-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        
        .flex-between {{ display: flex; justify-content: space-between; align-items: flex-start; }}
        .w-half {{ width: 48%; }}
    </style>
    <script>
        {js_vars}
    </script>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-title">ADAPTIVE_ML // NIFTY50 CONCEPT DRIFT PIPELINE</div>
            <div class="header-subtitle">ADWIN + PSO ENSEMBLE | 2020–2026</div>
        </header>
        
        <nav id="tabs">
            <button class="tab-btn active" data-target="tab-overview">Overview</button>
            <button class="tab-btn" data-target="tab-accuracy">Accuracy</button>
            <button class="tab-btn" data-target="tab-weights">Weights</button>
            <button class="tab-btn" data-target="tab-nifty">NIFTY50</button>
            <button class="tab-btn" data-target="tab-pso">PSO Shifts</button>
            <button class="tab-btn" data-target="tab-drift">Drift Events</button>
            <button class="tab-btn" data-target="tab-raw">Raw Data</button>
            <button class="tab-btn" data-target="tab-inference">Inference</button>
        </nav>
        
        <main>
            <!-- OVERVIEW -->
            <div id="tab-overview" class="tab-content active">
                <div class="grid-6">
                    <div class="card" style="display:flex; flex-direction:column;">
                        <div class="card-title">STATIC ACCURACY</div>
                        <div class="card-value text-red" id="val-static-acc">--</div>
                    </div>
                    <div class="card">
                        <div class="card-title">ADAPTIVE ACCURACY</div>
                        <div class="card-value text-green" id="val-adapt-acc">--</div>
                    </div>
                    <div class="card">
                        <div class="card-title">DELTA</div>
                        <div class="card-value text-green" id="val-delta">--</div>
                    </div>
                    <div class="card">
                        <div class="card-title">DRIFT EVENTS</div>
                        <div class="card-value text-amber" id="val-drifts">--</div>
                    </div>
                    <div class="card">
                        <div class="card-title">DAYS SIMULATED</div>
                        <div class="card-value text-accent" id="val-days">--</div>
                    </div>
                    <div class="card">
                        <div class="card-title">PREDICTIONS</div>
                        <div class="card-value text-accent" id="val-preds">--</div>
                    </div>
                </div>
                
                <div class="grid-2">
                    <div class="card">
                        <div class="card-title" style="margin-bottom:16px;">ROLLING ACCURACY (30D)</div>
                        <div class="chart-container h-220"><canvas id="overview-acc-chart"></canvas></div>
                    </div>
                    <div class="card">
                        <div class="card-title" style="margin-bottom:16px;">ENSEMBLE WEIGHTS</div>
                        <div class="chart-container h-220"><canvas id="overview-weights-chart"></canvas></div>
                    </div>
                </div>
                
                <div class="card" style="overflow-x:auto;">
                    <div class="card-title">DRIFT SUMMARY</div>
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Date</th>
                                <th>Row</th>
                                <th>Context</th>
                                <th>w_old →</th>
                                <th>w_medium →</th>
                                <th>w_recent →</th>
                            </tr>
                        </thead>
                        <tbody id="overview-drift-tbody"></tbody>
                    </table>
                </div>
            </div>
            
            <!-- ACCURACY -->
            <div id="tab-accuracy" class="tab-content">
                <div class="card">
                    <div class="custom-legend">
                        <div class="legend-item">
                            <div class="legend-color" style="background: var(--red);"></div>
                            <span>Static model (frozen weights)</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: var(--green);"></div>
                            <span>Adaptive model (PSO reweighted)</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-dashed"></div>
                            <span>Drift detected</span>
                        </div>
                    </div>
                    <div class="chart-container h-340"><canvas id="accuracy-chart"></canvas></div>
                </div>
            </div>
            
            <!-- WEIGHTS -->
            <div id="tab-weights" class="tab-content">
                <div class="card">
                    <div class="custom-legend">
                        <div class="legend-item">
                            <div class="legend-color" style="background: var(--accent);"></div>
                            <span>Model OLD (2015–17)</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: var(--amber);"></div>
                            <span>Model MEDIUM (2016–18)</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: var(--green);"></div>
                            <span>Model RECENT (2017–19)</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-dashed"></div>
                            <span>Drift detected</span>
                        </div>
                    </div>
                    <div class="chart-container h-340"><canvas id="weights-chart"></canvas></div>
                </div>
            </div>
            
            <!-- NIFTY50 -->
            <div id="tab-nifty" class="tab-content">
                <div class="card">
                    <div class="custom-legend">
                        <div class="legend-item">
                            <div class="legend-color" style="background: var(--text);"></div>
                            <span>NIFTY50 Close Price</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background: rgba(242,109,109,0.15);"></div>
                            <span>COVID-19 Volatility</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-dashed"></div>
                            <span>Drift detected</span>
                        </div>
                    </div>
                    <div class="chart-container h-360"><canvas id="nifty-chart"></canvas></div>
                </div>
            </div>
            
            <!-- PSO SHIFTS -->
            <div id="tab-pso" class="tab-content">
                <div class="card" style="margin-bottom: 24px;">
                    <div class="card-title" style="margin-bottom:16px;">WEIGHT SHIFTS AT DRIFT EVENTS</div>
                    <div class="chart-container h-300"><canvas id="pso-chart"></canvas></div>
                </div>
                <div class="grid-2" style="grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));" id="pso-detail-cards">
                    <!-- Populated by JS -->
                </div>
            </div>
            
            <!-- DRIFT EVENTS -->
            <div id="tab-drift" class="tab-content">
                <div id="drift-events-container"></div>
            </div>
            
            <!-- RAW DATA -->
            <div id="tab-raw" class="tab-content">
                <div class="card" style="overflow-x:auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Prediction</th>
                                <th>Truth</th>
                                <th>Error</th>
                                <th>Probability</th>
                                <th>w_old</th>
                                <th>w_medium</th>
                                <th>w_recent</th>
                            </tr>
                        </thead>
                        <tbody id="raw-tbody"></tbody>
                    </table>
                    <div class="pagination">
                        <button class="page-btn" id="btn-prev">← prev</button>
                        <span id="page-info" style="color:var(--muted);">page 1 of ?</span>
                        <button class="page-btn" id="btn-next">next →</button>
                    </div>
                </div>
            </div>
            
            <!-- INFERENCE -->
            <div id="tab-inference" class="tab-content">
                <div class="inference-card border-accent">
                    <div class="inference-title">CORE FINDING</div>
                    <p style="color:var(--muted);">The adaptive PSO ensemble achieved <span style="color:var(--text); font-weight:500;">57.44%</span> accuracy vs the static baseline of <span style="color:var(--text); font-weight:500;">54.75%</span> — a delta of <span style="color:var(--green); font-weight:500;">+2.69%</span> over 1,525 resolved trading day predictions (Jan 2020–Feb 2026). This represents 41 additional correct market direction calls.</p>
                </div>
                <div class="inference-card border-amber">
                    <div class="inference-title">DRIFT EVENT 1 — AUG 2020</div>
                    <p style="color:var(--muted);">ADWIN detected regime change in August 2020 corresponding to NIFTY50's recovery from COVID-19 crash lows. PSO collapsed w_recent to 0.018 and elevated w_medium to 0.541. Counterintuitive but sound — Model_MEDIUM (2016–18) captured the 2018 correction+recovery cycle, a closer analogue to post-COVID dynamics than the steady 2017–19 bull run embedded in Model_RECENT.</p>
                </div>
                <div class="inference-card border-amber">
                    <div class="inference-title">DRIFT EVENT 2 — JUN 2023</div>
                    <p style="color:var(--muted);">Post rate-hike stabilisation. RBI paused hikes, inflation cooling. PSO rehabilitated w_recent from 0.018 to 0.330, recognising that 2017–19 pre-hike bull conditions were partially re-emerging.</p>
                </div>
                <div class="inference-card border-amber">
                    <div class="inference-title">DRIFT EVENT 3 — JAN 2025</div>
                    <p style="color:var(--muted);">Most dramatic PSO decision: w_old surged to 0.851, placing 85% trust in the model trained on 2015–17. PSO discovered empirically that January 2025 market patterns most closely resembled early bull-market behaviour from that era — a non-obvious finding from pure optimisation on 60 resolved trading days.</p>
                </div>
                <div class="inference-card border-green">
                    <div class="inference-title">LIMITATIONS AND FUTURE WORK</div>
                    <p style="color:var(--muted);">ADWIN delta calibrated to 1.0 due to dataset size (1,525 samples). Standard values (delta=0.002) require >100,000 samples. Future work: larger multi-cycle datasets, sentiment features, multi-objective PSO balancing accuracy and confidence, explainability layer bridging PSO weight decisions to financial rationale.</p>
                    <br><p class="card-title" style="margin-bottom:0; color:var(--text);">Note: accuracy lines use real data from stream_results.csv and static_results.csv</p>
                </div>
            </div>
        </main>
    </div>

    <!-- MAIN DASHBOARD JS -->
    <script>
        // formatting helpers
        const pct = v => (v * 100).toFixed(2) + '%';
        const fp = v => v.toFixed(4);
        const DRIFT_CONTEXTS = [
            "Post-COVID recovery — new bull regime",
            "Post rate-hike cycle stabilisation",
            "2025 volatility — PSO trusted oldest regime"
        ];
        
        // initialize summary
        if(SUMMARY.static_accuracy) {{ // ensure we have data
            document.getElementById('val-static-acc').innerText = pct(SUMMARY.static_accuracy);
            document.getElementById('val-adapt-acc').innerText = pct(SUMMARY.adaptive_accuracy);
            document.getElementById('val-delta').innerText = '+' + pct(SUMMARY.delta);
            document.getElementById('val-drifts').innerText = SUMMARY.drift_count;
            document.getElementById('val-days').innerText = SUMMARY.total_days;
            document.getElementById('val-preds').innerText = SUMMARY.resolved_predictions;
        }}
        
        // initialize overview drift table
        const tbody = document.getElementById('overview-drift-tbody');
        DRIFT_EVENTS.forEach((e, i) => {{
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${{i+1}}</td>
                <td>${{e.date}}</td>
                <td><span class="badge" style="background:var(--surface2)">${{e.row_index}}</span></td>
                <td style="color:var(--text)">${{DRIFT_CONTEXTS[i] || ''}}</td>
                <td>${{fp(e.w_old_before)}} → <b style="color:var(--accent)">${{fp(e.w_old_after)}}</b></td>
                <td>${{fp(e.w_medium_before)}} → <b style="color:var(--amber)">${{fp(e.w_medium_after)}}</b></td>
                <td>${{fp(e.w_recent_before)}} → <b style="color:var(--green)">${{fp(e.w_recent_after)}}</b></td>
            `;
            tbody.appendChild(tr);
        }});
        
        // build drift detail cards for PSO tab
        const psoDetailCards = document.getElementById('pso-detail-cards');
        DRIFT_EVENTS.forEach((e, i) => {{
            const div = document.createElement('div');
            // drift-card adds padding and border
            div.className = 'drift-card';
            div.style.marginBottom = '0';
            div.innerHTML = `
                <div class="drift-header">EVENT ${{i+1}} | ${{e.date}}</div>
                <div class="card-title">${{DRIFT_CONTEXTS[i] || ''}}</div>
                <div class="flex-between" style="margin-top:16px;">
                    <div class="w-half">
                        <div class="card-title">BEFORE (Row ${{e.row_index}})</div>
                        <div class="weight-bars">
                            <div class="weight-row">
                                <span class="weight-label">w_old</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${{e.w_old_before*100}}%; background:var(--accent);"></div></div>
                                <span class="weight-value">${{fp(e.w_old_before)}}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_medium</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${{e.w_medium_before*100}}%; background:var(--amber);"></div></div>
                                <span class="weight-value">${{fp(e.w_medium_before)}}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_recent</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${{e.w_recent_before*100}}%; background:var(--green);"></div></div>
                                <span class="weight-value">${{fp(e.w_recent_before)}}</span>
                            </div>
                        </div>
                    </div>
                    <div class="w-half">
                        <div class="card-title">AFTER</div>
                        <div class="weight-bars">
                            <div class="weight-row">
                                <span class="weight-label">w_old</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${{e.w_old_after*100}}%; background:var(--accent);"></div></div>
                                <span class="weight-value">${{fp(e.w_old_after)}}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_medium</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${{e.w_medium_after*100}}%; background:var(--amber);"></div></div>
                                <span class="weight-value">${{fp(e.w_medium_after)}}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_recent</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${{e.w_recent_after*100}}%; background:var(--green);"></div></div>
                                <span class="weight-value">${{fp(e.w_recent_after)}}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            psoDetailCards.appendChild(div);
        }});
        
        // build drift events tab cards
        const driftEventsContainer = document.getElementById('drift-events-container');
        const driftLongContexts = [
            "ADWIN detected regime change in August 2020 corresponding to NIFTY50's recovery from COVID-19 crash lows. PSO collapsed w_recent to 0.018 and elevated w_medium to 0.541. Counterintuitive but sound — Model_MEDIUM (2016–18) captured the 2018 correction+recovery cycle, a closer analogue to post-COVID dynamics than the steady 2017–19 bull run embedded in Model_RECENT.",
            "Post rate-hike stabilisation. RBI paused hikes, inflation cooling. PSO rehabilitated w_recent from 0.018 to 0.330, recognising that 2017–19 pre-hike bull conditions were partially re-emerging.",
            "Most dramatic PSO decision: w_old surged to 0.851, placing 85% trust in the model trained on 2015–17. PSO discovered empirically that January 2025 market patterns most closely resembled early bull-market behaviour from that era — a non-obvious finding from pure optimisation on 60 resolved trading days."
        ];
        DRIFT_EVENTS.forEach((e, i) => {{
            const div = document.createElement('div');
            div.className = 'drift-card';
            div.innerHTML = `
                <div class="drift-header" style="font-size:1rem;">DRIFT EVENT ${{i+1}} | ${{e.date}} <span class="badge" style="background:var(--surface2); color:var(--text); margin-left:12px;">Row ${{e.row_index}}</span></div>
                <p style="margin-bottom:24px; color:var(--text); font-size:0.875rem;">${{driftLongContexts[i] || ''}}</p>
                <div class="flex-between">
                    <div class="w-half">
                        <div class="card-title">BEFORE DRIFT</div>
                        <div class="weight-bars">
                            <div class="weight-row">
                                <span class="weight-label">w_old</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${{e.w_old_before*100}}%; background:var(--accent);"></div></div>
                                <span class="weight-value">${{fp(e.w_old_before)}}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_medium</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${{e.w_medium_before*100}}%; background:var(--amber);"></div></div>
                                <span class="weight-value">${{fp(e.w_medium_before)}}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_recent</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${{e.w_recent_before*100}}%; background:var(--green);"></div></div>
                                <span class="weight-value">${{fp(e.w_recent_before)}}</span>
                            </div>
                        </div>
                    </div>
                    <div class="w-half">
                        <div class="card-title">AFTER PSO SHIFT</div>
                        <div class="weight-bars">
                            <div class="weight-row">
                                <span class="weight-label">w_old</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${{e.w_old_after*100}}%; background:var(--accent);"></div></div>
                                <span class="weight-value">${{fp(e.w_old_after)}}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_medium</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${{e.w_medium_after*100}}%; background:var(--amber);"></div></div>
                                <span class="weight-value">${{fp(e.w_medium_after)}}</span>
                            </div>
                            <div class="weight-row">
                                <span class="weight-label">w_recent</span>
                                <div class="weight-bar-bg"><div class="weight-bar-fill" style="width:${{e.w_recent_after*100}}%; background:var(--green);"></div></div>
                                <span class="weight-value">${{fp(e.w_recent_after)}}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            driftEventsContainer.appendChild(div);
        }});
        
        // Raw Data table
        const pageSize = 25;
        let currentPage = 1;
        const maxPages = Math.ceil(RAW_TABLE.length / pageSize);
        
        function renderTable() {{
            const tbody = document.getElementById('raw-tbody');
            tbody.innerHTML = '';
            const start = (currentPage - 1) * pageSize;
            const end = start + pageSize;
            const rows = RAW_TABLE.slice(start, end);
            
            rows.forEach(r => {{
                // 1 if UP, 0 if DOWN
                const predBadge = r.prediction === 1 ? '<span class="badge green">UP</span>' : '<span class="badge red">DOWN</span>';
                const truthBadge = r.truth === 1 ? '<span class="badge green">UP</span>' : '<span class="badge red">DOWN</span>';
                const errBadge = r.error === 0 ? '<span class="badge green">CORRECT</span>' : '<span class="badge red">WRONG</span>';
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${{r.date}}</td>
                    <td>${{predBadge}}</td>
                    <td>${{truthBadge}}</td>
                    <td>${{errBadge}}</td>
                    <td>${{fp(r.ensemble_probability)}}</td>
                    <td>${{fp(r.w_old)}}</td>
                    <td>${{fp(r.w_medium)}}</td>
                    <td>${{fp(r.w_recent)}}</td>
                `;
                tbody.appendChild(tr);
            }});
            
            document.getElementById('page-info').innerText = `page ${{currentPage}} of ${{maxPages}} — rows ${{start+1}}–${{Math.min(end, RAW_TABLE.length)}}`;
            document.getElementById('btn-prev').disabled = currentPage === 1;
            document.getElementById('btn-next').disabled = currentPage === maxPages;
        }}
        if(RAW_TABLE.length > 0) renderTable();
        document.getElementById('btn-prev').addEventListener('click', () => {{ if(currentPage > 1) {{ currentPage--; renderTable(); }} }});
        document.getElementById('btn-next').addEventListener('click', () => {{ if(currentPage < maxPages) {{ currentPage++; renderTable(); }} }});

        // CHARTS
        Chart.defaults.color = '#7a7f94';
        Chart.defaults.borderColor = 'rgba(255,255,255,0.04)';
        Chart.defaults.font.family = "'IBM Plex Mono', monospace";
        
        const chartsBuilt = {};
        
        function getDriftAnnotations() {{
            return DRIFT_EVENTS.map(d => {{
                // Find nearest index in DATES
                let minDiff = Infinity;
                let idx = 0;
                let targetTime = new Date(d.date).getTime();
                DATES.forEach((cDate, i) => {{
                    let diff = Math.abs(new Date(cDate).getTime() - targetTime);
                    if (diff < minDiff) {{ minDiff = diff; idx = i; }}
                }});
                return {{ type: 'line', xMin: idx, xMax: idx, borderColor: '#f0b429', borderDash: [4,4], borderWidth: 1 }};
            }});
        }}
        // In Chart.js 4, without annotation plugin, we draw vertical lines manually via plugin
        const driftPlugin = {{
            id: 'driftLines',
            beforeDraw: (chart) => {{
                const ctx = chart.ctx;
                const xAxis = chart.scales.x;
                const yAxis = chart.scales.y;
                
                DRIFT_EVENTS.forEach(d => {{
                    // find index in chart data labels
                    const labels = chart.data.labels;
                    let idx = labels.indexOf(d.date);
                    if (idx === -1) {{
                        let minDiff = Infinity;
                        let targetTime = new Date(d.date).getTime();
                        labels.forEach((lbl, i) => {{
                            let diff = Math.abs(new Date(lbl).getTime() - targetTime);
                            if (diff < minDiff) {{ minDiff = diff; idx = i; }}
                        }});
                    }}
                    
                    if (idx !== -1) {{
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
                    }}
                }});
            }}
        }};

        function buildOverviewCharts() {{
            if (chartsBuilt['overview']) return;
            
            new Chart(document.getElementById('overview-acc-chart'), {{
                type: 'line',
                data: {{
                    labels: DATES,
                    datasets: [
                        {{ label: 'Static', data: ROLLING_STATIC, borderColor: '#f26d6d', borderWidth: 1.5, pointRadius: 0, tension: 0.3 }},
                        {{ label: 'Adaptive', data: ROLLING_ADAPTIVE, borderColor: '#3ecf8e', borderWidth: 1.5, pointRadius: 0, tension: 0.3 }}
                    ]
                }},
                options: {{
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{ min: 0.3, max: 0.8, ticks: {{ callback: function(value) {{ return (value*100).toFixed(0) + '%'; }} }} }},
                        x: {{ ticks: {{ maxTicksLimit: 4 }} }}
                    }}
                }},
                plugins: [driftPlugin]
            }});
            
            new Chart(document.getElementById('overview-weights-chart'), {{
                type: 'line',
                data: {{
                    labels: DATES,
                    datasets: [
                        {{ label: 'w_old', data: W_OLD, borderColor: '#4f9cf9', borderWidth: 1.5, pointRadius: 0, tension: 0, stepped: true }},
                        {{ label: 'w_medium', data: W_MEDIUM, borderColor: '#f0b429', borderWidth: 1.5, pointRadius: 0, tension: 0, stepped: true }},
                        {{ label: 'w_recent', data: W_RECENT, borderColor: '#3ecf8e', borderWidth: 1.5, pointRadius: 0, tension: 0, stepped: true }}
                    ]
                }},
                options: {{
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{ min: 0, max: 1 }},
                        x: {{ ticks: {{ maxTicksLimit: 4 }} }}
                    }}
                }},
                plugins: [driftPlugin]
            }});
            
            chartsBuilt['overview'] = true;
        }}
        
        function buildAccuracyChart() {{
            if (chartsBuilt['accuracy']) return;
            new Chart(document.getElementById('accuracy-chart'), {{
                type: 'line',
                data: {{
                    labels: DATES,
                    datasets: [
                        {{ label: 'Static', data: ROLLING_STATIC, borderColor: '#f26d6d', backgroundColor: 'rgba(242,109,109,0.1)', fill: true, borderWidth: 1.5, pointRadius: 0, tension: 0.3 }},
                        {{ label: 'Adaptive', data: ROLLING_ADAPTIVE, borderColor: '#3ecf8e', backgroundColor: 'rgba(62,207,142,0.1)', fill: true, borderWidth: 1.5, pointRadius: 0, tension: 0.3 }}
                    ]
                }},
                options: {{
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: {{ 
                        legend: {{ display: false }},
                        tooltip: {{ backgroundColor: '#1e2230', titleColor: '#7a7f94', bodyColor: '#e8eaf0', borderColor: 'rgba(255,255,255,0.07)', borderWidth: 1 }}
                    }},
                    scales: {{
                        y: {{ min: 0.3, max: 0.8, ticks: {{ callback: function(value) {{ return (value*100).toFixed(0) + '%'; }} }} }},
                        x: {{ ticks: {{ maxTicksLimit: 8 }} }}
                    }}
                }},
                plugins: [driftPlugin]
            }});
            chartsBuilt['accuracy'] = true;
        }}
        
        function buildWeightsChart() {{
            if (chartsBuilt['weights']) return;
            new Chart(document.getElementById('weights-chart'), {{
                type: 'line',
                data: {{
                    labels: DATES,
                    datasets: [
                        {{ label: 'w_old', data: W_OLD, borderColor: '#4f9cf9', borderWidth: 1.5, pointRadius: 0, tension: 0, stepped: true }},
                        {{ label: 'w_medium', data: W_MEDIUM, borderColor: '#f0b429', borderWidth: 1.5, pointRadius: 0, tension: 0, stepped: true }},
                        {{ label: 'w_recent', data: W_RECENT, borderColor: '#3ecf8e', borderWidth: 1.5, pointRadius: 0, tension: 0, stepped: true }}
                    ]
                }},
                options: {{
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: {{ 
                        legend: {{ display: false }}, 
                        tooltip: {{ backgroundColor: '#1e2230', titleColor: '#7a7f94', bodyColor: '#e8eaf0', borderColor: 'rgba(255,255,255,0.07)', borderWidth: 1 }} 
                    }},
                    scales: {{
                        y: {{ min: 0, max: 1 }},
                        x: {{ ticks: {{ maxTicksLimit: 8 }} }}
                    }}
                }},
                plugins: [driftPlugin]
            }});
            chartsBuilt['weights'] = true;
        }}
        
        function buildNiftyChart() {{
            if (chartsBuilt['nifty']) return;
            
            // For shaded COVID region (Jan-2020 to Sep-2020)
            const covidData = CLOSE_DATES.map((d, i) => {{
                if (d >= '2020-01-01' && d <= '2020-09-30') return Math.max(...CLOSE); // arbitrary high to fill rect
                return null;
            }});

            new Chart(document.getElementById('nifty-chart'), {{
                type: 'line',
                data: {{
                    labels: CLOSE_DATES,
                    datasets: [
                        {{ 
                            label: 'NIFTY50 Close', 
                            data: CLOSE, 
                            borderColor: '#e8eaf0', 
                            borderWidth: 1.5, 
                            pointRadius: 0, 
                            tension: 0.1,
                            zIndex: 2
                        }},
                        {{
                            label: 'COVID-19 Volatility',
                            data: covidData,
                            backgroundColor: 'rgba(242,109,109,0.1)',
                            borderWidth: 0,
                            pointRadius: 0,
                            fill: 'start',
                            zIndex: 1
                        }}
                    ]
                }},
                options: {{
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: {{ 
                        legend: {{ display: false }}, 
                        tooltip: {{ backgroundColor: '#1e2230', titleColor: '#7a7f94', bodyColor: '#e8eaf0', borderColor: 'rgba(255,255,255,0.07)', borderWidth: 1 }} 
                    }},
                    scales: {{
                        y: {{ 
                            ticks: {{ 
                                callback: function(value) {{ return '₹' + value.toLocaleString('en-IN'); }}
                            }}
                        }},
                        x: {{ ticks: {{ maxTicksLimit: 8 }} }}
                    }}
                }},
                // Reuse driftPlugin logic but with close_dates map
                plugins: [{{
                    id: 'driftLinesNifty',
                    beforeDraw: (chart) => {{
                        const ctx = chart.ctx;
                        const xAxis = chart.scales.x;
                        const yAxis = chart.scales.y;
                        
                        DRIFT_EVENTS.forEach(d => {{
                            const labels = chart.data.labels;
                            let idx = labels.indexOf(d.date);
                            if (idx === -1) {{
                                let minDiff = Infinity;
                                let targetTime = new Date(d.date).getTime();
                                labels.forEach((lbl, i) => {{
                                    let diff = Math.abs(new Date(lbl).getTime() - targetTime);
                                    if (diff < minDiff) {{ minDiff = diff; idx = i; }}
                                }}  );
                            }}
                            
                            if (idx !== -1) {{
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
                            }}
                        }});
                    }}
                }}]
            }});
            chartsBuilt['nifty'] = true;
        }}
        
        function buildPsoChart() {{
            if (chartsBuilt['pso']) return;
            // X-axis names
            let psoLabels = ["Aug 2020", "Jun 2023", "Jan 2025"];
            if (DRIFT_EVENTS.length !== 3) {{
                psoLabels = DRIFT_EVENTS.map(d => d.date);
            }}
            
            const datasets = [
                {{ label: 'w_old (before)', data: DRIFT_EVENTS.map(d => d.w_old_before), backgroundColor: 'rgba(79,156,249,0.4)', borderWidth: 0 }},
                {{ label: 'w_old (after)', data: DRIFT_EVENTS.map(d => d.w_old_after), backgroundColor: 'rgba(79,156,249,0.9)', borderWidth: 0 }},
                {{ label: 'w_medium (before)', data: DRIFT_EVENTS.map(d => d.w_medium_before), backgroundColor: 'rgba(240,180,41,0.4)', borderWidth: 0 }},
                {{ label: 'w_medium (after)', data: DRIFT_EVENTS.map(d => d.w_medium_after), backgroundColor: 'rgba(240,180,41,0.9)', borderWidth: 0 }},
                {{ label: 'w_recent (before)', data: DRIFT_EVENTS.map(d => d.w_recent_before), backgroundColor: 'rgba(62,207,142,0.4)', borderWidth: 0 }},
                {{ label: 'w_recent (after)', data: DRIFT_EVENTS.map(d => d.w_recent_after), backgroundColor: 'rgba(62,207,142,0.9)', borderWidth: 0 }},
            ];
            
            new Chart(document.getElementById('pso-chart'), {{
                type: 'bar',
                data: {{ labels: psoLabels, datasets: datasets }},
                options: {{
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: {{ 
                        legend: {{ display: true, position: 'bottom', labels: {{ color: '#7a7f94', font: {{ family: "'IBM Plex Mono', monospace", size: 10 }}, usePointStyle: true, boxWidth: 6 }} }},
                        tooltip: {{ backgroundColor: '#1e2230', titleColor: '#7a7f94', bodyColor: '#e8eaf0', borderColor: 'rgba(255,255,255,0.07)', borderWidth: 1 }}
                    }},
                    scales: {{ y: {{ min: 0, max: 1 }} }}
                }}
            }});
            chartsBuilt['pso'] = true;
        }}
        
        // Tab switching logic
        document.querySelectorAll('.tab-btn').forEach(btn => {{
            btn.addEventListener('click', () => {{
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
            }});
        }});
        
        // build default charts
        buildOverviewCharts();
    </script>
</body>
</html>
"""
