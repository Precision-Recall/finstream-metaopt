/**
 * ═══════════════════════════════════════════════════════
 * UTILITIES MODULE - Helper Functions
 * ═══════════════════════════════════════════════════════
 */

const Utils = {
    /**
     * Format date for display
     */
    formatDate(dateStr, formatType = 'full') {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        
        if (formatType === 'monthYear') {
            return date.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' });
        }

        return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) + ' ' + 
               date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    },

    /**
     * Group daily data into Month-Year buckets
     */
    groupDataByMonthYear(data) {
        if (!data || data.length === 0) return [];

        const grouped = {};
        
        data.forEach(item => {
            const date = new Date(item.date);
            const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
            const label = this.formatDate(item.date, 'monthYear');

            if (!grouped[key]) {
                grouped[key] = {
                    label: label,
                    accuracies: [],
                    w_old: [],
                    w_medium: [],
                    w_recent: []
                };
            }

            // Brier-based Score (1 - (prob - item.truth)^2)
            const prob = item.ensemble_probability !== undefined ? item.ensemble_probability : (item.probability !== undefined ? item.probability : null);
            if (prob !== null && item.truth !== undefined) {
                grouped[key].accuracies.push(1 - Math.pow(prob - item.truth, 2));
            }
            if (item.w_old !== undefined) grouped[key].w_old.push(item.w_old);
            if (item.w_medium !== undefined) grouped[key].w_medium.push(item.w_medium);
            if (item.w_recent !== undefined) grouped[key].w_recent.push(item.w_recent);
        });

        return Object.keys(grouped).sort().map(key => {
            const g = grouped[key];
            const avg = (arr) => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
            
            return {
                label: g.label,
                avgBrierScore: avg(g.accuracies) * 100,
                avgWeightOld: avg(g.w_old),
                avgWeightMedium: avg(g.w_medium),
                avgWeightRecent: avg(g.w_recent)
            };
        });
    },

    /**
     * Analyze data characteristics to select optimal chart type
     */
    analyzeDataCharacteristics(data, fieldName = 'value') {
        if (!data || data.length === 0) {
            return { type: 'line', reason: 'empty_data' };
        }

        const values = data.map(d => {
            if (typeof d === 'number') return d;
            if (typeof d === 'object' && fieldName in d) return d[fieldName];
            return 0;
        }).filter(v => v !== null && v !== undefined);

        if (values.length === 0) return { type: 'line', reason: 'no_numeric_data' };

        // Calculate statistics
        const min = Math.min(...values);
        const max = Math.max(...values);
        const range = max - min;
        const mean = values.reduce((a, b) => a + b) / values.length;
        const variance = values.reduce((sq, n) => sq + Math.pow(n - mean, 2), 0) / values.length;
        const stdDev = Math.sqrt(variance);
        const cv = stdDev / mean;
        const uniqueValues = new Set(values).size;
        const dataLength = values.length;

        // Trend detection
        let trend = 0;
        if (dataLength >= 2) {
            for (let i = 1; i < dataLength; i++) {
                trend += Math.sign(values[i] - values[i - 1]);
            }
            trend = trend / (dataLength - 1);
        }

        const characteristics = {
            min, max, range, mean, stdDev, cv, uniqueValues, dataLength, trend,
            isMonotonic: Math.abs(trend) > 0.7,
            isVolatile: cv > 0.3,
            hasOutliers: Math.max(...values.map(v => Math.abs(v - mean) / (stdDev || 1))) > 3,
            isSmooth: cv < 0.15,
            dataPointsPerCategory: dataLength <= 12 ? 'few' : dataLength <= 50 ? 'moderate' : 'many'
        };

        // Decision tree for chart type
        let selectedType = 'line';
        let reason = 'default';

        if (characteristics.dataPointsPerCategory === 'few' && uniqueValues <= 5) {
            selectedType = 'bar';
            reason = 'categorical_few_categories';
        } else if (characteristics.isSmooth && characteristics.isMonotonic) {
            selectedType = 'line';
            reason = 'smooth_monotonic_trend';
        } else if (characteristics.isVolatile && dataLength <= 30) {
            selectedType = 'line';
            reason = 'volatile_with_points';
        } else if (range < 0.1 && dataLength > 20) {
            selectedType = 'area';
            reason = 'tight_range_many_points';
        } else if (dataLength <= 6) {
            selectedType = 'bar';
            reason = 'very_few_datapoints';
        }

        return {
            type: selectedType,
            reason,
            characteristics
        };
    },

    /**
     * Truncate text for display
     */
    truncate(text, maxLength = 30) {
        if (!text) return '—';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }
};

// Export utilities
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Utils };
}
