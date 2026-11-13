import sys

with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Chili option
old_chili = '<option value="chili">Ớt (Chili) — Mô hình bệnh chưa sẵn sàng</option>'
new_chili = '<option value="chili">Ớt (Chili / Pepper Bell) — Có mô hình bệnh (Model tong)</option>'
if old_chili in content:
    content = content.replace(old_chili, new_chili, 1)
    print("Updated Chili option in select.")

# 2. Add Low-Confidence Card right above the header or right after header in report-card
header_target = '<h2 style="font-size:22px; font-weight:700; color:var(--text-main); margin:2px 0 0 0;">KẾT QUẢ CHẨN ĐOÁN LÁ</h2>'
low_conf_html = '''<h2 style="font-size:22px; font-weight:700; color:var(--text-main); margin:2px 0 0 0;">KẾT QUẢ CHẨN ĐOÁN LÁ</h2>
                                    </div>
                                    <div style="display:flex; gap:8px; align-items:center;">
                                        <span class="pill pill-info" id="repModePill">Tự động nhận diện</span>
                                        <span class="pill" id="reportSeverityPill">Mức độ</span>
                                    </div>
                                </div>

                                <!-- MODULE 02: LOW CONFIDENCE & UNCERTAINTY WARNING CARD -->
                                <div id="repLowConfidenceCard" style="display:none; margin-bottom:14px; padding:12px 16px; background:rgba(239,68,68,0.06); border:1.5px solid rgba(239,68,68,0.35); border-radius:var(--radius-md);">
                                    <div style="display:flex; align-items:flex-start; gap:10px;">
                                        <span style="font-size:22px; line-height:1;">⚠️</span>
                                        <div style="flex:1;">
                                            <div style="display:flex; align-items:center; justify-content:space-between;">
                                                <div style="font-weight:700; color:var(--danger); font-size:13.5px;">
                                                    ĐỘ TIN CẬY MÔ HÌNH THẤP — CẦN KIỂM TRA THỰC ĐỊA HOẶC CHỤP LẠI
                                                </div>
                                                <span class="pill pill-warning" style="font-size:10px;">Chưa xác minh</span>
                                            </div>
                                            <div id="repLowConfidenceText" style="font-size:12.5px; color:var(--text-secondary); margin-top:4px; line-height:1.5;">
                                                Mô hình AI chưa đủ tin cậy (&lt; 45%) để đưa ra kết luận chắc chắn. Kết quả mang tính tham khảo sơ bộ.
                                            </div>
                                            <div style="display:flex; gap:10px; margin-top:8px; flex-wrap:wrap;">
                                                <button type="button" class="btn btn-sm btn-ghost" id="btnRetakePhotoWarning" style="border:1px solid var(--border); font-size:11.5px;">
                                                    📸 Chụp lại ảnh góc thẳng & đủ sáng
                                                </button>
                                                <button type="button" class="btn btn-sm btn-secondary" id="btnWarningAskExpert" style="font-size:11.5px;">
                                                    🧑‍🌾 Gửi mẫu cho Chuyên gia thẩm định
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>'''

old_header_block = '''<h2 style="font-size:22px; font-weight:700; color:var(--text-main); margin:2px 0 0 0;">KẾT QUẢ CHẨN ĐOÁN LÁ</h2>
                                    </div>
                                    <div style="display:flex; gap:8px; align-items:center;">
                                        <span class="pill pill-info" id="repModePill">Tự động nhận diện</span>
                                        <span class="pill" id="reportSeverityPill">Mức độ</span>
                                    </div>
                                </div>'''

if old_header_block in content:
    content = content.replace(old_header_block, low_conf_html, 1)
    print("Inserted repLowConfidenceCard.")

# 3. Add Follow-up Actions Section right after repSourcesBox
rep_sources_old = '''                                <div class="report-section" id="repSourcesBox" style="display:flex; align-items:center; gap:8px; font-size:12px; color:var(--text-muted); border-top:1px dashed var(--border-light); padding-top:10px;">
                                    <span class="pill pill-success" id="repSourcePill" style="font-size:10.5px;">Nguồn đã xác minh</span>
                                    <span id="repSourceText">Cơ sở tri thức Nông học Gari AI (Ưu tiên biện pháp sinh thái, không quảng bá thuốc)</span>
                                </div>
                            </div>'''

rep_sources_new = '''                                <div class="report-section" id="repSourcesBox" style="display:flex; align-items:center; gap:8px; font-size:12px; color:var(--text-muted); border-top:1px dashed var(--border-light); padding-top:10px;">
                                    <span class="pill pill-success" id="repSourcePill" style="font-size:10.5px;">Nguồn đã xác minh</span>
                                    <span id="repSourceText">Cơ sở tri thức Nông học Gari AI (Ưu tiên biện pháp sinh thái, không quảng bá thuốc)</span>
                                </div>

                                <!-- MODULE 02: FOLLOW-UP ACTIONS TOOLBAR -->
                                <div class="report-section" id="repFollowupActionsSection" style="border-top:1.5px solid var(--border); padding-top:14px; margin-top:8px;">
                                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                                        <span class="report-label" style="color:var(--primary); font-weight:700;">⚡ HÀNH ĐỘNG TIẾP THEO (FOLLOW-UP ACTIONS):</span>
                                        <span style="font-size:11.5px; color:var(--text-muted);">Trực tiếp từ chẩn đoán</span>
                                    </div>
                                    <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:10px;">
                                        <button type="button" class="btn btn-primary" id="btnAskAssistantFollowup" style="display:flex; align-items:center; justify-content:center; gap:8px; font-weight:600; padding:10px 14px; font-size:13px;">
                                            💬 <span>Hỏi Trợ lý AI về kết quả</span>
                                        </button>
                                        <button type="button" class="btn btn-secondary" id="btnCreateTaskFollowup" style="display:flex; align-items:center; justify-content:center; gap:8px; font-weight:600; padding:10px 14px; font-size:13px;">
                                            📋 <span>Tạo công việc vào Lịch</span>
                                        </button>
                                        <button type="button" class="btn btn-secondary" id="btnRequestExpertFollowup" style="display:flex; align-items:center; justify-content:center; gap:8px; font-weight:600; padding:10px 14px; font-size:13px; border-color:rgba(59,130,246,0.4); color:var(--primary);">
                                            🧑‍🌾 <span>Gửi Chuyên gia BVTV thẩm định</span>
                                        </button>
                                    </div>
                                </div>
                            </div>'''

if rep_sources_old in content:
    content = content.replace(rep_sources_old, rep_sources_new, 1)
    print("Inserted repFollowupActionsSection.")

# 4. Add Expert Review Modal near modalTierInfo
modal_tier_marker = '<div class="modal" id="modalTierInfo"'
expert_modal_code = '''    <!-- MODULE 02: EXPERT REVIEW MODAL -->
    <div class="modal" id="modalExpertReview" style="display:none; position:fixed; inset:0; z-index:9999; background:rgba(0,0,0,0.55); align-items:center; justify-content:center; padding:16px;">
        <div class="modal-content" style="background:var(--surface); border-radius:var(--radius-lg); max-width:520px; width:100%; border:1px solid var(--border); box-shadow:0 20px 40px rgba(0,0,0,0.2); overflow:hidden;">
            <div style="padding:16px 20px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; background:var(--surface-muted);">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:20px;">🧑‍🌾</span>
                    <h3 style="margin:0; font-size:16px; font-weight:700; color:var(--text-main);">Gửi Chuyên gia BVTV thẩm định</h3>
                </div>
                <button type="button" class="btn-close" id="btnCloseExpertModal" style="background:none; border:none; font-size:20px; cursor:pointer; color:var(--text-muted);">&times;</button>
            </div>
            <div style="padding:20px;">
                <p style="font-size:13px; color:var(--text-secondary); margin:0 0 14px 0; line-height:1.5;">
                    Mẫu bệnh này sẽ được gửi trực tiếp vào <strong>Cổng Chuyên gia GARI</strong> để kỹ sư bảo vệ thực vật xem xét hình ảnh, phân tích lâm sàng và đưa ra phác đồ điều trị chính xác.
                </p>
                <div style="display:flex; flex-direction:column; gap:12px;">
                    <div>
                        <label style="font-size:12px; font-weight:600; color:var(--text-muted); text-transform:uppercase;">Cây trồng & Dịch hại nghi ngờ</label>
                        <div id="expertModalCropDisease" style="font-size:14px; font-weight:700; color:var(--text-main); margin-top:3px;">-</div>
                    </div>
                    <div>
                        <label for="expertModalSymptoms" style="font-size:12px; font-weight:600; color:var(--text-muted); text-transform:uppercase;">Mô tả triệu chứng thực tế ngoài vườn <span style="color:var(--danger);">*</span></label>
                        <textarea id="expertModalSymptoms" class="input" rows="3" style="width:100%; margin-top:4px; font-size:13px; resize:vertical;" placeholder="Ví dụ: Vết đốm xuất hiện ở tầng lá dưới, lây lan sau cơn mưa 2 ngày..."></textarea>
                    </div>
                    <div id="expertModalAlert" style="display:none; padding:10px 12px; border-radius:8px; font-size:12.5px;"></div>
                </div>
            </div>
            <div style="padding:14px 20px; border-top:1px solid var(--border); background:var(--surface-muted); display:flex; justify-content:flex-end; gap:10px;">
                <button type="button" class="btn btn-secondary" id="btnCancelExpertModal">Hủy</button>
                <button type="button" class="btn btn-primary" id="btnSubmitExpertCase">🚀 Gửi hồ sơ thẩm định</button>
            </div>
        </div>
    </div>\n\n'''

if modal_tier_marker in content and 'id="modalExpertReview"' not in content:
    content = content.replace(modal_tier_marker, expert_modal_code + modal_tier_marker, 1)
    print("Inserted modalExpertReview.")

# 5. Add JS wiring for follow-up actions and low confidence card
# We find `initPlantHealthAssistant(data);` in JS
init_assistant_call = 'initPlantHealthAssistant(data);'
js_wiring = '''initPlantHealthAssistant(data);

            // MODULE 02: Handle Low-Confidence Warning Card
            const lowConfCard = document.getElementById('repLowConfidenceCard');
            const lowConfText = document.getElementById('repLowConfidenceText');
            const numConf = parseFloat(conf) || 0;
            const isUncertain = data.is_uncertain || numConf < 45 || data.status === 'disease_uncertain' || data.diagnosis_status === 'needs_review';
            if (lowConfCard) {
                if (isUncertain) {
                    lowConfCard.style.display = 'block';
                    if (lowConfText) {
                        lowConfText.textContent = data.uncertainty_explanation_vi || 'Mô hình AI chưa đủ tin cậy (< 45%) để đưa ra kết luận chắc chắn. Hãy kiểm tra thực địa hoặc chụp lại ảnh ở cự ly gần dưới ánh sáng tự nhiên.';
                    }
                } else {
                    lowConfCard.style.display = 'none';
                }
            }

            // MODULE 02: Wire Follow-up Action Buttons
            const btnAskFollowup = document.getElementById('btnAskAssistantFollowup');
            if (btnAskFollowup) {
                btnAskFollowup.onclick = () => {
                    const chatCard = document.getElementById('assistantChatCard');
                    if (chatCard) {
                        chatCard.scrollIntoView({ behavior: 'smooth' });
                        const chatInput = document.getElementById('assistantChatInput');
                        if (chatInput) {
                            const dName = data.disease_name_vi || data.prediction || 'bệnh này';
                            const cName = data.crop_name || (typeof data.crop === 'object' ? data.crop.name_vi : data.crop) || 'cây trồng';
                            chatInput.value = `Hãy giải thích chi tiết cơ chế phát sinh bệnh ${dName} trên ${cName} và hướng dẫn phác đồ sinh học an toàn.`;
                            chatInput.focus();
                        }
                    }
                };
            }

            const btnCreateTask = document.getElementById('btnCreateTaskFollowup');
            if (btnCreateTask) {
                btnCreateTask.onclick = async () => {
                    btnCreateTask.disabled = true;
                    btnCreateTask.textContent = 'Đang lưu việc...';
                    try {
                        const farmVal = document.getElementById('farmSelect') ? document.getElementById('farmSelect').value : null;
                        const plotVal = document.getElementById('plotSelect') ? document.getElementById('plotSelect').value : null;
                        const detectedCrop = (typeof data.crop === 'object' && data.crop) ? (data.crop.id || data.crop.name_vi || 'Tomato') : (data.crop_name || data.crop || 'Tomato');
                        const detectedDisease = data.disease_name_vi || data.prediction || 'Bệnh lá';
                        const tomorrow = new Date();
                        tomorrow.setDate(tomorrow.getDate() + 1);
                        const dueDateStr = tomorrow.toISOString().slice(0, 10);

                        const res = await fetch('/api/calendar/tasks', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                title: `Kiểm tra & xử lý: ${detectedDisease} trên ${detectedCrop}`,
                                crop_id: detectedCrop,
                                priority: (numConf > 70) ? 'high' : 'medium',
                                task_type: 'treatment',
                                due_date: dueDateStr,
                                farm_id: farmVal ? parseInt(farmVal) : null,
                                plot_id: plotVal ? parseInt(plotVal) : null,
                                notes: `Tạo từ chẩn đoán Module 02: ${detectedDisease} (Độ tin cậy: ${conf}%)`
                            })
                        });
                        const resJson = await res.json();
                        if (res.ok && resJson.success) {
                            btnCreateTask.className = 'btn btn-primary';
                            btnCreateTask.textContent = '✓ Đã tạo việc vào Lịch';
                            if (window.toast) window.toast('✅ Đã tạo công việc vào Lịch canh tác!');
                            else alert('✅ Đã tạo công việc vào Lịch canh tác!');
                        } else {
                            btnCreateTask.disabled = false;
                            btnCreateTask.textContent = 'Thử lại';
                            alert(resJson.detail || 'Không thể tạo công việc.');
                        }
                    } catch (e) {
                        btnCreateTask.disabled = false;
                        btnCreateTask.textContent = 'Lỗi kết nối';
                    }
                };
            }

            const openExpertModal = () => {
                const modal = document.getElementById('modalExpertReview');
                const cropDiseaseEl = document.getElementById('expertModalCropDisease');
                const alertEl = document.getElementById('expertModalAlert');
                if (modal) {
                    modal.style.display = 'flex';
                    if (cropDiseaseEl) {
                        const dName = data.disease_name_vi || data.prediction || 'Chưa xác định';
                        const cName = data.crop_name || (typeof data.crop === 'object' ? data.crop.name_vi : data.crop) || 'Cây trồng';
                        cropDiseaseEl.textContent = `${cName} — ${dName} (Độ tin cậy mô hình: ${conf}%)`;
                    }
                    if (alertEl) alertEl.style.display = 'none';
                }
            };

            const btnReqExpert = document.getElementById('btnRequestExpertFollowup');
            if (btnReqExpert) btnReqExpert.onclick = openExpertModal;

            const btnWarnExpert = document.getElementById('btnWarningAskExpert');
            if (btnWarnExpert) btnWarnExpert.onclick = openExpertModal;

            const btnRetake = document.getElementById('btnRetakePhotoWarning');
            if (btnRetake) {
                btnRetake.onclick = () => {
                    const dropZone = document.getElementById('dropZone');
                    if (dropZone) dropZone.scrollIntoView({ behavior: 'smooth' });
                    const fileInput = document.getElementById('fileInput');
                    if (fileInput) fileInput.click();
                };
            }'''

if init_assistant_call in content:
    content = content.replace(init_assistant_call, js_wiring, 1)
    print("Inserted JS wiring for follow-ups and low confidence.")

# 6. Wire modalExpertReview events in document ready or end of script
end_script_marker = 'initTierModal();'
expert_modal_js = '''initTierModal();

        // Expert review modal handlers
        (function setupExpertModal() {
            const modal = document.getElementById('modalExpertReview');
            const btnClose = document.getElementById('btnCloseExpertModal');
            const btnCancel = document.getElementById('btnCancelExpertModal');
            const btnSubmit = document.getElementById('btnSubmitExpertCase');
            const alertEl = document.getElementById('expertModalAlert');
            const symptomsInput = document.getElementById('expertModalSymptoms');

            const closeModal = () => {
                if (modal) modal.style.display = 'none';
            };
            if (btnClose) btnClose.onclick = closeModal;
            if (btnCancel) btnCancel.onclick = closeModal;
            if (modal) {
                modal.onclick = (e) => {
                    if (e.target === modal) closeModal();
                };
            }

            if (btnSubmit) {
                btnSubmit.onclick = async () => {
                    const desc = (symptomsInput ? symptomsInput.value.trim() : '') || 'Cần thẩm định thực địa';
                    btnSubmit.disabled = true;
                    btnSubmit.textContent = 'Đang gửi hồ sơ...';
                    if (alertEl) alertEl.style.display = 'none';

                    try {
                        const token = localStorage.getItem('gari_token') || sessionStorage.getItem('gari_token');
                        const headers = { 'Content-Type': 'application/json' };
                        if (token) headers['Authorization'] = `Bearer ${token}`;

                        const farmVal = document.getElementById('farmSelect') ? document.getElementById('farmSelect').value : null;
                        const plotVal = document.getElementById('plotSelect') ? document.getElementById('plotSelect').value : null;
                        const cropVal = document.getElementById('cropSelect') ? document.getElementById('cropSelect').value : null;

                        const payload = {
                            crop_id: cropVal || 'unknown',
                            symptoms_description: desc,
                            predicted_disease: document.getElementById('repDisease') ? document.getElementById('repDisease').textContent : 'Chưa xác định',
                            confidence: parseFloat(document.getElementById('repConfidence') ? document.getElementById('repConfidence').textContent : '0') / 100,
                            diagnosis_id: window.currentDiagnosisId || null,
                            farm_id: farmVal ? parseInt(farmVal) : null,
                            plot_id: plotVal ? parseInt(plotVal) : null
                        };

                        const res = await fetch('/api/expert/cases', {
                            method: 'POST',
                            headers: headers,
                            body: JSON.stringify(payload)
                        });
                        const resJson = await res.json();
                        if (res.ok && resJson.success) {
                            if (alertEl) {
                                alertEl.style.display = 'block';
                                alertEl.style.background = 'rgba(16,185,129,0.1)';
                                alertEl.style.border = '1px solid rgba(16,185,129,0.3)';
                                alertEl.style.color = 'var(--primary)';
                                alertEl.innerHTML = `<strong>Thành công!</strong> Hồ sơ #${resJson.case?.id || ''} đã được chuyển tới chuyên gia BVTV.`;
                            }
                            setTimeout(closeModal, 1800);
                        } else {
                            throw new Error(resJson.detail || 'Không thể gửi hồ sơ thẩm định.');
                        }
                    } catch (e) {
                        if (alertEl) {
                            alertEl.style.display = 'block';
                            alertEl.style.background = 'rgba(239,68,68,0.1)';
                            alertEl.style.border = '1px solid rgba(239,68,68,0.3)';
                            alertEl.style.color = 'var(--danger)';
                            alertEl.textContent = e.message;
                        }
                    } finally {
                        btnSubmit.disabled = false;
                        btnSubmit.textContent = '🚀 Gửi hồ sơ thẩm định';
                    }
                };
            }
        })();'''

if end_script_marker in content:
    content = content.replace(end_script_marker, expert_modal_js, 1)
    print("Inserted expert modal event handlers.")

with open('frontend2/predict.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("frontend2/predict.html patched successfully for Module 02 UI!")
