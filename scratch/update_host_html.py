import re

with open('frontend2/host.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add Expert Tab button to nav bar
old_nav_marker = '<button class="host-tab-btn" data-tab="tab-moderation">'
new_nav_btn = '''        <button class="host-tab-btn" data-tab="tab-experts">
            🌾 Thẩm định Chuyên gia
        </button>
        <button class="host-tab-btn" data-tab="tab-moderation">'''

if old_nav_marker in html and 'data-tab="tab-experts"' not in html:
    html = html.replace(old_nav_marker, new_nav_btn, 1)
    print("Added tab-experts navigation button.")

# 2. Add AI Diagnostics button to tab-models
model_header_old = '<button class="btn-ghost-sm" onclick="loadHostModels()">'
model_header_new = '''<div style="display:flex; gap:10px;">
                    <button class="btn-host-action" onclick="runHostAiTest()" id="btnHostAiTest" style="background:#059669; border-color:#059669;">
                        ⚡ Chạy Kiểm thử AI Realtime
                    </button>
                    <button class="btn-ghost-sm" onclick="loadHostModels()">
                        🔄 Làm mới trạng thái AI
                    </button>
                </div>'''

if model_header_old in html and 'runHostAiTest' not in html:
    html = html.replace(model_header_old, model_header_new, 1)
    print("Added AI test button to tab-models.")

# 3. Add Diagnostic result card in tab-models
model_grid_marker = '<div class="host-grid-4">'
diagnostic_box = '''<div id="aiTestResultBox" style="display:none; margin-bottom:20px; padding:16px 20px; border-radius:12px; background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.3);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="font-weight:600; color:#10b981; display:flex; align-items:center; gap:8px;">
                        <span>✅</span> Kết Quả Kiểm Thử Suy Luận AI Thực Tế
                    </div>
                    <span id="aiTestTimestamp" style="font-size:12px; color:var(--host-muted);"></span>
                </div>
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:16px; margin-top:12px;">
                    <div><span style="font-size:11px; color:var(--host-muted);">HỆ THỐNG / BACKEND:</span><div id="aiTestBackend" style="font-weight:600; font-size:14px;">--</div></div>
                    <div><span style="font-size:11px; color:var(--host-muted);">ĐỘ TRỄ SUY LUẬN:</span><div id="aiTestLatency" style="font-weight:700; color:#3b82f6; font-size:14px;">--</div></div>
                    <div><span style="font-size:11px; color:var(--host-muted);">KẾT QUẢ TEST LEAF:</span><div id="aiTestTop" style="font-weight:600; font-size:14px;">--</div></div>
                    <div><span style="font-size:11px; color:var(--host-muted);">ĐỘ TIN CẬY:</span><div id="aiTestConf" style="font-weight:700; color:#10b981; font-size:14px;">--</div></div>
                    <div><span style="font-size:11px; color:var(--host-muted);">GEMINI ASSISTANT:</span><div id="aiTestGemini" style="font-weight:600; font-size:14px;">--</div></div>
                </div>
            </div>
            '''
if model_grid_marker in html and 'aiTestResultBox' not in html:
    html = html.replace(model_grid_marker, diagnostic_box + '\n            ' + model_grid_marker, 1)
    print("Added aiTestResultBox inside tab-models.")

# 4. Add tab-experts section before tab-moderation section
mod_sec_marker = '<section id="tab-moderation" class="tab-panel">'
tab_experts_section = '''        <!-- TAB: EXPERT NETWORK MANAGEMENT -->
        <section id="tab-experts" class="tab-panel">
            <div class="section-header">
                <div>
                    <h2 class="section-title">🌾 Quản trị Mạng lưới Chuyên gia Nông nghiệp</h2>
                    <span style="font-size:13px; color:var(--host-muted);">Thẩm định hồ sơ năng lực, bằng cấp chuyên môn, cấp quyền tư vấn và giám sát phác đồ điều trị.</span>
                </div>
                <button class="btn-ghost-sm" onclick="loadHostExperts()">
                    🔄 Làm mới danh sách
                </button>
            </div>

            <div class="host-grid-4">
                <div class="host-card">
                    <div class="host-card-title">Chuyên Gia Đã Cấp Phép</div>
                    <div class="host-metric-val" id="expertTotalActiveCount" style="color:#10b981;">0</div>
                    <div class="host-metric-sub">Kỹ sư & Bác sĩ BVTV</div>
                </div>
                <div class="host-card">
                    <div class="host-card-title">Đơn Chờ Thẩm Định</div>
                    <div class="host-metric-val" id="expertPendingCount" style="color:#f59e0b;">0</div>
                    <div class="host-metric-sub">Cần phê duyệt</div>
                </div>
                <div class="host-card">
                    <div class="host-card-title">Ca Bệnh Đã Phản Hồi</div>
                    <div class="host-metric-val" id="expertCasesAnsweredCount">0</div>
                    <div class="host-metric-sub">Tư vấn qua hệ thống</div>
                </div>
                <div class="host-card">
                    <div class="host-card-title">Thời Gian Phản Hồi TB</div>
                    <div class="host-metric-val" style="color:#3b82f6;">&lt; 2h</div>
                    <div class="host-metric-sub">Cam kết SLA nông hộ</div>
                </div>
            </div>

            <!-- Pending Applications Table -->
            <div style="margin-top:28px;">
                <h3 style="font-size:16px; font-weight:700; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
                    <span>⏳</span> Đơn Đăng Ký Cần Xét Duyệt
                </h3>
                <div class="host-table-wrap">
                    <table class="host-table">
                        <thead>
                            <tr>
                                <th>Ứng Viên</th>
                                <th>Chức Danh & Đơn Vị</th>
                                <th>Chuyên Môn</th>
                                <th>Kinh Nghiệm</th>
                                <th>Liên Hệ</th>
                                <th>Hồ Sơ & Minh Chứng</th>
                                <th>Thao Tác</th>
                            </tr>
                        </thead>
                        <tbody id="expertApplicationsTableBody">
                            <tr><td colspan="7" style="text-align:center; padding:24px;">Đang tải đơn đăng ký...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Active Experts Table -->
            <div style="margin-top:36px;">
                <h3 style="font-size:16px; font-weight:700; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
                    <span>👨‍🔬</span> Danh Sách Chuyên Gia Đang Hoạt Động
                </h3>
                <div class="host-table-wrap">
                    <table class="host-table">
                        <thead>
                            <tr>
                                <th>Chuyên Gia</th>
                                <th>Học Vị / Chức Danh</th>
                                <th>Chuyên Khoa Cây Trồng</th>
                                <th>Ca Tư Vấn</th>
                                <th>Đánh Giá</th>
                                <th>Trạng Thái</th>
                                <th>Thao Tác</th>
                            </tr>
                        </thead>
                        <tbody id="activeExpertsTableBody">
                            <tr><td colspan="7" style="text-align:center; padding:24px;">Đang tải danh sách chuyên gia...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        '''

if mod_sec_marker in html and 'id="tab-experts"' not in html:
    html = html.replace(mod_sec_marker, tab_experts_section + mod_sec_marker, 1)
    print("Added tab-experts section.")

# 5. Add JavaScript handler for tab-experts and ai test
js_target = "if (targetId === 'tab-overview') loadOverviewData();"
new_js_target = """if (targetId === 'tab-overview') loadOverviewData();
                else if (targetId === 'tab-experts') loadHostExperts();"""
if js_target in html and "targetId === 'tab-experts'" not in html:
    html = html.replace(js_target, new_js_target, 1)
    print("Added tab-experts to tab click handler.")

# 6. Add JS helper functions before closing script
js_helpers = '''
        // --- EXPERTS & AI REALTIME TESTING ---
        async function runHostAiTest() {
            const btn = document.getElementById('btnHostAiTest');
            const box = document.getElementById('aiTestResultBox');
            if (btn) { btn.disabled = true; btn.textContent = '⏳ Đang kiểm tra...'; }
            try {
                const res = await fetch('/api/host/ai/test', {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    credentials: 'include'
                });
                const d = await res.json();
                if (d.success && d.diagnostics) {
                    const diag = d.diagnostics;
                    box.style.display = 'block';
                    document.getElementById('aiTestTimestamp').textContent = new Date(diag.tested_at).toLocaleTimeString('vi-VN');
                    document.getElementById('aiTestBackend').textContent = diag.active_backend + ' (' + diag.model_version + ')';
                    document.getElementById('aiTestLatency').textContent = diag.latency_ms + ' ms';
                    document.getElementById('aiTestTop').textContent = diag.top_prediction || 'N/A';
                    document.getElementById('aiTestConf').textContent = Math.round((diag.confidence || 0) * 100) + '%';
                    document.getElementById('aiTestGemini').textContent = diag.gemini_assistant_ready ? 'Sẵn sàng (Active)' : 'Chưa cấu hình API Key';
                } else {
                    alert('Lỗi kiểm thử AI: ' + (d.detail || 'Không xác định'));
                }
            } catch (err) {
                alert('Lỗi kết nối máy chủ AI: ' + err.message);
            } finally {
                if (btn) { btn.disabled = false; btn.textContent = '⚡ Chạy Kiểm thử AI Realtime'; }
            }
        }

        async function loadHostExperts() {
            try {
                const [appsRes, expertsRes] = await Promise.all([
                    fetch('/api/host/experts/applications', { credentials: 'include', headers: getAuthHeaders() }),
                    fetch('/api/host/experts?active_only=false', { credentials: 'include', headers: getAuthHeaders() })
                ]);
                
                const appsData = await appsRes.json();
                const expertsData = await expertsRes.json();

                const apps = (appsData.success && appsData.applications) ? appsData.applications : [];
                const experts = (expertsData.success && expertsData.experts) ? expertsData.experts : [];

                const pending = apps.filter(a => a.status === 'pending');
                document.getElementById('expertPendingCount').textContent = pending.length;
                document.getElementById('expertTotalActiveCount').textContent = experts.filter(e => e.is_active).length;

                // Render pending apps
                const appBody = document.getElementById('expertApplicationsTableBody');
                if (apps.length === 0) {
                    appBody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--host-muted);">Chưa có đơn đăng ký chuyên gia nào.</td></tr>';
                } else {
                    appBody.innerHTML = apps.map(a => {
                        const isPending = a.status === 'pending';
                        const badgeColor = isPending ? '#f59e0b' : (a.status === 'approved' ? '#10b981' : '#ef4444');
                        return `
                        <tr>
                            <td>
                                <div style="font-weight:600;">${escapeHtml(a.full_name)}</div>
                                <div style="font-size:12px; color:var(--host-muted);">${escapeHtml(a.email || '')}</div>
                            </td>
                            <td>
                                <div>${escapeHtml(a.title || 'Kỹ sư Nông học')}</div>
                                <div style="font-size:12px; color:var(--host-muted);">${escapeHtml(a.organization || 'Tự do')}</div>
                            </td>
                            <td>
                                <span style="font-size:12px; background:rgba(16,185,129,0.1); color:#10b981; padding:2px 8px; border-radius:10px;">
                                    ${escapeHtml((a.specialties || []).join(', ') || 'Chung')}
                                </span>
                            </td>
                            <td>${a.years_experience || 0} năm</td>
                            <td>${escapeHtml(a.phone || '--')}</td>
                            <td>
                                <div style="font-size:12px; max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(a.degree_details || '')}">
                                    ${escapeHtml(a.degree_details || 'Bằng cử nhân/kỹ sư')}
                                </div>
                            </td>
                            <td>
                                ${isPending ? `
                                    <div style="display:flex; gap:6px;">
                                        <button class="btn-host-action" style="padding:4px 10px; font-size:12px;" onclick="reviewExpertApp(${a.id}, 'approve')">Duyệt</button>
                                        <button class="btn-ghost-sm" style="padding:4px 10px; font-size:12px; color:#ef4444;" onclick="reviewExpertApp(${a.id}, 'reject')">Từ chối</button>
                                    </div>
                                ` : `
                                    <span style="font-size:12px; font-weight:600; color:${badgeColor}; text-transform:uppercase;">${a.status}</span>
                                `}
                            </td>
                        </tr>
                        `;
                    }).join('');
                }

                // Render active experts
                const expBody = document.getElementById('activeExpertsTableBody');
                if (experts.length === 0) {
                    expBody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--host-muted);">Chưa có chuyên gia nào được cấp phép hoạt động.</td></tr>';
                } else {
                    expBody.innerHTML = experts.map(e => {
                        const statusBadge = e.is_active ? 
                            '<span style="color:#10b981; font-weight:600;">Đang hoạt động</span>' : 
                            '<span style="color:#ef4444; font-weight:600;">Tạm dừng</span>';
                        return `
                        <tr>
                            <td>
                                <div style="font-weight:600;">${escapeHtml(e.full_name || 'Chuyên gia GARI')}</div>
                                <div style="font-size:12px; color:var(--host-muted);">${escapeHtml(e.email || '')}</div>
                            </td>
                            <td>${escapeHtml(e.title || 'Bác sĩ Cây trồng')}</td>
                            <td>${escapeHtml((e.specialties || []).join(', ') || 'Đa cây trồng')}</td>
                            <td>${e.total_cases_resolved || 0} ca</td>
                            <td>⭐ ${e.rating || '5.0'} / 5.0</td>
                            <td>${statusBadge}</td>
                            <td>
                                <button class="btn-ghost-sm" style="padding:4px 10px; font-size:12px;" onclick="toggleExpertStatus(${e.id}, ${!e.is_active})">
                                    ${e.is_active ? 'Tạm ngưng' : 'Kích hoạt'}
                                </button>
                            </td>
                        </tr>
                        `;
                    }).join('');
                }

            } catch (err) {
                console.error('Error loading experts:', err);
            }
        }

        async function reviewExpertApp(appId, action) {
            const notes = prompt(`Nhập ghi chú thẩm định (${action === 'approve' ? 'Phê duyệt' : 'Từ chối'}):`, action === 'approve' ? 'Hồ sơ đạt tiêu chuẩn chuyên gia BVTV GARI.' : 'Chưa đủ năm kinh nghiệm thực tế.');
            if (notes === null) return;

            try {
                const res = await fetch(`/api/host/experts/applications/${appId}/review`, {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ action: action, admin_notes: notes, commission_rate: 0.15 })
                });
                const d = await res.json();
                if (d.success) {
                    alert('Đã cập nhật đơn thẩm định thành công!');
                    loadHostExperts();
                } else {
                    alert('Thất bại: ' + (d.detail || 'Lỗi không xác định'));
                }
            } catch (err) {
                alert('Lỗi: ' + err.message);
            }
        }

        async function toggleExpertStatus(expertId, nextState) {
            if (!confirm(`Bạn có chắc muốn ${nextState ? 'kích hoạt' : 'tạm ngưng'} quyền chuyên gia này?`)) return;
            try {
                const res = await fetch(`/api/host/experts/${expertId}/status`, {
                    method: 'PATCH',
                    headers: getAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify({ is_active: nextState })
                });
                const d = await res.json();
                if (d.success) {
                    loadHostExperts();
                } else {
                    alert('Thất bại: ' + (d.detail || 'Lỗi'));
                }
            } catch (err) {
                alert('Lỗi: ' + err.message);
            }
        }
'''

if 'runHostAiTest' not in html:
    closing_script_marker = '</script>'
    last_script_idx = html.rfind(closing_script_marker)
    if last_script_idx != -1:
        html = html[:last_script_idx] + js_helpers + '\n    ' + html[last_script_idx:]
        print("Appended JS helper functions.")

with open('frontend2/host.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Finished upgrading frontend2/host.html!")
