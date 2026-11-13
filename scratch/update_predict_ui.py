import re

with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update <title>
content = re.sub(
    r'<title>.*?</title>',
    '<title>GARI Leaf Intelligence • Chẩn đoán & Trợ lý Sức khỏe Lá</title>',
    content,
    count=1
)

# 2. Add CSS styles before </style>
assistant_css = """
        /* GARI Leaf Intelligence & Assistant Chatbot Styles */
        .field-observation-accordion summary {
            list-style: none;
            user-select: none;
        }
        .field-observation-accordion summary::-webkit-details-marker {
            display: none;
        }
        .quick-prompt-pill {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 6px 12px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 99px;
            font-size: 11.5px;
            font-weight: 600;
            color: var(--text-secondary);
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s ease;
            flex-shrink: 0;
        }
        .quick-prompt-pill:hover {
            border-color: var(--primary);
            color: var(--primary);
            background: rgba(16, 185, 129, 0.08);
            transform: translateY(-1px);
        }
        .chat-bubble-user {
            align-self: flex-end;
            background: var(--primary);
            color: #ffffff;
            padding: 10px 14px;
            border-radius: 14px 14px 2px 14px;
            font-size: 13px;
            line-height: 1.5;
            max-width: 82%;
            box-shadow: 0 2px 8px rgba(16, 185, 129, 0.2);
            word-break: break-word;
        }
        .chat-bubble-bot {
            align-self: flex-start;
            background: var(--surface-muted);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 12px 16px;
            border-radius: 14px 14px 14px 2px;
            font-size: 13px;
            line-height: 1.6;
            max-width: 90%;
            word-break: break-word;
        }
        .chat-bubble-bot p {
            margin: 0 0 8px 0;
        }
        .chat-bubble-bot p:last-child {
            margin-bottom: 0;
        }
        .chat-bubble-bot ul, .chat-bubble-bot ol {
            margin: 6px 0;
            padding-left: 20px;
        }
        .chat-bubble-bot li {
            margin-bottom: 4px;
        }
        .chat-bubble-bot strong {
            color: var(--text-main);
        }
        .action-proposal-card {
            background: rgba(16, 185, 129, 0.08);
            border: 1.5px solid rgba(16, 185, 129, 0.35);
            border-radius: 10px;
            padding: 12px 14px;
            margin-top: 10px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .action-proposal-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }
        .action-proposal-title {
            font-size: 13px;
            font-weight: 700;
            color: var(--primary);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .action-proposal-meta {
            font-size: 11.5px;
            color: var(--text-secondary);
            display: flex;
            gap: 10px;
        }
        .multi-img-thumb {
            position: relative;
            width: 58px;
            height: 58px;
            border-radius: 8px;
            border: 1.5px solid var(--border);
            overflow: hidden;
            flex-shrink: 0;
            cursor: pointer;
        }
        .multi-img-thumb img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .multi-img-thumb .btn-del-thumb {
            position: absolute;
            top: 2px;
            right: 2px;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: rgba(0,0,0,0.6);
            color: #fff;
            border: none;
            font-size: 10px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
"""

if "/* GARI Leaf Intelligence & Assistant Chatbot Styles */" not in content:
    content = content.replace("</style>", assistant_css + "\n    </style>", 1)
    print("Added Assistant CSS")

# 3. Add Multi-image strip right below previewContainer
preview_target = """                            <div class="image-preview-box" id="previewContainer">
                                <img id="previewImg" src="" alt="Xem trước mẫu lá" />
                                <button type="button" class="btn-remove-preview" id="btnRemoveImg" title="Xóa ảnh">✕</button>
                            </div>"""

multi_img_markup = """                            <div class="image-preview-box" id="previewContainer">
                                <img id="previewImg" src="" alt="Xem trước mẫu lá" />
                                <button type="button" class="btn-remove-preview" id="btnRemoveImg" title="Xóa ảnh">✕</button>
                            </div>

                            <!-- Multi-image thumbnails strip for underside & additional leaves -->
                            <div id="multiImageStrip" style="margin-top:12px; display:none; padding:10px 12px; background:var(--surface-muted); border-radius:var(--radius-sm); border:1px solid var(--border-light);">
                                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                                    <span style="font-size:12px; font-weight:700; color:var(--text-main);">📸 Ảnh góc bổ sung (Mặt dưới / Toàn tán):</span>
                                    <button type="button" class="btn btn-ghost btn-sm" id="btnAddSecondaryImg" style="font-size:11px; padding:2px 8px; border:1px solid var(--border);">+ Thêm ảnh</button>
                                </div>
                                <div id="secondaryImagesList" style="display:flex; gap:8px; overflow-x:auto; padding-bottom:4px; align-items:center;">
                                    <span style="font-size:11.5px; color:var(--text-muted); font-style:italic;" id="secImgEmptyHint">Chưa có ảnh phụ</span>
                                </div>
                                <input type="file" id="secondaryFileInput" accept="image/*" multiple style="display:none;" />
                            </div>"""

if preview_target in content and 'id="multiImageStrip"' not in content:
    content = content.replace(preview_target, multi_img_markup, 1)
    print("Added multi-image markup")

# 4. Add Section C (Field observation accordion) before diagNotes or btnPredict
diag_notes_target = """                            <div class="form-group">
                                <label class="form-label" for="diagNotes">Ghi chú quan sát thực địa</label>
                                <input type="text" class="input" id="diagNotes" placeholder="VD: Tầng lá thấp, xuất hiện sau mưa rào 2 ngày..." />
                            </div>"""

field_obs_markup = """                            <!-- SECTION C: KHAI BÁO THỰC ĐỊA BỔ SUNG (ACCORDION / COMPACT) -->
                            <details class="field-observation-accordion" id="fieldObservationDetails" style="background:var(--surface-muted); border:1px solid var(--border); border-radius:var(--radius-md); padding:10px 14px; margin-bottom:14px;">
                                <summary style="font-size:12.5px; font-weight:700; color:var(--text-main); cursor:pointer; display:flex; align-items:center; justify-content:space-between;">
                                    <span>🌿 Thông tin thực địa bổ sung</span>
                                    <span class="pill pill-info" style="font-size:10px; padding:1px 6px;">Tăng độ chuẩn xác</span>
                                </summary>
                                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px;">
                                    <div class="form-group" style="margin-bottom:0;">
                                        <label class="form-label" style="font-size:11.5px; font-weight:600;">Giai đoạn sinh trưởng</label>
                                        <select class="select" id="fieldGrowthStage" style="font-size:12px; padding:6px 10px;">
                                            <option value="">-- Chưa xác định --</option>
                                            <option value="Cây con / Ươm mầm">Cây con / Ươm mầm</option>
                                            <option value="Phát triển thân lá / Đẻ nhánh">Phát triển thân lá / Đẻ nhánh</option>
                                            <option value="Ra hoa / Đậu quả">Ra hoa / Đậu quả</option>
                                            <option value="Nuôi củ / Nuôi quả chín">Nuôi củ / Nuôi quả chín</option>
                                            <option value="Thu hoạch / Phục hồi sau thu hoạch">Thu hoạch / Phục hồi sau thu hoạch</option>
                                        </select>
                                    </div>
                                    <div class="form-group" style="margin-bottom:0;">
                                        <label class="form-label" style="font-size:11.5px; font-weight:600;">Triệu chứng nổi bật</label>
                                        <input type="text" class="input" id="fieldSymptoms" placeholder="VD: Đốm cháy lá có quầng vàng..." style="font-size:12px; padding:6px 10px;" />
                                    </div>
                                </div>
                                <div class="form-group" style="margin-top:10px; margin-bottom:0;">
                                    <label class="form-label" style="font-size:11.5px; font-weight:600;">Thời tiết & Chăm sóc gần đây</label>
                                    <input type="text" class="input" id="fieldConditions" placeholder="VD: Mưa liên tục 3 ngày, vừa bón đạm cao..." style="font-size:12px; padding:6px 10px;" />
                                </div>
                            </details>

                            <div class="form-group">
                                <label class="form-label" for="diagNotes">Ghi chú quan sát thực địa</label>
                                <input type="text" class="input" id="diagNotes" placeholder="VD: Tầng lá thấp, xuất hiện sau mưa rào 2 ngày..." />
                            </div>"""

if diag_notes_target in content and 'id="fieldObservationDetails"' not in content:
    content = content.replace(diag_notes_target, field_obs_markup, 1)
    print("Added Section C field observation markup")

# 5. Add Section E (Integrated Assistant Chatbot card) before diagnosisFeedbackCard
feedback_target = """                        <!-- SPRINT 5: DIAGNOSIS FEEDBACK WIDGET (Pilot Feedback Loop) -->
                        <div class="card" id="diagnosisFeedbackCard" """

assistant_card_markup = """                        <!-- ========================================================================= -->
                        <!-- SECTION E: GARI PLANT HEALTH ASSISTANT (INTEGRATED AI CHATBOT)            -->
                        <!-- ========================================================================= -->
                        <div class="card assistant-chat-card" id="assistantChatCard" style="display:none; margin-top:16px; border:1.5px solid rgba(16,185,129,0.3); border-radius:var(--radius-lg); overflow:hidden; background:var(--surface); box-shadow:0 8px 30px rgba(0,0,0,0.04);">
                            <!-- Chatbot Header -->
                            <div style="display:flex; justify-content:space-between; align-items:center; padding:14px 18px; background:linear-gradient(135deg, rgba(16,185,129,0.08) 0%, rgba(59,130,246,0.04) 100%); border-bottom:1px solid var(--border); flex-wrap:wrap; gap:10px;">
                                <div style="display:flex; align-items:center; gap:10px;">
                                    <div style="width:36px; height:36px; border-radius:10px; background:var(--primary); color:#fff; display:flex; align-items:center; justify-content:center; font-size:18px; box-shadow:0 2px 8px rgba(16,185,129,0.3);">
                                        🩺
                                    </div>
                                    <div>
                                        <div style="display:flex; align-items:center; gap:8px;">
                                            <span style="font-size:14.5px; font-weight:800; color:var(--text-main);">GARI Plant Health Assistant</span>
                                            <span id="assistantStatusBadge" class="pill pill-success" style="font-size:10.5px;">Sẵn sàng</span>
                                        </div>
                                        <div style="font-size:11.5px; color:var(--text-secondary); margin-top:1px;">
                                            Trợ lý AI giải thích bệnh học thực địa & Hỗ trợ lập lịch canh tác IPM
                                        </div>
                                    </div>
                                </div>
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <button type="button" class="btn btn-ghost btn-sm" id="btnToggleDeepDive" title="Bật/Tắt giải thích bệnh học chuyên sâu" style="font-size:11.5px; padding:4px 10px; border:1px solid var(--border);">
                                        🔬 Chuyên sâu: <strong id="deepDiveStatusText" style="color:var(--text-muted); margin-left:3px;">Tắt</strong>
                                    </button>
                                    <button type="button" class="btn btn-ghost btn-sm" id="btnResetAssistantChat" title="Bắt đầu phân tích mới" style="font-size:11.5px; padding:4px 10px; border:1px solid var(--border);">
                                        🔄 Phân tích mới
                                    </button>
                                </div>
                            </div>

                            <!-- Unconfigured Banner (Hidden by default, shown if API not configured) -->
                            <div id="assistantUnconfiguredNotice" style="display:none; padding:14px 18px; background:rgba(245,158,11,0.08); border-bottom:1px solid rgba(245,158,11,0.3); color:#d97706; font-size:13px; line-height:1.5;">
                                <div style="display:flex; align-items:flex-start; gap:10px;">
                                    <span style="font-size:20px; line-height:1;">⚙️</span>
                                    <div>
                                        <strong>Trợ lý AI chuyên gia chưa được cấu hình.</strong> Vui lòng quay lại sau hoặc liên hệ ban quản trị để kích hoạt nhà cung cấp AI trong Host Console.
                                    </div>
                                </div>
                            </div>

                            <!-- Conversation Feed Container -->
                            <div id="assistantChatMessages" style="padding:18px 20px; max-height:450px; overflow-y:auto; display:flex; flex-direction:column; gap:14px; background:var(--surface);">
                                <!-- Messages dynamically rendered here -->
                            </div>

                            <!-- Contextual Quick Prompts Pills -->
                            <div id="assistantQuickPrompts" style="padding:8px 18px 12px 18px; border-top:1px solid var(--border-light); background:var(--surface-muted); display:flex; gap:6px; overflow-x:auto; white-space:nowrap;">
                                <button type="button" class="quick-prompt-pill" data-prompt="Giải thích bệnh này dễ hiểu cho nông dân giúp tôi.">💡 Giải thích dễ hiểu</button>
                                <button type="button" class="quick-prompt-pill" data-prompt="Dấu hiệu nào trên ảnh và vùng Grad-CAM cho thấy bệnh này?">🔍 Dấu hiệu trên ảnh</button>
                                <button type="button" class="quick-prompt-pill" data-prompt="Mầm bệnh này có thể bị nhầm lẫn với bệnh nào khác?">⚠️ Bệnh dễ nhầm lẫn</button>
                                <button type="button" class="quick-prompt-pill" data-prompt="Tôi nên thực hiện biện pháp sinh học hoặc canh tác gì trước tiên?">🌱 Xử lý trước mắt</button>
                                <button type="button" class="quick-prompt-pill" data-prompt="Cần theo dõi vết bệnh trong 48h tới như thế nào?">📅 Kế hoạch theo dõi 48h</button>
                                <button type="button" class="quick-prompt-pill" data-prompt="Tôi có cần chụp thêm ảnh góc khác hoặc mặt dưới lá không?">📸 Khi nào cần chụp lại?</button>
                            </div>

                            <!-- Chat Input Area -->
                            <div style="padding:12px 18px; border-top:1px solid var(--border); background:var(--surface); display:flex; gap:10px; align-items:center;">
                                <input type="text" id="assistantChatInput" class="input" placeholder="Hỏi thêm Trợ lý AI về kết quả chẩn đoán này..." style="flex:1; font-size:13px; padding:10px 14px;" />
                                <button type="button" class="btn btn-primary" id="btnSendAssistantMessage" style="font-weight:700; display:inline-flex; align-items:center; gap:6px; padding:10px 18px;">
                                    <span>Gửi</span>
                                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                                </button>
                            </div>
                        </div>

                        <!-- SPRINT 5: DIAGNOSIS FEEDBACK WIDGET (Pilot Feedback Loop) -->
                        <div class="card" id="diagnosisFeedbackCard" """

if feedback_target in content and 'id="assistantChatCard"' not in content:
    content = content.replace(feedback_target, assistant_card_markup, 1)
    print("Added Section E assistant chat card markup")

# 6. Unify init() in <script type="module">
old_init_block = """            const isLeafMode = urlParams.get('mode') === 'leaf';
            if (isLeafMode) {
                setupSaaSShell('leaf_check', 'Kiểm tra sức khỏe lá');
                document.title = 'Kiểm tra sức khỏe lá • Bác Sĩ Cây Trồng AI';
                const headlineEl = document.querySelector('.doctor-headline');
                if (headlineEl) headlineEl.textContent = 'Kiểm tra sức khỏe lá';
                const h1El = document.querySelector('h1.page-head-title') || document.querySelector('h1');
                if (h1El) h1El.textContent = 'Kiểm tra sức khỏe lá';
            } else {
                setupSaaSShell('predict', 'Trợ Lý Sức Khỏe Cây Trồng');
            }"""

new_init_block = """            setupSaaSShell('predict', 'GARI Leaf Intelligence');
            document.title = 'GARI Leaf Intelligence • Chẩn đoán & Trợ lý Sức khỏe Lá';
            const headlineEl = document.querySelector('.doctor-headline');
            if (headlineEl) headlineEl.textContent = 'GARI Leaf Intelligence';
            const h1El = document.querySelector('h1.page-head-title') || document.querySelector('h1');
            if (h1El) h1El.textContent = 'GARI Leaf Intelligence';"""

if old_init_block in content:
    content = content.replace(old_init_block, new_init_block, 1)
    print("Unified init() shell and titles")

with open('frontend2/predict.html', 'w', encoding='utf-8', newline='') as f:
    f.write(content)
print("Done updating predict.html markup and styles")
