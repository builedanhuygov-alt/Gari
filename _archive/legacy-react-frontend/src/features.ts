/**
 * GARI Centralized Feature Availability Configuration (React)
 */
export const GARI_FEATURES = {
  farms: false,       // Temporarily disabled per product roadmap
  community: false,   // Temporarily disabled per product roadmap
  hostConsole: true,  // Dedicated Host Admin console
  diagnosis: true,    // Core Leaf Intelligence
  assistant: true,    // Contextual AI Copilot
  expert: true,       // Agricultural Expert Network
  organization: true, // Enterprise & Cooperatives
  pricing: true,      // Subscriptions & Entitlements
} as const;
