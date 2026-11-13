with open('frontend2/host.html', 'r', encoding='utf-8') as f:
    html = f.read()

js_to_add = '''
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

                const pending = apps.filter(a => a.status === 'pending' || a.status === 'submitted');
                document.getElementById('expertPendingCount').textContent = pending.length;
                document.getElementById('expertTotalActiveCount').textContent = experts.filter(e => e.is_active).length;

                // Render pending apps
                const appBody = document.getElementById('expertApplicationsTableBody');
                if (apps.length === 0) {
                    appBody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--host-muted);">Chưa có đơn đăng ký chuyên gia nào.</td></tr>';
                } else {
                    appBody.innerHTML = apps.map(a => {
                        const isPending = a.status === 'pending' || a.status === 'submitted';
                        const badgeColor = isPending ? '#f59e0b' : (a.status === 'approved' ? '#10b981' : '#ef4444');
                        return `
                        <tr>
                            <td>
                                <div style="font-weight:600;">${escapeHtml(a.full_name)}</div>
                                <div style="font-size:12px; color:var(--host-muted);">${escapeHtml(a.email || '')}</div>
                            </td>
                            <td>
                                <div>${escapeHtml(a.title || a.specialization || 'Kỹ sư Nông học')}</div>
                                <div style="font-size:12px; color:var(--host-muted);">${escapeHtml(a.institution || a.organization || 'Tự do')}</div>
                            </td>
                            <td>
                                <span style="font-size:12px; background:rgba(16,185,129,0.1); color:#10b981; padding:2px 8px; border-radius:10px;">
                                    ${escapeHtml((a.primary_crops || a.specialties || []).join(', ') || 'Chung')}
                                </span>
                            </td>
                            <td>${a.years_experience || 5} năm</td>
                            <td>${escapeHtml(a.phone || '--')}</td>
                            <td>
                                <div style="font-size:12px; max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(a.degree || a.degree_details || '')}">
                                    ${escapeHtml(a.degree || a.degree_details || 'Bằng cử nhân/kỹ sư')}
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
                            <td>${escapeHtml(e.display_title || e.title || 'Bác sĩ Cây trồng')}</td>
                            <td>${escapeHtml((e.primary_crops || e.specialties || []).join(', ') || 'Đa cây trồng')}</td>
                            <td>${e.cases_resolved_count || 0} ca</td>
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

last_script_idx = html.rfind('</script>')
if last_script_idx != -1:
    html = html[:last_script_idx] + js_to_add + '\n    ' + html[last_script_idx:]
    with open('frontend2/host.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Appended JS helper functions to frontend2/host.html successfully!")
else:
    print("Could not find closing script tag.")
