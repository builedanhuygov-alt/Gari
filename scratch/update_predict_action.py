import sys

with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    content = f.read()

target = """            // Low-Risk Immediate Actions (Sprint 4: prioritize sanitation, isolation, observation)
            const rList = document.getElementById('repRecommendationsList');
            if (rList) {
                const actions = (ag.immediate_low_risk_actions && ag.immediate_low_risk_actions.length) ? ag.immediate_low_risk_actions : (data.recommendations || [
                    'Kiểm tra thêm các lá xung quanh cây trồng.',
                    'Theo dõi sự thay đổi của vết bệnh sau 2-3 ngày.',
                    'Giữ khu vực trồng thông thoáng, tránh tưới đẫm vào chiều muộn.'
                ]);
                rList.innerHTML = actions.map(r => `<li>${r}</li>`).join('');
            }"""

replacement = """            // Low-Risk Immediate Actions (Diagnosis -> Action: 1-click converting to Cultivation Task)
            const rList = document.getElementById('repRecommendationsList');
            if (rList) {
                const actions = (ag.immediate_low_risk_actions && ag.immediate_low_risk_actions.length) ? ag.immediate_low_risk_actions : (data.recommendations || [
                    'Kiểm tra thêm các lá xung quanh cây trồng.',
                    'Theo dõi sự thay đổi của vết bệnh sau 2-3 ngày.',
                    'Giữ khu vực trồng thông thoáng, tránh tưới đẫm vào chiều muộn.'
                ]);
                const detectedCrop = data.crop || data.crop_name || 'Cây trồng';
                const detectedDisease = data.predicted_disease_vi || data.predicted_disease || 'Dịch hại';
                rList.innerHTML = actions.map((r, idx) => `
                    <li style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:8px; padding:8px 12px; background:var(--bg-card); border:1px solid var(--border-color); border-radius:8px;">
                        <span style="flex:1; line-height:1.4; font-size:13px;">${r}</span>
                        <button type="button" class="btn btn-secondary btn-sm btn-create-task-from-rec" id="btnTaskRec_${idx}" style="white-space:nowrap; font-size:11px; padding:4px 8px; flex-shrink:0;">
                            ➕ Tạo việc vào Lịch
                        </button>
                    </li>
                `).join('');

                // Wire up click handlers
                actions.forEach((r, idx) => {
                    const btn = document.getElementById(`btnTaskRec_${idx}`);
                    if (btn) {
                        btn.onclick = async () => {
                            btn.disabled = true;
                            btn.textContent = 'Đang lưu...';
                            try {
                                const farmVal = document.getElementById('farmSelect') ? document.getElementById('farmSelect').value : null;
                                const plotVal = document.getElementById('plotSelect') ? document.getElementById('plotSelect').value : null;
                                const isUrgent = (data.severity === 'high' || (data.confidence || 0) > 0.85);
                                const isTreatment = /phun|thuốc|xử lý|cách ly/i.test(r);
                                
                                const tomorrow = new Date();
                                tomorrow.setDate(tomorrow.getDate() + 1);
                                const dueDateStr = tomorrow.toISOString().slice(0, 10);

                                const res = await fetch('/api/calendar/tasks', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        title: r.length > 80 ? (r.slice(0, 77) + '...') : r,
                                        crop_id: detectedCrop,
                                        priority: isUrgent ? 'high' : 'medium',
                                        task_type: isTreatment ? 'treatment' : 'monitoring',
                                        due_date: dueDateStr,
                                        farm_id: farmVal ? parseInt(farmVal) : null,
                                        plot_id: plotVal ? parseInt(plotVal) : null,
                                        notes: `Tạo từ chẩn đoán: ${detectedDisease} (${Math.round((data.confidence||0)*100)}%)`
                                    })
                                });
                                const json = await res.json();
                                if (res.ok && json.success) {
                                    btn.className = 'btn btn-primary btn-sm';
                                    btn.textContent = '✓ Đã thêm vào Lịch';
                                    if (window.toast) window.toast('✅ Đã tạo công việc vào Lịch canh tác thành công!');
                                } else {
                                    btn.disabled = false;
                                    btn.textContent = 'Thử lại';
                                    alert(json.detail || 'Không thể tạo công việc.');
                                }
                            } catch (e) {
                                btn.disabled = false;
                                btn.textContent = 'Lỗi kết nối';
                            }
                        };
                    }
                });
            }"""

target_crlf = target.replace('\n', '\r\n')
replacement_crlf = replacement.replace('\n', '\r\n')

if target_crlf in content:
    content = content.replace(target_crlf, replacement_crlf, 1)
    with open('frontend2/predict.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: predict.html updated with CRLF")
elif target in content:
    content = content.replace(target, replacement, 1)
    with open('frontend2/predict.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: predict.html updated with LF")
else:
    print("FAILED: Target not found in file")
