with open('frontend2/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update export function initFloatingChat()
target_stub = "export function initFloatingChat() {}"

replacement_func = """export function initFloatingChat() {
    if (document.getElementById('gariCopilotDrawer')) return;

    // 1. Create Floating Action Button (FAB)
    const fab = document.createElement('button');
    fab.id = 'gariCopilotFab';
    fab.className = 'copilot-fab';
    fab.type = 'button';
    fab.title = 'Mở Trợ lý Nông nghiệp GARI Copilot';
    fab.innerHTML = `<span class=\"fab-icon\">🤖</span> <span>GARI Copilot</span>`;
    document.body.appendChild(fab);

    // 2. Create Drawer
    const drawer = document.createElement('div');
    drawer.id = 'gariCopilotDrawer';
    drawer.className = 'copilot-drawer';
    drawer.innerHTML = `
        <div class=\"copilot-drawer-header\">
            <div>
                <div class=\"copilot-title\">🌿 GARI AgriTech Copilot</div>
                <div class=\"copilot-sub\">Trợ lý đồng hành canh tác & vi khí hậu Ba Vì</div>
            </div>
            <button id=\"btnCloseCopilot\" style=\"background:none; border:none; font-size:22px; cursor:pointer; color:var(--text-muted);\">&times;</button>
        </div>
        <div class=\"copilot-context-bar\" id=\"copilotContextBar\">
            <span class=\"copilot-ctx-chip\">Đang kết nối vi khí hậu...</span>
        </div>
        <div class=\"copilot-messages\" id=\"copilotMessages\">
            <div class=\"copilot-msg bot\">
                <div class=\"copilot-bubble\">
                    Chào bác nông dân! Tôi là Trợ lý Đồng hành GARI. Tôi có thể giúp bác kiểm tra tình hình các thửa ruộng/lô vườn, việc canh tác cần làm hôm nay, hoặc tư vấn kỹ thuật xử lý sâu bệnh theo khuyến nông thực địa.
                </div>
                <div class=\"copilot-chips\" id=\"copilotChips\">
                    <button class=\"copilot-chip\" data-q=\"Tình trạng các lô vườn của tôi thế nào?\">🌾 Tình trạng lô vườn</button>
                    <button class=\"copilot-chip\" data-q=\"Hôm nay có việc canh tác gì cần làm không?\">📋 Việc hôm nay & quá hạn</button>
                    <button class=\"copilot-chip\" data-q=\"Cà chua bị đốm lá muộn xử lý thế nào?\">🍅 Tư vấn bệnh cà chua</button>
                    <button class=\"copilot-chip\" data-q=\"Nhắc tôi phun phòng sâu tơ ngày mai\">📅 Lập lịch phun phòng</button>
                </div>
            </div>
        </div>
        <div class=\"copilot-input-area\">
            <input type=\"text\" id=\"copilotInput\" placeholder=\"Hỏi tình trạng ruộng, việc cần làm...\" autocomplete=\"off\">
            <button id=\"btnSendCopilot\" class=\"btn btn-primary btn-sm\">Gửi</button>
        </div>
    `;
    document.body.appendChild(drawer);

    // Toggle logic
    const openDrawer = async () => {
        drawer.classList.add('open');
        try {
            const res = await fetch('/api/copilot/context');
            const data = await res.json();
            if (data.success && data.context) {
                const ctx = data.context;
                const bar = document.getElementById('copilotContextBar');
                if (bar) {
                    bar.innerHTML = `
                        <span class=\"copilot-ctx-chip\">🌱 <strong>${ctx.farms_count}</strong> trại • <strong>${ctx.plots_count}</strong> lô</span>
                        <span class=\"copilot-ctx-chip\">📋 <strong>${ctx.tasks_summary.today_count}</strong> việc hôm nay</span>
                        <span class=\"copilot-ctx-chip\" style=\"${ctx.tasks_summary.overdue_count > 0 ? 'color:#b91c1c; font-weight:700;' : ''}\">⚠️ <strong>${ctx.tasks_summary.overdue_count}</strong> quá hạn</span>
                        <span class=\"copilot-ctx-chip\">🌤️ ${ctx.observed_weather ? ctx.observed_weather.temp_c : '24'}°C</span>
                    `;
                }
            }
        } catch {}
    };

    const closeDrawer = () => drawer.classList.remove('open');

    fab.onclick = openDrawer;
    document.getElementById('btnCloseCopilot').onclick = closeDrawer;

    // Send logic
    const sendMsg = async (text) => {
        const input = document.getElementById('copilotInput');
        const msg = (text || (input ? input.value : '') || '').trim();
        if (!msg) return;

        if (input) input.value = '';

        const container = document.getElementById('copilotMessages');
        const uEl = document.createElement('div');
        uEl.className = 'copilot-msg user';
        uEl.innerHTML = `<div class=\"copilot-bubble\">${msg}</div>`;
        container.appendChild(uEl);
        container.scrollTop = container.scrollHeight;

        const thinkEl = document.createElement('div');
        thinkEl.className = 'copilot-msg bot';
        thinkEl.innerHTML = `<div class=\"copilot-bubble\" style=\"font-style:italic; color:var(--text-muted);\">GARI Copilot đang tổng hợp dữ liệu...</div>`;
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
                    const draftJson = JSON.stringify(act.draft).replace(/\"/g, '&quot;');
                    actionHtml = `
                        <div class=\"copilot-action-card\">
                            <div class=\"copilot-action-title\">📋 ${act.draft.title}</div>
                            <div class=\"copilot-action-meta\">📅 Hạn: ${act.draft.due_date} • 🌿 Cây: ${act.draft.crop_id}</div>
                            <button type=\"button\" class=\"btn btn-primary btn-sm btn-confirm-copilot\" data-draft=\"${draftJson}\" style=\"font-size:11px; padding:4px 10px;\">
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

            bEl.innerHTML = `<div class=\"copilot-bubble\">${formattedReply}${actionHtml}</div>`;
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
            errEl.innerHTML = `<div class=\"copilot-bubble\" style=\"color:#b91c1c;\">Không thể kết nối đến máy chủ GARI. Vui lòng thử lại.</div>`;
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
}"""

content = content.replace(target_stub, replacement_func, 1)

# 2. Make sure window.toast is globally exposed
if "window.toast = toast;" not in content:
    content = content.replace("export function toast(msg, type = 'info') {", "export function toast(msg, type = 'info') {\n    window.toast = toast;")

# 3. Call initFloatingChat() at the end of setupSaaSShell
target_shell_end = """    const workspaceBtn = document.getElementById('workspaceSelector');
    if (workspaceBtn) {
        workspaceBtn.onclick = () => {
            window.location.href = '/frontend2/farms.html';
        };
    }
}"""

replacement_shell_end = """    const workspaceBtn = document.getElementById('workspaceSelector');
    if (workspaceBtn) {
        workspaceBtn.onclick = () => {
            window.location.href = '/frontend2/farms.html';
        };
    }

    // Initialize floating AI Copilot on all pages
    initFloatingChat();
}"""

content = content.replace(target_shell_end, replacement_shell_end, 1)

with open('frontend2/app.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS: app.js updated with GARI AI Copilot and global toast")
