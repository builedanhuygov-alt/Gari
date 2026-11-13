# -*- coding: utf-8 -*-
"""
Script to comprehensively overhaul frontend2/predict.html:
1. Purge Dev Mode Auth (#proDevConfigRow, #chkDevProAuth, X-Gari-Dev-Pro).
2. Add Authenticated User Header + Unauthenticated Onboarding Gateway + Diagnosis Lock Banner.
3. Add Create Organization Modal + Pro Subscription Upgrade Modal.
4. Wire Firebase & Unified Auth Client (window.gariAuth), state machine, RBAC context switcher, and Pro mode gating.
"""

import re
from pathlib import Path

predict_path = Path("frontend2/predict.html")
content = predict_path.read_text(encoding="utf-8")

# 1. Remove proDevConfigRow
pro_dev_pattern = re.compile(
    r'\s*<!-- Pro Dev Authorization Toggle -->\s*<div id="proDevConfigRow".*?</div>\s*</div>\s*(?=<!-- Manual Crop Selector)',
    re.DOTALL
)
m = pro_dev_pattern.search(content)
if m:
    content = content[:m.start()] + "\n                                </div>\n                            </div>\n\n                            " + content[m.end():]
    print("[1] Purged proDevConfigRow HTML")
else:
    print("[!] Could not match proDevConfigRow with regex, checking manual find")
    start_tag = '<!-- Pro Dev Authorization Toggle -->'
    end_tag = '<!-- Manual Crop Selector'
    s_idx = content.find(start_tag)
    e_idx = content.find(end_tag)
    if s_idx != -1 and e_idx != -1:
        content = content[:s_idx] + "</div>\n                            </div>\n\n                            " + content[e_idx:]
        print("[1] Purged proDevConfigRow manually")

# 2. Design the New First Screen:
# Replace the old doctor-hero with:
# - Authenticated User Header
# - Unauthenticated Onboarding Gateway
# - Diagnosis Lock Banner
# - Keep Trust & Safety, Photo Guide, Quota Bar

new_first_screen = """
                <!-- ========================================================================= -->
                <!-- 1. AUTHENTICATED USER HEADER (Visible when user is signed in)             -->
                <!-- ========================================================================= -->
                <div id="authenticatedUserHeader" style="display:none; margin-bottom:20px; padding:18px 22px; background:var(--surface); border:1.5px solid var(--border); border-radius:var(--radius-lg); box-shadow:0 2px 12px rgba(0,0,0,0.03);">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;">
                        <div style="display:flex; align-items:center; gap:14px;">
                            <div id="userAvatarBubble" style="width:46px; height:46px; border-radius:50%; background:linear-gradient(135deg, #10b981, #059669); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:17px; border:2px solid rgba(255,255,255,0.8); box-shadow:0 2px 8px rgba(16,185,129,0.3); flex-shrink:0;">
                                G
                            </div>
                            <div>
                                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                                    <h3 id="userDisplayName" style="margin:0; font-size:16px; font-weight:800; color:var(--text-main);">Nông dân Gari</h3>
                                    <span id="userPlanBadge" class="pill pill-success" style="font-size:11px; padding:2px 8px;">Cá nhân Free</span>
                                    <span id="userRoleBadge" class="pill pill-outline" style="font-size:11px; padding:2px 6px;">Nông hộ</span>
                                </div>
                                <div id="userEmailText" style="font-size:12px; color:var(--text-secondary); margin-top:2px;">nongdan@gari.vn</div>
                            </div>
                        </div>

                        <!-- Context Switcher & Action Controls -->
                        <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                            <!-- Active Context Dropdown -->
                            <div style="display:flex; align-items:center; gap:6px; background:var(--surface-muted); padding:6px 12px; border-radius:10px; border:1px solid var(--border);">
                                <span style="font-size:12px; color:var(--text-secondary); font-weight:600;">Ngữ cảnh:</span>
                                <select id="userActiveContextSelect" style="background:transparent; border:none; font-size:12.5px; font-weight:700; color:var(--primary); cursor:pointer; outline:none; max-width:220px;">
                                    <option value="personal">🍃 Cá nhân: Sổ tay riêng</option>
                                </select>
                            </div>

                            <!-- Pro Upgrade Button (Visible for Free tier) -->
                            <button type="button" id="btnHeaderUpgradePro" class="btn btn-warning btn-sm" style="display:none; font-weight:700; background:#f59e0b; color:#fff; border:none;">
                                ⭐ Nâng cấp Pro
                            </button>

                            <!-- Create Organization Button -->
                            <button type="button" id="btnHeaderCreateOrg" class="btn btn-secondary btn-sm" style="font-weight:600;">
                                🏢 Tạo HTX / Doanh nghiệp
                            </button>

                            <!-- Quick Guide Button -->
                            <button type="button" class="btn btn-ghost btn-sm" id="btnQuickGuide">📸 Hướng dẫn chụp</button>

                            <!-- Logout Button -->
                            <button type="button" id="btnHeaderLogout" class="btn btn-ghost btn-sm" style="color:var(--text-muted); font-size:12px;" title="Đăng xuất tài khoản">
                                🚪 Đăng xuất
                            </button>
                        </div>
                    </div>
                </div>

                <!-- ========================================================================= -->
                <!-- 2. UNAUTHENTICATED ONBOARDING GATEWAY (Visible when not logged in)        -->
                <!-- ========================================================================= -->
                <div id="authOnboardingGateway" style="margin-bottom:24px; padding:24px; background:linear-gradient(135deg, rgba(16,185,129,0.08) 0%, rgba(59,130,246,0.04) 100%); border:1.5px solid rgba(16,185,129,0.25); border-radius:var(--radius-lg);">
                    <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:24px; align-items:start;">
                        <!-- Left Value Proposition Column -->
                        <div>
                            <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                                <span class="doctor-badge">GARI AGRITECH AI LAB</span>
                                <span class="pill pill-success">Bác Sĩ Cây Trồng Thông Minh</span>
                            </div>
                            <h2 style="font-size:24px; font-weight:800; color:var(--text-main); margin:0 0 10px 0; line-height:1.3;">
                                Hệ thống AI nông nghiệp phát hiện dịch hại cây trồng chính xác
                            </h2>
                            <p style="font-size:13.5px; color:var(--text-secondary); line-height:1.6; margin:0 0 16px 0;">
                                Nền tảng thị giác máy tính nông nghiệp chuẩn xác cho nông hộ, hợp tác xã và doanh nghiệp. Tự động kiểm tra chất lượng ảnh lá (LeafGate), nhận diện cây và phân tích bệnh học chuyên sâu.
                            </p>
                            <div style="display:flex; flex-direction:column; gap:8px; margin-bottom:16px;">
                                <div style="display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--text-main);">
                                    <span style="color:var(--primary); font-size:15px; font-weight:800;">✓</span> <strong>7 Cây trồng chủ lực:</strong> Cà phê, Hồ tiêu, Lúa, Sầu riêng, Cà chua, Ớt, Ngô.
                                </div>
                                <div style="display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--text-main);">
                                    <span style="color:var(--primary); font-size:15px; font-weight:800;">✓</span> <strong>Thị giác máy tính Grad-CAM:</strong> Khoanh vùng đốm bệnh và mức độ chắc chắn trực quan.
                                </div>
                                <div style="display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--text-main);">
                                    <span style="color:var(--primary); font-size:15px; font-weight:800;">✓</span> <strong>Sổ tay nông trại & B2B RBAC:</strong> Quản lý dữ liệu phân quyền theo nông hộ hoặc Hợp tác xã.
                                </div>
                            </div>
                            <div style="display:flex; gap:10px;">
                                <button type="button" class="btn btn-secondary btn-sm" id="btnGatewayQuickGuide">📸 Hướng dẫn chụp ảnh</button>
                                <button type="button" class="btn btn-ghost btn-sm" id="btnGatewayTierInfo">👑 Quyền lợi gói cước</button>
                            </div>
                        </div>

                        <!-- Right Auth Form Card -->
                        <div style="background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:20px; box-shadow:0 8px 24px rgba(0,0,0,0.06);">
                            <!-- Auth Form Tabs -->
                            <div style="display:flex; border-bottom:1.5px solid var(--border); margin-bottom:16px;">
                                <button type="button" id="tabAuthLogin" class="auth-tab-btn active" style="flex:1; padding:8px 0; font-size:13px; font-weight:700; border:none; background:transparent; color:var(--primary); border-bottom:2px solid var(--primary); cursor:pointer;">
                                    Đăng nhập
                                </button>
                                <button type="button" id="tabAuthRegister" class="auth-tab-btn" style="flex:1; padding:8px 0; font-size:13px; font-weight:600; border:none; background:transparent; color:var(--text-secondary); border-bottom:2px solid transparent; cursor:pointer;">
                                    Đăng ký tài khoản
                                </button>
                                <button type="button" id="tabAuthReset" class="auth-tab-btn" style="flex:1; padding:8px 0; font-size:13px; font-weight:600; border:none; background:transparent; color:var(--text-secondary); border-bottom:2px solid transparent; cursor:pointer;">
                                    Quên mật khẩu
                                </button>
                            </div>

                            <!-- Tab 1: Login Form -->
                            <form id="formAuthLogin" onsubmit="return false;" style="display:flex; flex-direction:column; gap:12px;">
                                <div>
                                    <label class="form-label" style="font-size:12px;">Email tài khoản</label>
                                    <input type="email" id="loginEmail" class="input" placeholder="nongdan@example.com" required style="font-size:13px; padding:8px 12px;" />
                                </div>
                                <div>
                                    <label class="form-label" style="font-size:12px;">Mật khẩu</label>
                                    <input type="password" id="loginPassword" class="input" placeholder="••••••••" required style="font-size:13px; padding:8px 12px;" />
                                </div>
                                <div style="display:flex; justify-content:space-between; align-items:center; font-size:11.5px;">
                                    <label style="display:inline-flex; align-items:center; gap:5px; cursor:pointer; color:var(--text-secondary);">
                                        <input type="checkbox" id="loginRemember" checked /> Ghi nhớ đăng nhập
                                    </label>
                                    <a href="javascript:void(0)" id="linkForgotPass" style="color:var(--primary); text-decoration:none;">Quên mật khẩu?</a>
                                </div>
                                <div id="loginErrorMsg" style="display:none; color:var(--danger); font-size:12px; background:rgba(239,68,68,0.1); padding:8px; border-radius:6px; line-height:1.4;"></div>
                                <button type="submit" id="btnSubmitLogin" class="btn btn-primary" style="width:100%; font-weight:700;">
                                    Đăng nhập hệ thống
                                </button>
                            </form>

                            <!-- Tab 2: Register Form -->
                            <form id="formAuthRegister" onsubmit="return false;" style="display:none; flex-direction:column; gap:10px;">
                                <div>
                                    <label class="form-label" style="font-size:12px;">Họ và tên</label>
                                    <input type="text" id="regName" class="input" placeholder="Nguyễn Văn A" required style="font-size:13px; padding:8px 12px;" />
                                </div>
                                <div>
                                    <label class="form-label" style="font-size:12px;">Email liên hệ</label>
                                    <input type="email" id="regEmail" class="input" placeholder="nongdan@example.com" required style="font-size:13px; padding:8px 12px;" />
                                </div>
                                <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                                    <div>
                                        <label class="form-label" style="font-size:12px;">Mật khẩu</label>
                                        <input type="password" id="regPassword" class="input" placeholder="••••••••" required style="font-size:13px; padding:8px 12px;" />
                                    </div>
                                    <div>
                                        <label class="form-label" style="font-size:12px;">Số điện thoại</label>
                                        <input type="tel" id="regPhone" class="input" placeholder="0912..." style="font-size:13px; padding:8px 12px;" />
                                    </div>
                                </div>
                                <div>
                                    <label class="form-label" style="font-size:12px;">Tỉnh / Thành phố canh tác</label>
                                    <select id="regProvince" class="select" style="font-size:13px; padding:8px 12px;">
                                        <option value="Lâm Đồng">Lâm Đồng</option>
                                        <option value="Đắk Lắk">Đắk Lắk</option>
                                        <option value="Gia Lai">Gia Lai</option>
                                        <option value="Đồng Tháp">Đồng Tháp</option>
                                        <option value="An Giang">An Giang</option>
                                        <option value="Cần Thơ">Cần Thơ</option>
                                        <option value="Sơn La">Sơn La</option>
                                        <option value="Khác">Tỉnh thành khác</option>
                                    </select>
                                </div>
                                <div id="regErrorMsg" style="display:none; color:var(--danger); font-size:12px; background:rgba(239,68,68,0.1); padding:8px; border-radius:6px; line-height:1.4;"></div>
                                <button type="submit" id="btnSubmitRegister" class="btn btn-primary" style="width:100%; font-weight:700;">
                                    Tạo tài khoản Nông hộ (Miễn phí)
                                </button>
                            </form>

                            <!-- Tab 3: Password Reset Form -->
                            <form id="formAuthReset" onsubmit="return false;" style="display:none; flex-direction:column; gap:12px;">
                                <p style="font-size:12px; color:var(--text-secondary); margin:0;">
                                    Nhập email đã đăng ký. Hệ thống sẽ gửi thư xác thực để đặt lại mật khẩu an toàn.
                                </p>
                                <div>
                                    <label class="form-label" style="font-size:12px;">Email đăng ký</label>
                                    <input type="email" id="resetEmail" class="input" placeholder="nongdan@example.com" required style="font-size:13px; padding:8px 12px;" />
                                </div>
                                <div id="resetStatusMsg" style="display:none; font-size:12px; padding:8px; border-radius:6px; line-height:1.4;"></div>
                                <button type="submit" id="btnSubmitReset" class="btn btn-secondary" style="width:100%; font-weight:700;">
                                    Gửi yêu cầu đặt lại mật khẩu
                                </button>
                            </form>

                            <div style="margin-top:12px; font-size:11px; text-align:center; color:var(--text-muted);">
                                Bảo mật theo Nghị định 13/2023/NĐ-CP • Xác thực bảo mật Firebase & Gari Auth
                            </div>
                        </div>
                    </div>
                </div>

                <!-- ========================================================================= -->
                <!-- 3. DIAGNOSIS LOCK BANNER (Visible when unauthenticated)                   -->
                <!-- ========================================================================= -->
                <div id="diagnosisLockedBanner" style="display:block; margin-bottom:18px; padding:14px 18px; background:rgba(245,158,11,0.08); border:1.5px solid rgba(245,158,11,0.3); border-radius:12px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="font-size:22px;">🔒</span>
                        <div>
                            <div style="font-weight:700; color:#d97706; font-size:13.5px;">Khu vực chẩn đoán đang ở chế độ xem trước (Chưa đăng nhập)</div>
                            <div style="font-size:12px; color:var(--text-secondary);">Vui lòng đăng nhập hoặc tạo tài khoản ở biểu mẫu phía trên để mở khóa công cụ chẩn đoán AI và lưu trữ lịch sử nông trại.</div>
                        </div>
                    </div>
                    <button type="button" class="btn btn-secondary btn-sm" id="btnPromptLogin" style="font-weight:700;">
                        Đăng nhập ngay
                    </button>
                </div>
"""

# Replace doctor-hero
old_hero_start = '<div class="doctor-hero">'
old_hero_end = '<!-- TRUST & SAFETY & PRIVACY BANNER'

h_start = content.find(old_hero_start)
h_end = content.find(old_hero_end)
if h_start != -1 and h_end != -1:
    content = content[:h_start] + new_first_screen + "\n                " + content[h_end:]
    print("[2] Successfully replaced doctor-hero with Onboarding Gateway + Authenticated Header")
else:
    print("[!] Could not locate doctor-hero boundaries")

# 3. Add Modals: modalCreateOrg and modalProUpgrade before </main>
new_modals = """
                <!-- CREATE ORGANIZATION MODAL (B2B RBAC) -->
                <div id="modalCreateOrg" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.55); z-index:9999; align-items:center; justify-content:center; padding:16px;">
                    <div style="background:var(--surface); max-width:540px; width:100%; border-radius:16px; padding:24px; box-shadow:0 20px 40px rgba(0,0,0,0.25); border:1px solid var(--border);">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px;">
                            <div>
                                <span class="pill pill-success" style="margin-bottom:6px;">Khởi tạo Tổ chức Nông nghiệp (B2B)</span>
                                <h3 style="margin:4px 0 0 0; font-size:18px; font-weight:800;">Tạo Hợp Tác Xã / Doanh Nghiệp Mới</h3>
                            </div>
                            <button type="button" id="btnCloseCreateOrgModal" style="background:transparent; border:none; font-size:20px; cursor:pointer; color:var(--text-muted); padding:4px;">✕</button>
                        </div>

                        <form id="formCreateOrg" onsubmit="return false;" style="display:flex; flex-direction:column; gap:12px;">
                            <div>
                                <label class="form-label" style="font-weight:700;">Tên tổ chức / Hợp tác xã <span style="color:var(--danger);">*</span></label>
                                <input type="text" id="newOrgName" class="input" placeholder="Ví dụ: HTX Cà Phê Hữu Cơ Cư M'gar" required />
                            </div>

                            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                                <div>
                                    <label class="form-label" style="font-weight:700;">Loại hình tổ chức</label>
                                    <select id="newOrgType" class="select">
                                        <option value="cooperative">Hợp tác xã nông nghiệp</option>
                                        <option value="farm">Trang trại độc lập</option>
                                        <option value="agribusiness">Doanh nghiệp nông nghiệp</option>
                                        <option value="dealer">Đại lý vật tư BVTV</option>
                                        <option value="smallholder_group">Tổ nhóm nông hộ</option>
                                        <option value="other">Loại hình khác</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="form-label" style="font-weight:700;">Tỉnh / Thành phố</label>
                                    <select id="newOrgRegion" class="select">
                                        <option value="Đắk Lắk">Đắk Lắk</option>
                                        <option value="Lâm Đồng">Lâm Đồng</option>
                                        <option value="Gia Lai">Gia Lai</option>
                                        <option value="Đồng Tháp">Đồng Tháp</option>
                                        <option value="An Giang">An Giang</option>
                                        <option value="Cần Thơ">Cần Thơ</option>
                                        <option value="Sơn La">Sơn La</option>
                                        <option value="Toàn quốc">Tỉnh thành khác</option>
                                    </select>
                                </div>
                            </div>

                            <div>
                                <label class="form-label" style="font-weight:700;">Cây trồng chủ lực</label>
                                <input type="text" id="newOrgCrops" class="input" placeholder="Cà phê, Tiêu, Sầu riêng..." />
                                <div class="form-hint">Nhập các loại cây chủ đạo của thành viên HTX để tối ưu hóa gợi ý bệnh học.</div>
                            </div>

                            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                                <div>
                                    <label class="form-label" style="font-weight:700;">Email đại diện</label>
                                    <input type="email" id="newOrgEmail" class="input" placeholder="htx@example.com" />
                                </div>
                                <div>
                                    <label class="form-label" style="font-weight:700;">Số điện thoại</label>
                                    <input type="tel" id="newOrgPhone" class="input" placeholder="09..." />
                                </div>
                            </div>

                            <div id="createOrgErrorMsg" style="display:none; color:var(--danger); font-size:12.5px; background:rgba(239,68,68,0.1); padding:10px; border-radius:8px; line-height:1.4;"></div>

                            <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:8px;">
                                <button type="button" class="btn btn-ghost" id="btnCancelCreateOrg">Hủy</button>
                                <button type="submit" class="btn btn-primary" id="btnSubmitCreateOrg" style="font-weight:700;">Khởi tạo tổ chức</button>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- PRO UPGRADE & VIETQR PAYMENT MODAL -->
                <div id="modalProUpgrade" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.55); z-index:9999; align-items:center; justify-content:center; padding:16px;">
                    <div style="background:var(--surface); max-width:620px; width:100%; border-radius:18px; padding:24px; box-shadow:0 24px 48px rgba(0,0,0,0.3); border:1.5px solid rgba(245,158,11,0.3);">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px;">
                            <div>
                                <span class="pill pill-warning" style="margin-bottom:6px;">⭐ Gói Chuyên Nghiệp (Pro Subscription)</span>
                                <h3 style="margin:4px 0 0 0; font-size:20px; font-weight:800; color:var(--text-main);">Nâng Cấp Gói Gari Pro</h3>
                            </div>
                            <button type="button" id="btnCloseProModal" style="background:transparent; border:none; font-size:22px; cursor:pointer; color:var(--text-muted); padding:4px;">✕</button>
                        </div>

                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:18px;">
                            <div style="padding:16px; border:1.5px solid #f59e0b; border-radius:12px; background:linear-gradient(135deg, rgba(245,158,11,0.08) 0%, rgba(217,119,6,0.02) 100%);">
                                <div style="font-weight:700; color:#d97706; font-size:14px;">Gói Cá Nhân Pro (VIP)</div>
                                <div style="font-size:24px; font-weight:900; color:#d97706; margin:8px 0 4px 0;">129.000 đ <span style="font-size:13px; font-weight:500; color:var(--text-secondary);">/ tháng</span></div>
                                <div style="font-size:11.5px; color:var(--text-muted); margin-bottom:10px;">Hoặc 1.290.000 đ / năm (Tiết kiệm 2 tháng)</div>
                                <div style="display:flex; flex-direction:column; gap:6px; font-size:12px; color:var(--text-main);">
                                    <div>✓ <strong>150 lượt phân tích AI</strong> / ngày</div>
                                    <div>✓ <strong>Mở khóa Model tong 2:</strong> ViT GBIF 14,829 loài</div>
                                    <div>✓ <strong>Mở khóa Model 4:</strong> Pathology DINOv2</div>
                                    <div>✓ <strong>Quyền khởi tạo Hợp tác xã / Trang trại</strong></div>
                                    <div>✓ Xuất báo cáo mùa vụ Excel & PDF</div>
                                    <div>✓ Ưu tiên hỗ trợ nông học 24/7</div>
                                </div>
                            </div>

                            <!-- VietQR Bank Transfer Details -->
                            <div style="padding:16px; border:1px solid var(--border); border-radius:12px; background:var(--surface-muted); display:flex; flex-direction:column; justify-content:space-between;">
                                <div>
                                    <div style="font-weight:700; color:var(--text-main); font-size:13px; margin-bottom:6px;">Chuyển khoản kích hoạt nhanh (VietQR)</div>
                                    <div style="font-size:11.5px; color:var(--text-secondary); line-height:1.5;">
                                        Quét mã QR hoặc chuyển khoản ngân hàng theo cú pháp bên dưới để hệ thống đối soát tự động:
                                    </div>
                                    <div style="margin-top:10px; background:var(--surface); padding:10px; border-radius:8px; border:1px solid var(--border); font-size:12px; display:flex; flex-direction:column; gap:4px;">
                                        <div><strong>Ngân hàng:</strong> MBBank (Quân Đội)</div>
                                        <div><strong>Số TK:</strong> <code>0988668866</code></div>
                                        <div><strong>Chủ TK:</strong> GARI AGRI VIETNAM</div>
                                        <div><strong>Số tiền:</strong> <code>129.000 VND</code></div>
                                        <div><strong>Nội dung CK:</strong> <code id="proQrTransferContent">GARI PRO USER</code></div>
                                    </div>
                                </div>
                                <div style="margin-top:12px;">
                                    <button type="button" id="btnConfirmProPayment" class="btn btn-warning" style="width:100%; font-weight:700; font-size:13px; background:#f59e0b; color:#fff; border:none;">
                                        ✓ Tôi đã chuyển khoản xong
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div style="background:rgba(16,185,129,0.08); padding:10px 14px; border-radius:8px; font-size:11.5px; color:var(--primary); border:1px solid rgba(16,185,129,0.25);">
                            💡 <strong>Cam kết:</strong> Nâng cấp Pro kích hoạt quyền lợi tức thì. Nếu cần hỗ trợ kích hoạt khẩn cấp, vui lòng liên hệ hotline Gari AI Lab: <code>contact@gari.vn</code>.
                        </div>
                    </div>
                </div>
"""

m_end_idx = content.find("</main>")
if m_end_idx != -1:
    content = content[:m_end_idx] + new_modals + "\n            " + content[m_end_idx:]
    print("[3] Added modalCreateOrg and modalProUpgrade before </main>")

predict_path.write_text(content, encoding="utf-8")
print("Finished Phase 1 (HTML overhaul)")
