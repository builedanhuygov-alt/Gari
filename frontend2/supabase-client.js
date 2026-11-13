/**
 * GARI AgriTech AI Lab — Supabase Auth Client (supabase-client.js)
 * Modern client integrating official @supabase/supabase-js v2.48.0 (ESM)
 * with robust session persistence, Vietnamese error translation, and guaranteed timeout recovery.
 */

// Helper to bound any promise by a deterministic timeout
function withTimeout(promise, timeoutMs, timeoutErrorMessage) {
    let timer = null;
    const timeoutPromise = new Promise((_, reject) => {
        timer = setTimeout(() => {
            const err = new Error(timeoutErrorMessage || `Thao tác quá thời gian chờ (${Math.round(timeoutMs / 1000)}s).`);
            err.name = 'TimeoutError';
            reject(err);
        }, timeoutMs);
    });
    return Promise.race([promise, timeoutPromise]).finally(() => {
        if (timer) clearTimeout(timer);
    });
}

// Maps Supabase Auth error codes & messages to user-friendly Vietnamese
function mapSupabaseError(error) {
    if (!error) return new Error('Đã xảy ra lỗi không xác định.');
    const msg = (error.message || '').toLowerCase();
    const code = (error.code || '').toLowerCase();

    if (msg.includes('user already registered') || code === 'user_already_exists') {
        return new Error('Địa chỉ email này đã được đăng ký tài khoản. Vui lòng đăng nhập hoặc chọn Quên mật khẩu.');
    }
    if (msg.includes('invalid login credentials') || msg.includes('invalid_grant')) {
        return new Error('Email hoặc mật khẩu không chính xác.');
    }
    if (msg.includes('email not confirmed')) {
        return new Error('Tài khoản chưa được xác nhận email. Vui lòng kiểm tra hộp thư email để kích hoạt tài khoản.');
    }
    if (msg.includes('password should be at least') || msg.includes('weak_password')) {
        return new Error('Mật khẩu quá ngắn hoặc không đủ độ an toàn (tối thiểu 6 ký tự).');
    }
    if (msg.includes('over_email_send_rate_limit') || msg.includes('rate limit')) {
        return new Error('Bạn đã thao tác quá nhiều lần. Vui lòng chờ vài phút rồi thử lại.');
    }
    return new Error(error.message || 'Không thể kết nối đến máy chủ xác thực.');
}

class GariSupabaseAuthClient {
    constructor() {
        this.supabase = null;
        this.currentUser = null;
        this.session = null;
        this.isConfigured = false;
        this.authListeners = [];
        this._initPromise = null;
        this._registrationInFlight = false;
    }

    /**
     * Centralized, idempotent initialization
     */
    async init() {
        if (this._initPromise) return this._initPromise;
        this._initPromise = this._doInit().catch(err => {
            this._initPromise = null;
            throw err;
        });
        return this._initPromise;
    }

    async _doInit() {
        // 1. Resolve configuration from window injection or /api/auth/supabase-config
        let config = window.__GARI_SUPABASE_CONFIG__ || null;

        if (!config || !config.url || !config.publishableKey) {
            try {
                const res = await withTimeout(
                    fetch('/api/auth/supabase-config', { credentials: 'include' }),
                    5000,
                    'Không thể nạp cấu hình xác thực từ máy chủ.'
                );
                if (res.ok) {
                    const data = await res.json();
                    if (data && data.configured && data.url && data.publishableKey) {
                        config = data;
                    }
                }
            } catch (err) {
                console.debug('[GARI Supabase] Could not fetch remote config:', err?.message || err);
            }
        }

        if (config && config.url && config.publishableKey) {
            try {
                // Dynamically import pinned ESM version of @supabase/supabase-js v2.48.0
                const { createClient } = await withTimeout(
                    import('https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.48.0/+esm'),
                    7000,
                    'Không thể tải thư viện Supabase JS từ CDN.'
                );

                this.supabase = createClient(config.url, config.publishableKey, {
                    auth: {
                        persistSession: true,
                        autoRefreshToken: true,
                        detectSessionInUrl: true,
                        storage: window.localStorage
                    }
                });

                this.isConfigured = true;

                // Subscribe to auth state changes
                this.supabase.auth.onAuthStateChange(async (event, session) => {
                    this.session = session;
                    if (session && session.user) {
                        const token = session.access_token;
                        localStorage.setItem('gari_token', token);
                        await this.checkCurrentSession(token);
                    } else if (event === 'SIGNED_OUT') {
                        this.currentUser = null;
                        this.session = null;
                        localStorage.removeItem('gari_token');
                        localStorage.removeItem('gari_user');
                        this._notifyListeners(null);
                    }
                });

                // Restore active session
                const { data } = await this.supabase.auth.getSession();
                if (data && data.session) {
                    this.session = data.session;
                    localStorage.setItem('gari_token', data.session.access_token);
                    await this.checkCurrentSession(data.session.access_token);
                }
            } catch (loadErr) {
                console.warn('[GARI Supabase] Initialization warning:', loadErr?.message || loadErr);
                this.isConfigured = false;
            }
        } else {
            console.info('[GARI Supabase] Supabase client credentials not yet configured. Standing by for project configuration.');
            this.isConfigured = false;
        }

        return this.currentUser;
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
            try { cb(user); } catch (e) { console.error('[GARI Supabase] Listener error:', e); }
        });
    }

    /**
     * Validates current session against backend /api/user/profile
     */
    async checkCurrentSession(overrideToken) {
        const token = overrideToken || localStorage.getItem('gari_token');
        if (!token) {
            this.currentUser = null;
            this._notifyListeners(null);
            return null;
        }

        try {
            const res = await withTimeout(
                fetch('/api/user/profile', {
                    headers: { 'Authorization': `Bearer ${token}` },
                    credentials: 'include'
                }),
                7000,
                'Kiểm tra phiên đăng nhập quá thời gian chờ (7s).'
            );

            if (res.ok) {
                const data = await res.json();
                if (data && data.success) {
                    this.currentUser = {
                        identity: data.identity,
                        profile: data.profile,
                        subscription: data.subscription,
                        organizations: data.organizations,
                        system_role: data.system_role,
                        system_roles: data.system_roles,
                        account_type: data.account_type,
                        full_name: data.profile?.full_name || data.identity?.display_name || 'Người dùng Gari',
                        email: data.identity?.email || '',
                        is_host_admin: Boolean(data.system_roles?.is_host_admin)
                    };
                    localStorage.setItem('gari_user', JSON.stringify(this.currentUser));
                    this._notifyListeners(this.currentUser);
                    return this.currentUser;
                }
            }
        } catch (e) {
            console.debug('[GARI Supabase] Backend profile verification unreachable:', e?.message || e);
        }

        // Preserve session from local cached profile if offline
        try {
            const cached = localStorage.getItem('gari_user');
            if (cached) {
                this.currentUser = JSON.parse(cached);
                this._notifyListeners(this.currentUser);
                return this.currentUser;
            }
        } catch (_) {}

        return null;
    }

    /**
     * User Registration via Supabase Auth
     */
    async register(name, email, password, phone = '', province = 'Lâm Đồng', accountType = 'farmer') {
        name = (name || '').trim();
        email = (email || '').trim().toLowerCase();
        password = password || '';

        if (!name) throw new Error('Vui lòng nhập họ và tên.');
        if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error('Địa chỉ email không đúng định dạng.');
        if (password.length < 6) throw new Error('Mật khẩu phải có độ dài tối thiểu 6 ký tự.');

        if (!this.isConfigured || !this.supabase) {
            throw new Error('Dịch vụ xác thực Supabase chưa được cấu hình. Vui lòng thiết lập SUPABASE_URL và SUPABASE_PUBLISHABLE_KEY.');
        }

        if (this._registrationInFlight) {
            throw new Error('Yêu cầu đăng ký đang được xử lý, vui lòng chờ.');
        }

        this._registrationInFlight = true;

        try {
            // 1. Sign up on Supabase Auth with metadata
            const { data, error } = await withTimeout(
                this.supabase.auth.signUp({
                    email,
                    password,
                    options: {
                        data: {
                            full_name: name,
                            name: name,
                            phone: phone.trim(),
                            province: province.trim(),
                            account_type: accountType
                        }
                    }
                }),
                10000,
                'Đăng ký tài khoản Supabase quá thời gian chờ (10s).'
            );

            if (error) {
                throw mapSupabaseError(error);
            }

            // 2. Case: Email verification is required (no immediate session)
            if (data.user && !data.session) {
                return {
                    success: true,
                    requiresEmailVerification: true,
                    message: 'Đăng ký thành công! Hệ thống đã gửi liên kết xác nhận đến hộp thư của bạn. Vui lòng kiểm tra email trước khi đăng nhập.',
                    user: null
                };
            }

            // 3. Case: Immediate session granted -> Sync with Backend
            if (data.session && data.session.access_token) {
                const token = data.session.access_token;
                localStorage.setItem('gari_token', token);

                // Synchronize with FastAPI hybrid backend
                try {
                    await withTimeout(
                        fetch('/api/auth/supabase-sync', {
                            method: 'POST',
                            headers: {
                                'Authorization': `Bearer ${token}`,
                                'Content-Type': 'application/json'
                            },
                            credentials: 'include',
                            body: JSON.stringify({
                                full_name: name,
                                phone: phone.trim(),
                                province: province.trim(),
                                account_type: accountType
                            })
                        }),
                        10000,
                        'Đồng bộ tài khoản với máy chủ GARI quá thời gian chờ.'
                    );
                } catch (syncErr) {
                    console.warn('[GARI Supabase] Backend sync warning:', syncErr?.message || syncErr);
                }

                const user = await this.checkCurrentSession(token);
                return {
                    success: true,
                    requiresEmailVerification: false,
                    user,
                    token
                };
            }

            throw new Error('Không thể khởi tạo phiên đăng ký.');
        } finally {
            this._registrationInFlight = false;
        }
    }

    /**
     * User Login via Supabase Auth
     */
    async login(email, password, rememberMe = false) {
        email = (email || '').trim().toLowerCase();
        if (!email || !password) {
            throw new Error('Vui lòng nhập đầy đủ email và mật khẩu.');
        }

        if (!this.isConfigured || !this.supabase) {
            throw new Error('Dịch vụ xác thực Supabase chưa được cấu hình. Vui lòng thiết lập SUPABASE_URL và SUPABASE_PUBLISHABLE_KEY.');
        }

        const { data, error } = await withTimeout(
            this.supabase.auth.signInWithPassword({ email, password }),
            10000,
            'Đăng nhập Supabase quá thời gian chờ (10s).'
        );

        if (error) {
            throw mapSupabaseError(error);
        }

        if (!data || !data.session) {
            throw new Error('Không thể xác thực phiên đăng nhập.');
        }

        const token = data.session.access_token;
        this.session = data.session;
        localStorage.setItem('gari_token', token);

        // Sync session with backend
        try {
            await withTimeout(
                fetch('/api/auth/supabase-sync', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    credentials: 'include',
                    body: JSON.stringify({})
                }),
                7000,
                'Đồng bộ phiên đăng nhập quá thời gian chờ.'
            );
        } catch (_) {}

        const user = await this.checkCurrentSession(token);
        return { success: true, user, token };
    }

    /**
     * User Logout
     */
    async logout() {
        const token = localStorage.getItem('gari_token');

        // 1. Supabase Auth signOut
        if (this.supabase) {
            try {
                await withTimeout(this.supabase.auth.signOut(), 3000, 'Supabase signOut timeout');
            } catch (_) {}
        }

        // 2. Clear local storage
        try {
            const keysToRemove = [];
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                if (k && (k.startsWith('gari_') || k.startsWith('sb-'))) {
                    keysToRemove.push(k);
                }
            }
            keysToRemove.forEach(k => localStorage.removeItem(k));
        } catch (_) {}

        this.currentUser = null;
        this.session = null;
        this._notifyListeners(null);

        // 3. Notify backend
        if (token) {
            try {
                await withTimeout(
                    fetch('/api/auth/logout', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${token}` },
                        credentials: 'include'
                    }),
                    2500,
                    'Backend logout timeout'
                );
            } catch (_) {}
        }

        return { success: true, localCleared: true };
    }

    /**
     * Password Reset Email
     */
    async resetPassword(email) {
        email = (email || '').trim().toLowerCase();
        if (!email) throw new Error('Vui lòng nhập địa chỉ email.');

        if (!this.isConfigured || !this.supabase) {
            throw new Error('Dịch vụ xác thực Supabase chưa được cấu hình.');
        }

        const redirectTo = `${window.location.origin}/frontend2/forgot-password.html`;
        const { error } = await withTimeout(
            this.supabase.auth.resetPasswordForEmail(email, { redirectTo }),
            10000,
            'Yêu cầu khôi phục mật khẩu quá thời gian chờ (10s).'
        );

        if (error) {
            throw mapSupabaseError(error);
        }

        return {
            success: true,
            message: 'Đã gửi liên kết đặt lại mật khẩu đến email của bạn. Vui lòng kiểm tra hộp thư.'
        };
    }
}

// Instantiate and expose globally
window.gariAuth = new GariSupabaseAuthClient();
export default window.gariAuth;

