import os

css_to_append = """
/* ==========================================================================
   GARI MOBILE UI REDESIGN — PRODUCTION REFERENCE SPECIFICATION
   Colors: Primary #087A43 | Dark #064D32 | Light #E8F6EC | Bg #F5F8F5
   Target widths: 320px, 360px, 375px, 390px, 430px, Tablet & Desktop
   ========================================================================== */

:root {
    --gari-primary: #087A43;
    --gari-primary-hover: #066637;
    --gari-dark-green: #064D32;
    --gari-light-green: #E8F6EC;
    --gari-bg: #F5F8F5;
    --gari-surface: #FFFFFF;
    --gari-text: #17231C;
    --gari-muted: #6B7A70;
    --gari-warning: #E9A323;
    --gari-warning-bg: #FEF3C7;
    --gari-error: #D94B4B;
    --gari-error-bg: #FEE2E2;
    --gari-gold: #FFBE3D;
    --gari-border: #E5EBE5;
    --gari-shadow: 0 4px 20px -2px rgba(8, 122, 67, 0.06), 0 2px 6px -1px rgba(0, 0, 0, 0.03);
    --gari-radius: 20px;
}

/* Base Body Layout */
.dashboard-mobile-redesign {
    max-width: 1200px;
    margin: 0 auto;
    padding: 16px 16px 110px 16px !important;
    background: var(--gari-bg);
    display: flex;
    flex-direction: column;
    gap: 20px;
    box-sizing: border-box;
}

/* Topbar Brand Link (Mobile-First Header) */
.topbar-brand-link {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    text-decoration: none;
    color: var(--gari-text);
    margin-left: 4px;
}
.topbar-brand-icon {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background: var(--gari-light-green);
    color: var(--gari-primary);
    display: inline-flex;
    align-items: center;
    justify-content: center;
}
.topbar-brand-info {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
}
.topbar-brand-title {
    font-size: 17px;
    font-weight: 800;
    letter-spacing: -0.4px;
    color: var(--gari-text);
}
.topbar-brand-sub {
    font-size: 11px;
    font-weight: 500;
    color: var(--gari-muted);
}
.topbar-avatar-only {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
}
.user-avatar-caret {
    font-size: 12px;
    color: var(--gari-muted);
}
.topbar-icon-btn.mobile-search-btn {
    display: inline-flex;
}

/* ==========================================================================
   B. HERO BANNER
   ========================================================================== */
.hero-banner-v2 {
    position: relative;
    border-radius: var(--gari-radius);
    overflow: hidden;
    min-height: 240px;
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    padding: 24px 28px;
    box-shadow: 0 8px 24px -4px rgba(6, 77, 50, 0.25);
    background: var(--gari-dark-green);
}
.hero-bg-container {
    position: absolute;
    inset: 0;
    z-index: 1;
}
.hero-bg-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center 35%;
}
.hero-gradient-overlay {
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(6, 77, 50, 0.92) 0%, rgba(8, 122, 67, 0.85) 60%, rgba(6, 77, 50, 0.90) 100%);
    backdrop-filter: blur(1px);
}
.hero-inner-content {
    position: relative;
    z-index: 2;
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 580px;
}
.hero-badge-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}
.hero-pill-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 9999px;
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.35);
    color: var(--gari-dark-green);
    font-size: 11.5px;
    font-weight: 700;
    letter-spacing: -0.1px;
}
.hero-title-v2 {
    font-size: 28px;
    font-weight: 800;
    color: #FFFFFF;
    line-height: 1.22;
    letter-spacing: -0.5px;
    margin: 2px 0 0 0;
}
.hero-desc-v2 {
    font-size: 13.5px;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.92);
    margin: 0;
}
.hero-cta-wrap {
    margin-top: 4px;
}
.btn-hero-cta {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #FFFFFF;
    color: var(--gari-text);
    font-size: 13.5px;
    font-weight: 700;
    padding: 10px 20px;
    border-radius: 9999px;
    border: none;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.btn-hero-cta:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.2);
}
.btn-hero-cta:active {
    transform: scale(0.97);
}

/* Hero Right Leaf Visual */
.hero-visual-leaf-card {
    position: relative;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
    padding-left: 20px;
}
.leaf-viewfinder-frame {
    position: relative;
    width: 175px;
    height: 155px;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    border: 1.5px solid rgba(255, 255, 255, 0.25);
    background: #000000;
}
.leaf-viewfinder-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}
.reticle-corner {
    position: absolute;
    width: 16px;
    height: 16px;
    border-color: #22C55E;
    border-style: solid;
    pointer-events: none;
    filter: drop-shadow(0 0 4px rgba(34, 197, 94, 0.8));
}
.reticle-corner.top-left {
    top: 8px;
    left: 8px;
    border-width: 2.5px 0 0 2.5px;
    border-top-left-radius: 4px;
}
.reticle-corner.top-right {
    top: 8px;
    right: 8px;
    border-width: 2.5px 2.5px 0 0;
    border-top-right-radius: 4px;
}
.reticle-corner.bottom-left {
    bottom: 8px;
    left: 8px;
    border-width: 0 0 2.5px 2.5px;
    border-bottom-left-radius: 4px;
}
.reticle-corner.bottom-right {
    bottom: 8px;
    right: 8px;
    border-width: 0 2.5px 2.5px 0;
    border-bottom-right-radius: 4px;
}
.leaf-detection-tag {
    position: absolute;
    bottom: 8px;
    left: 8px;
    right: 8px;
    padding: 5px 8px;
    border-radius: 8px;
    background: rgba(23, 35, 28, 0.85);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.15);
    display: flex;
    align-items: center;
    gap: 6px;
    color: #FFFFFF;
    font-size: 11px;
    line-height: 1.2;
}

/* ==========================================================================
   C. QUICK-ACCESS FEATURE CARDS
   ========================================================================== */
.quick-access-section {
    width: 100%;
}
.quick-access-scroll-track {
    display: flex;
    gap: 12px;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    -webkit-overflow-scrolling: touch;
    padding: 4px 2px 8px 2px;
    scrollbar-width: none;
}
.quick-access-scroll-track::-webkit-scrollbar {
    display: none;
}
.quick-card {
    flex: 0 0 102px;
    height: 106px;
    scroll-snap-align: start;
    background: var(--gari-light-green);
    border-radius: 18px;
    text-decoration: none;
    color: var(--gari-text);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 6px;
    box-sizing: border-box;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    border: 1px solid transparent;
}
.quick-card:active {
    transform: scale(0.95);
}
.quick-card.active {
    background: var(--gari-primary);
    color: #FFFFFF;
    box-shadow: 0 4px 16px rgba(8, 122, 67, 0.28);
}
.quick-card.active .quick-icon-wrap {
    color: #FFFFFF;
}
.quick-card.active .quick-label {
    color: #FFFFFF;
}
.quick-icon-wrap {
    color: var(--gari-primary);
    display: flex;
    align-items: center;
    justify-content: center;
}
.quick-label {
    font-size: 12px;
    font-weight: 700;
    text-align: center;
    line-height: 1.25;
    color: var(--gari-text);
}

/* ==========================================================================
   D. AI CROP DIAGNOSIS CARD
   ========================================================================== */
.card-v2 {
    background: var(--gari-surface);
    border-radius: var(--gari-radius);
    border: 1px solid var(--gari-border);
    box-shadow: var(--gari-shadow);
    padding: 22px 24px;
    box-sizing: border-box;
}
.section-v2-header {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 20px;
}
.section-v2-header.flex-between {
    justify-content: space-between;
    align-items: center;
}
.header-left-group {
    display: flex;
    align-items: flex-start;
    gap: 12px;
}
.header-icon-square {
    width: 38px;
    height: 38px;
    border-radius: 12px;
    background: var(--gari-light-green);
    color: var(--gari-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.header-text-group {
    display: flex;
    flex-direction: column;
    gap: 3px;
}
.section-v2-title {
    font-size: 19px;
    font-weight: 800;
    color: var(--gari-text);
    margin: 0;
    letter-spacing: -0.3px;
}
.section-v2-desc {
    font-size: 13px;
    color: var(--gari-muted);
    margin: 0;
    line-height: 1.45;
}
.link-see-all {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--gari-primary);
    font-size: 13.5px;
    font-weight: 700;
    text-decoration: none;
    white-space: nowrap;
}
.link-see-all:hover {
    text-decoration: underline;
}

/* Diagnosis Grid Layout */
.diagnosis-grid-v2 {
    display: grid;
    grid-template-columns: 1.15fr 1fr;
    gap: 24px;
    align-items: start;
}
.diagnosis-upload-col {
    display: flex;
    flex-direction: column;
    gap: 12px;
}
.dropzone-v2 {
    border: 1.5px dashed #A7D7B5;
    border-radius: 18px;
    background: #FAFDFB;
    padding: 24px 18px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s ease;
    outline: none;
}
.dropzone-v2:hover, .dropzone-v2.dragover {
    border-color: var(--gari-primary);
    background: #F0F9F3;
}
.dropzone-icon-box {
    width: 52px;
    height: 52px;
    border-radius: 14px;
    background: var(--gari-light-green);
    color: var(--gari-primary);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 10px;
}
.dropzone-primary-text {
    font-size: 15px;
    font-weight: 800;
    color: var(--gari-text);
    margin-bottom: 4px;
}
.dropzone-secondary-text {
    font-size: 12.5px;
    color: var(--gari-muted);
    margin-bottom: 16px;
}
.dropzone-actions-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    flex-wrap: wrap;
}
.btn-diag-action {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 9px 18px;
    border-radius: 9999px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    transition: transform 0.15s ease, background-color 0.15s ease;
}
.btn-diag-action:active {
    transform: scale(0.96);
}
.btn-diag-action.primary {
    background: var(--gari-primary);
    color: #FFFFFF;
    border: none;
    box-shadow: 0 3px 10px rgba(8, 122, 67, 0.2);
}
.btn-diag-action.primary:hover {
    background: var(--gari-primary-hover);
}
.btn-diag-action.secondary {
    background: #FFFFFF;
    color: var(--gari-text);
    border: 1px solid #D0DED4;
}
.btn-diag-action.secondary:hover {
    background: #F8FAF8;
}

/* Image Preview Inside Dropzone */
.preview-img-container {
    position: relative;
    max-width: 280px;
    margin: 0 auto 12px auto;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.1);
}
.preview-img {
    width: 100%;
    height: auto;
    max-height: 190px;
    object-fit: cover;
    display: block;
}
.btn-remove-preview {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: rgba(0, 0, 0, 0.65);
    color: #FFFFFF;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
}
.preview-controls-row {
    display: flex;
    align-items: center;
    gap: 8px;
    justify-content: center;
    flex-wrap: wrap;
}
.select-crop-v2 {
    padding: 8px 12px;
    border-radius: 10px;
    border: 1px solid #D0DED4;
    background: #FFFFFF;
    color: var(--gari-text);
    font-size: 12.5px;
    font-weight: 600;
}
.btn-execute-diag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border-radius: 9999px;
    background: var(--gari-primary);
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 700;
    border: none;
    cursor: pointer;
}

/* Real Server Status Badge */
.server-status-wrap {
    display: flex;
    justify-content: center;
    margin-top: 4px;
}
.server-status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 9999px;
    background: var(--gari-light-green);
    color: var(--gari-primary);
    font-size: 12px;
    font-weight: 700;
    border: 1px solid rgba(8, 122, 67, 0.15);
}
.server-status-pill.warning {
    background: var(--gari-warning-bg);
    color: var(--gari-warning);
    border-color: rgba(233, 163, 35, 0.3);
}
.server-status-pill.offline {
    background: var(--gari-error-bg);
    color: var(--gari-error);
    border-color: rgba(217, 75, 75, 0.3);
}

/* Right Column: 3-Step Timeline */
.diagnosis-steps-col {
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.steps-timeline {
    display: flex;
    flex-direction: column;
    gap: 0;
}
.timeline-step {
    display: flex;
    align-items: stretch;
    gap: 14px;
}
.step-badge-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 32px;
}
.step-number {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: var(--gari-primary);
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.step-line {
    width: 2px;
    flex: 1;
    min-height: 28px;
    background: #C8E6C9;
    margin: 4px 0;
}
.step-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 0 20px 0;
}
.step-icon-box {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: var(--gari-light-green);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.step-content {
    display: flex;
    flex-direction: column;
    line-height: 1.3;
}
.step-title {
    font-size: 14.5px;
    font-weight: 800;
    color: var(--gari-text);
    margin: 0;
}
.step-sub {
    font-size: 12px;
    color: var(--gari-muted);
    margin: 2px 0 0 0;
}

/* ==========================================================================
   E. FARM OVERVIEW ("VƯỜN CỦA BẠN")
   ========================================================================== */
.farms-scroll-track {
    display: flex;
    gap: 14px;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    -webkit-overflow-scrolling: touch;
    padding: 4px 2px 10px 2px;
    scrollbar-width: none;
}
.farms-scroll-track::-webkit-scrollbar {
    display: none;
}
.farm-add-card {
    flex: 0 0 130px;
    height: 185px;
    scroll-snap-align: start;
    border: 1.5px dashed #C8D6CA;
    border-radius: 16px;
    background: #FAFDFB;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    text-decoration: none;
    color: var(--gari-text);
    transition: all 0.15s ease;
    box-sizing: border-box;
}
.farm-add-card:hover {
    border-color: var(--gari-primary);
    background: var(--gari-light-green);
}
.add-icon-plus {
    font-size: 32px;
    font-weight: 300;
    color: var(--gari-muted);
    line-height: 1;
}
.add-label {
    font-size: 13px;
    font-weight: 700;
    color: var(--gari-text);
}

.farm-card-v2 {
    flex: 0 0 220px;
    height: 185px;
    scroll-snap-align: start;
    border-radius: 16px;
    border: 1px solid var(--gari-border);
    background: #FFFFFF;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    transition: transform 0.15s ease;
}
.farm-card-v2:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.07);
}
.farm-card-img-wrap {
    position: relative;
    width: 100%;
    height: 98px;
    background: #E8ECE8;
}
.farm-card-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}
.farm-card-kebab {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.9);
    border: none;
    cursor: pointer;
    font-size: 15px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--gari-text);
}
.farm-card-body {
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    flex: 1;
    justify-content: space-between;
}
.farm-card-name {
    font-size: 14px;
    font-weight: 800;
    color: var(--gari-text);
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.farm-card-metrics {
    font-size: 11.5px;
    color: var(--gari-muted);
}
.farm-status-pill {
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 700;
}
.farm-status-pill .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
}
.farm-status-pill.healthy {
    background: var(--gari-light-green);
    color: var(--gari-primary);
}
.farm-status-pill.healthy .status-dot {
    background: var(--gari-primary);
}
.farm-status-pill.warning {
    background: var(--gari-warning-bg);
    color: var(--gari-warning);
}
.farm-status-pill.warning .status-dot {
    background: var(--gari-warning);
}
.farm-status-pill.danger {
    background: var(--gari-error-bg);
    color: var(--gari-error);
}
.farm-status-pill.danger .status-dot {
    background: var(--gari-error);
}

/* ==========================================================================
   F. GARI PRO UPGRADE BANNER
   ========================================================================== */
.pro-upgrade-banner-v2 {
    position: relative;
    border-radius: var(--gari-radius);
    background: var(--gari-dark-green);
    overflow: hidden;
    padding: 20px 24px;
    box-shadow: 0 6px 20px rgba(6, 77, 50, 0.22);
}
.pro-banner-bg-graphic {
    position: absolute;
    right: 0;
    bottom: 0;
    top: 0;
    width: 45%;
    opacity: 0.8;
    pointer-events: none;
}
.pro-banner-bg-graphic svg {
    width: 100%;
    height: 100%;
}
.pro-banner-content {
    position: relative;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
}
.pro-banner-text {
    max-width: 620px;
}
.pro-banner-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 17px;
    font-weight: 800;
    color: #FFFFFF;
    margin: 0 0 4px 0;
}
.crown-icon {
    font-size: 18px;
}
.pro-banner-desc {
    font-size: 12.5px;
    color: rgba(255, 255, 255, 0.88);
    margin: 0;
    line-height: 1.45;
}
.btn-pro-upgrade-cta {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 20px;
    border-radius: 9999px;
    background: var(--gari-gold);
    color: var(--gari-text);
    font-size: 13.5px;
    font-weight: 800;
    text-decoration: none;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    white-space: nowrap;
    transition: transform 0.15s ease;
}
.btn-pro-upgrade-cta:hover {
    transform: scale(1.02);
}
.btn-pro-upgrade-cta:active {
    transform: scale(0.97);
}

/* ==========================================================================
   G. FIXED BOTTOM NAVIGATION BAR
   ========================================================================== */
.mobile-bottom-nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 999;
    background: rgba(255, 255, 255, 0.96);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-top: 1px solid var(--gari-border);
    display: flex;
    align-items: center;
    justify-content: space-around;
    padding: 6px 8px max(env(safe-area-inset-bottom, 8px), 8px) 8px;
    box-shadow: 0 -2px 14px rgba(0, 0, 0, 0.05);
}
.bottom-nav-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    text-decoration: none;
    color: var(--gari-muted);
    font-size: 11px;
    font-weight: 700;
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px 8px;
    min-width: 54px;
    transition: color 0.15s ease;
}
.bottom-nav-item.active {
    color: var(--gari-primary);
}
.bottom-nav-item.active .bottom-nav-label {
    color: var(--gari-primary);
}
.bottom-nav-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
}
.bottom-nav-label {
    font-size: 11px;
    font-weight: 700;
    line-height: 1.1;
}

/* Center Prominent Scan Button */
.bottom-nav-scan-btn {
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transform: translateY(-14px);
    z-index: 1001;
}
.scan-btn-inner {
    width: 54px;
    height: 54px;
    border-radius: 50%;
    background: var(--gari-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 16px rgba(8, 122, 67, 0.42);
    border: 3.5px solid #FFFFFF;
    transition: transform 0.15s ease, background-color 0.15s ease;
}
.bottom-nav-scan-btn:active .scan-btn-inner {
    transform: scale(0.92);
}

/* ==========================================================================
   RESPONSIVE BEHAVIOR (320px - 430px, Tablet, Desktop)
   ========================================================================== */

/* Narrow Mobile: 320px - 360px */
@media (max-width: 360px) {
    .dashboard-mobile-redesign {
        padding: 10px 10px 100px 10px !important;
        gap: 16px;
    }
    .hero-banner-v2 {
        padding: 16px 14px;
        min-height: 210px;
    }
    .hero-title-v2 {
        font-size: 22px;
    }
    .hero-desc-v2 {
        font-size: 12px;
    }
    .btn-hero-cta {
        padding: 8px 14px;
        font-size: 12.5px;
    }
    .hero-visual-leaf-card {
        display: none !important;
    }
    .quick-card {
        flex: 0 0 92px;
        height: 98px;
        padding: 8px 4px;
    }
    .quick-label {
        font-size: 11px;
    }
    .card-v2 {
        padding: 16px 14px;
    }
    .section-v2-title {
        font-size: 16.5px;
    }
    .pro-upgrade-banner-v2 {
        padding: 16px 14px;
    }
    .btn-pro-upgrade-cta {
        width: 100%;
        justify-content: center;
    }
}

/* Mobile Screens: 361px - 640px */
@media (max-width: 640px) {
    .hero-visual-leaf-card {
        display: none;
    }
    .diagnosis-grid-v2 {
        grid-template-columns: 1fr;
        gap: 18px;
    }
    .pro-banner-content {
        flex-direction: column;
        align-items: flex-start;
    }
    .pro-banner-bg-graphic {
        display: none;
    }
    .topbar-center.desktop-only-search {
        display: none !important;
    }
    .breadcrumbs.desktop-only-crumb {
        display: none !important;
    }
}

/* Tablet Screens: 641px - 1024px */
@media (min-width: 641px) and (max-width: 1024px) {
    .hero-visual-leaf-card {
        display: flex;
    }
    .leaf-viewfinder-frame {
        width: 140px;
        height: 130px;
    }
    .diagnosis-grid-v2 {
        grid-template-columns: 1fr 1fr;
    }
}

/* Desktop Screens: 1025px+ */
@media (min-width: 1025px) {
    .mobile-bottom-nav {
        display: none !important;
    }
    .dashboard-mobile-redesign {
        padding-bottom: 40px !important;
    }
    .hero-visual-leaf-card {
        display: flex;
    }
    .quick-access-scroll-track {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 14px;
    }
    .quick-card {
        flex: unset;
        width: 100%;
    }
}
"""

with open('frontend2/style.css', 'r', encoding='utf-8') as f:
    orig = f.read()

if 'GARI MOBILE UI REDESIGN' not in orig:
    with open('frontend2/style.css', 'a', encoding='utf-8') as f:
        f.write("\n" + css_to_append + "\n")
    print('Successfully appended mobile styles to frontend2/style.css')
else:
    print('Styles already present')
