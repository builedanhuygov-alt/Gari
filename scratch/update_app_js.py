import re

with open('frontend2/app.js', 'r', encoding='utf-8') as f:
    code = f.read()

start_marker = 'export function initFloatingChat() {'
end_marker = 'export function ensureLegalFooter()'

start_idx = code.find(start_marker)
end_idx = code.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print('Error: Could not find markers in frontend2/app.js')
    sys.exit(1)

new_init_floating_chat = '''export function initFloatingChat() {
    if (document.getElementById('gariCopilotDrawer')) return;

    // 1. Create Floating Action Button (FAB)
    const fab = document.createElement('button');
    fab.id = 'gariCopilotFab';
    fab.className = 'copilot-fab';
    fab.type = 'button';
    fab.title = 'Mở Trợ lý Nông nghiệp GARI Copilot';
    fab.setAttribute('aria-label', 'Mở Trợ lý Nông nghiệp GARI Copilot');
    fab.setAttribute('aria-expanded', 'false');
    fab.setAttribute('aria-controls', 'gariCopilotDrawer');
    fab.innerHTML = `
        <span class="fab-pulse-ring" aria-hidden="true"></span>
        <span class="fab-icon" aria-hidden="true">🤖</span>
        <span class="fab-label">GARI Copilot</span>
    `;
    document.body.appendChild(fab);

    // 2. Create Backdrop Overlay
    const backdrop = document.createElement('div');
    backdrop.id = 'gariCopilotBackdrop';
    backdrop.className = 'copilot-backdrop';
    backdrop.setAttribute('aria-hidden', 'true');
    document.body.appendChild(backdrop);

    // 3. Create Dedicated Drawer
    const drawer = document.createElement('div');
    drawer.id = 'gariCopilotDrawer';
    drawer.className = 'copilot-drawer';
    drawer.setAttribute('role', 'dialog');
    drawer.setAttribute('aria-modal', 'true');
    drawer.setAttribute('aria-label', 'Trợ lý Nông nghiệp GARI Copilot');
    drawer.innerHTML = `
        <div class="copilot-drawer-header">
            <div class="copilot-header-info">
                <div class="copilot-title">🌿 GARI AgriTech Copilot</div>
                <div class="copilot-sub">Trợ lý đồng hành canh tác & vi khí hậu Ba Vì</div>
            </div>
            <div class="copilot-header-actions">
                <button type="button" id="btnMinimizeCopilot" class="copilot-header-btn" title="Thu nhỏ (Esc)" aria-label="Thu nhỏ">–</button>
                <button type="button" id="btnCloseCopilot" class="copilot-header-btn" title="Đóng (Esc)" aria-label="Đóng">&times;</button>
            </div>
        </div>
        <div class="copilot-context-bar" id="copilotContextBar">
            <span class="copilot-ctx-chip">Đang kết nối vi khí hậu...</span>
        </div>
        <div class="copilot-messages" id="copilotMessages" tabindex="0" aria-live="polite">
            <div class="copilot-msg bot">
                <div class="copilot-bubble">
                    Chào bác nông dân! Tôi là Trợ lý Đồng hành GARI. Tôi có thể giúp bác kiểm tra tình hình các thửa ruộng/lô vườn, việc canh tác cần làm hôm nay, hoặc tư vấn kỹ thuật xử lý sâu bệnh theo khuyến nông thực địa.
                </div>
                <div class="copilot-chips" id="copilotChips">
                    <button type="button" class="copilot-chip" data-q="Tình trạng các lô vườn của tôi thế nào?">🌾 Tình trạng lô vườn</button>
                    <button type="button" class="copilot-chip" data-q="Hôm nay có việc canh tác gì cần làm không?">📋 Việc hôm nay & quá hạn</button>
                    <button type="button" class="copilot-chip" data-q="Cà chua bị đốm lá muộn xử lý thế nào?">🍅 Tư vấn bệnh cà chua</button>
                    <button type="button" class="copilot-chip" data-q="Nhắc tôi phun phòng sâu tơ ngày mai">📅 Lập lịch phun phòng</button>
                </div>
            </div>
        </div>
        <div class="copilot-input-area">
            <input type="text" id="copilotInput" placeholder="Hỏi tình trạng ruộng, việc cần làm..." autocomplete="off" aria-label="Nội dung trao đổi với GARI Copilot">
            <button type="button" id="btnSendCopilot" class="btn btn-primary btn-sm">Gửi</button>
        </div>
    `;
    document.body.appendChild(drawer);

    // Focus trap & Open / Close State Management
    let lastActiveElement = null;

    const openDrawer = async () => {
        lastActiveElement = document.activeElement;
        drawer.classList.add('open');
        backdrop.classList.add('open');
        fab.classList.add('drawer-open');
        fab.setAttribute('aria-expanded', 'true');
        document.body.classList.add('copilot-open');

        // Auto-focus input after smooth transition
        setTimeout(() => {
            const input = document.getElementById('copilotInput');
            if (input) input.focus();
        }, 120);

        try {
            const res = await fetch('/api/copilot/context');
            const data = await res.json();
            if (data.success && data.context) {
                const ctx = data.context;
                const bar = document.getElementById('copilotContextBar');
                if (bar) {
                    bar.innerHTML = `
                        <span class="copilot-ctx-chip">🌱 <strong>${ctx.farms_count}</strong> trại • <strong>${ctx.plots_count}</strong> lô</span>
                        <span class="copilot-ctx-chip">📋 <strong>${ctx.tasks_summary.today_count}</strong> việc hôm nay</span>
                        <span class="copilot-ctx-chip" style="${ctx.tasks_summary.overdue_count > 0 ? 'color:#b91c1c; font-weight:700;' : ''}">⚠️ <strong>${ctx.tasks_summary.overdue_count}</strong> quá hạn</span>
                        <span class="copilot-ctx-chip">🌤️ ${ctx.observed_weather ? (ctx.observed_weather.temperature_c || ctx.observed_weather.temp_c || 24.5) : 24.5}°C (${ctx.observed_weather ? ctx.observed_weather.humidity_pct : 80}%)</span>
                    `;
                }
            }
        } catch {}
    };

    const closeDrawer = () => {
        drawer.classList.remove('open');
        backdrop.classList.remove('open');
        fab.classList.remove('drawer-open');
        fab.setAttribute('aria-expanded', 'false');
        document.body.classList.remove('copilot-open');

        // Restore focus smoothly
        try {
            if (lastActiveElement && typeof lastActiveElement.focus === 'function' && document.body.contains(lastActiveElement)) {
                lastActiveElement.focus();
            } else {
                fab.focus();
            }
        } catch {}
    };

    fab.onclick = openDrawer;
    document.getElementById('btnCloseCopilot').onclick = closeDrawer;
    const minBtn = document.getElementById('btnMinimizeCopilot');
    if (minBtn) minBtn.onclick = closeDrawer;
    backdrop.onclick = closeDrawer;

    // Keyboard navigation (Escape closes overlay)
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && drawer.classList.contains('open')) {
            closeDrawer();
        }
    });

    // Close on click outside on desktop
    document.addEventListener('pointerdown', (e) => {
        if (!drawer.classList.contains('open')) return;
        if (window.innerWidth > 1024) {
            if (!drawer.contains(e.target) && !fab.contains(e.target)) {
                closeDrawer();
            }
        }
    });

    // Send message logic
    const sendMsg = async (text) => {
        const input = document.getElementById('copilotInput');
        const msg = (text || (input ? input.value : '') || '').trim();
        if (!msg) return;

        if (input) input.value = '';

        const container = document.getElementById('copilotMessages');
        const uEl = document.createElement('div');
        uEl.className = 'copilot-msg user';
        uEl.innerHTML = `<div class="copilot-bubble">${msg}</div>`;
        container.appendChild(uEl);
        container.scrollTop = container.scrollHeight;

        const thinkEl = document.createElement('div');
        thinkEl.className = 'copilot-msg bot';
        thinkEl.innerHTML = `<div class="copilot-bubble" style="font-style:italic; color:var(--text-muted);">GARI Copilot đang tổng hợp dữ liệu...</div>`;
        container.appendChild(thinkEl);
        container.scrollTop = container.scrollHeight;

        try {
            const res = await fetch('/api/copilot/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: msg })
            });
            const data = await res.json();
            thinkEl.remove();

            const bEl = document.createElement('div');
            bEl.className = 'copilot-msg bot';

            let actionHtml = '';
            if (data.actions && data.actions.length > 0) {
                const act = data.actions[0];
                if (act.type === 'confirm_task_draft' && act.draft) {
                    const draftJson = JSON.stringify(act.draft).replace(/"/g, '&quot;');
                    actionHtml = `
                        <div class="copilot-action-card">
                            <div class="copilot-action-title">📋 ${act.draft.title}</div>
                            <div class="copilot-action-meta">📅 Hạn: ${act.draft.due_date} • 🌿 Cây: ${act.draft.crop_id}</div>
                            <button type="button" class="btn btn-primary btn-sm btn-confirm-copilot" data-draft="${draftJson}" style="font-size:11px; padding:4px 10px;">
                                ✅ ${act.label || 'Xác nhận & Lưu vào Lịch canh tác'}
                            </button>
                        </div>
                    `;
                }
            }

            const formattedReply = (data.reply || 'Đã ghi nhận yêu cầu của bác.')
                .replace(/\\n\\n/g, '<br><br>')
                .replace(/\\n- /g, '<br>• ')
                .replace(/\\n/g, '<br>');

            bEl.innerHTML = `<div class="copilot-bubble">${formattedReply}${actionHtml}</div>`;
            container.appendChild(bEl);
            container.scrollTop = container.scrollHeight;

            const confirmBtn = bEl.querySelector('.btn-confirm-copilot');
            if (confirmBtn) {
                confirmBtn.onclick = async () => {
                    confirmBtn.disabled = true;
                    confirmBtn.textContent = 'Đang lưu vào lịch...';
                    try {
                        const rawDraft = JSON.parse(confirmBtn.getAttribute('data-draft'));
                        const cRes = await fetch('/api/copilot/tasks/confirm-draft', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ draft: rawDraft })
                        });
                        const cJson = await cRes.json();
                        if (cRes.ok && cJson.success) {
                            confirmBtn.className = 'btn btn-secondary btn-sm';
                            confirmBtn.textContent = `✓ Đã lưu vào Lịch (#${cJson.task.id})`;
                            if (window.toast) window.toast('✅ Đã thêm công việc vào Lịch canh tác!');
                        } else {
                            confirmBtn.disabled = false;
                            confirmBtn.textContent = 'Thử lại';
                            alert(cJson.detail || 'Không thể tạo công việc.');
                        }
                    } catch {
                        confirmBtn.disabled = false;
                        confirmBtn.textContent = 'Lỗi kết nối';
                    }
                };
            }
        } catch {
            thinkEl.remove();
            const errEl = document.createElement('div');
            errEl.className = 'copilot-msg bot';
            errEl.innerHTML = `<div class="copilot-bubble" style="color:#b91c1c;">Không thể kết nối đến máy chủ GARI. Vui lòng thử lại.</div>`;
            container.appendChild(errEl);
        }
    };

    document.getElementById('btnSendCopilot').onclick = () => sendMsg();
    document.getElementById('copilotInput').onkeydown = (e) => {
        if (e.key === 'Enter') sendMsg();
    };

    document.addEventListener('click', (e) => {
        if (e.target && e.target.classList.contains('copilot-chip')) {
            const q = e.target.getAttribute('data-q');
            if (q) sendMsg(q);
        }
    });
}

'''

new_code = code[:start_idx] + new_init_floating_chat + code[end_idx:]

with open('frontend2/app.js', 'w', encoding='utf-8') as f:
    f.write(new_code)

print('Successfully updated frontend2/app.js')
