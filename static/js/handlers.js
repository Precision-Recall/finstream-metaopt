/**
 * ═══════════════════════════════════════════════════════
 * HANDLERS MODULE - Event Listeners & Interactions
 * ═══════════════════════════════════════════════════════
 */

const Handlers = {
    /**
     * Initialize all event handlers
     */
    init() {
        console.log('🎮 Initializing event handlers...');
        
        this.setupModeToggle();
        this.setupTabHandlers();
        this.setupRefreshButton();
        this.setupDriftPagination();
        
        console.log('✅ Event handlers ready');
    },

    /**
     * Mode toggle handlers (LIVE / SIMULATION)
     */
    setupModeToggle() {
        const liveModeBtn = document.getElementById('modeToggleLive');
        const simModeBtn = document.getElementById('modeToggleSimulation');

        if (liveModeBtn) {
            liveModeBtn.addEventListener('click', () => {
                console.log('👆 LIVE button clicked');
                DataLoader.switchMode('live');
            });
        }

        if (simModeBtn) {
            simModeBtn.addEventListener('click', () => {
                console.log('👆 SIMULATION button clicked');
                DataLoader.switchMode('simulation');
            });
        }
    },

    /**
     * Tab click handlers - Cache only, no API calls
     */
    setupTabHandlers() {
        const tabs = document.querySelectorAll('[data-tab]');
        
        tabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                const tabName = tab.getAttribute('data-tab');
                
                console.log(`📑 Tab clicked: ${tabName}`);
                
                // Dispatch tab change - let Renderers handle the rest
                dispatch({ type: 'SET_TAB', payload: tabName });
            });
        });
    },

    /**
     * Refresh button (manual refresh for live mode)
     */
    setupRefreshButton() {
        const refreshBtn = document.getElementById('liveRefreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                console.log('🔄 Manual refresh triggered');
                refreshBtn.textContent = 'Refreshing...';
                refreshBtn.disabled = true;
                
                try {
                    await DataLoader.loadLiveMode();
                } catch (error) {
                    console.error('❌ Refresh failed:', error);
                } finally {
                    refreshBtn.textContent = 'Refresh Now';
                    refreshBtn.disabled = false;
                }
            });
        }
    },

    /**
     * Drift events pagination
     */
    setupDriftPagination() {
        const prevBtn = document.getElementById('driftPrevBtn');
        const nextBtn = document.getElementById('driftNextBtn');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                console.log('⬅️  Previous page clicked');
                // Pagination logic here
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                console.log('➡️  Next page clicked');
                // Pagination logic here
            });
        }
    }
};

// Export handlers
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Handlers };
}
