# -*- coding: utf-8 -*-
"""
Phase 2: Wire JavaScript in frontend2/predict.html
Connects firebase-client.js, unified auth state machine, Pro gating, Org creation modal, and cleans out dev pro references.
"""

import re
from pathlib import Path

predict_path = Path("frontend2/predict.html")
content = predict_path.read_text(encoding="utf-8")

# Check if firebase-client.js is imported
if '/frontend2/firebase-client.js' not in content:
    # Add import in script
    script_import_target = "import { setupSaaSShell, fetchJSON, bindDropzone, toast } from '/static/frontend2/app.js?v=20261104_stable';"
    script_import_replacement = """import { setupSaaSShell, fetchJSON, bindDropzone, toast } from '/static/frontend2/app.js?v=20261104_stable';
        import '/frontend2/firebase-client.js';"""
    content = content.replace(script_import_target, script_import_replacement)
    print("[1] Imported firebase-client.js in script")

# Replace runInference dev pro check (lines around 2115)
dev_pro_pattern = re.compile(
    r"if\s*\(activeMode\s*===\s*'auto_pro'\)\s*\{\s*const\s*chkDevPro\s*=\s*document\.getElementById\('chkDevProAuth'\);\s*if\s*\(chkDevPro\s*&&\s*chkDevPro\.checked\)\s*\{\s*headers\['X-Gari-Dev-Pro'\]\s*=\s*'true';\s*\}\s*\}",
    re.DOTALL
)
if dev_pro_pattern.search(content):
    content = dev_pro_pattern.sub("// Dev Pro header bypass permanently eliminated", content)
    print("[2] Removed X-Gari-Dev-Pro injection from runInference")
else:
    print("[!] Could not match dev_pro_pattern with regex, checking manual match")
    needle = "headers['X-Gari-Dev-Pro'] = 'true';"
    if needle in content:
        # replace the block
        content = content.replace(needle, "// headers['X-Gari-Dev-Pro'] eliminated")
        print("[2] Replaced X-Gari-Dev-Pro needle manually")

# Remove proDevConfigRow references in JS
content = content.replace("const proDevConfigRow = document.getElementById('proDevConfigRow');\n", "")
content = content.replace("const proDevConfigRow = document.getElementById('proDevConfigRow');\r\n", "")
content = content.replace("if (proDevConfigRow) proDevConfigRow.style.display = 'none';\n", "")
content = content.replace("if (proDevConfigRow) proDevConfigRow.style.display = 'none';\r\n", "")
content = content.replace("if (proDevConfigRow) proDevConfigRow.style.display = 'flex';\n", "")
content = content.replace("if (proDevConfigRow) proDevConfigRow.style.display = 'flex';\r\n", "")
print("[3] Cleaned up proDevConfigRow JS references")

# Now let's inject our Auth, Org, and Pro gating module into the script
# We can place it right before `async function initDiagnosis()`
auth_module_code = """
        // =========================================================================
        // GARI AI LAB — UNIFIED AUTH & RBAC STATE MACHINE (Sprint 6 Overhaul)
        // =========================================================================
        let activeUser = null;
        let activeOrgId = null;

        function initAuthUI() {
            // Tab switching for Login / Register / Reset
            const tabLogin = document.getElementById('tabAuthLogin');
            const tabReg = document.getElementById('tabAuthRegister');
            const tabReset = document.getElementById('tabAuthReset');
            const formLogin = document.getElementById('formAuthLogin');
            const formReg = document.getElementById('formAuthRegister');
            const formReset = document.getElementById('formAuthReset');

            function setAuthTab(activeTab, activeForm) {
                [tabLogin, tabReg, tabReset].forEach(t => {
                    if (!t) return;
                    t.classList.remove('active');
                    t.style.fontWeight = '600';
                    t.style.color = 'var(--text-secondary)';
                    t.style.borderBottomColor = 'transparent';
                });
                [formLogin, formReg, formReset].forEach(f => {
                    if (f) f.style.display = 'none';
                });
                if (activeTab) {
                    activeTab.classList.add('active');
                    activeTab.style.fontWeight = '700';
                    activeTab.style.color = 'var(--primary)';
                    activeTab.style.borderBottomColor = 'var(--primary)';
                }
                if (activeForm) activeForm.style.display = 'flex';
            }

            if (tabLogin) tabLogin.onclick = () => setAuthTab(tabLogin, formLogin);
            if (tabReg) tabReg.onclick = () => setAuthTab(tabReg, formReg);
            if (tabReset) tabReset.onclick = () => setAuthTab(tabReset, formReset);

            const linkForgotPass = document.getElementById('linkForgotPass');
            if (linkForgotPass) linkForgotPass.onclick = () => setAuthTab(tabReset, formReset);

            // Form Submissions
            if (formLogin) {
                formLogin.onsubmit = async (e) => {
                    e.preventDefault();
                    const email = document.getElementById('loginEmail').value.trim();
                    const password = document.getElementById('loginPassword').value;
                    const errBox = document.getElementById('loginErrorMsg');
                    const btn = document.getElementById('btnSubmitLogin');

                    errBox.style.display = 'none';
                    btn.disabled = true;
                    btn.textContent = 'Đang đăng nhập...';

                    try {
                        await window.gariAuth.login(email, password);
                        toast('Đăng nhập thành công! Đã kết nối hệ thống.', 'success');
                    } catch (err) {
                        errBox.textContent = err.message || 'Đăng nhập không thành công. Vui lòng thử lại.';
                        errBox.style.display = 'block';
                    } finally {
                        btn.disabled = false;
                        btn.textContent = 'Đăng nhập hệ thống';
                    }
                };
            }

            if (formReg) {
                formReg.onsubmit = async (e) => {
                    e.preventDefault();
                    const name = document.getElementById('regName').value.trim();
                    const email = document.getElementById('regEmail').value.trim();
                    const password = document.getElementById('regPassword').value;
                    const phone = document.getElementById('regPhone').value.trim();
                    const province = document.getElementById('regProvince').value;
                    const errBox = document.getElementById('regErrorMsg');
                    const btn = document.getElementById('btnSubmitRegister');

                    errBox.style.display = 'none';
                    btn.disabled = true;
                    btn.textContent = 'Đang khởi tạo tài khoản...';

                    try {
                        await window.gariAuth.register(name, email, password, phone, province);
                        toast('Tạo tài khoản thành công! Chào mừng bạn đến với Gari.', 'success');
                    } catch (err) {
                        errBox.textContent = err.message || 'Đăng ký tài khoản không thành công.';
                        errBox.style.display = 'block';
                    } finally {
                        btn.disabled = false;
                        btn.textContent = 'Tạo tài khoản Nông hộ (Miễn phí)';
                    }
                };
            }

            if (formReset) {
                formReset.onsubmit = async (e) => {
                    e.preventDefault();
                    const email = document.getElementById('resetEmail').value.trim();
                    const msgBox = document.getElementById('resetStatusMsg');
                    const btn = document.getElementById('btnSubmitReset');

                    btn.disabled = true;
                    try {
                        const res = await window.gariAuth.resetPassword(email);
                        msgBox.style.display = 'block';
                        msgBox.style.background = 'rgba(16,185,129,0.1)';
                        msgBox.style.color = '#10b981';
                        msgBox.textContent = res.message || 'Yêu cầu đã gửi thành công.';
                    } catch (err) {
                        msgBox.style.display = 'block';
                        msgBox.style.background = 'rgba(239,68,68,0.1)';
                        msgBox.style.color = '#ef4444';
                        msgBox.textContent = err.message || 'Lỗi khi gửi yêu cầu đặt lại mật khẩu.';
                    } finally {
                        btn.disabled = false;
                    }
                };
            }

            // Header Action Buttons
            const btnLogout = document.getElementById('btnHeaderLogout');
            if (btnLogout) {
                btnLogout.onclick = async () => {
                    await window.gariAuth.logout();
                    toast('Đã đăng xuất khỏi phiên làm việc an toàn.', 'info');
                };
            }

            const btnPromptLogin = document.getElementById('btnPromptLogin');
            if (btnPromptLogin) {
                btnPromptLogin.onclick = () => {
                    document.getElementById('loginEmail')?.focus();
                    document.getElementById('authOnboardingGateway')?.scrollIntoView({ behavior: 'smooth' });
                };
            }

            // Context Switcher Listener
            const ctxSelect = document.getElementById('userActiveContextSelect');
            if (ctxSelect) {
                ctxSelect.onchange = () => {
                    const val = ctxSelect.value;
                    const badge = document.getElementById('selectedContextBadge');
                    if (val === 'personal') {
                        activeOrgId = null;
                        if (badge) {
                            badge.textContent = '🍃 Cá nhân';
                            badge.style.background = 'rgba(16,185,129,0.12)';
                            badge.style.color = '#10b981';
                        }
                    } else if (val.startsWith('org_')) {
                        activeOrgId = parseInt(val.replace('org_', ''), 10);
                        if (badge) {
                            const optText = ctxSelect.options[ctxSelect.selectedIndex].textContent;
                            badge.textContent = optText.split('(')[0].trim();
                            badge.style.background = 'rgba(59,130,246,0.12)';
                            badge.style.color = '#2563eb';
                        }
                    }
                    loadQuotaStatus();
                    loadDiagnosisContexts();
                };
            }

            initModals();
        }

        function syncAuthState(user) {
            activeUser = user;
            const headerEl = document.getElementById('authenticatedUserHeader');
            const gatewayEl = document.getElementById('authOnboardingGateway');
            const lockedBanner = document.getElementById('diagnosisLockedBanner');

            if (user) {
                if (headerEl) headerEl.style.display = 'block';
                if (gatewayEl) gatewayEl.style.display = 'none';
                if (lockedBanner) lockedBanner.style.display = 'none';

                const name = (user.profile && (user.profile.full_name || user.profile.name)) || (user.identity && user.identity.display_name) || 'Nông dân Gari';
                const email = (user.identity && user.identity.email) || '';
                const plan = user.subscription || {};

                const nameEl = document.getElementById('userDisplayName');
                if (nameEl) nameEl.textContent = name;
                const emailEl = document.getElementById('userEmailText');
                if (emailEl) emailEl.textContent = email;
                const avatarEl = document.getElementById('userAvatarBubble');
                if (avatarEl) avatarEl.textContent = (name || 'G')[0].toUpperCase();

                const roleEl = document.getElementById('userRoleBadge');
                if (roleEl) {
                    if (user.system_role && user.system_role.is_admin) {
                        roleEl.textContent = 'Quản trị viên';
                        roleEl.className = 'pill pill-danger';
                    } else {
                        roleEl.textContent = user.profile.account_type || 'Nông hộ';
                        roleEl.className = 'pill pill-outline';
                    }
                }

                const planEl = document.getElementById('userPlanBadge');
                const btnUpgrade = document.getElementById('btnHeaderUpgradePro');
                if (planEl) {
                    planEl.textContent = plan.plan_name || 'Cá nhân Free';
                    planEl.className = plan.is_vip ? 'pill pill-warning' : 'pill pill-success';
                }
                if (btnUpgrade) {
                    btnUpgrade.style.display = plan.is_vip ? 'none' : 'inline-flex';
                }

                // Transfer content code for QR transfer
                const qrCodeEl = document.getElementById('proQrTransferContent');
                if (qrCodeEl && user.profile && user.profile.id) {
                    qrCodeEl.textContent = `GARI PRO ${user.profile.id}`;
                }

                // Populate active context switcher
                const ctxSelect = document.getElementById('userActiveContextSelect');
                if (ctxSelect) {
                    ctxSelect.innerHTML = '<option value="personal">🍃 Cá nhân: Sổ tay riêng</option>';
                    if (user.organizations && user.organizations.length > 0) {
                        user.organizations.forEach(org => {
                            const opt = document.createElement('option');
                            opt.value = `org_${org.org_id}`;
                            opt.textContent = `🏢 ${org.org_name} (${org.role})`;
                            if (activeOrgId === org.org_id) opt.selected = true;
                            ctxSelect.appendChild(opt);
                        });
                    }
                }
            } else {
                if (headerEl) headerEl.style.display = 'none';
                if (gatewayEl) gatewayEl.style.display = 'block';
                if (lockedBanner) lockedBanner.style.display = 'flex';
                activeOrgId = null;
            }

            loadQuotaStatus();
            loadDiagnosisContexts();
        }

        function initModals() {
            // Organization creation modal
            const modalCreateOrg = document.getElementById('modalCreateOrg');
            const btnHeaderCreateOrg = document.getElementById('btnHeaderCreateOrg');
            const btnCloseCreateOrgModal = document.getElementById('btnCloseCreateOrgModal');
            const btnCancelCreateOrg = document.getElementById('btnCancelCreateOrg');

            if (btnHeaderCreateOrg) {
                btnHeaderCreateOrg.onclick = () => {
                    if (!activeUser) {
                        toast('Vui lòng đăng nhập trước khi khởi tạo tổ chức.', 'warning');
                        document.getElementById('authOnboardingGateway')?.scrollIntoView({ behavior: 'smooth' });
                        return;
                    }
                    const canCreate = activeUser.subscription && activeUser.subscription.can_create_organization;
                    if (!canCreate) {
                        window.openProUpgradeModal('Tạo Hợp tác xã hoặc Doanh nghiệp yêu cầu tài khoản nâng cấp gói Pro hoặc Doanh nghiệp. Vui lòng nâng cấp gói để tiếp tục.');
                        return;
                    }
                    if (modalCreateOrg) modalCreateOrg.style.display = 'flex';
                };
            }

            const closeCreateOrg = () => {
                if (modalCreateOrg) modalCreateOrg.style.display = 'none';
                const err = document.getElementById('createOrgErrorMsg');
                if (err) err.style.display = 'none';
            };
            if (btnCloseCreateOrgModal) btnCloseCreateOrgModal.onclick = closeCreateOrg;
            if (btnCancelCreateOrg) btnCancelCreateOrg.onclick = closeCreateOrg;

            const formCreateOrg = document.getElementById('formCreateOrg');
            if (formCreateOrg) {
                formCreateOrg.onsubmit = async (e) => {
                    e.preventDefault();
                    const name = document.getElementById('newOrgName').value.trim();
                    const org_type = document.getElementById('newOrgType').value;
                    const region = document.getElementById('newOrgRegion').value;
                    const primary_crops = document.getElementById('newOrgCrops').value.trim();
                    const contact_email = document.getElementById('newOrgEmail').value.trim();
                    const contact_phone = document.getElementById('newOrgPhone').value.trim();
                    const errBox = document.getElementById('createOrgErrorMsg');
                    const btnSubmit = document.getElementById('btnSubmitCreateOrg');

                    errBox.style.display = 'none';
                    btnSubmit.disabled = true;
                    btnSubmit.textContent = 'Đang khởi tạo...';

                    try {
                        const res = await fetch('/api/organizations', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                ...window.gariAuth.getAuthHeaders()
                            },
                            credentials: 'include',
                            body: JSON.stringify({
                                name,
                                organization_type: org_type,
                                region,
                                primary_crops,
                                contact_email,
                                contact_phone
                            })
                        });
                        const data = await res.json();
                        if (!res.ok || !data.success) {
                            throw new Error(data.detail || data.message || 'Khởi tạo tổ chức thất bại.');
                        }
                        toast('Khởi tạo tổ chức thành công! Chúc mừng bạn.', 'success');
                        closeCreateOrg();
                        formCreateOrg.reset();
                        await window.gariAuth.checkCurrentSession();
                    } catch (err) {
                        errBox.textContent = err.message || 'Lỗi khi khởi tạo tổ chức.';
                        errBox.style.display = 'block';
                    } finally {
                        btnSubmit.disabled = false;
                        btnSubmit.textContent = 'Khởi tạo tổ chức';
                    }
                };
            }

            // Pro Upgrade Modal
            const modalProUpgrade = document.getElementById('modalProUpgrade');
            const btnCloseProModal = document.getElementById('btnCloseProModal');
            const btnHeaderUpgradePro = document.getElementById('btnHeaderUpgradePro');
            const btnGatewayTierInfo = document.getElementById('btnGatewayTierInfo');
            const btnConfirmProPayment = document.getElementById('btnConfirmProPayment');

            window.openProUpgradeModal = (reason) => {
                if (modalProUpgrade) {
                    modalProUpgrade.style.display = 'flex';
                    if (reason) toast(reason, 'info');
                }
            };

            if (btnHeaderUpgradePro) btnHeaderUpgradePro.onclick = () => window.openProUpgradeModal();
            if (btnGatewayTierInfo) btnGatewayTierInfo.onclick = () => window.openProUpgradeModal();
            if (btnCloseProModal) btnCloseProModal.onclick = () => { modalProUpgrade.style.display = 'none'; };

            if (btnConfirmProPayment) {
                btnConfirmProPayment.onclick = () => {
                    toast('Cảm ơn bạn! Yêu cầu đối soát chuyển khoản đã được ghi nhận. Hệ thống sẽ kích hoạt trong ít phút.', 'success');
                    if (modalProUpgrade) modalProUpgrade.style.display = 'none';
                };
            }
        }
"""

# Insert auth_module_code right before `async function initDiagnosis()`
init_diag_target = "async function initDiagnosis() {"
content = content.replace(init_diag_target, auth_module_code + "\n        " + init_diag_target)
print("[4] Injected Auth & RBAC State Machine functions")

# In init() function, call initAuthUI, listen to onAuthStateChanged, and init gariAuth
init_fn_target = """        function init() {
            const urlParams = new URLSearchParams(window.location.search);"""

init_fn_replacement = """        function init() {
            const urlParams = new URLSearchParams(window.location.search);
            initAuthUI();
            if (window.gariAuth) {
                window.gariAuth.onAuthStateChanged(syncAuthState);
                window.gariAuth.init();
            }"""
content = content.replace(init_fn_target, init_fn_replacement)
print("[5] Hooked initAuthUI and gariAuth into init()")

# Now update btnModePro.onclick to enforce Pro gating
old_btn_pro = """            if (btnModePro) {
                btnModePro.onclick = () => {
                    currentDiagnosisMode = 'auto_pro';
                    resetModeButtons();
                    btnModePro.classList.add('active');
                    btnModePro.style.borderColor = '#f59e0b';
                    btnModePro.style.background = 'rgba(245,158,11,0.1)';
                    btnModePro.style.color = '#d97706';

                    manualCropGroup.style.display = 'none';
                    modeExplanation.innerHTML = 'Chế độ Pro: Kiểm định lá cây -> Nhận diện loài thực vật bằng mô hình Pro <strong>Model tong 2 (ViT GBIF 14,829 loài)</strong> -> Tự động chuyển đến mô hình bệnh học tương ứng.';
                };
            }"""

new_btn_pro = """            if (btnModePro) {
                btnModePro.onclick = () => {
                    const isVip = (activeUser && activeUser.subscription && activeUser.subscription.is_vip) || (currentQuotaData && currentQuotaData.is_vip);
                    if (!isVip) {
                        window.openProUpgradeModal('Tính năng Tự động Pro (Model ViT GBIF 14,829 loài) yêu cầu tài khoản nâng cấp gói Pro. Vui lòng nâng cấp gói để mở khóa.');
                        return;
                    }
                    currentDiagnosisMode = 'auto_pro';
                    resetModeButtons();
                    btnModePro.classList.add('active');
                    btnModePro.style.borderColor = '#f59e0b';
                    btnModePro.style.background = 'rgba(245,158,11,0.1)';
                    btnModePro.style.color = '#d97706';

                    manualCropGroup.style.display = 'none';
                    modeExplanation.innerHTML = 'Chế độ Pro: Kiểm định lá cây -> Nhận diện loài thực vật bằng mô hình Pro <strong>Model tong 2 (ViT GBIF 14,829 loài)</strong> -> Tự động chuyển đến mô hình bệnh học tương ứng.';
                };
            }"""
content = content.replace(old_btn_pro, new_btn_pro)
print("[6] Gated btnModePro click with Pro entitlement check")

# Update runInference to check authentication and use window.gariAuth.getAuthHeaders()
old_run_auth_check = """                const token = localStorage.getItem('gari_token');
                const headers = token ? { 'Authorization': `Bearer ${token}` } : {};"""

new_run_auth_check = """                if (!activeUser) {
                    toast('Vui lòng đăng nhập để sử dụng công cụ chẩn đoán AI.', 'warning');
                    document.getElementById('authOnboardingGateway')?.scrollIntoView({ behavior: 'smooth' });
                    document.getElementById('loginEmail')?.focus();
                    return;
                }
                const headers = window.gariAuth ? window.gariAuth.getAuthHeaders() : {};
                if (activeOrgId) {
                    fd.append('org_id', activeOrgId);
                }"""

content = content.replace(old_run_auth_check, new_run_auth_check)
print("[7] Updated runInference with auth guard and active organization context")

predict_path.write_text(content, encoding="utf-8")
print("Finished Phase 2 (JavaScript overhaul)")
