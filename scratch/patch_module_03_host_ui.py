from pathlib import Path

path = Path("frontend2/host.html")
content = path.read_text(encoding="utf-8")

# 1. Add Assistant Provider Manager HTML card inside tab-api
target_table_end = '''                </table>
            </div>
        </section>'''

assistant_card_html = '''                </table>
            </div>

            <!-- MODULE 03: CONTEXTUAL AI ASSISTANT PROVIDER MANAGER -->
            <div class="card" style="margin-top:24px; padding:20px; background:var(--host-surface); border:1px solid var(--host-border); border-radius:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                    <div>
                        <h3 style="margin:0; font-size:16px; font-weight:700; color:var(--host-text);">🩺 Quản lý AI Provider cho Trợ lý Nông học (Contextual AI Assistant)</h3>
                        <p style="margin:4px 0 0 0; font-size:12.5px; color:var(--host-muted);">Cấu hình nhà cung cấp LLM (Gemini, OpenAI, Anthropic, Mock), khóa bí mật và thông số suy luận.</p>
                    </div>
                    <span id="hostAssistantStatusPill" class="host-pill host-pill-gray">Đang tải...</span>
                </div>

                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:16px;">
                    <div>
                        <label style="font-size:12px; font-weight:600; color:var(--host-muted);">AI PROVIDER</label>
                        <select id="hostAssistantProviderSelect" class="input" style="width:100%; margin-top:4px;">
                            <option value="disabled">Disabled (Tắt trợ lý)</option>
                            <option value="gemini">Google Gemini (Khuyến nghị)</option>
                            <option value="openai_compatible">OpenAI-Compatible (GPT-4o / vLLM / Ollama)</option>
                            <option value="anthropic">Anthropic (Claude 3.5)</option>
                            <option value="mock">Mock / Offline Engine (Testing)</option>
                        </select>
                    </div>
                    <div>
                        <label style="font-size:12px; font-weight:600; color:var(--host-muted);">MÔ HÌNH (MODEL NAME)</label>
                        <input id="hostAssistantModelInput" class="input" style="width:100%; margin-top:4px;" placeholder="gemini-2.5-flash / gpt-4o-mini" />
                    </div>
                    <div>
                        <label style="font-size:12px; font-weight:600; color:var(--host-muted);">API KEY (LƯU TRÊN MÁY CHỦ BẢO MẬT)</label>
                        <input id="hostAssistantApiKeyInput" type="password" class="input" style="width:100%; margin-top:4px;" placeholder="Nhập API key mới hoặc để trống để giữ nguyên" />
                    </div>
                    <div>
                        <label style="font-size:12px; font-weight:600; color:var(--host-muted);">BASE URL (CHO OPENAI / OLLAMA)</label>
                        <input id="hostAssistantBaseUrlInput" class="input" style="width:100%; margin-top:4px;" placeholder="https://api.openai.com/v1" />
                    </div>
                </div>

                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:16px; padding-top:14px; border-top:1px solid var(--host-border); flex-wrap:wrap; gap:10px;">
                    <div style="display:flex; gap:16px; align-items:center;">
                        <label style="display:flex; align-items:center; gap:6px; font-size:12.5px; cursor:pointer;">
                            <input type="checkbox" id="hostAssistantCitationsCheck" checked />
                            <span>Tự động trích dẫn nguồn nông học (PPRI, FAO)</span>
                        </label>
                        <label style="display:flex; align-items:center; gap:6px; font-size:12.5px; cursor:pointer;">
                            <input type="checkbox" id="hostAssistantDeepDiveCheck" checked />
                            <span>Bật chế độ phân tích bệnh học chuyên sâu</span>
                        </label>
                    </div>
                    <div style="display:flex; gap:10px;">
                        <button type="button" class="btn-ghost-sm" id="btnHostTestAssistant" onclick="testAssistantHostConfig()">⚡ Kiểm tra kết nối (Ping)</button>
                        <button type="button" class="btn-primary-sm" id="btnHostSaveAssistant" onclick="saveAssistantHostConfig()">💾 Lưu cấu hình</button>
                    </div>
                </div>
                <div id="hostAssistantAlert" style="display:none; margin-top:12px; padding:10px 14px; border-radius:8px; font-size:12.5px;"></div>
            </div>
        </section>'''

if target_table_end in content:
    content = content.replace(target_table_end, assistant_card_html, 1)
    print("Inserted assistant card in host.html")

# 2. Add JavaScript functions for Assistant Provider Manager
js_code = '''
        // =========================================================================
        // MODULE 03: HOST CONSOLE ASSISTANT CONFIGURATION JS
        // =========================================================================
        async function loadAssistantHostConfig() {
            try {
                const res = await fetch('/api/host/assistant/config', { headers: getAuthHeaders(), credentials: 'include' });
                const d = await res.json();
                if (d.success && d.config) {
                    const cfg = d.config;
                    document.getElementById('hostAssistantProviderSelect').value = cfg.provider || 'disabled';
                    document.getElementById('hostAssistantModelInput').value = cfg.model || '';
                    document.getElementById('hostAssistantBaseUrlInput').value = cfg.base_url || '';
                    document.getElementById('hostAssistantApiKeyInput').placeholder = cfg.has_api_key ? `Đã lưu (${cfg.api_key_masked})` : 'Chưa có API key';
                    document.getElementById('hostAssistantApiKeyInput').value = '';
                    document.getElementById('hostAssistantCitationsCheck').checked = !!cfg.citations_enabled;
                    document.getElementById('hostAssistantDeepDiveCheck').checked = !!cfg.deep_dive_enabled;

                    const pill = document.getElementById('hostAssistantStatusPill');
                    if (cfg.is_configured) {
                        pill.className = 'host-pill host-pill-active';
                        pill.textContent = `Sẵn sàng (${cfg.provider})`;
                    } else {
                        pill.className = 'host-pill host-pill-inactive';
                        pill.textContent = 'Chưa cấu hình';
                    }
                }
            } catch (e) {
                console.error("loadAssistantHostConfig error:", e);
            }
        }

        async function saveAssistantHostConfig() {
            const btn = document.getElementById('btnHostSaveAssistant');
            const alertEl = document.getElementById('hostAssistantAlert');
            btn.disabled = true;
            btn.textContent = 'Đang lưu...';
            if (alertEl) alertEl.style.display = 'none';

            const payload = {
                provider: document.getElementById('hostAssistantProviderSelect').value,
                model: document.getElementById('hostAssistantModelInput').value.trim(),
                base_url: document.getElementById('hostAssistantBaseUrlInput').value.trim(),
                citations_enabled: document.getElementById('hostAssistantCitationsCheck').checked,
                deep_dive_enabled: document.getElementById('hostAssistantDeepDiveCheck').checked,
                reason: 'Cập nhật từ Host Console Web'
            };

            const keyVal = document.getElementById('hostAssistantApiKeyInput').value.trim();
            if (keyVal) {
                payload.api_key = keyVal;
            }

            try {
                const res = await fetch('/api/host/assistant/config', {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify(payload)
                });
                const d = await res.json();
                if (res.ok && d.success) {
                    alertEl.style.display = 'block';
                    alertEl.style.background = 'rgba(16,185,129,0.1)';
                    alertEl.style.border = '1px solid rgba(16,185,129,0.3)';
                    alertEl.style.color = '#10b981';
                    alertEl.innerHTML = `<strong>Thành công!</strong> ${d.message}`;
                    loadAssistantHostConfig();
                    loadApiControls();
                } else {
                    throw new Error(d.detail || 'Không thể lưu cấu hình.');
                }
            } catch (e) {
                alertEl.style.display = 'block';
                alertEl.style.background = 'rgba(239,68,68,0.1)';
                alertEl.style.border = '1px solid rgba(239,68,68,0.3)';
                alertEl.style.color = '#ef4444';
                alertEl.textContent = e.message;
            } finally {
                btn.disabled = false;
                btn.textContent = '💾 Lưu cấu hình';
            }
        }

        async function testAssistantHostConfig() {
            const btn = document.getElementById('btnHostTestAssistant');
            const alertEl = document.getElementById('hostAssistantAlert');
            btn.disabled = true;
            btn.textContent = 'Đang ping...';
            if (alertEl) alertEl.style.display = 'none';

            const payload = {
                provider: document.getElementById('hostAssistantProviderSelect').value,
                model: document.getElementById('hostAssistantModelInput').value.trim()
            };
            const keyVal = document.getElementById('hostAssistantApiKeyInput').value.trim();
            if (keyVal) payload.api_key = keyVal;

            try {
                const res = await fetch('/api/host/assistant/test', {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    credentials: 'include',
                    body: JSON.stringify(payload)
                });
                const d = await res.json();
                if (res.ok && d.success) {
                    alertEl.style.display = 'block';
                    alertEl.style.background = 'rgba(16,185,129,0.1)';
                    alertEl.style.border = '1px solid rgba(16,185,129,0.3)';
                    alertEl.style.color = '#10b981';
                    alertEl.innerHTML = `<strong>Kết nối thành công!</strong> [${d.provider}:${d.model}] phản hồi trong <strong>${d.latency_ms}ms</strong>.<br><div style="font-size:11.5px; opacity:0.9; margin-top:4px;">"${d.sample_response}"</div>`;
                } else {
                    alertEl.style.display = 'block';
                    alertEl.style.background = 'rgba(239,68,68,0.1)';
                    alertEl.style.border = '1px solid rgba(239,68,68,0.3)';
                    alertEl.style.color = '#ef4444';
                    alertEl.innerHTML = `<strong>Lỗi kết nối Provider:</strong> ${d.error_detail || d.message || 'Không thể kết nối.'}`;
                }
            } catch (e) {
                alertEl.style.display = 'block';
                alertEl.style.background = 'rgba(239,68,68,0.1)';
                alertEl.style.border = '1px solid rgba(239,68,68,0.3)';
                alertEl.style.color = '#ef4444';
                alertEl.textContent = e.message;
            } finally {
                btn.disabled = false;
                btn.textContent = '⚡ Kiểm tra kết nối (Ping)';
            }
        }
'''

# Wire loadAssistantHostConfig inside loadApiControls
old_load_api = 'async function loadApiControls() {'
new_load_api = 'async function loadApiControls() {\n            loadAssistantHostConfig();'

if old_load_api in content:
    content = content.replace(old_load_api, new_load_api, 1)
    print("Wired loadAssistantHostConfig in loadApiControls")

content = content + "\n<script>" + js_code + "</script>\n"
path.write_text(content, encoding="utf-8")
print("frontend2/host.html patched successfully for Module 03.")
