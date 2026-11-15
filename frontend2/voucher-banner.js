/**
 * GARI AgriTech AI Lab — Animated VIP 7-Day Voucher Campaign Component
 * Campaign: GARI VIP miễn phí 7 ngày dành cho học sinh THPT Nguyễn Hồng Đạo
 * Voucher Code: Gari-THPTNHD1
 */

const VOUCHER_CODE = 'Gari-THPTNHD1';
const CAMPAIGN_TITLE = 'ĐẶC QUYỀN THPT NGUYỄN HỒNG ĐẠO';

export class GariVoucherBanner {
    constructor(containerId = 'gariVoucherBannerContainer') {
        this.containerId = containerId;
        this.voucherCode = VOUCHER_CODE;
        this.status = null;
        this.isActivating = false;
        this.modalEl = null;
        this.bannerEl = null;
    }

    async init() {
        this.ensureModal();
        this.renderBanner();
        this.bindEvents();
        await this.syncVoucherStatus();

        // Listen for auth state changes to re-evaluate voucher status
        if (typeof window !== 'undefined') {
            window.addEventListener('gari:auth-state-changed', () => {
                this.syncVoucherStatus();
            });
        }
    }

    async syncVoucherStatus() {
        if (!window.gariAuth || typeof window.gariAuth.getVoucherStatus !== 'function') return;
        try {
            this.status = await window.gariAuth.getVoucherStatus(this.voucherCode);
            this.updateBannerState(this.status);
        } catch (_) {}
    }

    renderBanner() {
        const container = document.getElementById(this.containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="gari-vip-voucher-banner" id="gariVipVoucherBanner" role="region" aria-label="Chương trình ưu đãi GARI VIP THPT Nguyễn Hồng Đạo">
                <!-- Ambient Glow Overlays -->
                <div class="voucher-ambient-glow"></div>
                <div class="voucher-particles-layer">
                    <span class="particle p1"></span>
                    <span class="particle p2"></span>
                    <span class="particle p3"></span>
                </div>

                <div class="voucher-banner-grid">
                    <!-- Left Column: Typography & Action -->
                    <div class="voucher-content-col">
                        <div class="voucher-badge-row">
                            <span class="voucher-badge">
                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                                ${CAMPAIGN_TITLE}
                            </span>
                            <span class="voucher-subtag">Hạn mức: 5 lượt/ngày</span>
                        </div>

                        <h2 class="voucher-headline">
                            Trải nghiệm GARI VIP miễn phí 7 ngày!
                        </h2>

                        <p class="voucher-desc">
                            Khám phá sức mạnh AI nông nghiệp và các công cụ chẩn đoán cây trồng thông minh.
                        </p>

                        <div class="voucher-action-row" id="voucherActionRow">
                            <div class="voucher-code-pill" id="btnCopyVoucher" title="Bấm để sao chép mã voucher">
                                <span class="code-label">Mã ưu đãi:</span>
                                <strong class="code-value">${this.voucherCode}</strong>
                                <svg class="copy-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                            </div>

                            <button type="button" class="btn-voucher-cta" id="btnOpenVoucherModal">
                                <span>Kích hoạt ưu đãi</span>
                                <span class="cta-arrow">→</span>
                            </button>
                        </div>

                        <div class="voucher-footnote" id="voucherFootnote">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                            <span>7 ngày kể từ khi kích hoạt thành công • Tối đa 5 lượt chẩn đoán/ngày</span>
                        </div>
                    </div>

                    <!-- Right Column: Animated Botanical AI Leaf Graphic -->
                    <div class="voucher-visual-col">
                        <div class="voucher-leaf-stage">
                            <!-- Background Leaf Image (Required Official Asset) -->
                            <img src="/static/frontend2/images/voucher_thpt_nhd_banner.jpg" 
                                 alt="Lá bệnh phẩm thực vật AI chẩn đoán" 
                                 class="voucher-leaf-img"
                                 id="voucherLeafImg"
                                 loading="lazy" />

                            <!-- Shimmer Light Sweep Layer -->
                            <div class="emerald-light-sweep"></div>

                            <!-- AI Scanning Laser Beam -->
                            <div class="ai-scan-beam"></div>

                            <!-- Concentric Radar Detection Rings -->
                            <div class="radar-detection-ring ring-1"></div>
                            <div class="radar-detection-ring ring-2"></div>

                            <!-- Target Reticle & HUD Spot -->
                            <div class="hud-target-reticle">
                                <span class="reticle-dot"></span>
                                <span class="reticle-tag">AI VIP ANALYSIS</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        this.bannerEl = container.querySelector('#gariVipVoucherBanner');
    }

    updateBannerState(status) {
        if (!status) return;
        const actionRow = document.getElementById('voucherActionRow');
        const footnote = document.getElementById('voucherFootnote');
        if (!actionRow) return;

        if (status.is_activated && !status.is_expired) {
            const daysLeft = status.days_left ?? 7;
            actionRow.innerHTML = `
                <div class="voucher-activated-pill">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                    <span>Bạn đã kích hoạt ưu đãi — <strong>VIP Trải nghiệm</strong> (Còn ${daysLeft} ngày)</span>
                </div>
                <button type="button" class="btn-voucher-info-link" id="btnOpenVoucherModal">
                    Xem chi tiết →
                </button>
            `;
            if (footnote) {
                footnote.innerHTML = `
                    <span style="color:#10b981; font-weight:600;">✓ Quyền lợi VIP dùng thử đang có hiệu lực đến ${status.expires_at ? new Date(status.expires_at).toLocaleDateString('vi-VN') : 'hết hạn'}.</span>
                `;
            }
            this.rebindOpenModalBtn();
        } else if (status.is_activated && status.is_expired) {
            actionRow.innerHTML = `
                <div class="voucher-expired-pill">
                    <span>Gói VIP trải nghiệm (7 ngày) đã kết thúc. Bạn đã sử dụng voucher này.</span>
                </div>
            `;
            if (footnote) {
                footnote.innerHTML = `
                    <span>Cảm ơn bạn đã tham gia chương trình THPT Nguyễn Hồng Đạo. Hãy nâng cấp gói để tiếp tục sử dụng.</span>
                `;
            }
        }
    }

    ensureModal() {
        if (document.getElementById('modalVoucherActivation')) return;

        const modalWrap = document.createElement('div');
        modalWrap.id = 'modalVoucherActivation';
        modalWrap.className = 'gari-voucher-modal-backdrop';
        modalWrap.innerHTML = `
            <div class="gari-voucher-modal-card" role="dialog" aria-labelledby="voucherModalTitle" aria-modal="true">
                <button type="button" class="btn-close-voucher-modal" id="btnCloseVoucherModal" aria-label="Đóng cửa sổ">✕</button>

                <!-- Modal Body (Dynamic state: Confirm / Processing / Success) -->
                <div id="voucherModalBody">
                    <div class="voucher-modal-badge">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                        ${CAMPAIGN_TITLE}
                    </div>

                    <h3 class="voucher-modal-title" id="voucherModalTitle">
                        Xác nhận kích hoạt GARI VIP
                    </h3>

                    <p class="voucher-modal-intro">
                        Bạn đang chuẩn bị kích hoạt chương trình GARI VIP miễn phí 7 ngày dành cho học sinh THPT Nguyễn Hồng Đạo.
                    </p>

                    <div class="voucher-details-box">
                        <div class="voucher-detail-item">
                            <span class="detail-label">Mã voucher:</span>
                            <span class="detail-value highlight">${this.voucherCode}</span>
                        </div>
                        <div class="voucher-detail-item">
                            <span class="detail-label">Thời hạn trải nghiệm:</span>
                            <span class="detail-value">7 ngày (tính từ thời điểm kích hoạt)</span>
                        </div>
                        <div class="voucher-detail-item">
                            <span class="detail-label">Hạn mức chẩn đoán:</span>
                            <span class="detail-value">Tối đa 5 lượt/ngày</span>
                        </div>
                        <div class="voucher-detail-item">
                            <span class="detail-label">Loại gói quyền lợi:</span>
                            <span class="detail-value">VIP Trải nghiệm (vip_trial)</span>
                        </div>
                        <div class="voucher-detail-item">
                            <span class="detail-label">Chính sách sử dụng:</span>
                            <span class="detail-value">Chỉ áp dụng 1 lần duy nhất cho mỗi tài khoản</span>
                        </div>
                    </div>

                    <div id="voucherModalNotice" class="voucher-modal-notice" style="display:none;"></div>

                    <div class="voucher-modal-actions">
                        <button type="button" class="btn btn-secondary" id="btnCancelVoucherModal">
                            Để sau
                        </button>
                        <button type="button" class="btn btn-primary btn-confirm-voucher" id="btnConfirmVoucherActivate">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m5 13 4 4L19 7"/></svg>
                            <span>Xác nhận & Kích hoạt</span>
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modalWrap);
        this.modalEl = modalWrap;
    }

    bindEvents() {
        this.rebindOpenModalBtn();

        // Copy Voucher Code button
        const btnCopy = document.getElementById('btnCopyVoucher');
        if (btnCopy) {
            btnCopy.onclick = (e) => {
                e.stopPropagation();
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(this.voucherCode);
                    const origHtml = btnCopy.innerHTML;
                    btnCopy.innerHTML = `<span style="color:#10b981; font-weight:700;">✓ Đã sao chép!</span>`;
                    setTimeout(() => { btnCopy.innerHTML = origHtml; }, 2000);
                }
            };
        }

        // Modal Close triggers
        const btnClose = document.getElementById('btnCloseVoucherModal');
        const btnCancel = document.getElementById('btnCancelVoucherModal');
        if (btnClose) btnClose.onclick = () => this.closeModal();
        if (btnCancel) btnCancel.onclick = () => this.closeModal();

        // Click outside modal backdrop
        if (this.modalEl) {
            this.modalEl.onclick = (e) => {
                if (e.target === this.modalEl) this.closeModal();
            };
        }

        // ESC Key to close modal
        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modalEl && this.modalEl.classList.contains('show')) {
                this.closeModal();
            }
        });

        // Confirm Activation Button
        const btnConfirm = document.getElementById('btnConfirmVoucherActivate');
        if (btnConfirm) {
            btnConfirm.onclick = () => this.handleConfirmActivation();
        }
    }

    rebindOpenModalBtn() {
        const btnOpen = document.getElementById('btnOpenVoucherModal');
        if (btnOpen) {
            btnOpen.onclick = (e) => {
                e.preventDefault();
                this.openModal();
            };
        }
        if (this.bannerEl) {
            this.bannerEl.onclick = (e) => {
                // Don't trigger if clicked copy button
                if (e.target.closest('#btnCopyVoucher')) return;
                this.openModal();
            };
            this.bannerEl.style.cursor = 'pointer';
        }
    }

    openModal() {
        if (!this.modalEl) this.ensureModal();
        this.modalEl.classList.add('show');
    }

    closeModal() {
        if (this.modalEl) this.modalEl.classList.remove('show');
    }

    async handleConfirmActivation() {
        if (this.isActivating) return;

        // Check authentication first
        if (!window.gariAuth || !window.gariAuth.currentUser) {
            const noticeBox = document.getElementById('voucherModalNotice');
            if (noticeBox) {
                noticeBox.style.display = 'block';
                noticeBox.className = 'voucher-modal-notice warning';
                noticeBox.innerHTML = `
                    <strong>Chưa đăng nhập!</strong> Vui lòng đăng nhập hoặc tạo tài khoản để kích hoạt quyền lợi VIP 7 ngày.
                    <div style="margin-top:8px;">
                        <button type="button" class="btn btn-sm btn-primary" id="btnModalGoLogin">Đăng nhập ngay →</button>
                    </div>
                `;
                const btnGoLogin = noticeBox.querySelector('#btnModalGoLogin');
                if (btnGoLogin) {
                    btnGoLogin.onclick = () => {
                        this.closeModal();
                        if (typeof window.openAuthModal === 'function') {
                            window.openAuthModal('login');
                        } else {
                            window.location.href = '/frontend2/login.html';
                        }
                    };
                }
            }
            return;
        }

        const btnConfirm = document.getElementById('btnConfirmVoucherActivate');
        const btnCancel = document.getElementById('btnCancelVoucherModal');
        const noticeBox = document.getElementById('voucherModalNotice');

        this.isActivating = true;
        if (btnConfirm) {
            btnConfirm.disabled = true;
            btnConfirm.innerHTML = `<span class="spinner-small"></span> Đang kích hoạt...`;
        }
        if (btnCancel) btnCancel.disabled = true;
        if (noticeBox) noticeBox.style.display = 'none';

        try {
            const result = await window.gariAuth.activateVoucher(this.voucherCode);
            this.renderSuccessModal(result.voucher || result);
            await this.syncVoucherStatus();

            // Notify user toast if available
            if (typeof window.toast === 'function') {
                window.toast('Kích hoạt GARI VIP 7 ngày thành công!', 'success');
            }
        } catch (err) {
            if (noticeBox) {
                noticeBox.style.display = 'block';
                noticeBox.className = 'voucher-modal-notice error';
                noticeBox.textContent = err.message || 'Kích hoạt voucher không thành công. Vui lòng thử lại sau.';
            }
        } finally {
            this.isActivating = false;
            if (btnConfirm) {
                btnConfirm.disabled = false;
                btnConfirm.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m5 13 4 4L19 7"/></svg>
                    <span>Xác nhận & Kích hoạt</span>
                `;
            }
            if (btnCancel) btnCancel.disabled = false;
        }
    }

    renderSuccessModal(voucher) {
        const modalBody = document.getElementById('voucherModalBody');
        if (!modalBody) return;

        const activatedDate = voucher.activated_at ? new Date(voucher.activated_at).toLocaleDateString('vi-VN') : 'Hôm nay';
        const expiresDate = voucher.expires_at ? new Date(voucher.expires_at).toLocaleDateString('vi-VN') : 'Sau 7 ngày';

        modalBody.innerHTML = `
            <div style="text-align:center; padding:10px 0;">
                <div class="voucher-success-icon-wrap">
                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                </div>

                <div class="voucher-modal-badge" style="margin:12px auto 6px;">
                    ĐÃ KÍCH HOẠT THÀNH CÔNG
                </div>

                <h3 class="voucher-modal-title" style="margin-bottom:8px;">
                    Chúc mừng! GARI VIP trải nghiệm đã được kích hoạt.
                </h3>

                <p class="voucher-modal-intro" style="margin-bottom:16px;">
                    Chào mừng bạn đến với gói đặc quyền dành cho học sinh THPT Nguyễn Hồng Đạo!
                </p>

                <div class="voucher-details-box" style="text-align:left;">
                    <div class="voucher-detail-item">
                        <span class="detail-label">Trạng thái:</span>
                        <span class="detail-value" style="color:#10b981; font-weight:700;">● Đang hoạt động (VIP Trải nghiệm)</span>
                    </div>
                    <div class="voucher-detail-item">
                        <span class="detail-label">Ngày kích hoạt:</span>
                        <span class="detail-value">${activatedDate}</span>
                    </div>
                    <div class="voucher-detail-item">
                        <span class="detail-label">Ngày hết hạn:</span>
                        <span class="detail-value">${expiresDate}</span>
                    </div>
                    <div class="voucher-detail-item">
                        <span class="detail-label">Thời gian còn lại:</span>
                        <span class="detail-value highlight">7 ngày</span>
                    </div>
                    <div class="voucher-detail-item">
                        <span class="detail-label">Giới hạn chẩn đoán:</span>
                        <span class="detail-value">Tối đa 5 lượt/ngày</span>
                    </div>
                </div>

                <div style="margin-top:20px;">
                    <button type="button" class="btn btn-primary" id="btnModalDone" style="width:100%; font-weight:700; padding:10px 16px;">
                        Bắt đầu chẩn đoán AI ngay →
                    </button>
                </div>
            </div>
        `;

        const btnDone = modalBody.querySelector('#btnModalDone');
        if (btnDone) {
            btnDone.onclick = () => {
                this.closeModal();
                const diagnosisSection = document.getElementById('diagnosisWorkspace') || document.querySelector('.dropzone-container');
                if (diagnosisSection) {
                    diagnosisSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            };
        }
    }
}

// Auto-initialize helper
export function initVoucherBanner(containerId = 'gariVoucherBannerContainer') {
    const banner = new GariVoucherBanner(containerId);
    banner.init();
    window.gariVoucherBanner = banner;
    return banner;
}
