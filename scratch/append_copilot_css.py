with open('frontend2/style.css', 'a', encoding='utf-8') as f:
    f.write('''

/* ==========================================================================
   GARI AgriTech AI Copilot Drawer & FAB
   ========================================================================== */
.copilot-fab {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 999;
    display: flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(135deg, #15803d, #16a34a);
    color: #ffffff;
    border: none;
    padding: 10px 16px;
    border-radius: 9999px;
    font-size: 13px;
    font-weight: 600;
    box-shadow: 0 4px 14px rgba(22, 163, 74, 0.35);
    cursor: pointer;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.copilot-fab:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(22, 163, 74, 0.45);
}
.copilot-fab .fab-icon {
    font-size: 16px;
    line-height: 1;
}

.copilot-drawer {
    position: fixed;
    top: 0;
    right: -440px;
    width: 400px;
    max-width: 92vw;
    height: 100vh;
    background: var(--bg-card);
    border-left: 1px solid var(--border-color);
    box-shadow: -8px 0 24px rgba(0, 0, 0, 0.12);
    z-index: 10000;
    display: flex;
    flex-direction: column;
    transition: right 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.copilot-drawer.open {
    right: 0;
}

.copilot-drawer-header {
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--bg-surface);
}
.copilot-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-heading);
}
.copilot-sub {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
}

.copilot-context-bar {
    padding: 8px 14px;
    background: var(--bg-base);
    border-bottom: 1px solid var(--border-color);
    display: flex;
    gap: 6px;
    overflow-x: auto;
    font-size: 11px;
}
.copilot-ctx-chip {
    padding: 3px 8px;
    border-radius: 12px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    white-space: nowrap;
    color: var(--text-muted);
}
.copilot-ctx-chip strong {
    color: var(--text-heading);
}

.copilot-messages {
    flex: 1;
    overflow-y: auto;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}
.copilot-msg {
    display: flex;
    flex-direction: column;
    max-width: 90%;
}
.copilot-msg.user {
    align-self: flex-end;
}
.copilot-msg.bot {
    align-self: flex-start;
}
.copilot-bubble {
    padding: 10px 12px;
    border-radius: 10px;
    font-size: 13px;
    line-height: 1.5;
}
.copilot-msg.user .copilot-bubble {
    background: var(--primary);
    color: #ffffff;
    border-bottom-right-radius: 2px;
}
.copilot-msg.bot .copilot-bubble {
    background: var(--bg-surface);
    color: var(--text-main);
    border: 1px solid var(--border-color);
    border-bottom-left-radius: 2px;
}

.copilot-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}
.copilot-chip {
    font-size: 11px;
    padding: 4px 8px;
    border-radius: 12px;
    border: 1px solid var(--border-color);
    background: var(--bg-card);
    color: var(--primary);
    cursor: pointer;
    transition: all 0.15s ease;
}
.copilot-chip:hover {
    background: var(--primary-light);
    color: var(--primary-dark);
}

.copilot-action-card {
    margin-top: 8px;
    padding: 10px;
    background: var(--bg-base);
    border: 1px dashed var(--primary);
    border-radius: 8px;
    font-size: 12px;
}
.copilot-action-title {
    font-weight: 600;
    color: var(--text-heading);
    margin-bottom: 4px;
}
.copilot-action-meta {
    color: var(--text-muted);
    font-size: 11px;
    margin-bottom: 8px;
}

.copilot-input-area {
    padding: 12px 14px;
    border-top: 1px solid var(--border-color);
    display: flex;
    gap: 8px;
    background: var(--bg-surface);
}
.copilot-input-area input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 13px;
    background: var(--bg-card);
    color: var(--text-main);
}
''')
print("Copilot CSS appended successfully")
