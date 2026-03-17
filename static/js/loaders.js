/**
 * ═══════════════════════════════════════════════════════
 * DATA LOADER MODULE - Orchestrates Data Loading
 * ═══════════════════════════════════════════════════════
 */

const DataLoader = {
    /**
     * Load config and cache it
     */
    async ensureConfig() {
        const state = getState();
        if (state.config) {
            console.log('✓ Config already cached');
            return state.config;
        }
        
        const config = await API.loadConfig();
        if (config) {
            dispatch({ type: 'SET_CONFIG', payload: config });
        }
        return config;
    },

    /**
     * Load live data with mode guards
     */
    async loadLiveMode() {
        const state = getState();
        
        // Guard: Only in live mode
        if (state.mode !== 'live') {
            console.log('⚠️  Not in live mode, skipping load');
            return;
        }
        
        // Guard: Prevent duplicate loads
        if (state.live.isLoading) {
            console.log('⚠️  Already loading live data');
            return;
        }

        dispatch({ type: 'SET_LIVE_LOADING', payload: true });

        try {
            const config = await this.ensureConfig();
            const data = await API.loadLiveData();

            // Re-check mode (might have changed during fetch)
            const currentState = getState();
            if (currentState.mode !== 'live') {
                console.log('⚠️  Mode changed during fetch, discarding data');
                return;
            }

            // Dispatch data
            dispatch({
                type: 'SET_LIVE_DATA',
                payload: {
                    state: data.state,
                    predictions: data.predictions,
                    drift: data.drift,
                    evaluations: data.evaluations,
                    models: data.models,
                    error: null
                }
            });

            Firebase.setConnectionStatus(true);
            console.log('✅ Live data loaded');
        } catch (error) {
            console.error('❌ Live load failed:', error);
            dispatch({ type: 'SET_LIVE_ERROR', payload: error.message });
            Firebase.setConnectionStatus(false);
        } finally {
            dispatch({ type: 'SET_LIVE_LOADING', payload: false });
        }
    },

    /**
     * Load simulation data with mode guards
     */
    async loadSimulationMode() {
        const state = getState();
        
        // Guard: Only in simulation mode
        if (state.mode !== 'simulation') {
            console.log('⚠️  Not in simulation mode, skipping load');
            return;
        }
        
        // Guard: Prevent duplicate loads
        if (state.simulation.isLoading) {
            console.log('⚠️  Already loading simulation data');
            return;
        }

        dispatch({ type: 'SET_SIMULATION_LOADING', payload: true });

        try {
            const config = await this.ensureConfig();
            const [data, models] = await Promise.all([
                API.loadSimulationData(),
                API.loadModelRegistry()
            ]);

            // Re-check mode (might have changed during fetch)
            const currentState = getState();
            if (currentState.mode !== 'simulation') {
                console.log('⚠️  Mode changed during fetch, discarding data');
                return;
            }

            // Dispatch data
            dispatch({
                type: 'SET_SIMULATION_DATA',
                payload: {
                    summary: data.summary,
                    predictions: data.predictions,
                    drift: data.drift,
                    error: null
                }
            });

            // Model Registry is shared or live-specific? 
            // The simulation summary might have its own models, but the UI uses live.models mostly.
            // Let's store them in live.models for now as a fallback for the registry tab.
            dispatch({
                type: 'SET_LIVE_DATA',
                payload: { models: models }
            });

            Firebase.setConnectionStatus(true);
            console.log('✅ Simulation data loaded');
        } catch (error) {
            console.error('❌ Simulation load failed:', error);
            dispatch({ type: 'SET_SIMULATION_ERROR', payload: error.message });
            Firebase.setConnectionStatus(false);
        } finally {
            dispatch({ type: 'SET_SIMULATION_LOADING', payload: false });
        }
    },

    /**
     * Switch mode and load appropriate data
     */
    async switchMode(mode) {
        const state = getState();

        if (state.mode === mode) {
            console.log(`ℹ️  Already in ${mode.toUpperCase()} mode`);
            return;
        }

        console.log(`🔄 Switching to ${mode.toUpperCase()}...`);
        dispatch({ type: 'SET_MODE', payload: mode });

        // Set default tab for the mode
        const defaultTab = mode === 'live' ? 'overview' : 'simulation-data';
        dispatch({ type: 'SET_TAB', payload: defaultTab });

        // Clean up previous mode
        Firebase.unsubscribeAll();

        // Load new mode data
        if (mode === 'live') {
            await this.loadLiveMode();
        } else {
            await this.loadSimulationMode();
        }
    }
};

// Export DataLoader
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DataLoader };
}
