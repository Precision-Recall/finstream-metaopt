/**
 * ═══════════════════════════════════════════════════════
 * REDUX STORE MODULE
 * ═══════════════════════════════════════════════════════
 * Single source of truth for application state
 */

const store = {
    state: {
        mode: 'live', // 'live' | 'simulation'
        
        live: {
            predictions: [],
            drift: [],
            state: null,
            lastUpdated: null,
            isLoading: false,
            error: null
        },
        
        simulation: {
            predictions: [],
            drift: [],
            summary: null,
            lastUpdated: null,
            isLoading: false,
            error: null
        },
        
        config: null,
        modelRegistry: null,
        activeTab: 'overview' // Default tab
    },
    
    listeners: []
};

/**
 * Pure reducer function - all state updates go through here
 */
function reducer(state, action) {
    switch (action.type) {
        case 'SET_MODE':
            return { ...state, mode: action.payload };

        case 'SET_TAB':
            return { ...state, activeTab: action.payload };
        
        case 'SET_LIVE_DATA':
            return {
                ...state,
                live: {
                    ...state.live,
                    ...action.payload,
                    lastUpdated: Date.now()
                }
            };
        
        case 'SET_SIMULATION_DATA':
            return {
                ...state,
                simulation: {
                    ...state.simulation,
                    ...action.payload,
                    lastUpdated: Date.now()
                }
            };
        
        case 'SET_CONFIG':
            return { ...state, config: action.payload };
        
        case 'SET_MODEL_REGISTRY':
            return { ...state, modelRegistry: action.payload };
        
        case 'SET_LIVE_LOADING':
            return {
                ...state,
                live: { ...state.live, isLoading: action.payload }
            };
        
        case 'SET_SIMULATION_LOADING':
            return {
                ...state,
                simulation: { ...state.simulation, isLoading: action.payload }
            };
        
        case 'SET_LIVE_ERROR':
            return {
                ...state,
                live: { ...state.live, error: action.payload }
            };
        
        case 'SET_SIMULATION_ERROR':
            return {
                ...state,
                simulation: { ...state.simulation, error: action.payload }
            };
        
        default:
            return state;
    }
}

/**
 * Dispatch an action to update state
 */
function dispatch(action) {
    const oldState = store.state;
    store.state = reducer(store.state, action);
    
    console.log(`📤 Action: ${action.type}`);
    
    // Notify all subscribers
    store.listeners.forEach(listener => {
        try {
            listener(store.state);
        } catch (error) {
            console.error('❌ Subscriber error:', error);
        }
    });
}

/**
 * Subscribe to state changes
 */
function subscribe(listener) {
    store.listeners.push(listener);
    
    return () => {
        store.listeners = store.listeners.filter(fn => fn !== listener);
    };
}

/**
 * Get current state
 */
function getState() {
    return store.state;
}

// Export store functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { store, dispatch, subscribe, getState, reducer };
}
