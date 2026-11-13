/**
 * GARI AgriTech AI Lab — Independent Auth Server Client Adapter
 * (gari-auth-service-client.js)
 * 
 * Replaces client-side Firebase and Supabase SDKs with a lightweight,
 * secure-cookie authentication client connecting to the dedicated GARI Auth VPS.
 * 
 * Invariants:
 * 1. Uses HttpOnly cookies for session storage; never stores raw credentials in localStorage.
 * 2. Transmits CSRF tokens via X-CSRF-Token header on mutating requests.
 * 3. Never passes passwords or tokens in query parameters or URLs.
 * 4. Deterministic timeouts with automatic button/UI loading-state recovery.
 * 5. Zero reliance on Windows PC or developer laptop.
 */

function withTimeout(promise, timeoutMs, timeoutErrorMessage) {
    let timer = null;
    const timeoutPromise = new Promise((_, reject) => {
        timer = setTimeout(() => {
            const err = new Error(timeoutErrorMessage || `Yêu cầu xác thực quá thời gian chờ (${Math.round(timeoutMs / 1000)}s).`);
            err.name = 'TimeoutError';
            reject(err);
        }, timeoutMs);
    });
    return Promise.race([promise, timeoutPromise]).finally(() => {
        if (timer) clearTimeout(timer);
    });
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

export class GariAuthServiceClient {
    constructor(baseUrl = '') {
        // Defaults to same-origin or configured Auth VPS base URL (e.g. 'https://auth.gari.vn')
        this.baseUrl = (baseUrl || window.__GARI_AUTH_API_URL__ || '').replace(/\/$/, '');
        this.currentUser = null;
        this.authListeners = [];
        this.csrfToken = null;
        this._initPromise = null;
    }

    async init() {
        if (this._initPromise) return this._initPromise;
        this._initPromise = this._doInit();
        return this._initPromise;
    }

    async _doInit() {
        // 1. Fetch CSRF token
        try {
            const res = await withTimeout(
                fetch(`${this.baseUrl}/api/v1/auth/csrf`, { credentials: 'include' }),
                4000,
                'Không thể kết nối máy chủ xác thực GARI Auth.'
            );
            if (res.ok) {
                const data = await res.json();
                if (data && data.csrf_token) {
                    this.csrfToken = data.csrf_token;
                }
            }
        } catch (e) {
            console.debug('[GARI Auth Service] CSRF handshake standby:', e?.message || e);
        }

        // 2. Check current session
        return await this.checkCurrentSession();
    }

    _getHeaders(includeCsrf = true) {
        const headers = { 'Content-Type': 'application/json' };
        const csrf = this.csrfToken || getCookie('gari_csrf_token');
        if (includeCsrf && csrf) {
            headers['X-CSRF-Token'] = csrf;
        }
        return headers;
    }

    onAuthStateChanged(callback) {
        if (typeof callback === 'function') {
            this.authListeners.push(callback);
            if (this.currentUser !== undefined && this.currentUser !== null) {
                callback(this.currentUser);
            }
        }
    }

    _notifyListeners(user) {
        this.authListeners.forEach(cb => {
            try { cb(user); } catch (e) { console.error('[GARI Auth Service] Listener error:', e); }
        });
    }

    _normalizeUser(user) {
        if (!user) return null;
        return {
            ...user,
            id: user.id,
            email: user.email,
            full_name: user.full_name,
            identity: {
                email: user.email,
                display_name: user.full_name
            },
            profile: {
                full_name: user.full_name,
                name: user.full_name
            },
            system_role: {
                is_admin: user.account_type === 'admin',
                primary_role: user.account_type
            },
            role: user.account_type,
            is_host_admin: user.account_type === 'admin'
        };
    }

    async checkCurrentSession() {
        try {
            const res = await withTimeout(
                fetch(`${this.baseUrl}/api/v1/auth/me`, {
                    credentials: 'include',
                    headers: this._getHeaders(false)
                }),
                5000,
                'Kiểm tra phiên làm việc quá thời gian chờ.'
            );

            if (res.ok) {
                const user = await res.json();
                this.currentUser = this._normalizeUser(user);
                sessionStorage.setItem('gari_user_cache', JSON.stringify(this.currentUser));
                this._notifyListeners(this.currentUser);
                return this.currentUser;
            }
        } catch (e) {
            console.debug('[GARI Auth Service] Session check error:', e?.message || e);
        }

        this.currentUser = null;
        sessionStorage.removeItem('gari_user_cache');
        this._notifyListeners(null);
        return null;
    }

    async register(name, email, password, phone = '', province = '') {
        name = (name || '').trim();
        email = (email || '').trim().toLowerCase();
        password = password || '';

        if (!name) throw new Error('Vui lòng nhập họ và tên.');
        if (!email) throw new Error('Vui lòng nhập địa chỉ email.');
        if (password.length < 8) throw new Error('Mật khẩu phải có độ dài tối thiểu 8 ký tự.');

        const res = await withTimeout(
            fetch(`${this.baseUrl}/api/v1/auth/register`, {
                method: 'POST',
                headers: this._getHeaders(false),
                credentials: 'include',
                body: JSON.stringify({ email, password, full_name: name })
            }),
            8000,
            'Yêu cầu tạo tài khoản quá thời gian chờ (8s).'
        );

        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(data.detail || 'Không thể tạo tài khoản. Vui lòng thử lại.');
        }

        if (data.csrf_token) this.csrfToken = data.csrf_token;
        this.currentUser = this._normalizeUser(data.user);
        sessionStorage.setItem('gari_user_cache', JSON.stringify(this.currentUser));
        this._notifyListeners(this.currentUser);
        return { success: true, user: this.currentUser };
    }

    async login(email, password, rememberMe = false, fetchOptions = {}) {
        email = (email || '').trim().toLowerCase();
        password = password || '';

        if (!email || !password) {
            throw new Error('Vui lòng nhập đầy đủ email và mật khẩu.');
        }

        const res = await withTimeout(
            fetch(`${this.baseUrl}/api/v1/auth/login`, {
                ...fetchOptions,
                method: 'POST',
                headers: { ...this._getHeaders(false), ...(fetchOptions.headers || {}) },
                credentials: 'include',
                body: JSON.stringify({ email, password, remember_me: Boolean(rememberMe) })
            }),
            8000,
            'Yêu cầu đăng nhập quá thời gian chờ (8s).'
        );

        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(data.detail || 'Đăng nhập không thành công. Vui lòng thử lại.');
        }

        if (data.csrf_token) this.csrfToken = data.csrf_token;
        this.currentUser = this._normalizeUser(data.user);
        sessionStorage.setItem('gari_user_cache', JSON.stringify(this.currentUser));
        this._notifyListeners(this.currentUser);
        return { success: true, user: this.currentUser };
    }

    async logout() {
        try {
            await withTimeout(
                fetch(`${this.baseUrl}/api/v1/auth/logout`, {
                    method: 'POST',
                    headers: this._getHeaders(true),
                    credentials: 'include'
                }),
                4000,
                'Yêu cầu đăng xuất quá thời gian chờ.'
            );
        } catch (_) {}

        this.currentUser = null;
        sessionStorage.removeItem('gari_user_cache');
        this._notifyListeners(null);
        return { success: true };
    }

    async changePassword(currentPassword, newPassword) {
        if (!currentPassword || !newPassword) {
            throw new Error('Vui lòng nhập đầy đủ mật khẩu hiện tại và mật khẩu mới.');
        }
        if (newPassword.length < 8) {
            throw new Error('Mật khẩu mới phải có ít nhất 8 ký tự.');
        }

        const res = await withTimeout(
            fetch(`${this.baseUrl}/api/v1/auth/change-password`, {
                method: 'POST',
                headers: this._getHeaders(true),
                credentials: 'include',
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            }),
            8000,
            'Đổi mật khẩu quá thời gian chờ.'
        );

        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(data.detail || 'Đổi mật khẩu không thành công.');
        }
        return { success: true, message: data.message };
    }
}

// Global instance registration
window.GariAuthServiceClient = GariAuthServiceClient;
window.gariAuth = new GariAuthServiceClient();

export default GariAuthServiceClient;
