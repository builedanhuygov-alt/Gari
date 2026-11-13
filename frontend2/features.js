/**
 * GARI Centralized Feature Availability Configuration
 * 
 * Controls module availability across all web and mobile views.
 * Disabled modules are gracefully hidden from navigation and
 * direct routes show official under-development notices.
 */
(function () {
    const GARI_FEATURES = {
        farms: false,          // Temporarily disabled: Under development
        community: false,      // Temporarily disabled: Under development
        hostConsole: true,     // Dedicated Host Admin console
        diagnosis: true,       // Core Leaf Intelligence
        assistant: true,       // Contextual AI Copilot
        expert: true,          // Agricultural Expert Network
        organization: true,    // Enterprise & Cooperatives
        pricing: true,         // Subscriptions & Entitlements
    };

    if (typeof window !== 'undefined') {
        window.GARI_FEATURES = GARI_FEATURES;
    }
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = GARI_FEATURES;
    }
})();
