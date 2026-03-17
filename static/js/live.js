/**
 * ---------------------------------------------------------------
 * MAIN ENTRY POINT - Concept Drift Monitor
 * ---------------------------------------------------------------
 * 
 * MODULAR ARCHITECTURE:
 * +- store.js         ? Redux state management (dispatch, subscribe, getState)
 * +- api.js           ? Backend API communication (/api/*)
 * +- firebase.js      ? Real-time listeners (Firestore integration pending)
 * +- loaders.js       ? Data orchestration with mode guards
 * +- renderers.js     ? All UI & chart rendering from state
 * +- handlers.js      ? Event listeners (all grouped here)
 * +- utils.js         ? Helper functions (pure utilities)
 * +- live.js          ? This file - minimal entry point
 * 
 * DATA FLOW:
 * User Action ? Handler (handlers.js) 
 *   ? DataLoader method (loaders.js) 
 *     ? API/Firebase fetch (api.js, firebase.js)
 *       ? dispatch action (store.js)
 *         ? Reducer updates state
 *           ? Subscribers notified
 *             ? Renderers update UI from new state (renderers.js)
 * 
 * KEY DESIGN PRINCIPLES:
 * � Single responsibility - each module has one clear purpose
 * � No circular dependencies - strict layering (UI ? Loader ? API ? Store)
 * � Redux subscription pattern - UI renders from state, never direct API calls
 * � Mode guards prevent race conditions (live ? simulation switching)
 * � Firebase integration ready - TODO items marked in firebase.js
 * ---------------------------------------------------------------
 */

// ---------------------------------------------------------------
// APPLICATION INITIALIZATION
// ---------------------------------------------------------------

/**
 * Main initialization function - called when DOM is loaded
 * 
 * Orchestrates:
 * 1. Firebase real-time listeners (with placeholder for actual SDK)
 * 2. Redux subscriber - re-render UI whenever state changes
 * 3. Event handler registration (mode toggles, tabs, refresh, pagination)
 * 4. Initial data load for live mode
 * 5. Connection status monitoring
 */
async function initializeDashboard() {
    console.log('?? Initializing Concept Drift Monitor...');
    try {
        // 1. Initialize Firebase (real-time connection)
        console.log('?? Initializing Firebase...');
        await Firebase.init();
        
        // 2. Subscribe to state changes
        // Whenever dispatch() is called, this callback fires with new state
        // This is the reactive pattern - UI always mirrors current state
        subscribe((state) => {
            console.log('?? State updated - re-rendering UI (mode:', state.mode + ')');
            Renderers.renderFromState(state);
        });
        
        // 3. Register all event listeners
        // This connects UI events ? handlers ? data loaders ? store updates
        console.log('? Registering event handlers...');
        Handlers.init();
        
        // 4. Load initial data (live mode)
        // After DataLoader.loadLiveMode() completes:
        //   ? Fetches data from backend (/api/live/*)
        //   ? Dispatches SET_LIVE_DATA action
        //   ? Reducer updates state.live
        //   ? Subscriber callback fires
        //   ? Renderers re-render UI with new data
        console.log('?? Loading initial data...');
        await DataLoader.loadLiveMode();
        
        console.log('? Dashboard ready!');
    } catch (error) {
        console.error('? Initialization failed:', error);
    }
}

// ---------------------------------------------------------------
// ENTRY POINT
// ---------------------------------------------------------------

// Initialize when DOM is fully ready
document.addEventListener('DOMContentLoaded', initializeDashboard);

// ---------------------------------------------------------------
// DEBUG API
// ---------------------------------------------------------------

/**
 * Expose key functions for debugging in browser console
 * Usage:
 *   window.APP.getState()        - Check current state
 *   window.APP.dispatch({...})   - Manually dispatch actions
 *   window.APP.subscribe(fn)     - Add state listener
 *   window.APP.DataLoader.*      - Trigger data loads
 *   window.APP.Firebase.*        - Check Firebase status
 *   window.APP.Renderers.*       - Manually trigger renders
 */
window.APP = {
    // State management
    getState,
    dispatch,
    subscribe,
    
    // Data loading
    DataLoader,
    API,
    
    // Real-time connection
    Firebase,
    
    // UI rendering
    Renderers,
    
    // Utilities
    Utils: {
        formatDate,
        groupDataByMonthYear,
        analyzeDataCharacteristics,
        truncate
    }
};

console.log('?? Tip: Use window.APP.getState() to inspect application state in console');
