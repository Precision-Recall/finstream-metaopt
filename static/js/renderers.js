/**
 * ═══════════════════════════════════════════════════════
 * RENDERERS MODULE - UI & Chart Rendering
 * ═══════════════════════════════════════════════════════
 */

const Renderers = {
    chartInstances: {},

    /**
     * Render entire UI from store state
     */
    renderFromState(state = getState()) {
        console.log(`🎨 Rendering UI (Mode: ${state.mode}, Tab: ${state.activeTab})...`);
        
        // 1. Mode Container visibility (Live vs Simulation containers)
        const liveContainer = document.getElementById('liveContainer');
        if (state.mode === 'live') {
            if (liveContainer) liveContainer.style.display = 'block';
            document.getElementById('modeToggleLive')?.classList.add('active');
            document.getElementById('modeToggleSimulation')?.classList.remove('active');
        } else {
            if (liveContainer) liveContainer.style.display = 'none';
            document.getElementById('modeToggleLive')?.classList.remove('active');
            document.getElementById('modeToggleSimulation')?.classList.add('active');
        }

        // 2. Overview sub-container visibility (Exclusive to Overview tab)
        const liveOverview = document.getElementById('liveOverview');
        const simOverview = document.getElementById('simOverview');
        if (state.mode === 'live') {
            if (liveOverview) liveOverview.style.display = 'block';
            if (simOverview) simOverview.style.display = 'none';
        } else {
            if (liveOverview) liveOverview.style.display = 'none';
            if (simOverview) simOverview.style.display = 'block';
        }

        // 3. Tab Visibility & Styling (Reactive to state.activeTab & state.mode)
        this._updateTabsUI(state.activeTab, state.mode);

        // 4. Delegate specific rendering
        if (state.mode === 'live') {
            this.renderLiveMode(state);
        } else {
            this.renderSimulationMode(state);
        }
    },

    /**
     * Render live mode UI
     */
    renderLiveMode(state = getState()) {
        console.log('📊 Rendering LIVE mode...');
        const live = state.live;

        // Update stat cards
        if (live.predictions && live.predictions.length > 0) {
            const latest = live.predictions[live.predictions.length - 1];
            this._updateElement('todayPred', latest.prediction === 1 ? 'UP' : 'DOWN');
            this._updateElement('todayProb', `Confidence: ${(latest.ensemble_probability * 100).toFixed(2)}%`);
            this._updateElement('activeFeatureCount', latest.active_feature_count || '—');
            this._updateElement('lastEvaluated', Utils.formatDate(latest.date) || '—');
            this._updateElement('driftCountLive', live.drift?.length || 0);
            
            // Overview Cards (Live)
            let avgBrierScore = 0;
            const resolvedPredictions = live.predictions.filter(p => p.resolved);
            
            if (resolvedPredictions.length > 0) {
                // Consistent Brier-based Score Calculation (skip if missing)
                const totalScore = resolvedPredictions.reduce((sum, p) => {
                    const prob = p.ensemble_probability !== undefined ? p.ensemble_probability : (p.probability !== undefined ? p.probability : null);
                    if (prob !== null && p.truth !== undefined) {
                        return sum + (1 - Math.pow(prob - p.truth, 2));
                    }
                    return sum;
                }, 0);
                
                // Only count those that were actually scored
                const scoredCount = resolvedPredictions.filter(p => {
                    const prob = p.ensemble_probability !== undefined ? p.ensemble_probability : (p.probability !== undefined ? p.probability : null);
                    return prob !== null && p.truth !== undefined;
                }).length;

                avgBrierScore = scoredCount > 0 ? (totalScore / scoredCount) * 100 : 0;
                
                this._updateElement('liveOverviewBrier', `${avgBrierScore.toFixed(1)}%`);
            } else {
                this._updateElement('liveOverviewBrier', 'Pending');
            }
            
            this._updateElement('liveOverviewFeatures', latest.active_feature_count || '—');
            this._updateElement('liveOverviewDrift', live.drift?.length || 0);

            // Update weights
            const weights = [
                { name: 'XGBoost', value: latest.w_old || 0.333 },
                { name: 'LightGBM', value: latest.w_medium || 0.333 },
                { name: 'ExtraTrees', value: latest.w_recent || 0.333 }
            ];
            this._populateWeights(weights);
            
            // Update features
            this._populateLiveFeatures(latest.active_features);
        } else {
            this._updateElement('todayPred', '—');
            this._updateElement('liveOverviewAcc', '0%');
        }

        // Update tables
        this._populateLiveTable(live);
        this._populateLiveDriftTable(live);
        this._populateDriftEventsTab(live.drift || []);

        // Create charts
        this.createBrierScoreChart('brierCanvas', live.predictions);
        this.createBrierScoreChart('liveOverviewBrierCanvas', live.predictions);
        this.createWeightsChart('weightsCanvas', live.predictions);

        // Model Registry (should show in both modes if data exists)
        this._populateModelRegistry(live.models || []);

        // Update timestamp
        this._updateElement('lastUpdated', `Updated: ${new Date().toLocaleTimeString()}`);
    },

    /**
     * Render simulation mode UI
     */
    renderSimulationMode(state = getState()) {
        console.log('📊 Rendering SIMULATION mode...');
        const sim = state.simulation;

        if (sim.isLoading && !sim.summary) {
            console.log('⏳ Simulation data loading...');
            this._updateElement('lastUpdated', 'Loading simulation data...');
            return;
        }

        if (!sim.summary) {
            console.warn('⚠️  No simulation summary available');
            this._updateElement('lastUpdated', 'Waiting for simulation data...');
            return;
        }

        // Update summary stats
        const s = sim.summary;
        console.log('📋 Simulation summary from /api/summary:', s);

        const staticBrier  = s?.static_brier_score  != null ? s.static_brier_score  : null;
        const adaptiveBrier = s?.adaptive_brier_score != null ? s.adaptive_brier_score : null;
        const delta = s?.delta != null ? s.delta : null;

        const metrics = {
            'overviewStaticBrier':   staticBrier  != null ? `${(staticBrier  * 100).toFixed(2)}%` : 'N/A',
            'overviewAdaptiveBrier': adaptiveBrier != null ? `${(adaptiveBrier * 100).toFixed(2)}%` : 'N/A',
            'overviewBrierDelta':    delta         != null ? `${(delta > 0 ? '+' : '')}${(delta * 100).toFixed(2)}%` : 'N/A',
            'overviewDriftCount': s?.drift_count || 0,
            'overviewDays': s?.total_days || 0,
            'overviewPreds': s?.resolved_predictions || 0
        };

        Object.entries(metrics).forEach(([id, val]) => this._updateElement(id, val));

        // Create charts
        this.createBrierScoreChart('overviewBrierCanvas', sim.predictions);
        this.createBrierScoreChart('brierCanvas', sim.predictions); // Main Brier Tab
        
        this.createWeightsChart('overviewWeightsCanvas', sim.predictions);
        this.createWeightsChart('weightsCanvas', sim.predictions); // Main Weights Tab
        
        // Simulation-specific charts
        if (sim.predictions && sim.predictions.length > 0) {
            this.createNiftyChart('niftyCanvas', sim.predictions);
        }
        if (sim.drift && sim.drift.length > 0) {
            this.drawHeatmap('heatmapCanvas', sim.drift);
        }

        // Update drift tables
        this._populateDriftEventsTab(sim.drift); // MAIN Drift Tab

        // Also show model registry in sim mode if we have live models
        if (state.live.models && state.live.models.length > 0) {
             this._populateModelRegistry(state.live.models);
        }

        // Update timestamp
        this._updateElement('lastUpdated', `Updated: ${new Date().toLocaleTimeString()}`);
    },

    /**
     * Create Brier Score chart
     */
    createBrierScoreChart(canvasId, predictions = []) {
        const ctx = document.getElementById(canvasId)?.getContext('2d');
        if (!ctx || !predictions || predictions.length === 0) return;

        if (this.chartInstances[canvasId]) {
            this.chartInstances[canvasId].destroy();
        }

        // In simulation mode, all data points are usually "resolved" (past data)
        const isSimulation = getState().mode === 'simulation';
        const resolved = isSimulation ? predictions : predictions.filter(p => p.resolved);
        
        let labels, scoreData, label;
        let rollingLabelText = 'Rolling Brier Score (30d)';
        
        if (resolved.length === 0) {
            // If no resolved data, but we have predictions, show placeholders
            labels = predictions.map(p => Utils.formatDate(p.date, 'short'));
            scoreData = predictions.map(p => null); // Don't plot anything
            label = 'Waiting for Resolution';
            rollingLabelText = 'Brier Score (Pending)';
        } else if (resolved.length < 30) {
            labels = resolved.map(p => Utils.formatDate(p.date, 'short'));
            scoreData = [];
            resolved.forEach(p => {
                const prob = p.ensemble_probability !== undefined ? p.ensemble_probability : (p.probability !== undefined ? p.probability : null);
                if (prob !== null && p.truth !== undefined) {
                    scoreData.push((1 - Math.pow(prob - p.truth, 2)) * 100);
                }
            });
            // Match labels to scoreData if some were skipped
            if (scoreData.length < labels.length) {
                const validPoints = resolved.filter(p => {
                    const prob = p.ensemble_probability !== undefined ? p.ensemble_probability : (p.probability !== undefined ? p.probability : null);
                    return prob !== null && p.truth !== undefined;
                });
                labels = validPoints.map(p => Utils.formatDate(p.date, 'short'));
            }

            label = 'Daily Brier Score (%)';
            rollingLabelText = 'Rolling Brier Score (1d)';
        } else {
            const grouped = Utils.groupDataByMonthYear(resolved);
            labels = grouped.map(g => g.label);
            scoreData = grouped.map(g => g.avgBrierScore);
            label = 'Monthly Avg Brier Score (%)';
        }

        // Update label element if it exists
        const labelId = canvasId === 'liveOverviewBrierCanvas' ? 'liveOverviewAccLabel' : canvasId + 'Label';
        this._updateElement(labelId, rollingLabelText);

        this.chartInstances[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: label,
                    data: scoreData,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: predictions.length < 30 ? 4 : 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { min: 0, max: 100, ticks: { color: '#8892a8' }, grid: { color: 'rgba(31, 45, 71, 0.5)' } },
                    x: { ticks: { color: '#8892a8', maxRotation: 45, minRotation: 45 }, grid: { display: false } }
                }
            }
        });
    },

    /**
     * Create weights chart
     */
    createWeightsChart(canvasId, predictions = []) {
        const ctx = document.getElementById(canvasId)?.getContext('2d');
        if (!ctx || !predictions || predictions.length === 0) return;

        if (this.chartInstances[canvasId]) {
            this.chartInstances[canvasId].destroy();
        }

        const isSmall = predictions.length < 30;
        const grouped = isSmall
            ? predictions.map(p => ({ 
                label: Utils.formatDate(p.date, 'short'), 
                avgWeightOld: p.w_old, 
                avgWeightMedium: p.w_medium, 
                avgWeightRecent: p.w_recent,
                avgWeightLogistic: p.w_logistic 
            }))
            : Utils.groupDataByMonthYear(predictions);

        const labels = grouped.map(g => g.label);

        this.chartInstances[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'XGBoost',
                        data: grouped.map(g => (g.avgWeightOld || 0) * 100),
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: isSmall ? 3 : 0
                    },
                    {
                        label: 'LightGBM',
                        data: grouped.map(g => (g.avgWeightMedium || 0) * 100),
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: isSmall ? 3 : 0
                    },
                    {
                        label: 'ExtraTrees',
                        data: grouped.map(g => (g.avgWeightRecent || 0) * 100),
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: isSmall ? 3 : 0
                    },
                    {
                        label: 'Linear Regression',
                        data: grouped.map(g => (g.avgWeightLogistic || 0) * 100),
                        borderColor: '#8b5cf6',
                        backgroundColor: 'rgba(139, 92, 246, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: isSmall ? 3 : 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom', labels: { color: '#8892a8', boxWidth: 12 } } },
                scales: {
                    y: { min: 0, max: 100, ticks: { color: '#8892a8' }, grid: { color: 'rgba(31, 45, 71, 0.5)' } },
                    x: { ticks: { color: '#8892a8', display: labels.length < 15 }, grid: { display: false } }
                }
            }
        });
    },

    /**
     * Create NIFTY50 Price chart
     */
    createNiftyChart(canvasId, predictions = []) {
        const canvas = document.getElementById(canvasId);
        const ctx = canvas?.getContext('2d');
        if (!ctx || !predictions || predictions.length === 0) return;

        if (this.chartInstances[canvasId]) {
            this.chartInstances[canvasId].destroy();
        }

        const data = predictions.slice(-200); 
        const labels = data.map(d => Utils.formatDate(d.date, 'short'));
        const prices = data.map(d => d.price || d.close || d.ensemble_probability * 10000 + 10000); // Fallback for demo
        
        this.chartInstances[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'NIFTY50 Simulated Price',
                    data: prices,
                    borderColor: '#3b82f6',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.1,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { ticks: { color: '#8892a8' }, grid: { color: 'rgba(31, 45, 71, 0.5)' } },
                    x: { ticks: { color: '#8892a8', display: false }, grid: { display: false } }
                }
            }
        });
    },

    /**
     * Create MHO Council (PSO, GA, GWO) fitness chart
     */
    /**
     * Draw MHO Council Decisions Heatmap using Canvas 2D API
     * Grid: 3 rows (PSO, GA, GWO) x 5 columns (Last 5 Drift Events)
     */
    drawHeatmap(canvasId, driftEvents = []) {
        const canvas = document.getElementById(canvasId);
        const ctx = canvas?.getContext('2d');
        if (!ctx || !driftEvents || driftEvents.length === 0) return;

        // Take last 5 events
        const recent = driftEvents.slice(-5);
        if (recent.length === 0) return;

        const algos = [
            { key: 'cw_pso', label: 'PSO' },
            { key: 'cw_ga', label: 'GA' },
            { key: 'cw_gwo', label: 'GWO' }
        ];

        // Canvas setup
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        const w = rect.width || 800;
        const h = 180;

        canvas.width = w * dpr;
        canvas.height = h * dpr;
        ctx.scale(dpr, dpr);

        // Layout constants
        const leftMargin = 70;
        const topMargin = 40;
        const bottomMargin = 45;
        const rightMargin = 30;
        
        // Calculate max grid size to center it
        const maxGridW = Math.min(w - leftMargin - rightMargin, 650);
        const startX = leftMargin + (w - leftMargin - rightMargin - maxGridW) / 2;
        
        const gridW = maxGridW;
        const gridH = h - topMargin - bottomMargin;
        const cellW = gridW / recent.length;
        const cellH = gridH / algos.length;

        // Clear and set background
        ctx.fillStyle = '#111827'; // Darker theme match
        ctx.fillRect(0, 0, w, h);

        // Draw Cells
        algos.forEach((algo, rowIdx) => {
            // Row Label
            ctx.fillStyle = '#9ca3af';
            ctx.font = '12px Inter, sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(algo.label, startX - 15, topMargin + rowIdx * cellH + cellH / 2 + 5);

            recent.forEach((event, colIdx) => {
                const val = event[algo.key] || 0.333;
                const x = startX + colIdx * cellW;
                const y = topMargin + rowIdx * cellH;

                // Cell Background (Interpolated)
                ctx.fillStyle = this._getHeatmapColor(val);
                ctx.fillRect(x + 1, y + 1, cellW - 2, cellH - 2);

                // Weight Text
                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 11px Inter, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(val.toFixed(3), x + cellW / 2, y + cellH / 2 + 4);

                // Column Labels (only on first row)
                if (rowIdx === 0) {
                    ctx.fillStyle = '#9ca3af';
                    ctx.font = '10px Inter, sans-serif';
                    ctx.textAlign = 'center';
                    
                    const dateObj = new Date(event.date);
                    const dateStr = dateObj.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
                    ctx.fillText(dateStr, x + cellW / 2, topMargin - 12);
                }
            });
        });

        // Color Legend at bottom
        const legendW = 160;
        const legendH = 8;
        const legendX = (w - legendW) / 2;
        const legendY = h - 25;

        const gradient = ctx.createLinearGradient(legendX, 0, legendX + legendW, 0);
        gradient.addColorStop(0, '#1e2230');  // Low
        gradient.addColorStop(0.5, '#2E75B6'); // Mid
        gradient.addColorStop(1, '#3ecf8e');  // High
        
        ctx.fillStyle = gradient;
        ctx.fillRect(legendX, legendY, legendW, legendH);

        // Legend Labels
        ctx.fillStyle = '#6b7280';
        ctx.font = '10px Inter, sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText('0.318', legendX - 8, legendY + 8);
        ctx.textAlign = 'center';
        ctx.fillText('0.333', legendX + legendW/2, legendY + 20); // Mid label
        ctx.textAlign = 'left';
        ctx.fillText('0.344', legendX + legendW + 8, legendY + 8);
    },

    /**
     * Color interpolation for heatmap weights
     * Low (<=0.318) -> #1e2230
     * Mid (0.333)   -> #2E75B6
     * High (>=0.344) -> #3ecf8e
     */
    _getHeatmapColor(val) {
        if (val <= 0.318) return '#1e2230';
        if (val >= 0.344) return '#3ecf8e';

        if (val < 0.333) {
            const p = (val - 0.318) / (0.333 - 0.318);
            return this._lerpColor('#1e2230', '#2E75B6', p);
        } else {
            const p = (val - 0.333) / (0.344 - 0.333);
            return this._lerpColor('#2E75B6', '#3ecf8e', p);
        }
    },

    /**
     * Interpolate between two hex colors
     */
    _lerpColor(a, b, amount) {
        const ah = parseInt(a.replace(/#/g, ''), 16),
            ar = ah >> 16, ag = ah >> 8 & 0xff, ab = ah & 0xff,
            bh = parseInt(b.replace(/#/g, ''), 16),
            br = bh >> 16, bg = bh >> 8 & 0xff, bb = bh & 0xff,
            rr = ar + amount * (br - ar),
            rg = ag + amount * (bg - ag),
            rb = ab + amount * (bb - ab);

        return '#' + ((1 << 24) + (Math.round(rr) << 16) + (Math.round(rg) << 8) + Math.round(rb)).toString(16).slice(1);
    },

    // ─────────────────────────────────────────────────────
    // Private helpers
    // ─────────────────────────────────────────────────────

    _updateElement(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    },

    _updateTabsUI(activeTabName, currentMode = 'live') {
        const tabs = document.querySelectorAll('[data-tab]');
        
        tabs.forEach(tab => {
            const modes = tab.getAttribute('data-modes')?.split(',') || [];
            const isVisible = modes.includes(currentMode);
            const tabName = tab.getAttribute('data-tab');
            
            tab.style.display = isVisible ? 'inline-block' : 'none';

            if (tabName === activeTabName) {
                tab.classList.toggle('active', isVisible);
            } else {
                tab.classList.remove('active');
            }
        });

        // Show/hide sections
        document.querySelectorAll('.tab-section').forEach(section => {
            if (section.id === activeTabName) {
                section.style.display = 'block';
            } else {
                section.style.display = 'none';
            }
        });
    },

    _populateWeights(weights) {
        const container = document.getElementById('liveWeights');
        if (!container) return;

        container.innerHTML = weights.map(w => `
            <div style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; font-size: 0.875rem; margin-bottom: 4px;">
                    <span>${w.name}</span>
                    <span style="font-family: monospace; font-weight: 600;">${(w.value * 100).toFixed(1)}%</span>
                </div>
                <div style="background-color: var(--bg-tertiary); height: 16px; border-radius: 3px; overflow: hidden;">
                    <div style="background: linear-gradient(90deg, #3b82f6, #10b981); width: ${w.value * 100}%; height: 100%;"></div>
                </div>
            </div>
        `).join('');
    },

    _populateLiveFeatures(features) {
        const container = document.getElementById('liveFeatures');
        if (!container) return;

        const featureArray = Array.isArray(features) ? features : [];
        container.innerHTML = featureArray.length === 0 
            ? '<p style="color: var(--text-dim);">No features selected</p>'
            : featureArray.map(f => `<span style="display: inline-block; padding: 4px 8px; margin: 3px 3px 3px 0; background-color: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: 3px; font-size: 0.8rem;">${f}</span>`).join('');
    },

    _populateLiveTable(live) {
        const tbody = document.querySelector('#liveTable tbody');
        if (!tbody || !live.predictions) return;

        const recent = live.predictions.slice(-10).reverse();
        const today = new Date().toDateString();
        
        tbody.innerHTML = recent.map(r => {
            const predDate = new Date(r.date).toDateString();
            const isResolved = predDate !== today;
            let statusIcon = '—';
            
            if (isResolved) {
                statusIcon = r.error === 0 ? '✅' : '❌';
            }
            
            return `
                <tr>
                    <td>${Utils.formatDate(r.date)}</td>
                    <td><span class="badge ${r.prediction === 1 ? 'badge-green' : 'badge-red'}">${r.prediction === 1 ? 'UP' : 'DOWN'}</span></td>
                    <td>${(r.ensemble_probability * 100).toFixed(1)}%</td>
                    <td>${statusIcon}</td>
                </tr>
            `;
        }).join('');
    },

    _populateLiveDriftTable(live) {
        const tbody = document.querySelector('#liveDriftTable tbody');
        if (!tbody) return;

        if (!live.drift || live.drift.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-dim); padding: 40px 0;">No drift events</td></tr>';
            return;
        }

        const recent = live.drift.slice(-5).reverse();
        tbody.innerHTML = recent.map(d => `
            <tr>
                <td>${Utils.formatDate(d.date)}</td>
                <td>${d.row_index || '—'}</td>
                <td style="font-size: 0.75rem;">${Utils.truncate(d.active_features_before)}</td>
                <td style="font-size: 0.75rem;">${Utils.truncate(d.active_features_after)}</td>
            </tr>
        `).join('');
    },


    _populateSimDriftPreview(sim) {
        const tbody = document.querySelector('#simDriftTable tbody');
        if (!tbody || !sim.drift) return;

        const recent = sim.drift.slice(-5).reverse();
        if (recent.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-dim); padding: 20px 0;">No drift detected</td></tr>';
            return;
        }

        tbody.innerHTML = recent.map(d => {
            // Calculate Logistic model shift as a measure of recent impact
            const shift = ((d.w_logistic_after || 0) - (d.w_logistic_before || 0)) * 100;
            return `
                <tr>
                    <td>${Utils.formatDate(d.date, 'short')}</td>
                    <td>${d.row_index}</td>
                    <td style="font-size: 0.75rem;">PSO:${d.fit_pso?.toFixed(2)} GA:${d.fit_ga?.toFixed(2)} GWO:${d.fit_gwo?.toFixed(2)}</td>
                    <td>${(shift >= 0 ? '+' : '')}${shift.toFixed(1)}%</td>
                </tr>
            `;
        }).join('');
    },

    _populateModelRegistry(models) {
        const container = document.getElementById('modelCardsContainer');
        if (!container) return;

        if (!models || models.length === 0) {
            container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-dim);">No models registered</div>';
            return;
        }

        container.innerHTML = models.map(m => {
            const name = m.model_name || m.id || 'Unknown Model';
            const status = m.status || 'active';
            const acc = m.val_brier_score || m.val_accuracy || m.brier_score || m.accuracy || 0;
            const period = m.train_period || 'Unknown period';
            const trainedAt = m.trained_at ? Utils.formatDate(m.trained_at) : 'Date Unknown';

            return `
                <div class="stat-card" style="border-left: 4px solid var(--accent-primary);">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-weight: 600;">${name}</span>
                        <span class="badge ${status === 'active' ? 'badge-green' : ''}">${status}</span>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.85rem;">
                        <div>Validation Brier: <strong>${(acc * 100).toFixed(1)}%</strong></div>
                        <div style="color: var(--text-dim); margin-top: 4px;">Train Period: ${period}</div>
                        <div style="color: var(--text-dim);">Trained on: ${trainedAt}</div>
                    </div>
                </div>
            `;
        }).join('');

        // Render comparison chart
        this._renderModelBrierChart(models);
    },

    _populateDriftEventsTab(driftData) {
        const container = document.getElementById('driftEventsContainer');
        if (!container) return;

        if (!driftData || driftData.length === 0) {
            container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-dim);">No drift events recorded</div>';
            return;
        }

        const isSimulation = getState().mode === 'simulation';
        const recent = [...driftData].reverse();

        container.innerHTML = recent.map(d => `
            <div class="stat-card" style="margin-bottom: 15px; border-left: 4px solid var(--accent-secondary);">
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <span style="font-weight: 600; color: var(--text-primary);">${Utils.formatDate(d.date)}</span>
                    <span class="badge badge-accent">Row: ${d.row_index || '—'}</span>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; font-size: 0.85rem;">
                    <div>
                        <div style="color: var(--text-dim); margin-bottom: 4px;">${isSimulation ? 'Council Fitness (P/G/W)' : 'Features Before'}</div>
                        <div style="font-family: monospace;">
                            ${isSimulation 
                                ? `${d.fit_pso?.toFixed(2)} / ${d.fit_ga?.toFixed(2)} / ${d.fit_gwo?.toFixed(2)}` 
                                : Utils.truncate(d.active_features_before)}
                        </div>
                    </div>
                    <div>
                        <div style="color: var(--text-dim); margin-bottom: 4px;">${isSimulation ? 'Recent Model Shift' : 'Features After'}</div>
                        <div style="font-family: monospace; color: var(--accent-secondary);">
                            ${isSimulation ? `${((d.w_recent_after - (d.w_recent_before || 0)) * 100).toFixed(2)}%` : Utils.truncate(d.active_features_after)}
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
    },

    _renderModelBrierChart(models) {
        const canvasId = 'modelBrierCanvas';
        const ctx = document.getElementById(canvasId)?.getContext('2d');
        if (!ctx || !models || models.length === 0) return;

        if (this.chartInstances[canvasId]) {
            this.chartInstances[canvasId].destroy();
        }

        const labels = models.map(m => m.model_name || m.id || 'Unknown');
        const data = models.map(m => (m.val_brier_score || m.val_accuracy || m.brier_score || m.accuracy || 0) * 100);

        this.chartInstances[canvasId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Validation Brier Score (%)',
                    data: data,
                    backgroundColor: [
                        'rgba(59, 130, 246, 0.6)', 
                        'rgba(245, 158, 11, 0.6)', 
                        'rgba(16, 185, 129, 0.6)',
                        'rgba(139, 92, 246, 0.6)'
                    ],
                    borderColor: [
                        '#3b82f6', 
                        '#f59e0b', 
                        '#10b981',
                        '#8b5cf6'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => `Brier Score: ${context.parsed.y.toFixed(1)}%`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { color: '#8892a8' },
                        grid: { color: 'rgba(31, 45, 71, 0.5)' }
                    },
                    x: {
                        ticks: { color: '#8892a8' },
                        grid: { display: false }
                    }
                }
            }
        });
    }
};

// Export renderers
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Renderers };
}
