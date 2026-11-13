with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update init() to include initPlantHealthAssistantEvents()
old_init_tail = """            initViewerEvents();
            initTierModal();
            loadRecentPlantRecords();
        }"""

new_init_tail = """            initViewerEvents();
            initTierModal();
            loadRecentPlantRecords();
            initPlantHealthAssistantEvents();
            initSecondaryImageHandlers();
        }"""

if old_init_tail in content:
    content = content.replace(old_init_tail, new_init_tail, 1)
    print("Added initPlantHealthAssistantEvents and secondary image init to init()")

# 2. Add secondaryFiles handling in preview setup
old_file_change = """                    reader.onload = e => {
                        document.getElementById('previewImg').src = e.target.result;
                        document.getElementById('previewContainer').style.display = 'block';
                        document.getElementById('dropZone').style.display = 'none';
                    };"""

new_file_change = """                    reader.onload = e => {
                        document.getElementById('previewImg').src = e.target.result;
                        document.getElementById('previewContainer').style.display = 'block';
                        document.getElementById('dropZone').style.display = 'none';
                        const secStrip = document.getElementById('multiImageStrip');
                        if (secStrip) secStrip.style.display = 'block';
                    };"""

if old_file_change in content:
    content = content.replace(old_file_change, new_file_change, 1)
    print("Updated fileInput reader onload")

old_remove_img = """                document.getElementById('previewContainer').style.display = 'none';
                document.getElementById('dropZone').style.display = 'flex';"""

new_remove_img = """                document.getElementById('previewContainer').style.display = 'none';
                document.getElementById('dropZone').style.display = 'flex';
                const secStrip = document.getElementById('multiImageStrip');
                if (secStrip) secStrip.style.display = 'none';
                secondaryFiles = [];
                renderSecondaryThumbnails();"""

if old_remove_img in content:
    content = content.replace(old_remove_img, new_remove_img, 1)
    print("Updated btnRemoveImg handler")

# 3. In runInference: append field observation data
old_run_notes = """            const notesVal = document.getElementById('diagNotes').value;
            if (notesVal) fd.append('notes', notesVal);"""

new_run_notes = """            const notesVal = document.getElementById('diagNotes').value;
            if (notesVal) fd.append('notes', notesVal);

            const growthStageVal = document.getElementById('fieldGrowthStage')?.value;
            if (growthStageVal) fd.append('growth_stage', growthStageVal);

            const userSymptomsVal = document.getElementById('fieldSymptoms')?.value;
            if (userSymptomsVal) fd.append('user_symptoms', userSymptomsVal);

            const fieldConditionsVal = document.getElementById('fieldConditions')?.value;
            if (fieldConditionsVal) fd.append('field_conditions', fieldConditionsVal);

            if (secondaryFiles && secondaryFiles.length > 0) {
                const secMeta = secondaryFiles.map((f, idx) => ({ name: f.name, size: f.size, index: idx }));
                fd.append('image_references', JSON.stringify(secMeta));
            }"""

if old_run_notes in content:
    content = content.replace(old_run_notes, new_run_notes, 1)
    print("Added field observations to runInference")

# 4. In renderDiagnosisReport: call initPlantHealthAssistant(data)
old_report_tail = """            // Refresh recent plant records
            loadRecentPlantRecords();
        }"""

new_report_tail = """            // Refresh recent plant records
            loadRecentPlantRecords();

            // SPRINT 6: Activate Integrated GARI Plant Health Assistant Chatbot
            initPlantHealthAssistant(data);
        }"""

if old_report_tail in content:
    content = content.replace(old_report_tail, new_report_tail, 1)
    print("Added initPlantHealthAssistant(data) call in renderDiagnosisReport")

# 5. Add the complete Assistant Chat logic before the closing </script>
assistant_script_logic = """
        // =========================================================================
        // SPRINT 6: GARI PLANT HEALTH ASSISTANT (INTEGRATED AI DISEASE EXPLAINER)
        // =========================================================================
        let secondaryFiles = [];
        let currentAssistantDiagnosis = null;
        let assistantConversationHistory = [];
        let isDeepDiveMode = false;
        let isAssistantConfigured = false;

        function initSecondaryImageHandlers() {
            const btnAddSec = document.getElementById('btnAddSecondaryImg');
            const secInput = document.getElementById('secondaryFileInput');
            if (!btnAddSec || !secInput) return;

            btnAddSec.onclick = () => secInput.click();
            secInput.onchange = () => {
                if (secInput.files && secInput.files.length > 0) {
                    for (let i = 0; i < secInput.files.length; i++) {
                        if (secondaryFiles.length >= 4) {
                            toast('Tối đa 4 ảnh góc bổ sung cho một lượt khám.');
                            break;
                        }
                        secondaryFiles.push(secInput.files[i]);
                    }
                    secInput.value = '';
                    renderSecondaryThumbnails();
                }
            };
        }

        function renderSecondaryThumbnails() {
            const list = document.getElementById('secondaryImagesList');
            if (!list) return;
            if (secondaryFiles.length === 0) {
                list.innerHTML = '<span style="font-size:11.5px; color:var(--text-muted); font-style:italic;" id="secImgEmptyHint">Chưa có ảnh phụ</span>';
                return;
            }
            list.innerHTML = '';
            secondaryFiles.forEach((file, idx) => {
                const thumb = document.createElement('div');
                thumb.className = 'multi-img-thumb';
                const url = URL.createObjectURL(file);
                thumb.innerHTML = `
                    <img src="${url}" alt="Ảnh phụ ${idx + 1}" />
                    <button type="button" class="btn-del-thumb" title="Xóa ảnh này">✕</button>
                `;
                thumb.querySelector('.btn-del-thumb').onclick = (e) => {
                    e.stopPropagation();
                    secondaryFiles.splice(idx, 1);
                    renderSecondaryThumbnails();
                };
                list.appendChild(thumb);
            });
        }

        function initPlantHealthAssistantEvents() {
            const btnSend = document.getElementById('btnSendAssistantMessage');
            const input = document.getElementById('assistantChatInput');
            const btnDeep = document.getElementById('btnToggleDeepDive');
            const btnReset = document.getElementById('btnResetAssistantChat');

            if (btnSend && input) {
                btnSend.onclick = () => {
                    const text = input.value.trim();
                    if (!text) return;
                    input.value = '';
                    sendAssistantMessage(text);
                };

                input.onkeydown = (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        btnSend.click();
                    }
                };
            }

            if (btnDeep) {
                btnDeep.onclick = () => toggleDeepDive();
            }

            if (btnReset) {
                btnReset.onclick = () => resetAssistantChat();
            }

            // Quick prompts buttons
            document.querySelectorAll('.quick-prompt-pill').forEach(btn => {
                btn.onclick = () => {
                    const prompt = btn.getAttribute('data-prompt');
                    if (prompt) {
                        sendAssistantMessage(prompt);
                    }
                };
            });
        }

        function toggleDeepDive() {
            isDeepDiveMode = !isDeepDiveMode;
            const textEl = document.getElementById('deepDiveStatusText');
            const btnDeep = document.getElementById('btnToggleDeepDive');
            if (textEl && btnDeep) {
                if (isDeepDiveMode) {
                    textEl.textContent = 'Bật';
                    textEl.style.color = 'var(--primary)';
                    btnDeep.style.borderColor = 'var(--primary)';
                    btnDeep.style.background = 'rgba(16,185,129,0.08)';
                    toast('Đã kích hoạt chế độ giải thích bệnh học chuyên sâu.');
                } else {
                    textEl.textContent = 'Tắt';
                    textEl.style.color = 'var(--text-muted)';
                    btnDeep.style.borderColor = 'var(--border)';
                    btnDeep.style.background = 'transparent';
                }
            }
        }

        function resetAssistantChat() {
            assistantConversationHistory = [];
            const container = document.getElementById('assistantChatMessages');
            if (container) container.innerHTML = '';
            if (currentAssistantDiagnosis) {
                renderInitialAssistantGreeting(currentAssistantDiagnosis);
                toast('Đã làm mới phiên hội thoại với Trợ lý AI.');
            }
        }

        async function initPlantHealthAssistant(data) {
            currentAssistantDiagnosis = data;
            assistantConversationHistory = [];
            const card = document.getElementById('assistantChatCard');
            const unconfNotice = document.getElementById('assistantUnconfiguredNotice');
            const badge = document.getElementById('assistantStatusBadge');
            const input = document.getElementById('assistantChatInput');
            const btnSend = document.getElementById('btnSendAssistantMessage');

            if (!card) return;
            card.style.display = 'block';

            // Check public status
            try {
                const res = await fetch('/api/assistant/status');
                if (res.ok) {
                    const statusData = await res.json();
                    isAssistantConfigured = boolHelper(statusData.is_configured);
                    if (!isAssistantConfigured) {
                        if (unconfNotice) unconfNotice.style.display = 'block';
                        if (badge) {
                            badge.className = 'pill pill-warning';
                            badge.textContent = 'Chưa cấu hình API';
                        }
                        if (input) {
                            input.disabled = true;
                            input.placeholder = 'Trợ lý AI chuyên gia chưa được cấu hình. Vui lòng quay lại sau.';
                        }
                        if (btnSend) btnSend.disabled = true;
                        renderUnconfiguredAssistantState();
                        return;
                    } else {
                        if (unconfNotice) unconfNotice.style.display = 'none';
                        if (badge) {
                            badge.className = 'pill pill-success';
                            badge.textContent = 'Sẵn sàng';
                        }
                        if (input) {
                            input.disabled = false;
                            input.placeholder = 'Hỏi thêm Trợ lý AI về vết bệnh này...';
                        }
                        if (btnSend) btnSend.disabled = false;
                    }
                }
            } catch (e) {
                console.warn('Could not check assistant status:', e);
            }

            // Load existing conversation history from server if available
            const diagId = data.diagnosis_id || data.id;
            let loadedHistory = [];
            if (diagId) {
                try {
                    const token = localStorage.getItem('gari_token');
                    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
                    const hRes = await fetch(`/api/assistant/history/${diagId}`, { headers, credentials: 'include' });
                    if (hRes.ok) {
                        const hData = await hRes.json();
                        loadedHistory = hData.history || [];
                    }
                } catch (e) {
                    console.debug('History fetch skipped:', e);
                }
            }

            const messagesContainer = document.getElementById('assistantChatMessages');
            if (messagesContainer) messagesContainer.innerHTML = '';

            if (loadedHistory.length > 0) {
                loadedHistory.forEach(turn => {
                    appendChatBubble('user', turn.user_message);
                    appendChatBubble('assistant', turn.bot_response, turn.actions);
                    assistantConversationHistory.push({ role: 'user', content: turn.user_message });
                    assistantConversationHistory.push({ role: 'assistant', content: turn.bot_response });
                });
            } else {
                renderInitialAssistantGreeting(data);
            }
        }

        function boolHelper(val) {
            return val === true || val === 'true' || val === 1 || val === '1';
        }

        function renderUnconfiguredAssistantState() {
            const container = document.getElementById('assistantChatMessages');
            if (!container) return;
            container.innerHTML = `
                <div class="chat-bubble-bot" style="border-left:3px solid var(--warning);">
                    <p><strong>Trợ lý AI chuyên gia chưa được cấu hình. Vui lòng quay lại sau.</strong></p>
                    <p style="font-size:12px; color:var(--text-secondary); margin-top:4px;">
                        Tính năng giải thích bệnh học tự động qua mô hình ngôn ngữ lớn đang tạm ngừng trên máy chủ. Bạn vẫn có thể sử dụng đầy đủ kết quả chẩn đoán thị giác máy tính và khuyến nghị nông học sẵn có ở bảng bên trên.
                    </p>
                </div>
            `;
        }

        function renderInitialAssistantGreeting(data) {
            const container = document.getElementById('assistantChatMessages');
            if (!container) return;

            const crop = data.crop_name_vi || data.crop_name || data.crop || 'Cây trồng';
            const disease = data.disease_name_vi || data.prediction || 'Mầm bệnh';
            const conf = data.disease_score != null ? (data.disease_score * 100).toFixed(1) : (data.confidence != null ? (data.confidence * 100).toFixed(1) : '95.0');
            const isHealthy = (data.class_id && data.class_id.toLowerCase().includes('healthy')) || data.severity === 'HEALTHY' || data.is_healthy;
            const rCount = (data.regions || []).length;

            let greeting = '';
            if (isHealthy) {
                greeting = `
                    <p>Chào bạn, tôi là <strong>GARI Plant Health Assistant</strong>. 🍃</p>
                    <p>Mô hình thị giác máy tính xác định mẫu lá <strong>${crop}</strong> này <strong>khỏe mạnh</strong> (độ tin cậy: ${conf}%). Không phát hiện vết bệnh hay đốm hoại tử khu trú.</p>
                    <p>Bạn có thể bấm vào các gợi ý bên dưới hoặc đặt câu hỏi để tôi hướng dẫn cách chăm sóc phòng ngừa sinh học!</p>
                `;
            } else {
                greeting = `
                    <p>Chào bạn, tôi là <strong>GARI Plant Health Assistant</strong>. Tôi đã sẵn sàng phân tích chuyên sâu hồ sơ chẩn đoán này cùng bạn.</p>
                    <p>📌 <strong>Tổng hợp nhận diện:</strong></p>
                    <ul>
                        <li>Cây trồng: <strong>${crop}</strong></li>
                        <li>Bệnh nghi ngờ: <strong>${disease}</strong> (Độ tương đồng mô hình: <strong>${conf}%</strong>)</li>
                        <li>Tiêu điểm chú ý Grad-CAM: Phát hiện <strong>${rCount} vùng nghi vấn tổn thương</strong> trên phiến lá.</li>
                    </ul>
                    <p>Bạn cần tôi giải thích thêm về dấu hiệu đốm bệnh, mầm bệnh dễ nhầm lẫn hay các bước kiểm tra ngoài vườn trước tiên?</p>
                `;
            }

            const bubble = document.createElement('div');
            bubble.className = 'chat-bubble-bot';
            bubble.innerHTML = greeting;
            container.appendChild(bubble);
        }

        async function sendAssistantMessage(userText) {
            if (!currentAssistantDiagnosis) {
                toast('Vui lòng thực hiện kiểm tra lá trước khi hỏi Trợ lý AI.');
                return;
            }
            if (!isAssistantConfigured) {
                toast('Trợ lý AI chuyên gia chưa được cấu hình. Vui lòng quay lại sau.');
                return;
            }

            const diagId = currentAssistantDiagnosis.diagnosis_id || currentAssistantDiagnosis.id;
            const container = document.getElementById('assistantChatMessages');
            const input = document.getElementById('assistantChatInput');
            const btnSend = document.getElementById('btnSendAssistantMessage');

            // 1. Render User message
            appendChatBubble('user', userText);

            // 2. Render typing indicator
            const typingBubble = document.createElement('div');
            typingBubble.className = 'chat-bubble-bot';
            typingBubble.id = 'assistantTypingIndicator';
            typingBubble.innerHTML = `
                <div style="display:flex; align-items:center; gap:8px; color:var(--text-secondary); font-size:12.5px;">
                    <span class="status-dot"></span> Đang phân tích dữ liệu bệnh học & thực địa...
                </div>
            `;
            container.appendChild(typingBubble);
            container.scrollTop = container.scrollHeight;

            if (input) input.disabled = true;
            if (btnSend) btnSend.disabled = true;

            // 3. Prepare payload
            const fieldCtx = {
                growth_stage: document.getElementById('fieldGrowthStage')?.value || '',
                user_symptoms: document.getElementById('fieldSymptoms')?.value || '',
                field_conditions: document.getElementById('fieldConditions')?.value || '',
                notes: document.getElementById('diagNotes')?.value || ''
            };

            const payload = {
                diagnosis_id: Number(diagId),
                message: userText,
                conversation_history: assistantConversationHistory,
                field_context: fieldCtx,
                deep_dive: isDeepDiveMode
            };

            try {
                const token = localStorage.getItem('gari_token');
                const headers = { 'Content-Type': 'application/json' };
                if (token) headers['Authorization'] = `Bearer ${token}`;

                const res = await fetch('/api/assistant/chat', {
                    method: 'POST',
                    headers: headers,
                    credentials: 'include',
                    body: JSON.stringify(payload)
                });

                const data = await res.json();
                typingBubble.remove();

                if (!res.ok || !data.success) {
                    const errMsg = data.reply || data.detail || 'Không thể nhận phản hồi từ Trợ lý AI.';
                    appendChatBubble('assistant', errMsg);
                    toast(errMsg);
                    return;
                }

                // Append assistant reply and actions
                appendChatBubble('assistant', data.reply, data.actions);

                // Update conversation history
                assistantConversationHistory.push({ role: 'user', content: userText });
                assistantConversationHistory.push({ role: 'assistant', content: data.reply });

            } catch (err) {
                typingBubble.remove();
                appendChatBubble('assistant', 'Lỗi kết nối đến máy chủ Trợ lý AI. Vui lòng thử lại sau.');
                console.error('Assistant error:', err);
            } finally {
                if (input) {
                    input.disabled = false;
                    input.focus();
                }
                if (btnSend) btnSend.disabled = false;
            }
        }

        function appendChatBubble(role, text, actions = null) {
            const container = document.getElementById('assistantChatMessages');
            if (!container) return;

            const bubble = document.createElement('div');
            if (role === 'user') {
                bubble.className = 'chat-bubble-user';
                bubble.textContent = text;
            } else {
                bubble.className = 'chat-bubble-bot';
                bubble.innerHTML = formatAssistantMarkdown(text);

                // Render Action proposal cards if present
                if (actions && Array.isArray(actions) && actions.length > 0) {
                    actions.forEach((act, actIdx) => {
                        const actCard = document.createElement('div');
                        actCard.className = 'action-proposal-card';
                        actCard.innerHTML = `
                            <div class="action-proposal-header">
                                <span class="action-proposal-title">
                                    <span>📅 Đề xuất công việc theo dõi</span>
                                </span>
                                <span class="pill pill-info" style="font-size:10px; text-transform:uppercase;">${act.priority || 'Trung bình'}</span>
                            </div>
                            <div style="font-size:13px; font-weight:700; color:var(--text-main); margin-top:2px;">
                                ${act.title}
                            </div>
                            <div style="font-size:12px; color:var(--text-secondary); line-height:1.4;">
                                ${act.description || 'Thực hiện theo dõi và kiểm tra vết bệnh ngoài đồng ruộng.'}
                            </div>
                            <div class="action-proposal-meta">
                                <span>Hạn thực hiện: <strong>${act.due_date || 'Sau 48h'}</strong></span>
                                <span>Phân loại: <strong>${act.task_type || 'Kiểm tra'}</strong></span>
                            </div>
                            <div style="margin-top:4px;">
                                <button type="button" class="btn btn-primary btn-sm btn-confirm-assistant-action" id="btnConfirmAct_${Date.now()}_${actIdx}" style="width:100%; font-size:12px; font-weight:700;">
                                    ✓ Xác nhận & Thêm vào Lịch canh tác
                                </button>
                            </div>
                        `;
                        const btnConfirm = actCard.querySelector('.btn-confirm-assistant-action');
                        btnConfirm.onclick = () => confirmAssistantAction(act, btnConfirm);
                        bubble.appendChild(actCard);
                    });
                }
            }

            container.appendChild(bubble);
            container.scrollTop = container.scrollHeight;
        }

        async function confirmAssistantAction(actionDraft, btnEl) {
            if (!currentAssistantDiagnosis) return;
            const diagId = currentAssistantDiagnosis.diagnosis_id || currentAssistantDiagnosis.id;
            btnEl.disabled = true;
            btnEl.textContent = 'Đang lưu vào Lịch canh tác...';

            try {
                const token = localStorage.getItem('gari_token');
                const headers = { 'Content-Type': 'application/json' };
                if (token) headers['Authorization'] = `Bearer ${token}`;

                const res = await fetch('/api/assistant/action/confirm', {
                    method: 'POST',
                    headers: headers,
                    credentials: 'include',
                    body: JSON.stringify({
                        diagnosis_id: Number(diagId),
                        action_draft: actionDraft
                    })
                });

                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.detail || 'Không thể tạo công việc.');
                }

                btnEl.textContent = '✓ Đã thêm vào Lịch canh tác';
                btnEl.style.background = '#10b981';
                btnEl.style.borderColor = '#10b981';
                toast('Đã thêm công việc vào Lịch canh tác thông minh thành công!');

            } catch (err) {
                btnEl.disabled = false;
                btnEl.textContent = 'Thử lại việc lưu';
                toast(err.message || 'Lỗi khi lưu công việc.');
            }
        }

        function formatAssistantMarkdown(md) {
            if (!md) return '';
            let s = md
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');

            // Bold **text**
            s = s.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
            // Italic *text*
            s = s.replace(/\\*(.*?)\\*/g, '<em>$1</em>');

            // Paragraphs & lines
            const lines = s.split('\\n');
            let html = '';
            let inList = false;

            for (let line of lines) {
                const trimmed = line.trim();
                if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                    if (!inList) {
                        html += '<ul>';
                        inList = true;
                    }
                    html += `<li>${trimmed.substring(2)}</li>`;
                } else if (/^\\d+\\.\\s/.test(trimmed)) {
                    if (!inList) {
                        html += '<ol>';
                        inList = true;
                    }
                    html += `<li>${trimmed.replace(/^\\d+\\.\\s/, '')}</li>`;
                } else {
                    if (inList) {
                        html += '</ul>';
                        inList = false;
                    }
                    if (trimmed.length > 0) {
                        html += `<p>${trimmed}</p>`;
                    }
                }
            }
            if (inList) html += '</ul>';
            return html;
        }
"""

if "SPRINT 6: GARI PLANT HEALTH ASSISTANT" not in content:
    content = content.replace("</script>", assistant_script_logic + "\n    </script>", 1)
    print("Added complete Assistant Chat logic to script")

with open('frontend2/predict.html', 'w', encoding='utf-8', newline='') as f:
    f.write(content)
print("Done updating predict.html JavaScript")
