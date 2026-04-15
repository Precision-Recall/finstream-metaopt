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

/**
 * ═══════════════════════════════════════════════════════
 * FULLSCREEN CHART MODAL FUNCTIONS
 * ═══════════════════════════════════════════════════════
 */

var fullscreenChartInstance = null;
var fullscreenSourceCanvas = null;

/**
 * Open chart in fullscreen mode
 * @param {string} canvasId - ID of the canvas to expand
 * @param {string} chartTitle - Title for the fullscreen modal
 */
function openChartFullscreen(canvasId, chartTitle) {
    const sourceCanvas = document.getElementById(canvasId);
    if (!sourceCanvas) {
        console.warn(`Canvas not found: ${canvasId}`);
        return;
    }
    
    fullscreenSourceCanvas = canvasId;
    const overlay = document.getElementById('chartFullscreenOverlay');
    const title = document.getElementById('fullscreenTitle');
    const fsCanvas = document.getElementById('fullscreenChartCanvas');
    
    // Update title
    title.textContent = chartTitle;
    
    // Show overlay
    overlay.classList.add('active');
    
    // Get source chart instance
    const sourceChartInstance = Renderers.chartInstances[canvasId];
    
    // Clone chart data and create new instance
    setTimeout(() => {
        if (sourceChartInstance) {
            // Create new chart with same config but larger
            const fsCtx = fsCanvas.getContext('2d');
            fullscreenChartInstance = new Chart(fsCtx, {
                type: sourceChartInstance.config.type,
                data: JSON.parse(JSON.stringify(sourceChartInstance.data)),
                options: {
                    ...sourceChartInstance.options,
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        ...sourceChartInstance.options.plugins,
                        legend: {
                            ...sourceChartInstance.options.plugins?.legend,
                            position: 'top',
                            labels: {
                                ...sourceChartInstance.options.plugins?.legend?.labels,
                                boxWidth: 15,
                                padding: 20,
                                font: { size: 14 }
                            }
                        }
                    }
                }
            });
        }
        
        // Adjust canvas size
        fsCanvas.style.width = '100%';
        fsCanvas.style.height = '100%';
        
        // Focus on modal
        overlay.focus();
    }, 100);
}

/**
 * Close fullscreen chart modal
 */
function closeChartFullscreen() {
    const overlay = document.getElementById('chartFullscreenOverlay');
    overlay.classList.remove('active');
    
    // Destroy fullscreen chart instance
    if (fullscreenChartInstance) {
        fullscreenChartInstance.destroy();
        fullscreenChartInstance = null;
    }
    
    fullscreenSourceCanvas = null;
}

/**
 * Export current fullscreen chart as PNG
 */
function exportChart() {
    const fsCanvas = document.getElementById('fullscreenChartCanvas');
    const title = document.getElementById('fullscreenTitle').textContent;
    const timestamp = new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' });
    const filename = `${title.replace(/\s+/g, '_')}_${timestamp}.png`;
    
    const link = document.createElement('a');
    link.href = fsCanvas.toDataURL('image/png');
    link.download = filename;
    link.click();
}

/**
 * Export fullscreen chart as PDF with data
 */
function exportChartPDF() {
    const fsCanvas = document.getElementById('fullscreenChartCanvas');
    const title = document.getElementById('fullscreenTitle').textContent;
    const timestamp = new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' });
    const filename = `${title.replace(/\s+/g, '_')}_${timestamp}.pdf`;
    
    // Get chart image
    const chartImage = fsCanvas.toDataURL('image/png');
    
    // Get state data for info
    const state = getState ? getState() : {};
    const currentDate = new Date().toLocaleString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    
    // Create PDF content
    const element = document.createElement('div');
    element.innerHTML = `
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="text-align: center; color: #333; margin-bottom: 10px;">${title}</h1>
            <p style="text-align: center; color: #666; margin-bottom: 20px;">Exported: ${currentDate}</p>
            <img src="${chartImage}" style="width: 100%; max-width: 800px; margin: 30px auto; display: block; border: 1px solid #ccc; padding: 10px;" />
            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666;">
                <p><strong>Chart Title:</strong> ${title}</p>
                <p><strong>Export Date:</strong> ${currentDate}</p>
                <p style="margin-top: 20px; font-style: italic;">This PDF was automatically generated from the Concept Drift Monitor dashboard.</p>
            </div>
        </div>
    `;
    
    // PDF options
    const opt = {
        margin: 10,
        filename: filename,
        image: { type: 'png', quality: 0.98 },
        html2canvas: { scale: 2, logging: false },
        jsPDF: { orientation: 'portrait', unit: 'mm', format: 'a4' }
    };
    
    // Generate PDF
    html2pdf().set(opt).from(element).save();
}

/**
 * Handle keyboard shortcuts (ESC to close)
 */
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const overlay = document.getElementById('chartFullscreenOverlay');
        if (overlay?.classList.contains('active')) {
            closeChartFullscreen();
        }
    }
});

/**
 * Close modal when clicking outside the content
 */
document.addEventListener('click', (e) => {
    const overlay = document.getElementById('chartFullscreenOverlay');
    if (e.target === overlay && overlay.classList.contains('active')) {
        closeChartFullscreen();
    }
});