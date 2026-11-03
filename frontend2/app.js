// Gari AI Lab — Vietnamese-First AgriTech SaaS Core UI Framework (frontend2/app.js)
// Clean vanilla JS, zero heavy external dependencies.

const svg = (paths) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;

export const ICONS = {
    overview: svg('<rect width="7" height="9" x="3" y="3" rx="1.5"/><rect width="7" height="5" x="14" y="3" rx="1.5"/><rect width="7" height="9" x="14" y="12" rx="1.5"/><rect width="7" height="5" x="3" y="16" rx="1.5"/>'),
    predict: svg('<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><circle cx="12" cy="12" r="3.5"/><path d="m14.5 9.5 2-2"/>'),
    farms: svg('<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>'),
    crops: svg('<path d="M7 20h10"/><path d="M10 20c5.5-2.5.8-6.4 3-10"/><path d="M9.5 9.4c1.1.8 1.8 2.2 2.3 3.7-2 .4-3.5.4-4.8-.3-1.2-.6-2.3-1.9-3-4.2 2.8-.5 4.4 0 5.5.8z"/><path d="M14.1 6a7 7 0 0 0-1.1 4c1.9-.1 3.3-.6 4.3-1.4 1-1 1.6-2.3 1.7-4.6-2.7.1-4 1-4.9 2z"/>'),
    disease: svg('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><circle cx="12" cy="11" r="3"/>'),
    risk: svg('<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/><path d="m11 13-3 5h4l-1 4"/>'),
    support: svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
    reports: svg('<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/>'),
    admin: svg('<path d="M12 2v4"/><path d="M12 18v4"/><path d="m4.93 4.93 2.83 2.83"/><path d="m16.24 16.24 2.83 2.83"/><path d="M2 12h4"/><path d="M18 12h4"/><path d="m4.93 19.07 2.83-2.83"/><path d="m16.24 7.76 2.83-2.83"/><circle cx="12" cy="12" r="3"/>'),
    settings: svg('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.9 2.9l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.9-2.9l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.9-2.9l.1.1a1.7 1.7 0 0 0 1.9.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5h0a1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.9 2.9l-.1.1a1.7 1.7 0 0 0-.3 1.9v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>'),
    leaf: svg('<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>'),
    bell: svg('<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>'),
    menu: svg('<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>'),
    sun: svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
    moon: svg('<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>'),
    cloudSun: svg('<path d="M12 2v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="M20 12h2"/><path d="m19.07 4.93-1.41 1.41"/><path d="M15.947 12.65a4 4 0 0 0-5.925-4.128"/><path d="M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6Z"/>'),
    search: svg('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>'),
    chevronDown: svg('<polyline points="6 9 12 15 18 9"/>'),
    chevronRight: svg('<path d="m9 18 6-6-6-6"/>'),
    sparkles: svg('<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>'),
};

// Categorized Vietnamese SaaS Navigation
export const NAV_GROUPS = [
    {
        title: 'KHÔNG GIAN LÀM VIỆC',
        links: [
            { key: 'overview', href: '/frontend2/index.html', label: 'Tổng quan vườn', icon: ICONS.overview },
            { key: 'predict', href: '/frontend2/predict.html', label: 'Kiểm tra sức khỏe lá', icon: ICONS.predict },
            { key: 'farms', href: '/frontend2/farms.html', label: 'Hồ sơ vườn trồng', icon: ICONS.farms },
        ]
    },
    {
        title: 'TRÍ TUỆ NÔNG NGHIỆP',
        links: [
            { key: 'crops', href: '/frontend2/crops.html', label: 'Thư viện cây trồng', icon: ICONS.crops },
            { key: 'disease', href: '/frontend2/disease.html', label: 'Thư viện bệnh cây', icon: ICONS.disease },
            { key: 'collect', href: '/frontend2/collect.html', label: 'Thu thập thực địa', icon: ICONS.crops, badge: 'Thực nghiệm' },
            { key: 'risk', href: '/frontend2/risk.html', label: 'Giám sát nguy cơ', icon: ICONS.risk, badge: 'Trực tiếp' },
            { key: 'support', href: '/frontend2/support.html', label: 'Tư vấn khuyến nông', icon: ICONS.support },
        ]
    },
    {
        title: 'DOANH NGHIỆP & B2B',
        links: [
            { key: 'landing', href: '/frontend2/landing.html', label: 'Giới thiệu & Pilot', icon: ICONS.sparkles },
            { key: 'onboarding', href: '/frontend2/onboarding.html', label: 'Hồ sơ đối tượng', icon: ICONS.farms },
            { key: 'organization', href: '/frontend2/organization.html', label: 'Tổ chức & Đội ngũ', icon: ICONS.support },
            { key: 'pricing', href: '/frontend2/pricing.html', label: 'Bảng giá & Gói cước', icon: ICONS.sparkles },
            { key: 'reports', href: '/frontend2/reports.html', label: 'Nhật ký theo dõi', icon: ICONS.reports },
            { key: 'admin', href: '/frontend2/admin.html', label: 'Chỉ số & Quản trị', icon: ICONS.admin },
            { key: 'settings', href: '/frontend2/settings.html', label: 'Cài đặt', icon: ICONS.settings },
        ]
    }
];

const THEME_KEY = 'gari-theme';
const SIDEBAR_COLLAPSED_KEY = 'gari-sidebar-collapsed';
export const AUTH_TOKEN_KEY = 'gari_token';
export const USER_INFO_KEY = 'gari_user';

export function getInitials(fullName) {
    if (!fullName) return 'GA';
    const parts = fullName.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function initTheme() {
    try {
        const saved = localStorage.getItem(THEME_KEY);
        if (saved === 'dark') {
            document.documentElement.dataset.theme = 'dark';
        } else {
            document.documentElement.dataset.theme = 'light';
        }
    } catch {
        document.documentElement.dataset.theme = 'light';
    }
}

export function toggleTheme() {
    const isDark = document.documentElement.dataset.theme === 'dark';
    const next = isDark ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem(THEME_KEY, next); } catch {}
    updateThemeIcons();
}

function updateThemeIcons() {
    const isDark = document.documentElement.dataset.theme === 'dark';
    document.querySelectorAll('.btn-theme-toggle').forEach(btn => {
        btn.innerHTML = isDark ? ICONS.sun : ICONS.moon;
        btn.setAttribute('title', isDark ? 'Chuyển sang Giao diện Sáng' : 'Chuyển sang Giao diện Tối');
    });
}

/**
 * Authentication Guard: validates existing session with backend.
 * If invalid or expired, redirects to login page.
 */
export async function checkAuth(redirectIfUnauth = true) {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    try {
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        const res = await fetch('/api/auth/me', { headers, credentials: 'include' });
        if (res.ok) {
            const data = await res.json();
            if (data.success && data.user) {
                localStorage.setItem(USER_INFO_KEY, JSON.stringify(data.user));
                return data.user;
            }
        }
    } catch (err) {
        console.warn('Xác thực phiên trực tuyến thất bại:', err);
    }

    // Invalid session
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(USER_INFO_KEY);

    if (redirectIfUnauth) {
        const currentPath = window.location.pathname + window.location.search;
        window.location.href = `/frontend2/login.html?redirect=${encodeURIComponent(currentPath)}`;
    }
    return null;
}

/**
 * Log out user: invalidates session on server and cleans local storage
 */
export async function logout() {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    try {
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        await fetch('/api/auth/logout', { method: 'POST', headers, credentials: 'include' });
    } catch (e) {}

    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(USER_INFO_KEY);
    toast('Đã đăng xuất thành công.');
    setTimeout(() => {
        window.location.href = '/frontend2/login.html';
    }, 300);
}

export function formatAccountType(type) {
    const map = {
        'farmer': 'Nông Hộ Cá Thể',
        'cooperative': 'Hợp Tác Xã',
        'expert': 'Chuyên Gia BVTV',
        'enterprise': 'Doanh Nghiệp'
    };
    return map[type] || type || 'Nông Hộ Cá Thể';
}

/**
 * Initializes the SaaS shell for a given page with complete Vietnamese rendering
 */
export async function setupSaaSShell(activeKey = 'overview', activeTitle = 'Tổng quan nông nghiệp') {
    initTheme();

    // Check authentication
    const currentUser = await checkAuth(true);
    const userFullName = currentUser ? (currentUser.full_name || currentUser.name || 'Người dùng Gari') : 'Kỹ sư Đan Huỳnh';
    const userAccountType = currentUser ? formatAccountType(currentUser.account_type) : 'Chuyên gia Nông học';
    const userEmail = currentUser ? currentUser.email : 'danhuynh@gari.vn';
    const initials = getInitials(userFullName);

    const sidebar = document.getElementById('appSidebar');
    const topbar = document.getElementById('appTopbar');
    const isCollapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true';

    if (sidebar) {
        if (isCollapsed) sidebar.classList.add('collapsed');

        const navGroupsHtml = NAV_GROUPS.map(group => {
            const linksHtml = group.links.map(item => {
                const isActive = item.key === activeKey;
                return `
                    <a href="${item.href}" class="nav-link ${isActive ? 'active' : ''}" data-key="${item.key}" title="${item.label}">
                        <span class="nav-link-icon">${item.icon}</span>
                        <span class="nav-link-text">${item.label}</span>
                        ${item.badge ? `<span class="nav-link-badge">${item.badge}</span>` : ''}
                    </a>
                `;
            }).join('');

            return `
                <div class="nav-group-title">${group.title}</div>
                ${linksHtml}
            `;
        }).join('');

        sidebar.innerHTML = `
            <div class="sidebar-brand">
                <a href="/frontend2/index.html" style="display:flex; align-items:center; gap:10px;">
                    <div class="brand-logo">
                        ${ICONS.leaf}
                    </div>
                    <div class="brand-info">
                        <div class="brand-title-row">
                            <span class="brand-name">GARI</span>
                            <span class="brand-tag">AI LAB</span>
                        </div>
                        <span class="brand-sub">Trí tuệ Nông nghiệp</span>
                    </div>
                </a>
            </div>

            <!-- Workspace Selector -->
            <div class="workspace-card" id="workspaceSelector" title="Chuyển vùng canh tác">
                <span class="workspace-dot"></span>
                <div class="workspace-info">
                    <span class="workspace-title">Không gian Nông trại</span>
                    <span class="workspace-plan">${userAccountType}</span>
                </div>
                <span class="workspace-chevron">${ICONS.chevronDown}</span>
            </div>

            <!-- Navigation Links -->
            <nav class="sidebar-nav">
                ${navGroupsHtml}
            </nav>

            <!-- User Profile in Sidebar Footer -->
            <div class="sidebar-footer">
                <div class="sidebar-user-card" id="sidebarUserCard" title="Xem hồ sơ">
                    <div class="user-avatar" id="sidebarAvatar">${initials}</div>
                    <div class="sidebar-user-info">
                        <span class="sidebar-user-name" id="sidebarUserName">${userFullName}</span>
                        <span class="sidebar-user-role">
                            <span class="pulse-online"></span>
                            ${userAccountType}
                        </span>
                    </div>
                </div>
            </div>
        `;
    }

    if (topbar) {
        topbar.innerHTML = `
            <div class="topbar-left">
                <button type="button" class="sidebar-toggle-btn" id="btnToggleSidebar" title="Thu gọn / Mở rộng thanh bên">
                    ${ICONS.menu}
                </button>
                <div class="breadcrumbs">
                    <span class="breadcrumb-root">Gari</span>
                    <span class="breadcrumb-sep">/</span>
                    <span class="breadcrumb-current" id="topbarCrumb">${activeTitle}</span>
                </div>
            </div>

            <div class="topbar-center">
                <div class="topbar-search-trigger" id="topbarSearchTrigger" role="button" tabindex="0" title="Tìm kiếm nhanh (Ctrl + K)">
                    ${ICONS.search}
                    <span>Tìm nhanh cây trồng, bệnh cây, nông trại...</span>
                    <kbd class="search-kbd">Ctrl K</kbd>
                </div>
            </div>

            <div class="topbar-right">
                <div class="weather-badge" id="topbarWeather" title="Trạm quan trắc vi khí hậu tự động">
                    ${ICONS.cloudSun}
                    <span>Trạm Ba Vì: 24.5°C • 82% RH</span>
                </div>

                <div class="lang-pill" id="langSelector" title="Ngôn ngữ hệ thống">
                    <span>🇻🇳</span>
                    <span>VN</span>
                </div>

                <button type="button" class="topbar-icon-btn btn-theme-toggle" id="btnTheme" title="Chuyển đổi Sáng / Tối">
                    ${document.documentElement.dataset.theme === 'dark' ? ICONS.sun : ICONS.moon}
                </button>

                <!-- Notifications Dropdown -->
                <div style="position:relative;">
                    <button type="button" class="topbar-icon-btn" id="btnAlerts" title="Cảnh báo nông nghiệp mới">
                        ${ICONS.bell}
                        <span class="unread-badge" id="unreadBadge" style="display:none;"></span>
                    </button>
                    <div class="notifications-dropdown" id="notificationsDropdown">
                        <div class="notif-header">
                            <span class="notif-title">Cảnh báo Nông nghiệp</span>
                            <span class="notif-count" id="notifCountBadge">0 thông báo</span>
                        </div>
                        <div class="notif-list" id="notifListContainer">
                            <div style="padding:16px; text-align:center; color:var(--text-muted); font-size:12px;">Đang tải cảnh báo...</div>
                        </div>
                        <div class="notif-footer">
                            <a href="/frontend2/risk.html">Xem toàn bộ trạm quan trắc →</a>
                        </div>
                    </div>
                </div>

                <!-- User Profile Dropdown Button -->
                <div style="position:relative;">
                    <div class="user-profile" id="userProfileBtn" title="Hồ sơ tài khoản">
                        <div class="user-avatar" id="topbarAvatar">${initials}</div>
                        <div class="user-meta">
                            <span class="user-name" id="topbarUserName">${userFullName}</span>
                            <span class="user-role" id="topbarUserRole">${userAccountType}</span>
                        </div>
                        <span style="font-size:10px; color:var(--text-muted); margin-left:2px;">▼</span>
                    </div>

                    <!-- Dropdown Panel -->
                    <div class="user-dropdown-panel" id="userDropdownPanel">
                        <div class="user-dropdown-header">
                            <div style="font-weight:700; font-size:13px; color:var(--text-main);" id="dropdownFullName">${userFullName}</div>
                            <div style="font-size:11.5px; color:var(--text-muted);" id="dropdownEmail">${userEmail}</div>
                            <div style="margin-top:4px;"><span class="pill pill-neutral" id="dropdownAccountType">${userAccountType}</span></div>
                        </div>
                        <div class="user-dropdown-divider"></div>
                        <a href="/frontend2/farms.html" class="user-dropdown-item">
                            <span>🌾</span> <span>Nông trại của tôi</span>
                        </a>
                        <a href="/frontend2/data-management.html" class="user-dropdown-item">
                            <span>🛡️</span> <span>Dữ liệu cá nhân (DSR)</span>
                        </a>
                        <a href="/frontend2/privacy-policy.html" class="user-dropdown-item">
                            <span>📜</span> <span>Chính sách bảo mật</span>
                        </a>
                        <a href="/frontend2/settings.html" class="user-dropdown-item">
                            <span>⚙️</span> <span>Cài đặt tài khoản</span>
                        </a>
                        <div class="user-dropdown-divider"></div>
                        <button type="button" class="user-dropdown-item logout-btn" id="btnLogoutAction">
                            <span>🚪</span> <span style="color:var(--danger); font-weight:600;">Đăng xuất</span>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    ensureCommandPalette();
    bindShellEvents();
    fetchLiveWeather();
    fetchNotifications();
    ensureLegalFooter();
    ensureCookieBanner();
}

/**
 * Creates and binds the Command Palette (Ctrl+K)
 */
function ensureCommandPalette() {
    if (document.getElementById('cmdPaletteBackdrop')) return;

    const modal = document.createElement('div');
    modal.id = 'cmdPaletteBackdrop';
    modal.className = 'cmd-palette-backdrop';
    modal.innerHTML = `
        <div class="cmd-palette-modal">
            <div class="cmd-input-wrap">
                ${ICONS.search}
                <input type="text" class="cmd-input" id="cmdInput" placeholder="Tìm kiếm trang, cây trồng hoặc bệnh cây... (Esc để đóng)" autocomplete="off">
            </div>
            <div class="cmd-results" id="cmdResults">
                <div class="cmd-group-label">ĐIỀU HƯỚNG NHANH</div>
                <a href="/frontend2/index.html" class="cmd-item">
                    <span class="cmd-item-icon">${ICONS.overview}</span>
                    <span>Tổng quan nông nghiệp</span>
                    <span class="cmd-item-badge">Trang</span>
                </a>
                <a href="/frontend2/predict.html" class="cmd-item">
                    <span class="cmd-item-icon">${ICONS.predict}</span>
                    <span>Chẩn đoán bệnh lá bằng AI</span>
                    <span class="cmd-item-badge">Công cụ</span>
                </a>
                <a href="/frontend2/farms.html" class="cmd-item">
                    <span class="cmd-item-icon">${ICONS.farms}</span>
                    <span>Danh sách nông trại của tôi</span>
                    <span class="cmd-item-badge">Dữ liệu</span>
                </a>
                <a href="/frontend2/crops.html" class="cmd-item">
                    <span class="cmd-item-icon">${ICONS.crops}</span>
                    <span>Thư viện 44 cây trồng AI</span>
                    <span class="cmd-item-badge">Mô hình</span>
                </a>
                <a href="/frontend2/risk.html" class="cmd-item">
                    <span class="cmd-item-icon">${ICONS.risk}</span>
                    <span>Giám sát nguy cơ dịch hại & vi khí hậu</span>
                    <span class="cmd-item-badge">IoT</span>
                </a>
                <a href="/frontend2/support.html" class="cmd-item">
                    <span class="cmd-item-icon">${ICONS.support}</span>
                    <span>Hỗ trợ & Tư vấn chuyên gia nông học</span>
                    <span class="cmd-item-badge">Dịch vụ</span>
                </a>
                <div class="cmd-group-label">MÔ HÌNH CÂY TRỒNG PHỔ BIẾN</div>
                <a href="/frontend2/predict.html?crop=Tomato" class="cmd-item">
                    <span class="cmd-item-icon">${ICONS.leaf}</span>
                    <span>Cà chua (Tomato) — Đốm vi khuẩn, Mốc sương</span>
                    <span class="cmd-item-badge">ConvNeXt</span>
                </a>
                <a href="/frontend2/predict.html?crop=Rice" class="cmd-item">
                    <span class="cmd-item-icon">${ICONS.leaf}</span>
                    <span>Lúa (Rice) — Đạo ôn lá, Đốm nâu</span>
                    <span class="cmd-item-badge">ConvNeXt</span>
                </a>
                <a href="/frontend2/predict.html?crop=Potato" class="cmd-item">
                    <span class="cmd-item-icon">${ICONS.leaf}</span>
                    <span>Khoai tây (Potato) — Bệnh úa sớm, Mốc sương</span>
                    <span class="cmd-item-badge">ConvNeXt</span>
                </a>
            </div>
            <div class="cmd-footer">
                <span>Dùng phím ↑ ↓ để di chuyển, Enter để mở</span>
                <span>ESC để đóng</span>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    const input = modal.querySelector('#cmdInput');
    const results = modal.querySelector('#cmdResults');

    input.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        const items = results.querySelectorAll('.cmd-item');
        items.forEach(it => {
            const text = it.textContent.toLowerCase();
            it.style.display = text.includes(query) ? 'flex' : 'none';
        });
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeCommandPalette();
    });
}

export function openCommandPalette() {
    const modal = document.getElementById('cmdPaletteBackdrop');
    if (!modal) return;
    modal.classList.add('open');
    const input = document.getElementById('cmdInput');
    if (input) {
        input.value = '';
        input.focus();
        const items = modal.querySelectorAll('.cmd-item');
        items.forEach(it => it.style.display = 'flex');
    }
}

export function closeCommandPalette() {
    const modal = document.getElementById('cmdPaletteBackdrop');
    if (modal) modal.classList.remove('open');
}

function bindShellEvents() {
    const toggleBtn = document.getElementById('btnToggleSidebar');
    const sidebar = document.getElementById('appSidebar');
    const backdrop = document.getElementById('sidebarBackdrop');

    if (toggleBtn && sidebar) {
        toggleBtn.onclick = () => {
            if (window.innerWidth <= 1024) {
                sidebar.classList.toggle('drawer-open');
                if (backdrop) backdrop.classList.toggle('show');
            } else {
                sidebar.classList.toggle('collapsed');
                const isCollapsed = sidebar.classList.contains('collapsed');
                try { localStorage.setItem(SIDEBAR_COLLAPSED_KEY, isCollapsed ? 'true' : 'false'); } catch {}
            }
        };
    }

    if (backdrop && sidebar) {
        backdrop.onclick = () => {
            sidebar.classList.remove('drawer-open');
            backdrop.classList.remove('show');
        };
    }

    const themeBtn = document.getElementById('btnTheme');
    if (themeBtn) {
        themeBtn.onclick = toggleTheme;
    }

    const searchTrigger = document.getElementById('topbarSearchTrigger');
    if (searchTrigger) {
        searchTrigger.onclick = openCommandPalette;
    }

    const langBtn = document.getElementById('langSelector');
    if (langBtn) {
        langBtn.onclick = () => {
            toast('Hệ thống đang hoạt động ở chế độ Tiếng Việt mặc định.');
        };
    }

    // Alerts Dropdown Toggle
    const alertsBtn = document.getElementById('btnAlerts');
    const notifDropdown = document.getElementById('notificationsDropdown');
    if (alertsBtn && notifDropdown) {
        alertsBtn.onclick = (e) => {
            e.stopPropagation();
            if (userDropdown) userDropdown.classList.remove('show');
            notifDropdown.classList.toggle('show');
        };
    }

    // User Profile Dropdown Toggle
    const userBtn = document.getElementById('userProfileBtn');
    const userDropdown = document.getElementById('userDropdownPanel');
    if (userBtn && userDropdown) {
        userBtn.onclick = (e) => {
            e.stopPropagation();
            if (notifDropdown) notifDropdown.classList.remove('show');
            userDropdown.classList.toggle('show');
        };
    }

    // Logout Action
    const logoutBtn = document.getElementById('btnLogoutAction');
    if (logoutBtn) {
        logoutBtn.onclick = () => {
            if (confirm('Bạn có chắc chắn muốn đăng xuất khỏi Gari AI Lab?')) {
                logout();
            }
        };
    }

    // Global click listener to close dropdowns
    document.addEventListener('click', (e) => {
        if (notifDropdown && !notifDropdown.contains(e.target) && e.target !== alertsBtn) {
            notifDropdown.classList.remove('show');
        }
        if (userDropdown && !userDropdown.contains(e.target) && !userBtn.contains(e.target)) {
            userDropdown.classList.remove('show');
        }
    });

    // Global keyboard shortcut: Ctrl+K or Cmd+K
    window.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            const modal = document.getElementById('cmdPaletteBackdrop');
            if (modal && modal.classList.contains('open')) {
                closeCommandPalette();
            } else {
                openCommandPalette();
            }
        }
        if (e.key === 'Escape') {
            closeCommandPalette();
            if (notifDropdown) notifDropdown.classList.remove('show');
            if (userDropdown) userDropdown.classList.remove('show');
        }
    });

    const workspaceBtn = document.getElementById('workspaceSelector');
    if (workspaceBtn) {
        workspaceBtn.onclick = () => {
            window.location.href = '/frontend2/farms.html';
        };
    }
}

async function fetchLiveWeather() {
    try {
        const res = await fetch('/api/risk/monitoring');
        const data = await res.json();
        if (data.success && data.observed_weather) {
            const w = data.observed_weather;
            const el = document.getElementById('topbarWeather');
            if (el) {
                const station = w.station.split('&')[0].replace('Trạm Khí tượng', '').trim();
                el.innerHTML = `${ICONS.cloudSun} <span>${station}: ${w.temperature_c}°C • ${w.humidity_pct}% RH</span>`;
            }
        }
    } catch {
        // Keep default
    }
}

async function fetchNotifications() {
    const listContainer = document.getElementById('notifListContainer');
    const badge = document.getElementById('unreadBadge');
    const countBadge = document.getElementById('notifCountBadge');
    if (!listContainer) return;

    try {
        const data = await fetchJSON('/api/notifications');
        const notifs = data.notifications || [];
        const unreadCount = notifs.filter(n => !n.is_read).length;

        if (badge) {
            badge.style.display = unreadCount > 0 ? 'block' : 'none';
        }
        if (countBadge) {
            countBadge.textContent = unreadCount > 0 ? `${unreadCount} mới` : `${notifs.length} thông báo`;
        }

        if (notifs.length === 0) {
            listContainer.innerHTML = '<div style="padding:20px; text-align:center; color:var(--text-muted); font-size:12.5px;">Chưa có thông báo nào.</div>';
            return;
        }

        listContainer.innerHTML = notifs.map(n => `
            <div class="notif-item ${n.is_read ? 'read' : 'unread'}" style="${n.is_read ? 'opacity:0.75;' : 'background:var(--primary-soft);'}">
                <div class="notif-item-head">
                    <span class="notif-item-title">${n.title}</span>
                    <span class="pill ${n.notification_type === 'warning' ? 'pill-warning' : 'pill-success'}">${n.notification_type === 'warning' ? 'Cảnh báo' : 'Hệ thống'}</span>
                </div>
                <div class="notif-item-desc">${n.message}</div>
                <div style="font-size:10.5px; color:var(--text-muted); margin-top:2px;">${n.created_at || 'Gần đây'}</div>
            </div>
        `).join('');

    } catch (err) {
        listContainer.innerHTML = '<div style="padding:16px; text-align:center; color:var(--text-muted); font-size:12px;">Đang cập nhật cảnh báo trực tiếp.</div>';
    }
}

export function toast(msg, type = 'info') {
    let t = document.getElementById('globalToast');
    if (!t) {
        t = document.createElement('div');
        t.id = 'globalToast';
        t.className = 'toast-notice';
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2600);
}

/**
 * Animated number count-up for KPI cards
 */
export function animateCountUp(elementId, targetValue, duration = 800, suffix = '', decimals = 0) {
    const el = document.getElementById(elementId);
    if (!el) return;
    
    if (typeof targetValue !== 'number' || isNaN(targetValue)) {
        el.textContent = targetValue != null ? `${targetValue}${suffix}` : 'Chưa có dữ liệu';
        return;
    }

    const start = 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const ease = 1 - Math.pow(1 - progress, 3);
        const current = start + (targetValue - start) * ease;
        el.textContent = `${current.toFixed(decimals)}${suffix}`;
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            el.textContent = `${targetValue.toFixed(decimals)}${suffix}`;
        }
    }

    requestAnimationFrame(update);
}

export async function fetchJSON(url, opts = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 6000); // 6s timeout

    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    const headers = {
        'Accept': 'application/json',
        ...(opts.headers || {})
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    try {
        const res = await fetch(url, {
            ...opts,
            headers,
            credentials: 'include',
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (res.status === 401) {
            // Unauthorized access - clear session and redirect
            localStorage.removeItem(AUTH_TOKEN_KEY);
            localStorage.removeItem(USER_INFO_KEY);
            const currentPath = window.location.pathname + window.location.search;
            if (!currentPath.includes('login.html') && !currentPath.includes('register.html')) {
                window.location.href = `/frontend2/login.html?redirect=${encodeURIComponent(currentPath)}`;
            }
            throw new Error('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
        }

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || data.error || data.message || 'Lỗi yêu cầu API');
        return data;
    } catch (err) {
        clearTimeout(timeoutId);
        throw err;
    }
}

export function bindDropzone(dropEl, fileInput) {
    if (!dropEl || !fileInput) return;

    ['dragenter', 'dragover'].forEach(evt => {
        dropEl.addEventListener(evt, (e) => {
            e.preventDefault();
            dropEl.style.borderColor = 'var(--primary)';
            dropEl.style.backgroundColor = 'var(--primary-soft)';
        });
    });

    ['dragleave', 'drop'].forEach(evt => {
        dropEl.addEventListener(evt, (e) => {
            e.preventDefault();
            dropEl.style.borderColor = 'var(--border)';
            dropEl.style.backgroundColor = 'var(--surface)';
        });
    });

    dropEl.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            fileInput.files = files;
            fileInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
    });

    dropEl.addEventListener('click', (e) => {
        if (e.target !== fileInput) {
            fileInput.click();
        }
    });
}

// Backwards compatibility
export function initAppShell(key, title) {
    setupSaaSShell(key, title);
}
export function initBottomNav() {}
export function animateIn() {}
export function registerReveal() {}
export function animateHero() {}
export function initFloatingChat() {}

/**
 * Injects WCAG AA compliant Legal Footer into the page if not present
 */
export function ensureLegalFooter() {
    if (document.getElementById('appLegalFooter')) return;

    const footer = document.createElement('footer');
    footer.id = 'appLegalFooter';
    footer.className = 'app-legal-footer';
    footer.setAttribute('role', 'contentinfo');
    footer.innerHTML = `
        <div class="legal-footer-content">
            <div class="legal-footer-info">
                <strong>Gari AI Lab</strong> — Nền tảng AgriTech Trí tuệ Nhân tạo Việt Nam (Pilot Beta)
                <span class="legal-footer-sep">•</span>
                <span>Tuân thủ Nghị định 13/2023/NĐ-CP & An toàn Dữ liệu Nông học</span>
            </div>
            <div class="legal-footer-links">
                <a href="/frontend2/privacy-policy.html">Chính sách bảo mật</a>
                <a href="/frontend2/terms-of-service.html">Điều khoản dịch vụ</a>
                <a href="/frontend2/cookie-policy.html">Chính sách Cookie</a>
                <a href="/frontend2/refund-policy.html">Chính sách hoàn tiền</a>
                <a href="/frontend2/data-management.html">Quản lý dữ liệu (DSR)</a>
                <button type="button" class="btn-cookie-reopen" id="btnReopenCookies">Cài đặt Cookie</button>
            </div>
        </div>
    `;

    const target = document.querySelector('.app-content') || document.querySelector('.app-main') || document.querySelector('.main-content') || document.body;
    target.appendChild(footer);

    const reopenBtn = document.getElementById('btnReopenCookies');
    if (reopenBtn) {
        reopenBtn.onclick = () => openCookieModal();
    }
}

/**
 * Injects Accessible Cookie Banner & Preference Modal
 */
export function ensureCookieBanner() {
    if (document.getElementById('cookieBannerWrap')) return;

    const savedConsent = localStorage.getItem('gari_cookie_consent');

    if (!document.getElementById('cookieModalBackdrop')) {
        const modal = document.createElement('div');
        modal.id = 'cookieModalBackdrop';
        modal.className = 'cookie-modal-backdrop';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-labelledby', 'cookieModalTitle');
        modal.innerHTML = `
            <div class="cookie-modal-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <h3 id="cookieModalTitle" style="font-size:17px; font-weight:700; color:var(--text-main); display:flex; align-items:center; gap:8px;">
                        🍪 Tùy Chọn Cookie & Quyền Riêng Tư
                    </h3>
                    <button type="button" class="btn btn-ghost btn-sm" id="btnCloseCookieModal" style="font-size:18px; padding:4px 8px;">✕</button>
                </div>
                <p style="font-size:13px; color:var(--text-secondary); line-height:1.5;">
                    Gari AI Lab cam kết KHÔNG sử dụng cookie theo dõi quảng cáo của bên thứ ba. Bạn có thể tùy chỉnh các lưu trữ trình duyệt dưới đây:
                </p>
                <div>
                    <div class="cookie-pref-item">
                        <div>
                            <div style="font-weight:700; font-size:13.5px; color:var(--text-main);">Cookie kỹ thuật bắt buộc</div>
                            <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Duy trì phiên đăng nhập bảo mật và thực thi giới hạn quota chẩn đoán.</div>
                        </div>
                        <span class="pill pill-success" style="white-space:nowrap;">Luôn bật</span>
                    </div>
                    <div class="cookie-pref-item">
                        <div>
                            <div style="font-weight:700; font-size:13.5px; color:var(--text-main);">Bộ nhớ giao diện & Cài đặt</div>
                            <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Lưu tùy chọn giao diện Sáng/Tối và trạng thái thu gọn thanh bên.</div>
                        </div>
                        <input type="checkbox" id="prefThemeStorage" checked style="accent-color:var(--primary); width:18px; height:18px; cursor:pointer;" />
                    </div>
                </div>
                <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:8px;">
                    <button type="button" class="btn btn-secondary btn-sm" id="btnRejectOptionalCookies">
                        Chỉ dùng cần thiết
                    </button>
                    <button type="button" class="btn btn-primary btn-sm" id="btnSaveCookiePreferences">
                        Lưu lựa chọn của tôi
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        document.getElementById('btnCloseCookieModal').onclick = () => closeCookieModal();
        document.getElementById('btnRejectOptionalCookies').onclick = () => {
            applyCookieConsent('essential_only');
            closeCookieModal();
        };
        document.getElementById('btnSaveCookiePreferences').onclick = () => {
            applyCookieConsent('all');
            closeCookieModal();
        };
    }

    window.gariOpenCookieModal = openCookieModal;

    // Show banner if not yet decided
    if (!savedConsent) {
        const banner = document.createElement('div');
        banner.id = 'cookieBannerWrap';
        banner.className = 'cookie-banner-wrap';
        banner.setAttribute('role', 'region');
        banner.setAttribute('aria-label', 'Thông báo Cookie và Quyền riêng tư');
        banner.innerHTML = `
            <div class="cookie-banner-head">
                <span>🛡️</span>
                <span>Bảo vệ quyền riêng tư & Cookie tại Gari AI Lab</span>
            </div>
            <div class="cookie-banner-desc">
                Chúng tôi cam kết <strong>không sử dụng cookie theo dõi quảng cáo bên thứ ba</strong>. 
                Hệ thống chỉ sử dụng cookie kỹ thuật bắt buộc để duy trì phiên làm việc và bảo vệ dữ liệu nông học theo 
                <a href="/frontend2/privacy-policy.html" style="color:var(--primary); font-weight:600; text-decoration:underline;">Nghị định 13/2023/NĐ-CP</a>.
            </div>
            <div class="cookie-banner-btns">
                <button type="button" class="btn btn-ghost btn-sm" id="btnBannerCustomize">Tùy chỉnh</button>
                <button type="button" class="btn btn-secondary btn-sm" id="btnBannerEssential">Chỉ dùng cần thiết</button>
                <button type="button" class="btn btn-primary btn-sm" id="btnBannerAcceptAll">Chấp nhận tất cả</button>
            </div>
        `;
        document.body.appendChild(banner);

        document.getElementById('btnBannerAcceptAll').onclick = () => {
            applyCookieConsent('all');
            banner.remove();
        };
        document.getElementById('btnBannerEssential').onclick = () => {
            applyCookieConsent('essential_only');
            banner.remove();
        };
        document.getElementById('btnBannerCustomize').onclick = () => {
            openCookieModal();
        };
    }
}

function openCookieModal() {
    const modal = document.getElementById('cookieModalBackdrop');
    if (modal) modal.classList.add('open');
}

function closeCookieModal() {
    const modal = document.getElementById('cookieModalBackdrop');
    if (modal) modal.classList.remove('open');
}

function applyCookieConsent(choice) {
    localStorage.setItem('gari_cookie_consent', choice);
    toast(choice === 'all' ? 'Đã lưu tùy chọn Cookie đầy đủ.' : 'Đã chọn chỉ dùng Cookie bắt buộc.');
    const banner = document.getElementById('cookieBannerWrap');
    if (banner) banner.remove();

    fetch('/api/privacy/consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            consent_type: 'cookie_preferences',
            status: 'granted',
            metadata: { choice: choice }
        })
    }).catch(() => {});
}
