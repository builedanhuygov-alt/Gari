import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/style.css', 'r', encoding='utf-8') as f:
    css = f.read()

s_marker = '/* ==========================================================================\n   GARI AgriTech AI Copilot Drawer & FAB'
e_marker = '/* ==========================================================================\n   GARI MOBILE UI REDESIGN — PRODUCTION REFERENCE SPECIFICATION'

start_idx = css.find(s_marker)
end_idx = css.find(e_marker)

if start_idx == -1 or end_idx == -1:
    print(f"Error: Markers not found! start={start_idx}, end={end_idx}")
    sys.exit(1)

copilot_and_motion_css = '''/* ==========================================================================
   GARI AgriTech AI Copilot — Stacking Context, Drawer & Overlay
   ========================================================================== */

/* Prevent page scrolling when Copilot overlay is open */
body.copilot-open {
    overflow: hidden !important;
    touch-action: none !important;
    -webkit-overflow-scrolling: auto !important;
}

/* 1. Backdrop Overlay */
.copilot-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 18, 0.45);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    z-index: 9998;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.copilot-backdrop.open {
    opacity: 1;
    pointer-events: auto;
}

/* 2. Floating Action Button (FAB) */
.copilot-fab {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 900;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(135deg, #087A43, #064D32);
    color: #ffffff;
    border: none;
    padding: 10px 18px;
    border-radius: 9999px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: -0.01em;
    box-shadow: 0 4px 16px rgba(8, 122, 67, 0.35), 0 2px 6px rgba(0, 0, 0, 0.12);
    cursor: pointer;
    transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1),
                box-shadow 0.22s cubic-bezier(0.16, 1, 0.3, 1),
                opacity 0.2s ease;
    animation: gariFabEntrance 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
}
.copilot-fab:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(8, 122, 67, 0.45), 0 3px 8px rgba(0, 0, 0, 0.15);
}
.copilot-fab:active {
    transform: scale(0.96);
}
.copilot-fab.drawer-open {
    opacity: 0;
    pointer-events: none;
    transform: scale(0.85);
}
.copilot-fab .fab-icon {
    font-size: 17px;
    line-height: 1;
}
.copilot-fab .fab-label {
    line-height: 1;
}
.copilot-fab .fab-pulse-ring {
    position: absolute;
    inset: -3px;
    border-radius: 9999px;
    border: 2px solid rgba(8, 122, 67, 0.65);
    pointer-events: none;
    animation: gariFabPulseCue 2.4s ease-out 1s 2;
    opacity: 0;
}

@keyframes gariFabEntrance {
    0% {
        opacity: 0;
        transform: translateY(20px) scale(0.9);
    }
    100% {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

@keyframes gariFabPulseCue {
    0% {
        transform: scale(0.98);
        opacity: 0.85;
    }
    50% {
        transform: scale(1.16);
        opacity: 0;
    }
    100% {
        transform: scale(1.16);
        opacity: 0;
    }
}

/* Responsive FAB for mobile - placed gracefully above mobile bottom nav */
@media (max-width: 1024px) {
    .copilot-fab {
        bottom: calc(76px + env(safe-area-inset-bottom, 0px));
        right: 16px;
        padding: 9px 15px;
        font-size: 12.5px;
        z-index: 950;
    }
}

/* 3. Drawer Component - Floating Panel on Desktop, Dedicated Sheet on Mobile */
.copilot-drawer {
    position: fixed;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--bg-card, #ffffff);
    transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1),
                opacity 0.22s ease;
}

/* Desktop: Floating Window */
@media (min-width: 1025px) {
    .copilot-drawer {
        bottom: 24px;
        right: 24px;
        width: 410px;
        max-width: calc(100vw - 48px);
        height: min(620px, calc(100vh - 48px));
        max-height: calc(100vh - 48px);
        border-radius: 20px;
        border: 1px solid var(--border-color, #E5EBE5);
        box-shadow: 0 16px 44px rgba(0, 0, 0, 0.18), 0 2px 8px rgba(0, 0, 0, 0.08);
        opacity: 0;
        transform: translateY(24px) scale(0.96);
        pointer-events: none;
    }
    .copilot-drawer.open {
        opacity: 1;
        transform: translateY(0) scale(1);
        pointer-events: auto;
    }
}

/* Mobile: Dedicated Full-Height Drawer (100dvh safe) */
@media (max-width: 1024px) {
    .copilot-drawer {
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        width: 100vw;
        height: 100dvh;
        max-height: 100dvh;
        border-radius: 0;
        border: none;
        padding-top: env(safe-area-inset-top, 0px);
        box-shadow: 0 -4px 32px rgba(0, 0, 0, 0.25);
        opacity: 0;
        transform: translateY(100%);
        pointer-events: none;
    }
    .copilot-drawer.open {
        opacity: 1;
        transform: translateY(0);
        pointer-events: auto;
    }
}

/* Header */
.copilot-drawer-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color, #E5EBE5);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--bg-surface, #ffffff);
    flex-shrink: 0;
}
.copilot-header-info {
    flex: 1;
    min-width: 0;
}
.copilot-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-heading, #17231C);
    letter-spacing: -0.01em;
}
.copilot-sub {
    font-size: 11px;
    color: var(--text-muted, #6B7A70);
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.copilot-header-actions {
    display: flex;
    align-items: center;
    gap: 4px;
}
.copilot-header-btn {
    width: 32px;
    height: 32px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    border-radius: 8px;
    font-size: 20px;
    line-height: 1;
    cursor: pointer;
    color: var(--text-muted, #6B7A70);
    transition: background-color 0.15s ease, color 0.15s ease, transform 0.12s ease;
}
.copilot-header-btn:hover {
    background: rgba(0, 0, 0, 0.06);
    color: var(--text-heading, #17231C);
}
.copilot-header-btn:active {
    transform: scale(0.92);
}

/* Context Bar */
.copilot-context-bar {
    padding: 8px 14px;
    background: var(--bg-base, #F5F8F5);
    border-bottom: 1px solid var(--border-color, #E5EBE5);
    display: flex;
    gap: 6px;
    overflow-x: auto;
    font-size: 11px;
    flex-shrink: 0;
    scrollbar-width: none;
}
.copilot-context-bar::-webkit-scrollbar {
    display: none;
}
.copilot-ctx-chip {
    padding: 3px 9px;
    border-radius: 12px;
    background: var(--bg-card, #ffffff);
    border: 1px solid var(--border-color, #E5EBE5);
    white-space: nowrap;
    color: var(--text-muted, #6B7A70);
}
.copilot-ctx-chip strong {
    color: var(--text-heading, #17231C);
}

/* Message Scroll Area */
.copilot-messages {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}
.copilot-msg {
    display: flex;
    flex-direction: column;
    max-width: 88%;
}
.copilot-msg.user {
    align-self: flex-end;
}
.copilot-msg.bot {
    align-self: flex-start;
}
.copilot-bubble {
    padding: 10px 14px;
    border-radius: 12px;
    font-size: 13px;
    line-height: 1.5;
    word-break: break-word;
}
.copilot-msg.user .copilot-bubble {
    background: #087A43;
    color: #ffffff;
    border-bottom-right-radius: 3px;
}
.copilot-msg.bot .copilot-bubble {
    background: var(--bg-surface, #ffffff);
    color: var(--text-main, #17231C);
    border: 1px solid var(--border-color, #E5EBE5);
    border-bottom-left-radius: 3px;
}

/* Quick Chips */
.copilot-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}
.copilot-chip {
    font-size: 11.5px;
    padding: 5px 10px;
    border-radius: 14px;
    border: 1px solid rgba(8, 122, 67, 0.25);
    background: rgba(8, 122, 67, 0.05);
    color: #087A43;
    cursor: pointer;
    transition: background-color 0.15s ease, transform 0.12s ease;
}
.copilot-chip:hover {
    background: rgba(8, 122, 67, 0.12);
    transform: translateY(-1px);
}
.copilot-chip:active {
    transform: scale(0.96);
}

/* Action Draft Cards */
.copilot-action-card {
    margin-top: 10px;
    padding: 12px;
    background: var(--bg-base, #F5F8F5);
    border: 1px dashed #087A43;
    border-radius: 10px;
    font-size: 12px;
}
.copilot-action-title {
    font-weight: 600;
    color: var(--text-heading, #17231C);
    margin-bottom: 4px;
}
.copilot-action-meta {
    color: var(--text-muted, #6B7A70);
    font-size: 11px;
    margin-bottom: 8px;
}

/* Input Area (Keyboard-Safe & Pinned) */
.copilot-input-area {
    padding: 10px 14px calc(12px + env(safe-area-inset-bottom, 0px)) 14px;
    border-top: 1px solid var(--border-color, #E5EBE5);
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-surface, #ffffff);
    flex-shrink: 0;
}
.copilot-input-area input {
    flex: 1;
    min-width: 0;
    padding: 9px 12px;
    border: 1px solid var(--border-color, #E5EBE5);
    border-radius: 8px;
    font-size: 13px;
    background: var(--bg-card, #ffffff);
    color: var(--text-main, #17231C);
    outline: none;
    transition: border-color 0.15s ease;
}
.copilot-input-area input:focus {
    border-color: #087A43;
    box-shadow: 0 0 0 2px rgba(8, 122, 67, 0.15);
}
.copilot-input-area button {
    flex-shrink: 0;
    padding: 9px 14px;
    border-radius: 8px;
    background: #087A43;
    color: #fff;
    border: none;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: filter 0.15s ease, transform 0.1s ease;
}
.copilot-input-area button:hover {
    filter: brightness(1.06);
}
.copilot-input-area button:active {
    transform: scale(0.96);
}


/* ==========================================================================
   GARI PREMIUM MOTION SYSTEM
   Lightweight, GPU-accelerated (transform & opacity), zero external dependencies
   ========================================================================== */

/* Motion Variables */
:root {
    --gari-ease-out: cubic-bezier(0.16, 1, 0.3, 1);
    --gari-ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
    --gari-dur-fast: 160ms;
    --gari-dur-normal: 260ms;
    --gari-dur-slow: 380ms;
}

/* Core Entrance Keyframes */
@keyframes gariFadeUp {
    0% {
        opacity: 0;
        transform: translateY(12px);
    }
    100% {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes gariScaleIn {
    0% {
        opacity: 0;
        transform: scale(0.95);
    }
    100% {
        opacity: 1;
        transform: scale(1);
    }
}

@keyframes gariScanBeam {
    0% {
        top: 0%;
        opacity: 0.3;
    }
    50% {
        opacity: 1;
    }
    100% {
        top: 100%;
        opacity: 0.3;
    }
}

@keyframes gariPulseSoft {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.6;
    }
}

@keyframes gariSpin {
    to {
        transform: rotate(360deg);
    }
}

/* 1. Page and Section Staggered Entrance */
.hero-banner-v2 {
    animation: gariFadeUp var(--gari-dur-slow) var(--gari-ease-out) both;
}

.quick-card {
    animation: gariFadeUp var(--gari-dur-normal) var(--gari-ease-out) both;
    transition: transform var(--gari-dur-fast) var(--gari-ease-out),
                box-shadow var(--gari-dur-fast) var(--gari-ease-out),
                background-color var(--gari-dur-fast) ease;
}
.quick-card:nth-child(1) { animation-delay: 30ms; }
.quick-card:nth-child(2) { animation-delay: 60ms; }
.quick-card:nth-child(3) { animation-delay: 90ms; }
.quick-card:nth-child(4) { animation-delay: 120ms; }
.quick-card:nth-child(5) { animation-delay: 150ms; }
.quick-card:nth-child(6) { animation-delay: 180ms; }

.card-v2 {
    animation: gariFadeUp var(--gari-dur-slow) var(--gari-ease-out) 100ms both;
    transition: transform var(--gari-dur-fast) var(--gari-ease-out),
                box-shadow var(--gari-dur-fast) var(--gari-ease-out);
}

.farm-cards-scroll {
    animation: gariFadeUp var(--gari-dur-slow) var(--gari-ease-out) 160ms both;
}

.pro-upgrade-banner-v2 {
    animation: gariFadeUp var(--gari-dur-slow) var(--gari-ease-out) 220ms both;
    transition: transform var(--gari-dur-fast) var(--gari-ease-out),
                box-shadow var(--gari-dur-fast) var(--gari-ease-out);
}

/* 2. Interactive Card Micro-interactions (Hover elevation & Touch tap feedback) */
.quick-card:hover,
.farm-card-v2:hover,
.card-v2:hover {
    transform: translateY(-2px);
}

.quick-card:active,
.farm-card-v2:active {
    transform: scale(0.97) translateY(0);
}

.farm-card-v2 {
    transition: transform var(--gari-dur-fast) var(--gari-ease-out),
                box-shadow var(--gari-dur-fast) var(--gari-ease-out);
}

/* 3. Button Micro-interactions & Loading State */
.btn-v2-primary,
.hero-cta-btn,
.btn-primary,
.btn-v2-secondary,
.btn-v2-outline,
.btn-diag-action {
    transition: transform var(--gari-dur-fast) var(--gari-ease-out),
                box-shadow var(--gari-dur-fast) var(--gari-ease-out),
                filter var(--gari-dur-fast) ease;
}
.btn-v2-primary:hover,
.hero-cta-btn:hover,
.btn-primary:hover,
.btn-diag-action:hover {
    transform: translateY(-1px);
    filter: brightness(1.05);
}
.btn-v2-primary:active,
.hero-cta-btn:active,
.btn-primary:active,
.btn-v2-secondary:active,
.btn-v2-outline:active,
.btn-diag-action:active {
    transform: scale(0.97);
}

/* 4. Diagnosis Scan Beam & Image Preview */
.dropzone-preview-wrap,
#dropzonePreviewView {
    animation: gariScaleIn var(--gari-dur-normal) var(--gari-ease-out) both;
}

.diag-scan-beam {
    display: none;
    position: absolute;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, transparent, #22c55e, #10b981, transparent);
    box-shadow: 0 0 14px #22c55e;
    pointer-events: none;
    z-index: 10;
}
.diag-scan-beam.scanning {
    display: block;
    animation: gariScanBeam 1.8s ease-in-out infinite;
}

/* Modal animation */
.modal-backdrop.show .modal-box,
.modal-backdrop.show .modal-box-diag {
    animation: gariScaleIn 0.28s cubic-bezier(0.16, 1, 0.3, 1) both;
}

/* 5. Mobile Bottom Navigation Transitions */
.bottom-nav-item {
    transition: transform var(--gari-dur-fast) var(--gari-ease-out),
                color var(--gari-dur-fast) ease;
}
.bottom-nav-item:active {
    transform: scale(0.92);
}
.bottom-nav-item.active .bottom-nav-icon {
    transform: scale(1.08);
    transition: transform var(--gari-dur-fast) var(--gari-ease-out);
}
.bottom-nav-scan-btn .scan-btn-inner {
    transition: transform var(--gari-dur-fast) var(--gari-ease-out),
                box-shadow var(--gari-dur-fast) var(--gari-ease-out);
}
.bottom-nav-scan-btn:active .scan-btn-inner {
    transform: scale(0.94);
}

/* 6. Accessibility: Full prefers-reduced-motion override */
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.001ms !important;
        scroll-behavior: auto !important;
    }
    .copilot-backdrop,
    .copilot-drawer,
    .copilot-fab {
        transition: none !important;
    }
}

'''

new_css = css[:start_idx] + copilot_and_motion_css + css[end_idx:]

with open('frontend2/style.css', 'w', encoding='utf-8') as f:
    f.write(new_css)

print('Successfully updated frontend2/style.css with Copilot overlay & Motion System!')
