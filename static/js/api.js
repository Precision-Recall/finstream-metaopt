/**
 * ═══════════════════════════════════════════════════════
 * API MODULE - All Backend Data Fetching
 * ═══════════════════════════════════════════════════════
 */

const API = {
    /**
     * Load system configuration
     */
    async loadConfig() {
        try {
            console.log('⚙️  Loading system configuration...');
            const response = await fetch('/api/config');
            
            if (!response.ok) {
                throw new Error(`Config API failed: ${response.status}`);
            }
            
            const config = await response.json();
            console.log('✅ Config loaded:', config);
            return config;
        } catch (error) {
            console.error('❌ Config load failed:', error);
            return null;
        }
    },

    /**
     * Load live mode data
     */
    async loadLiveData() {
        try {
            console.log('📡 Fetching live data...');
            
            const [stateRes, predictionsRes, driftRes, evaluationsRes, modelsRes] = await Promise.all([
                this._fetch('/api/live/state', 'live/state'),
                this._fetch('/api/live/predictions', 'live/predictions'),
                this._fetch('/api/live/drift', 'live/drift'),
                this._fetch('/api/live/evaluations', 'live/evaluations'),
                this.loadModelRegistry()
            ]);

            return {
                state: stateRes,
                predictions: Array.isArray(predictionsRes) ? predictionsRes.reverse() : [],
                drift: Array.isArray(driftRes) ? driftRes : [],
                evaluations: Array.isArray(evaluationsRes) ? evaluationsRes : [],
                models: Array.isArray(modelsRes) ? modelsRes : []
            };
        } catch (error) {
            console.error('❌ Live data fetch failed:', error);
            throw error;
        }
    },

    /**
     * Load simulation mode data
     */
    async loadSimulationData() {
        try {
            console.log('📊 Fetching simulation data...');
            
            const [summaryRes, simulationRes, driftRes] = await Promise.all([
                this._fetch('/api/summary', 'simulation/summary'),
                this._fetch('/api/simulation', 'simulation/data'),
                this._fetch('/api/simulation_drift', 'simulation/drift')
            ]);

            return {
                summary: summaryRes,
                predictions: simulationRes?.adaptive || [],
                drift: Array.isArray(driftRes) ? driftRes : []
            };
        } catch (error) {
            console.error('❌ Simulation data fetch failed:', error);
            throw error;
        }
    },

    /**
     * Load model registry
     */
    async loadModelRegistry() {
        try {
            console.log('🏛️  Loading model registry...');
            const response = await fetch('/api/model_registry');
            
            if (!response.ok) {
                throw new Error(`Model registry API failed: ${response.status}`);
            }
            
            const models = await response.json();
            console.log('✅ Model registry loaded:', models.length, 'models');
            return models;
        } catch (error) {
            console.error('❌ Model registry load failed:', error);
            return [];
        }
    },

    /**
     * Internal fetch helper with logging
     */
    async _fetch(url, label) {
        try {
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`${label}: ${response.status}`);
            }
            
            const data = await response.json();
            console.log(`   ✓ ${label}:`, data);
            return data;
        } catch (error) {
            console.error(`   ✗ ${label}:`, error.message);
            // Return empty list for 404, null for other errors
            return (error.message.includes('404')) ? [] : null;
        }
    }
};

// Export API
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { API };
}
