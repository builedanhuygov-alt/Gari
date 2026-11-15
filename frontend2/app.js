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
    community: svg('<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>'),
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
    calendar: svg('<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>'),
    camera: svg('<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>'),
    bot: svg('<rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/>'),
    check: svg('<polyline points="20 6 9 17 4 12"/>'),
    alertTriangle: svg('<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'),
};

// Categorized Vietnamese SaaS Navigation with Dynamic Role & Organization Gating
export function getNavGroups(currentUser) {
    const hasOrg = !!(currentUser && (currentUser.has_organizations || (currentUser.organizations && currentUser.organizations.length > 0)));
    const isHost = !!(currentUser && currentUser.is_host_admin);

    const groups = [
        {
            title: 'NÔNG HỘ',
            links: [
                { key: 'overview', href: '/frontend2/index.html', label: 'Tổng quan vườn', icon: ICONS.overview },
                { key: 'farms', href: '/frontend2/farms.html', label: 'Vườn trồng & Nông trại', icon: ICONS.farms },
                { key: 'predict', href: '/frontend2/predict.html', label: 'GARI Leaf Intelligence', icon: ICONS.predict },
                { key: 'agents', href: '/frontend2/agents.html', label: 'Trợ lý AI Nông nghiệp', icon: ICONS.bot },
                { key: 'reports', href: '/frontend2/reports.html', label: 'Lịch sử chẩn đoán', icon: ICONS.reports },
            ]
        },
        {
            title: 'CHĂM SÓC CÂY TRỒNG',
            links: [
                { key: 'calendar', href: '/frontend2/crops.html#calendar', label: 'Lịch canh tác thông minh', icon: ICONS.calendar },
                { key: 'crops', href: '/frontend2/crops.html', label: 'Thư viện cây trồng', icon: ICONS.crops },
                { key: 'disease', href: '/frontend2/disease.html', label: 'Thư viện bệnh cây', icon: ICONS.disease },
                { key: 'support', href: '/frontend2/support.html', label: 'Tư vấn chuyên gia', icon: ICONS.support },
                { key: 'community', href: '/frontend2/community.html', label: 'Cộng đồng & Tri thức', icon: ICONS.community },
            ]
        },
        {
            title: 'THEO DÕI RỦI RO',
            links: [
                { key: 'risk', href: '/frontend2/risk.html', label: 'Cảnh báo dịch hại & Giám sát', icon: ICONS.risk },
            ]
        },
        {
            title: 'DỊCH VỤ',
            links: [
                { key: 'pricing', href: '/frontend2/pricing.html', label: 'Gói dịch vụ & Pilot', icon: ICONS.sparkles },
                { key: 'collect', href: '/frontend2/collect.html', label: 'Thu thập thực địa', icon: ICONS.camera },
            ]
        }
    ];

    // DOANH NGHIỆP is strictly gated: only shown if user belongs to an organization
    if (hasOrg) {
        groups.push({
            title: 'DOANH NGHIỆP',
            links: [
                { key: 'organization', href: '/frontend2/organization.html', label: 'Tổ chức & Đội ngũ', icon: ICONS.support },
                { key: 'b2b_reports', href: '/frontend2/reports.html', label: 'Báo cáo vùng trồng', icon: ICONS.reports },
                { key: 'onboarding', href: '/frontend2/onboarding.html', label: 'Onboarding B2B', icon: ICONS.farms },
                { key: 'admin', href: '/frontend2/admin.html', label: 'Chỉ số & Quản trị', icon: ICONS.admin },
            ]
        });
    }

    // Expert Portal is available to certified experts or host admins
    const isExpert = !!(currentUser && (currentUser.is_expert || currentUser.is_host_admin));
    if (isExpert) {
        groups.push({
            title: 'CHUYÊN GIA NÔNG NGHIỆP',
            links: [
                { key: 'expert', href: '/frontend2/expert-portal.html', label: 'Cổng Chuyên gia (Portal)', icon: ICONS.support, badge: 'Expert' },
            ]
        });
    }

    // Host System Console is strictly gated: only shown if is_host_admin is True on server
    if (isHost) {
        groups.push({
            title: 'HỆ THỐNG MÁY CHỦ',
            links: [
                { key: 'host', href: '/host', label: 'Host Admin Console', icon: ICONS.admin, badge: 'Host' },
            ]
        });
    }

    // Centralized Feature Availability Filtering
    const features = window.GARI_FEATURES || { farms: false, community: false, hostConsole: true };
    const filteredGroups = groups.map(g => ({
        ...g,
        links: g.links.filter(l => {
            if (l.key === 'farms' && features.farms === false) return false;
            if (l.key === 'community' && features.community === false) return false;
            if (l.key === 'host' && (!currentUser || !currentUser.is_host_admin || features.hostConsole === false)) return false;
            return true;
        })
    })).filter(g => g.links.length > 0);

    return filteredGroups;
}

export const NAV_GROUPS = getNavGroups(null);

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
    try {
        const token = localStorage.getItem(AUTH_TOKEN_KEY);
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        const res = await fetch('/api/v1/auth/me', { headers, credentials: 'include' });
        if (res.ok) {
            const data = await res.json();
            const user = (data && data.user) ? data.user : (data && data.email ? data : null);
            if (user) {
                localStorage.setItem(USER_INFO_KEY, JSON.stringify(user));
                return user;
            }
        }
        if (res.status === 401) {
            // Explicitly invalid or revoked session
            localStorage.removeItem(AUTH_TOKEN_KEY);
            localStorage.removeItem(USER_INFO_KEY);
            if (redirectIfUnauth) {
                const currentPath = window.location.pathname + window.location.search;
                window.location.href = `/frontend2/login.html?redirect=${encodeURIComponent(currentPath)}`;
            }
            return null;
        }
    } catch (err) {
        console.warn('[GARI Shell] Session check offline fallback:', err?.message || err);
        // On network error, retain cached user to prevent unnecessary logout
        try {
            const cached = JSON.parse(localStorage.getItem(USER_INFO_KEY));
            if (cached && (cached.email || cached.id)) {
                return cached;
            }
        } catch (_) {}
    }

    // Invalid session fallback
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(USER_INFO_KEY);
    if (redirectIfUnauth) {
        const currentPath = window.location.pathname + window.location.search;
        window.location.href = `/frontend2/login.html?redirect=${encodeURIComponent(currentPath)}`;
    }
    return null;
}

/**
 * Log out user: invalidates session on server, signs out of Firebase, and cleans local storage
 */
export async function logout() {
    if (window.gariAuth) {
        try {
            await window.gariAuth.logout();
        } catch (_) {}
    }

    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    try {
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        await fetch('/api/auth/logout', { method: 'POST', headers, credentials: 'include' });
    } catch (e) {}

    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(USER_INFO_KEY);
    localStorage.removeItem('gari_host_token');
    sessionStorage.clear();
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
export async function setupSaaSShell(activeKey = 'overview', activeTitle = 'Tổng quan nông nghiệp', redirectIfUnauth = true) {
    initTheme();

    // Check authentication: allow public onboarding & preview gateway on predict & overview pages
    const shouldRedirect = (activeKey === 'predict' || activeKey === 'overview') ? false : redirectIfUnauth;
    const currentUser = await checkAuth(shouldRedirect);
    const userFullName = currentUser ? (currentUser.full_name || currentUser.name || 'Người dùng Gari') : 'Khách nông hộ';
    const userAccountType = currentUser ? formatAccountType(currentUser.account_type) : 'Chưa đăng nhập';
    const userEmail = currentUser ? currentUser.email : '';
    const initials = currentUser ? getInitials(userFullName) : 'G';

    const sidebar = document.getElementById('appSidebar');
    const topbar = document.getElementById('appTopbar');
    const isCollapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true';

    if (sidebar) {
        if (isCollapsed) sidebar.classList.add('collapsed');

        const activeNavGroups = getNavGroups(currentUser);
        const navGroupsHtml = activeNavGroups.map(group => {
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
                ${group.title ? `<div class="nav-group-title">${group.title}</div>` : ''}
                ${linksHtml}
            `;
        }).join('');

        sidebar.innerHTML = `
            <div class="sidebar-brand">
                <a href="/frontend2/index.html" class="sidebar-brand-link">
                    <div class="brand-logo">
                        ${ICONS.leaf}
                    </div>
                    <div class="brand-info">
                        <div class="brand-title-row">
                            <span class="brand-name">GARI</span>
                            <span class="brand-subname">AgriTech</span>
                            <span class="brand-tag-ailab">AI LAB</span>
                        </div>
                        <span class="brand-sub">Trí tuệ Nông nghiệp</span>
                    </div>
                </a>
            </div>

            <!-- Workspace Selector -->
            <div class="workspace-card" id="workspaceSelector" title="Chuyển vùng canh tác">
                <span class="workspace-farm-icon">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#4ade80" stroke-width="2"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
                </span>
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

            <!-- Sidebar Promo Card (GARI Pilot) -->
            <div class="sidebar-promo-card">
                <div class="promo-text-wrap">
                    <div class="promo-title">Nâng cấp GARI Pilot</div>
                    <p class="promo-desc">Mở rộng tính năng, phân tích chuyên sâu và tư vấn cá nhân hóa.</p>
                    <a href="/frontend2/pricing.html" class="btn-promo-cta">Tìm hiểu gói →</a>
                </div>
                <div class="promo-img-wrap">
                    <img src="/static/frontend2/images/seedling_promo.jpg" alt="GARI Pilot Tea Leaf Sprout" class="promo-seedling-img" loading="lazy">
                </div>
            </div>

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
                    <span style="font-size:12px; color:rgba(255,255,255,0.4);">▾</span>
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
                <a href="/frontend2/index.html" class="topbar-brand-link" title="GARI AgriTech">
                    <span class="topbar-brand-icon">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.3"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/></svg>
                    </span>
                    <span class="topbar-brand-info">
                        <span class="topbar-brand-title">GARI</span>
                        <span class="topbar-brand-sub">Trợ lý nông nghiệp AI</span>
                    </span>
                </a>
                <div class="breadcrumbs desktop-only-crumb">
                    <span class="breadcrumb-sep">/</span>
                    <span class="breadcrumb-current" id="topbarCrumb">${activeTitle}</span>
                </div>
            </div>

            <div class="topbar-center desktop-only-search">
                <div class="topbar-search-trigger" id="topbarSearchTrigger" role="button" tabindex="0" title="Tìm kiếm nhanh (Ctrl + K)">
                    ${ICONS.search}
                    <span>Tìm nhanh cây trồng, bệnh cây, hướng dẫn canh tác...</span>
                    <kbd class="search-kbd">Ctrl K</kbd>
                </div>
            </div>

            <div class="topbar-right">
                <button type="button" class="topbar-icon-btn mobile-search-btn" id="btnSearchMobile" title="Tìm kiếm nhanh">
                    ${ICONS.search}
                </button>

                <button type="button" class="topbar-icon-btn btn-theme-toggle" id="btnTheme" title="Chuyển đổi Sáng / Tối">
                    ${document.documentElement.dataset.theme === 'dark' ? ICONS.sun : ICONS.moon}
                </button>

                <!-- Notifications Dropdown -->
                <div style="position:relative;">
                    <button type="button" class="topbar-icon-btn" id="btnAlerts" title="Cảnh báo nông nghiệp mới">
                        ${ICONS.bell}
                        <span class="unread-badge" id="unreadBadge">2</span>
                    </button>
                    <div class="notifications-dropdown" id="notificationsDropdown">
                        <div class="notif-header" style="display:flex; align-items:center; justify-content:space-between;">
                            <div>
                                <span class="notif-title">Cảnh báo Nông nghiệp</span>
                                <div class="notif-count" id="notifCountBadge">2 cảnh báo mới</div>
                            </div>
                            <button type="button" id="btnMarkAllNotifsRead" style="font-size:11px; color:var(--primary); background:none; border:none; cursor:pointer; font-weight:600; text-decoration:underline;">
                                Đã đọc tất cả
                            </button>
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
                    <div class="user-profile topbar-avatar-only" id="userProfileBtn" title="Hồ sơ: ${userFullName} (${userAccountType})">
                        <div class="user-avatar" id="topbarAvatar">${initials}</div>
                        <span class="user-avatar-caret">▾</span>
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
                        ${currentUser && currentUser.is_host_admin ? `
                        <div class="user-dropdown-divider"></div>
                        <a href="/host" class="user-dropdown-item" style="color:var(--primary); font-weight:700;">
                            <span>⚡</span> <span>Bảng điều khiển Máy chủ (Host)</span>
                        </a>` : ''}
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
    initBottomNav(activeKey);
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

    // Close mobile drawer when clicking navigation link
    if (sidebar) {
        sidebar.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth <= 1024) {
                    sidebar.classList.remove('drawer-open');
                    if (backdrop) backdrop.classList.remove('show');
                }
            });
        });
    }

    const themeBtn = document.getElementById('btnTheme');
    if (themeBtn) {
        themeBtn.onclick = toggleTheme;
    }

    const searchTrigger = document.getElementById('topbarSearchTrigger');
    if (searchTrigger) {
        searchTrigger.onclick = openCommandPalette;
    }
    const mobileSearchBtn = document.getElementById('btnSearchMobile');
    if (mobileSearchBtn) {
        mobileSearchBtn.onclick = openCommandPalette;
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

    const btnMarkAll = document.getElementById('btnMarkAllNotifsRead');
    if (btnMarkAll) {
        btnMarkAll.onclick = async (e) => {
            e.stopPropagation();
            try {
                const res = await fetchJSON('/api/notifications/mark-all-read', { method: 'POST' });
                toast('Đã đánh dấu tất cả thông báo là đã đọc!');
                fetchNotifications();
            } catch (err) {
                toast('Không thể cập nhật thông báo.');
            }
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

    // Initialize floating AI Copilot on all pages
    initFloatingChat();
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
            if (unreadCount > 0) {
                badge.style.display = 'inline-flex';
                badge.textContent = unreadCount > 9 ? '9+' : unreadCount;
            } else {
                badge.style.display = 'none';
            }
        }
        if (countBadge) {
            countBadge.textContent = unreadCount > 0 ? `${unreadCount} thông báo mới` : 'Tất cả đã đọc';
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
    window.toast = toast;
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
    if (opts.body && typeof opts.body === 'string' && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }
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
            // Unauthorized access - clear session
            localStorage.removeItem(AUTH_TOKEN_KEY);
            localStorage.removeItem(USER_INFO_KEY);
            const currentPath = window.location.pathname + window.location.search;
            const isPublicPage = currentPath === '/' || currentPath === '/dashboard' || currentPath.includes('index.html') || currentPath.includes('predict.html') || currentPath.includes('landing.html');
            if (!isPublicPage && !currentPath.includes('login.html') && !currentPath.includes('register.html')) {
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
export function initBottomNav(activeKey = 'overview') {
    if (document.getElementById('mobileBottomNav')) return;

    const nav = document.createElement('nav');
    nav.id = 'mobileBottomNav';
    nav.className = 'mobile-bottom-nav';
    nav.setAttribute('aria-label', 'Thanh điều hướng chính');
    const features = window.GARI_FEATURES || { farms: false, community: false };

    // Tab 2: Vườn if enabled, else Hỏi AI
    const tab2Html = features.farms !== false ? `
        <a href="/frontend2/farms.html" class="bottom-nav-item ${activeKey === 'farms' ? 'active' : ''}" data-key="farms">
            <span class="bottom-nav-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22v-7"/><path d="M17 8a5 5 0 0 0-10 0c0 7 5 9 5 9s5-2 5-9Z"/><path d="m9 11 3 3 3-3"/></svg>
            </span>
            <span class="bottom-nav-label">Vườn</span>
        </a>
    ` : `
        <a href="javascript:void(0)" class="bottom-nav-item ${activeKey === 'assistant' ? 'active' : ''}" data-key="assistant" onclick="window.openGariCopilot && window.openGariCopilot()" title="Hỏi Trợ lý AI GARI">
            <span class="bottom-nav-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><circle cx="9" cy="10" r="1" fill="currentColor"/><circle cx="12" cy="10" r="1" fill="currentColor"/><circle cx="15" cy="10" r="1" fill="currentColor"/></svg>
            </span>
            <span class="bottom-nav-label">Hỏi AI</span>
        </a>
    `;

    // Tab 4: Cộng đồng if enabled, else Chuyên gia
    const tab4Html = features.community !== false ? `
        <a href="/frontend2/community.html" class="bottom-nav-item ${activeKey === 'community' ? 'active' : ''}" data-key="community">
            <span class="bottom-nav-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            </span>
            <span class="bottom-nav-label">Cộng đồng</span>
        </a>
    ` : `
        <a href="/frontend2/support.html" class="bottom-nav-item ${activeKey === 'support' ? 'active' : ''}" data-key="support" title="Kết nối Chuyên gia Nông học">
            <span class="bottom-nav-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
            </span>
            <span class="bottom-nav-label">Chuyên gia</span>
        </a>
    `;

    nav.innerHTML = `
        <a href="/frontend2/index.html" class="bottom-nav-item ${activeKey === 'overview' ? 'active' : ''}" data-key="overview">
            <span class="bottom-nav-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>
            </span>
            <span class="bottom-nav-label">Trang chủ</span>
        </a>
        ${tab2Html}
        <button type="button" class="bottom-nav-scan-btn" id="btnBottomNavScan" title="Chẩn đoán bệnh cây">
            <span class="scan-btn-inner">
                <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="#FFFFFF" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/>
                    <circle cx="12" cy="12" r="3"/>
                </svg>
            </span>
        </button>
        ${tab4Html}
        <button type="button" class="bottom-nav-item ${activeKey === 'more' ? 'active' : ''}" id="btnBottomNavMore" data-key="more">
            <span class="bottom-nav-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/></svg>
            </span>
            <span class="bottom-nav-label">Khác</span>
        </button>
    `;
    document.body.appendChild(nav);

    // Bind bottom nav actions
    const scanBtn = nav.querySelector('#btnBottomNavScan');
    if (scanBtn) {
        scanBtn.onclick = () => {
            const diagSection = document.getElementById('aiCropDiagnosisSection');
            if (diagSection) {
                diagSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                const fileInput = document.getElementById('dashboardFileInput');
                if (fileInput) {
                    fileInput.setAttribute('capture', 'environment');
                    fileInput.click();
                }
            } else {
                window.location.href = '/frontend2/predict.html';
            }
        };
    }

    const moreBtn = nav.querySelector('#btnBottomNavMore');
    if (moreBtn) {
        moreBtn.onclick = () => {
            const sidebar = document.getElementById('appSidebar');
            const backdrop = document.getElementById('sidebarBackdrop');
            if (sidebar) {
                sidebar.classList.toggle('drawer-open');
                if (backdrop) backdrop.classList.toggle('show');
            }
        };
    }
}
export function animateIn() {}
export function registerReveal() {}
export function animateHero() {}
export function initFloatingChat() {
    if (document.getElementById('gariCopilotDrawer')) return;

    // 1. Create Floating Action Button (FAB)
    const fab = document.createElement('button');
    fab.id = 'gariCopilotFab';
    fab.className = 'copilot-fab';
    fab.type = 'button';
    fab.title = 'Mở Trợ lý Nông nghiệp GARI Copilot';
    fab.setAttribute('aria-label', 'Mở Trợ lý Nông nghiệp GARI Copilot');
    fab.setAttribute('aria-expanded', 'false');
    fab.setAttribute('aria-controls', 'gariCopilotDrawer');
    fab.innerHTML = `
        <span class="fab-pulse-ring" aria-hidden="true"></span>
        <span class="fab-icon" aria-hidden="true">🤖</span>
        <span class="fab-label">GARI Copilot</span>
    `;
    document.body.appendChild(fab);

    // 2. Create Backdrop Overlay
    const backdrop = document.createElement('div');
    backdrop.id = 'gariCopilotBackdrop';
    backdrop.className = 'copilot-backdrop';
    backdrop.setAttribute('aria-hidden', 'true');
    document.body.appendChild(backdrop);

    // 3. Create Dedicated Drawer
    const drawer = document.createElement('div');
    drawer.id = 'gariCopilotDrawer';
    drawer.className = 'copilot-drawer';
    drawer.setAttribute('role', 'dialog');
    drawer.setAttribute('aria-modal', 'true');
    drawer.setAttribute('aria-label', 'Trợ lý Nông nghiệp GARI Copilot');
    drawer.innerHTML = `
        <div class="copilot-drawer-header">
            <div class="copilot-header-info">
                <div class="copilot-title">🌿 GARI AgriTech Copilot</div>
                <div class="copilot-sub">Trợ lý đồng hành canh tác & vi khí hậu Ba Vì</div>
            </div>
            <div class="copilot-header-actions">
                <button type="button" id="btnMinimizeCopilot" class="copilot-header-btn" title="Thu nhỏ (Esc)" aria-label="Thu nhỏ">–</button>
                <button type="button" id="btnCloseCopilot" class="copilot-header-btn" title="Đóng (Esc)" aria-label="Đóng">&times;</button>
            </div>
        </div>
        <div class="copilot-context-bar" id="copilotContextBar">
            <span class="copilot-ctx-chip">Đang kết nối vi khí hậu...</span>
        </div>
        <div class="copilot-messages" id="copilotMessages" tabindex="0" aria-live="polite">
            <div class="copilot-msg bot">
                <div class="copilot-bubble">
                    Chào bác nông dân! Tôi là Trợ lý Đồng hành GARI. Tôi có thể giúp bác kiểm tra tình hình các thửa ruộng/lô vườn, việc canh tác cần làm hôm nay, hoặc tư vấn kỹ thuật xử lý sâu bệnh theo khuyến nông thực địa.
                </div>
                <div class="copilot-chips" id="copilotChips">
                    <button type="button" class="copilot-chip" data-q="Tình trạng các lô vườn của tôi thế nào?">🌾 Tình trạng lô vườn</button>
                    <button type="button" class="copilot-chip" data-q="Hôm nay có việc canh tác gì cần làm không?">📋 Việc hôm nay & quá hạn</button>
                    <button type="button" class="copilot-chip" data-q="Cà chua bị đốm lá muộn xử lý thế nào?">🍅 Tư vấn bệnh cà chua</button>
                    <button type="button" class="copilot-chip" data-q="Nhắc tôi phun phòng sâu tơ ngày mai">📅 Lập lịch phun phòng</button>
                </div>
            </div>
        </div>
        <div class="copilot-input-area">
            <input type="text" id="copilotInput" placeholder="Hỏi tình trạng ruộng, việc cần làm..." autocomplete="off" aria-label="Nội dung trao đổi với GARI Copilot">
            <button type="button" id="btnSendCopilot" class="btn btn-primary btn-sm">Gửi</button>
        </div>
    `;
    document.body.appendChild(drawer);

    // Focus trap & Open / Close State Management
    let lastActiveElement = null;

    const openDrawer = async () => {
        lastActiveElement = document.activeElement;
        drawer.classList.add('open');
        backdrop.classList.add('open');
        fab.classList.add('drawer-open');
        fab.setAttribute('aria-expanded', 'true');
        document.body.classList.add('copilot-open');

        // Auto-focus input after smooth transition
        setTimeout(() => {
            const input = document.getElementById('copilotInput');
            if (input) input.focus();
        }, 120);

        try {
            const res = await fetch('/api/copilot/context');
            const data = await res.json();
            if (data.success && data.context) {
                const ctx = data.context;
                const bar = document.getElementById('copilotContextBar');
                if (bar) {
                    bar.innerHTML = `
                        <span class="copilot-ctx-chip">🌱 <strong>${ctx.farms_count}</strong> trại • <strong>${ctx.plots_count}</strong> lô</span>
                        <span class="copilot-ctx-chip">📋 <strong>${ctx.tasks_summary.today_count}</strong> việc hôm nay</span>
                        <span class="copilot-ctx-chip" style="${ctx.tasks_summary.overdue_count > 0 ? 'color:#b91c1c; font-weight:700;' : ''}">⚠️ <strong>${ctx.tasks_summary.overdue_count}</strong> quá hạn</span>
                        <span class="copilot-ctx-chip">🌤️ ${ctx.observed_weather ? (ctx.observed_weather.temperature_c || ctx.observed_weather.temp_c || 24.5) : 24.5}°C (${ctx.observed_weather ? ctx.observed_weather.humidity_pct : 80}%)</span>
                    `;
                }
            }
        } catch {}
    };

    const closeDrawer = () => {
        drawer.classList.remove('open');
        backdrop.classList.remove('open');
        fab.classList.remove('drawer-open');
        fab.setAttribute('aria-expanded', 'false');
        document.body.classList.remove('copilot-open');

        // Restore focus smoothly
        try {
            if (lastActiveElement && typeof lastActiveElement.focus === 'function' && document.body.contains(lastActiveElement)) {
                lastActiveElement.focus();
            } else {
                fab.focus();
            }
        } catch {}
    };

    fab.onclick = openDrawer;
    document.getElementById('btnCloseCopilot').onclick = closeDrawer;
    const minBtn = document.getElementById('btnMinimizeCopilot');
    if (minBtn) minBtn.onclick = closeDrawer;
    backdrop.onclick = closeDrawer;

    // Keyboard navigation (Escape closes overlay)
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && drawer.classList.contains('open')) {
            closeDrawer();
        }
    });

    // Close on click outside on desktop
    document.addEventListener('pointerdown', (e) => {
        if (!drawer.classList.contains('open')) return;
        if (window.innerWidth > 1024) {
            if (!drawer.contains(e.target) && !fab.contains(e.target)) {
                closeDrawer();
            }
        }
    });

    // Send message logic
    const sendMsg = async (text) => {
        const input = document.getElementById('copilotInput');
        const msg = (text || (input ? input.value : '') || '').trim();
        if (!msg) return;

        if (input) input.value = '';

        const container = document.getElementById('copilotMessages');
        const uEl = document.createElement('div');
        uEl.className = 'copilot-msg user';
        uEl.innerHTML = `<div class="copilot-bubble">${msg}</div>`;
        container.appendChild(uEl);
        container.scrollTop = container.scrollHeight;

        const thinkEl = document.createElement('div');
        thinkEl.className = 'copilot-msg bot';
        thinkEl.innerHTML = `<div class="copilot-bubble" style="font-style:italic; color:var(--text-muted);">GARI Copilot đang tổng hợp dữ liệu...</div>`;
        container.appendChild(thinkEl);
        container.scrollTop = container.scrollHeight;

        try {
            const res = await fetch('/api/copilot/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: msg })
            });
            const data = await res.json();
            thinkEl.remove();

            const bEl = document.createElement('div');
            bEl.className = 'copilot-msg bot';

            let actionHtml = '';
            if (data.actions && data.actions.length > 0) {
                const act = data.actions[0];
                if (act.type === 'confirm_task_draft' && act.draft) {
                    const draftJson = JSON.stringify(act.draft).replace(/"/g, '&quot;');
                    actionHtml = `
                        <div class="copilot-action-card">
                            <div class="copilot-action-title">📋 ${act.draft.title}</div>
                            <div class="copilot-action-meta">📅 Hạn: ${act.draft.due_date} • 🌿 Cây: ${act.draft.crop_id}</div>
                            <button type="button" class="btn btn-primary btn-sm btn-confirm-copilot" data-draft="${draftJson}" style="font-size:11px; padding:4px 10px;">
                                ✅ ${act.label || 'Xác nhận & Lưu vào Lịch canh tác'}
                            </button>
                        </div>
                    `;
                }
            }

            const formattedReply = (data.reply || 'Đã ghi nhận yêu cầu của bác.')
                .replace(/\n\n/g, '<br><br>')
                .replace(/\n- /g, '<br>• ')
                .replace(/\n/g, '<br>');

            bEl.innerHTML = `<div class="copilot-bubble">${formattedReply}${actionHtml}</div>`;
            container.appendChild(bEl);
            container.scrollTop = container.scrollHeight;

            const confirmBtn = bEl.querySelector('.btn-confirm-copilot');
            if (confirmBtn) {
                confirmBtn.onclick = async () => {
                    confirmBtn.disabled = true;
                    confirmBtn.textContent = 'Đang lưu vào lịch...';
                    try {
                        const rawDraft = JSON.parse(confirmBtn.getAttribute('data-draft'));
                        const cRes = await fetch('/api/copilot/tasks/confirm-draft', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ draft: rawDraft })
                        });
                        const cJson = await cRes.json();
                        if (cRes.ok && cJson.success) {
                            confirmBtn.className = 'btn btn-secondary btn-sm';
                            confirmBtn.textContent = `✓ Đã lưu vào Lịch (#${cJson.task.id})`;
                            if (window.toast) window.toast('✅ Đã thêm công việc vào Lịch canh tác!');
                        } else {
                            confirmBtn.disabled = false;
                            confirmBtn.textContent = 'Thử lại';
                            alert(cJson.detail || 'Không thể tạo công việc.');
                        }
                    } catch {
                        confirmBtn.disabled = false;
                        confirmBtn.textContent = 'Lỗi kết nối';
                    }
                };
            }
        } catch {
            thinkEl.remove();
            const errEl = document.createElement('div');
            errEl.className = 'copilot-msg bot';
            errEl.innerHTML = `<div class="copilot-bubble" style="color:#b91c1c;">Không thể kết nối đến máy chủ GARI. Vui lòng thử lại.</div>`;
            container.appendChild(errEl);
        }
    };

    document.getElementById('btnSendCopilot').onclick = () => sendMsg();
    document.getElementById('copilotInput').onkeydown = (e) => {
        if (e.key === 'Enter') sendMsg();
    };

    document.addEventListener('click', (e) => {
        if (e.target && e.target.classList.contains('copilot-chip')) {
            const q = e.target.getAttribute('data-q');
            if (q) sendMsg(q);
        }
    });
}

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
