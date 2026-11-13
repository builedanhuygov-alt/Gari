/**
 * GARI AgriTech AI Lab — Firebase & Unified Auth Client (firebase-client.js)
 * Modern modular auth client supporting official Firebase Auth SDK v10 (ESM)
 * with robust session persistence, Vietnamese error translation, and safe fallback.
 */

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

class GariAuthClient {
    constructor() {
        this.firebaseApp = null;
        this.firebaseAuth = null;
        this.currentUser = null;
        this.idToken = null;
        this.isFirebaseReady = false;
        this.authListeners = [];
        this.config = null;
        this._initPromise = null;
        this._registrationInFlight = false;
        this._loginInFlight = false;
        this._fbMethods = null;
    }

    /**
     * Centralized, idempotent initialization with failure recovery
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
        // 1. Try window-injected config first, then fetch /api/auth/firebase-config
        let config = window.__GARI_FIREBASE_CONFIG__ || null;

        if (!config || !config.apiKey) {
            try {
                const res = await safeFetch('/api/auth/firebase-config', {}, 5000);
                if (res.ok) {
                    const data = await res.json();
                    if (data && data.configured && data.config && data.config.apiKey) {
                        config = data.config;
                    }
                }
            } catch (err) {
                console.warn('[GARI Auth] Could not fetch Firebase config:', err?.message || err);
            }
        }

        if (config && config.apiKey && config.projectId) {
            this.config = config;
            await this._initFirebaseSDK(config);
        } else {
            console.info('[GARI Auth] Firebase Client API keys not configured. Operating in standard session mode.');
        }

        // 2. Restore and verify existing session
        await this.checkCurrentSession();
        return this.currentUser;
    }

    async _initFirebaseSDK(config) {
        try {
            const { initializeApp, getApps, getApp } = await withTimeout(
                import('https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js'),
                7000,
                'Không thể tải Firebase App SDK từ CDN.'
            );
            const { 
                getAuth, 
                onAuthStateChanged,
                onIdTokenChanged,
                signInWithEmailAndPassword, 
                createUserWithEmailAndPassword, 
                signOut, 
                sendPasswordResetEmail,
                sendEmailVerification,
                updateProfile,
                GoogleAuthProvider, 
                signInWithPopup 
            } = await withTimeout(
                import('https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js'),
                7000,
                'Không thể tải Firebase Auth SDK từ CDN.'
            );
            
            // Avoid duplicate initialization
            const existingApps = getApps();
            this.firebaseApp = existingApps.length > 0 ? getApp() : initializeApp(config);
            this.firebaseAuth = getAuth(this.firebaseApp);
            this._fbMethods = {
                signInWithEmailAndPassword,
                createUserWithEmailAndPassword,
                signOut,
                sendPasswordResetEmail,
                sendEmailVerification,
                updateProfile,
                GoogleAuthProvider,
                signInWithPopup
            };
            this.isFirebaseReady = true;

            // Listen for token updates (automatic refresh before 1-hour expiration)
            onIdTokenChanged(this.firebaseAuth, async (fbUser) => {
                if (fbUser) {
                    try {
                        const token = await fbUser.getIdToken();
                        this.idToken = token;
                        localStorage.setItem('gari_token', token);
                    } catch (e) {
                        console.debug('[GARI Auth] Token refresh error:', e);
                    }
                }
            });

            // Listen for auth state changes
            onAuthStateChanged(this.firebaseAuth, async (fbUser) => {
                if (fbUser) {
                    if (this._registrationInFlight) return;
                    try {
                        const token = await fbUser.getIdToken();
                        this.idToken = token;
                        localStorage.setItem('gari_token', token);
                        await this.checkCurrentSession(token);
                    } catch (e) {
                        console.warn('[GARI Auth] Auth state change session sync:', e?.message || e);
                    }
                } else {
                    if (this.currentUser && this.currentUser.identity && this.currentUser.identity.provider_id === 'firebase') {
                        this.currentUser = null;
                        this.idToken = null;
                        localStorage.removeItem('gari_token');
                        localStorage.removeItem('gari_user');
                        this._notifyListeners(null);
                    }
                }
            });

            console.info('[GARI Auth] Firebase Auth SDK v10 initialized successfully.');
        } catch (err) {
            console.warn('[GARI Auth] Firebase SDK import failed. Using native session fallback.', err);
            this.isFirebaseReady = false;
        }
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
            try { cb(user); } catch (e) { console.error('[GARI Auth] Listener error:', e); }
        });
    }

    /**
     * Validates current session against backend /api/user/profile or /api/auth/me.
     * If backend is temporarily offline, falls back to Firebase authenticated user.
     */
    async checkCurrentSession(overrideToken) {
        const token = overrideToken || localStorage.getItem('gari_token');
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

        try {
            const res = await safeFetch('/api/user/profile', {
                headers,
                credentials: 'include'
            }, 7000);

            if (res.ok) {
                const data = await res.json();
                if (data.success) {
                    this.currentUser = {
                        identity: data.identity,
                        profile: data.profile,
                        subscription: data.subscription,
                        organizations: data.organizations,
                        system_role: data.system_role,
                        system_roles: data.system_roles,
                        account_type: data.account_type,
                        raw: data.raw_user,
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
            console.debug('[GARI Auth] Backend profile check unreachable:', e?.message || e);
        }

        // If backend check failed, but Firebase has an authenticated user, preserve session
        if (this.isFirebaseReady && this.firebaseAuth && this.firebaseAuth.currentUser) {
            const fbUser = this.firebaseAuth.currentUser;
            const cachedUser = safeGetCachedUser();
            this.currentUser = cachedUser || {
                identity: {
                    uid: fbUser.uid,
                    firebase_uid: fbUser.uid,
                    email: fbUser.email || '',
                    email_verified: Boolean(fbUser.emailVerified),
                    display_name: fbUser.displayName || (fbUser.email ? fbUser.email.split('@')[0] : 'Nông dân Gari'),
                    photo_url: fbUser.photoURL,
                    provider_id: 'firebase'
                },
                profile: {
                    full_name: fbUser.displayName || 'Nông dân Gari',
                    email: fbUser.email || ''
                },
                account_type: { key: 'farmer', label: 'Nông Hộ Cá Thể' },
                system_roles: { is_host_admin: false, is_expert: false, primary_role: 'farmer' },
                subscription: { plan: 'free', quota_limit: 10, quota_used: 0 },
                full_name: fbUser.displayName || 'Nông dân Gari',
                email: fbUser.email || '',
                is_host_admin: false
            };
            this._notifyListeners(this.currentUser);
            return this.currentUser;
        }

        // If there is a cached user and a valid token, don't clear prematurely during network glitch
        const cached = safeGetCachedUser();
        if (cached && token) {
            this.currentUser = cached;
            this._notifyListeners(this.currentUser);
            return this.currentUser;
        }

        this.currentUser = null;
        this._notifyListeners(null);
        return null;
    }

    /**
     * Synchronizes verified Firebase ID token to backend SQLite user database.
     */
    async _exchangeFirebaseToken(idToken, registration = null, rememberMe = false) {
        const body = { id_token: idToken, remember_me: Boolean(rememberMe) };
        if (registration) Object.assign(body, registration);

        try {
            const res = await safeFetch('/api/auth/firebase-login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(body)
            }, 10000);

            const data = await safeJson(res);
            if (res.ok && data.success) {
                if (data.token) {
                    this.idToken = data.token;
                    localStorage.setItem('gari_token', data.token);
                }
                return this.checkCurrentSession(data.token);
            }

            if (!res.ok) {
                // If backend returned a clear business error (e.g. banned account)
                if (res.status === 403 || res.status === 400) {
                    throw createAuthError(data, res.status, 'Không thể xác thực tài khoản.');
                }
            }
        } catch (err) {
            // Re-throw explicit auth errors
            if (err.message && !err.message.includes('fetch') && !err.message.includes('Failed')) {
                throw err;
            }
            console.warn('[GARI Auth] Backend sync temporary failure:', err?.message || err);
        }

        // If backend sync had network error, keep token in storage and construct user from Firebase
        this.idToken = idToken;
        localStorage.setItem('gari_token', idToken);
        return this.checkCurrentSession(idToken);
    }

    /**
     * Email and Password Login
     */
    /**
     * Email and Password Login with explicit provider-aware routing.
     * Rules:
     * - Rule A: If Firebase returns 'auth/user-not-found':
     *   Native SQLite authentication attempted only if account is known to belong to SQLite-only provider.
     * - Rule B: If Firebase returns 'auth/invalid-credential':
     *   Treated as ambiguous. Resolve provider through trusted mechanism (/api/auth/provider-lookup).
     *   If not sqlite_only, return normal invalid-credentials error without fallback.
     * - Rule C: If Firebase returns 'auth/wrong-password':
     *   Show invalid-credentials error, never fallback.
     * - Rule D: If FastAPI returns 401:
     *   Reject with invalid credentials; never issue a session or fallback identity.
     * - Rule E: If FastAPI returns 503:
     *   Show service-unavailable error; never bypass authentication.
     */
    async login(email, password, rememberMe = false, fetchOptions = {}) {
        if (this._loginInFlight) {
            throw new GariAuthError(
                'ALREADY_IN_FLIGHT',
                'Yêu cầu đăng nhập đang được xử lý. Vui lòng đợi trong giây lát.',
                'CONCURRENT_LOGIN_BLOCKED',
                'IN_FLIGHT'
            );
        }

        email = (email || '').trim().toLowerCase();
        if (!email || !password) {
            throw new Error('Vui lòng nhập đầy đủ email và mật khẩu.');
        }

        this._loginInFlight = true;
        try {
            return await this._executeLogin(email, password, rememberMe, fetchOptions);
        } finally {
            this._loginInFlight = false;
        }
    }

    async _executeLogin(email, password, rememberMe = false, fetchOptions = {}) {
        // 1. Firebase Authentication (when configured)
        if (this.isFirebaseReady && this.firebaseAuth && this._fbMethods) {
            try {
                const cred = await withTimeout(
                    this._fbMethods.signInWithEmailAndPassword(this.firebaseAuth, email, password),
                    10000,
                    'Đăng nhập qua Firebase quá thời gian chờ (10s).'
                );
                const token = await withTimeout(cred.user.getIdToken(), 5000);
                const user = await this._exchangeFirebaseToken(token, null, rememberMe);
                return { success: true, user, provider: 'firebase' };
            } catch (fbErr) {
                const code = (fbErr?.code || '').toLowerCase();

                // Rule C: Explicit wrong password on Firebase -> Never fallback
                if (code === 'auth/wrong-password') {
                    throw new GariAuthError(
                        'INVALID_CREDENTIALS',
                        'Email hoặc mật khẩu không chính xác.',
                        { email, code },
                        'invalid_credentials'
                    );
                }

                // If configuration failure (e.g. invalid API key), warn and attempt native
                if (code.includes('api-key') || code === 'auth/operation-not-allowed') {
                    console.warn('[GARI Auth] Firebase configuration issue, falling back to native auth:', fbErr?.code);
                } 
                // Rule A & B: 'auth/user-not-found' or ambiguous 'auth/invalid-credential'
                else if (code === 'auth/user-not-found' || code === 'auth/invalid-credential') {
                    // Resolve provider through trusted backend lookup
                    let isSqliteAccount = false;
                    try {
                        const lookupRes = await safeFetch('/api/auth/provider-lookup', {
                            ...fetchOptions,
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', ...(fetchOptions.headers || {}) },
                            body: JSON.stringify({ email })
                        }, 5000);
                        if (lookupRes.status === 503 || lookupRes.status === 502 || lookupRes.status === 504) {
                            throw new GariAuthError(
                                'BACKEND_UNAVAILABLE',
                                'Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát.',
                                { email, status: lookupRes.status },
                                'backend_unavailable'
                            );
                        }
                        if (lookupRes.status === 429) {
                            throw new GariAuthError(
                                'TOO_MANY_REQUESTS',
                                'Bạn đã gửi quá nhiều yêu cầu xác thực. Vui lòng thử lại sau 1 phút.',
                                { email, status: 429 },
                                'too_many_requests'
                            );
                        }
                        if (lookupRes.ok) {
                            const lookupData = await lookupRes.json();
                            if (lookupData.exists && (lookupData.provider === 'sqlite_only' || lookupData.provider === 'hybrid')) {
                                isSqliteAccount = true;
                            }
                        }
                    } catch (lookupErr) {
                        if (lookupErr?.code === 'BACKEND_UNAVAILABLE' || lookupErr?.code === 'TOO_MANY_REQUESTS') {
                            throw lookupErr;
                        }
                        console.debug('[GARI Auth] Provider lookup unreachable:', lookupErr?.message || lookupErr);
                    }

                    // Rule A & B: Only route to native SQLite if account is confirmed to belong to SQLite provider
                    if (!isSqliteAccount) {
                        throw new GariAuthError(
                            'INVALID_CREDENTIALS',
                            'Email hoặc mật khẩu không chính xác.',
                            { email, code },
                            'invalid_credentials'
                        );
                    }
                    console.info('[GARI Auth] Routing to SQLite-only provider for verified native account.');
                } else {
                    // Other Firebase errors (e.g. user-disabled, too-many-requests)
                    throw mapFirebaseError(fbErr);
                }
            }
        }

        // 2. Native Backend Authentication (FastAPI + SQLite password verification)
        const res = await safeFetch('/api/auth/login', {
            ...fetchOptions,
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...(fetchOptions.headers || {}) },
            credentials: 'include',
            body: JSON.stringify({ email, password, remember_me: Boolean(rememberMe) })
        }, 10000);

        // Rule E: HTTP 502/503/504 Backend Unavailable -> Show service-unavailable message, do not bypass
        if (res.status === 503 || res.status === 502 || res.status === 504) {
            throw new GariAuthError(
                'SERVICE_UNAVAILABLE',
                'Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát.',
                { status: res.status },
                'service_unavailable'
            );
        }

        const data = await safeJson(res);

        // Rule D: HTTP 401 Unauthorized -> Never issue session, never create fallback identity
        if (res.status === 401 || !res.ok || !data.success) {
            throw createAuthError(data, res.status, 'Email hoặc mật khẩu không chính xác.');
        }

        if (data.token) {
            localStorage.setItem('gari_token', data.token);
            this.idToken = data.token;
        }
        const user = await this.checkCurrentSession(data.token);
        return { success: true, user, provider: 'native' };
    }

    /**
     * User Registration
     * Supported account types:
     * - 'farmer' (Nông hộ)
     * - 'cooperative' (Hợp tác xã)
     * - 'agricultural_service_provider' / 'enterprise' (Dịch vụ BVTV)
     * Client cannot grant Host Admin or verified Expert roles.
     */
    async register(name, email, password, phone = '', province = 'Lâm Đồng', accountType = 'farmer', marketingOptIn = false) {
        name = (name || '').trim();
        email = (email || '').trim().toLowerCase();
        password = password || '';

        if (!name) throw new Error('Vui lòng nhập họ và tên.');
        if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error('Địa chỉ email không đúng định dạng.');
        if (password.length < 6) throw new Error('Mật khẩu phải có độ dài tối thiểu 6 ký tự.');

        // Normalize non-privileged account types
        const typeMap = {
            'farmer': 'farmer', 'nông hộ': 'farmer', 'nông hộ cá thể': 'farmer',
            'cooperative': 'cooperative', 'hợp tác xã': 'cooperative',
            'agricultural_service_provider': 'enterprise', 'agricultural service provider': 'enterprise',
            'dịch vụ bvtv': 'enterprise', 'đơn vị dịch vụ nông nghiệp': 'enterprise',
            'enterprise': 'enterprise'
        };
        const safeAccountType = typeMap[String(accountType).toLowerCase()] || 'farmer';

        // 1. Firebase Registration
        if (this.isFirebaseReady && this.firebaseAuth && this._fbMethods) {
            this._registrationInFlight = true;
            try {
                const cred = await withTimeout(
                    this._fbMethods.createUserWithEmailAndPassword(this.firebaseAuth, email, password),
                    10000,
                    'Tạo tài khoản qua Firebase quá thời gian chờ (10s).'
                );
                
                // Update display name
                try {
                    await withTimeout(this._fbMethods.updateProfile(cred.user, { displayName: name }), 5000);
                } catch (_) {}

                // Send verification email if supported
                try {
                    if (cred.user && !cred.user.emailVerified) {
                        await withTimeout(this._fbMethods.sendEmailVerification(cred.user), 5000);
                    }
                } catch (_) {}

                const token = await withTimeout(cred.user.getIdToken(), 5000);
                const user = await this._exchangeFirebaseToken(token, {
                    full_name: name,
                    phone: phone.trim(),
                    province: province.trim(),
                    account_type: safeAccountType,
                    terms_agreed: true,
                    marketing_opt_in: Boolean(marketingOptIn)
                });
                return { success: true, user, provider: 'firebase' };
            } catch (fbErr) {
                const code = (fbErr?.code || '').toLowerCase();
                if (code.includes('api-key') || code === 'auth/operation-not-allowed') {
                    console.warn('[GARI Auth] Firebase configuration issue, falling back to native registration:', fbErr?.code);
                } else {
                    // Safe recovery from partial failures: if Firebase created the user but profile sync was interrupted,
                    // sign in with the same credentials and complete the sync.
                    if (fbErr?.code === 'auth/email-already-in-use') {
                        try {
                            const existing = await withTimeout(this._fbMethods.signInWithEmailAndPassword(this.firebaseAuth, email, password), 8000);
                            const token = await withTimeout(existing.user.getIdToken(), 5000);
                            const user = await this._exchangeFirebaseToken(token, {
                                full_name: name,
                                phone: phone.trim(),
                                province: province.trim(),
                                account_type: safeAccountType,
                                terms_agreed: true,
                                marketing_opt_in: Boolean(marketingOptIn)
                            });
                            return { success: true, user, provider: 'firebase' };
                        } catch (_) {
                            // If credentials do not match or recovery fails, clearly report that email already exists
                            throw mapFirebaseError({ code: 'auth/email-already-in-use' });
                        }
                    }
                    console.warn('[GARI Auth] Firebase signup failure:', fbErr?.code || fbErr);
                    throw mapFirebaseError(fbErr);
                }
            } finally {
                this._registrationInFlight = false;
            }
        }

        // 2. Native Backend Fallback
        const res = await safeFetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                full_name: name,
                name: name,
                email,
                password,
                confirm_password: password,
                phone: phone.trim(),
                province: province.trim(),
                account_type: safeAccountType,
                terms_agreed: true,
                marketing_opt_in: Boolean(marketingOptIn)
            })
        }, 10000);

        const data = await safeJson(res);
        if (!res.ok || !data.success) {
            throw createAuthError(data, res.status, 'Đăng ký tài khoản thất bại.');
        }
        if (data.token) {
            localStorage.setItem('gari_token', data.token);
            this.idToken = data.token;
        }
        const user = await this.checkCurrentSession(data.token);
        return { success: true, user, provider: 'native' };
    }

    /**
     * Password Reset
     */
    async resetPassword(email) {
        email = (email || '').trim().toLowerCase();
        if (!email) throw new Error('Vui lòng nhập địa chỉ email.');

        if (this.isFirebaseReady && this.firebaseAuth && this._fbMethods) {
            try {
                await this._fbMethods.sendPasswordResetEmail(this.firebaseAuth, email);
                return { success: true, message: 'Đã gửi liên kết đặt lại mật khẩu đến email của bạn. Vui lòng kiểm tra hộp thư.' };
            } catch (fbErr) {
                console.warn('[GARI Auth] Firebase password reset error:', fbErr?.code || fbErr);
                throw mapFirebaseError(fbErr);
            }
        }

        const res = await safeFetch('/api/auth/forgot-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        }, 10000);
        const data = await safeJson(res);
        if (!res.ok || !data.success) {
            throw createAuthError(data, res.status, 'Không tìm thấy tài khoản với email này.');
        }
        return { success: true, message: data.message || 'Yêu cầu đặt lại mật khẩu đã được tiếp nhận.', reset_token: data.reset_token };
    }

    /**
     * Logout
     * Guarantees non-blocking client-side cleanup while attempting bounded server revocation.
     */
    async logout() {
        // 1. Firebase sign-out when applicable
        if (this.isFirebaseReady && this.firebaseAuth && this._fbMethods) {
            try {
                await this._fbMethods.signOut(this.firebaseAuth);
            } catch (e) {
                console.warn('[GARI Auth] Firebase signout error:', e?.message || e);
            }
        }

        // 2. Unconditionally clear only GARI-owned authentication storage immediately
        const token = this.idToken || localStorage.getItem('gari_token');
        const gariLocalKeys = ['gari_token', 'gari_user', 'gari_host_token', 'gari_active_farm', 'gari_active_org'];
        gariLocalKeys.forEach(k => localStorage.removeItem(k));

        try {
            const extraLocal = [];
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                if (k && (k.startsWith('gari_') || k.startsWith('firebase:authUser'))) extraLocal.push(k);
            }
            extraLocal.forEach(k => localStorage.removeItem(k));

            const extraSession = [];
            for (let i = 0; i < sessionStorage.length; i++) {
                const k = sessionStorage.key(i);
                if (k && (k.startsWith('gari_') || k.startsWith('firebase:authUser'))) extraSession.push(k);
            }
            extraSession.forEach(k => sessionStorage.removeItem(k));
        } catch (_) {}

        this.currentUser = null;
        this.idToken = null;
        this._notifyListeners(null);

        // 3. Attempt server-side session invalidation with bounded timeout (2.5s)
        let serverRevoked = false;
        if (token) {
            try {
                const res = await safeFetch('/api/auth/logout', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` },
                    credentials: 'include'
                }, 2500);
                serverRevoked = Boolean(res && res.ok);
            } catch (e) {
                console.debug('[GARI Auth] Server-side session revocation skipped/unreachable:', e?.message || e);
            }
        }

        return {
            success: true,
            localCleared: true,
            serverRevoked
        };
    }

    getAuthHeaders() {
        const token = this.idToken || localStorage.getItem('gari_token');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }
}

/**
 * Standardized client fetch wrapper with AbortSignal timeout and structured error handling.
 */
async function safeFetch(url, options = {}, timeoutMs = 10000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    if (options.signal) {
        if (options.signal.aborted) {
            clearTimeout(timeoutId);
            controller.abort();
        } else {
            options.signal.addEventListener('abort', () => {
                clearTimeout(timeoutId);
                controller.abort();
            });
        }
    }

    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        return response;
    } catch (err) {
        if (err.name === 'AbortError' || (typeof err.message === 'string' && err.message.includes('aborted'))) {
            throw new GariAuthError(
                'NETWORK_TIMEOUT',
                `Kết nối đến máy chủ quá thời gian chờ (${Math.round(timeoutMs / 1000)}s). Vui lòng kiểm tra mạng và thử lại.`,
                'FETCH_TIMEOUT',
                'TIMEOUT'
            );
        }
        if (err instanceof GariAuthError) {
            throw err;
        }
        throw new GariAuthError(
            'NETWORK_ERROR',
            'Không thể kết nối đến máy chủ GARI. Vui lòng kiểm tra kết nối mạng của bạn.',
            err?.message || 'FETCH_FAILED',
            'NETWORK_FAILURE'
        );
    } finally {
        clearTimeout(timeoutId);
    }
}

function safeGetCachedUser() {
    try {
        const item = localStorage.getItem('gari_user');
        return item ? JSON.parse(item) : null;
    } catch (_) {
        return null;
    }
}

async function safeJson(response) {
    try {
        const text = await response.text();
        return text ? JSON.parse(text) : {};
    } catch (_) {
        return {};
    }
}

class GariAuthError extends Error {
    constructor(category, message, technicalDetail = null, rawCode = null) {
        super(message);
        this.name = 'GariAuthError';
        this.category = category;
        this.rawCode = rawCode;
        this.technicalDetail = sanitizeLogData(technicalDetail);

        // Safe client console logging without leaking credentials
        console.warn(`[GARI Auth][${category}] ${message}`, {
            code: rawCode,
            detail: this.technicalDetail
        });
    }
}

function sanitizeLogData(data) {
    if (!data) return null;
    if (typeof data === 'string') {
        return data.replace(/(password|token|key|secret)=([^\s&]+)/gi, '$1=[REDACTED]');
    }
    if (typeof data === 'object') {
        const copy = Array.isArray(data) ? [...data] : { ...data };
        for (const k of Object.keys(copy)) {
            if (/password|token|secret|key|authorization/i.test(k)) {
                copy[k] = '[REDACTED]';
            } else if (typeof copy[k] === 'object') {
                copy[k] = sanitizeLogData(copy[k]);
            }
        }
        return copy;
    }
    return data;
}

function createAuthError(data, statusCode, fallback) {
    const code = data?.code || '';
    const detail = data?.detail || data?.message || '';

    // 1. Backend unavailable (HTTP 502, 503, 504, DNS error)
    if (code === 'BACKEND_NOT_CONFIGURED' || code === 'BACKEND_UNAVAILABLE' || statusCode === 502 || statusCode === 503 || statusCode === 504) {
        return new GariAuthError(
            'BACKEND_UNAVAILABLE',
            'Máy chủ dịch vụ hiện chưa sẵn sàng hoặc đang bảo trì (502/503). Vui lòng thử lại sau giây lát.',
            detail || `HTTP ${statusCode}`,
            code || `HTTP_${statusCode}`
        );
    }

    // 2. CORS failure
    if (code === 'CORS_ERROR' || (typeof detail === 'string' && detail.toLowerCase().includes('cors'))) {
        return new GariAuthError(
            'CORS_ERROR',
            'Lỗi bảo mật kết nối mạng (CORS). Vui lòng thử tải lại trang hoặc kiểm tra cấu hình tên miền.',
            detail,
            code || 'CORS_BLOCKED'
        );
    }

    // 3. Database permission failure (HTTP 403 or permission denied)
    if (statusCode === 403 || code === 'PERMISSION_DENIED' || (typeof detail === 'string' && detail.toLowerCase().includes('permission'))) {
        return new GariAuthError(
            'DATABASE_PERMISSION_ERROR',
            detail || 'Không có quyền truy cập hoặc ghi dữ liệu vào hệ thống. Vui lòng liên hệ bộ phận hỗ trợ.',
            detail,
            code || 'HTTP_403'
        );
    }

    // 4. Duplicate email (HTTP 409 Conflict)
    if (statusCode === 409 || code === 'EMAIL_ALREADY_EXISTS') {
        return new GariAuthError(
            'DUPLICATE_EMAIL',
            'Địa chỉ email này đã được đăng ký trên hệ thống GARI. Vui lòng đăng nhập hoặc dùng tính năng Quên mật khẩu.',
            detail,
            code || 'HTTP_409'
        );
    }

    // 5. Invalid registration data (HTTP 400, 422)
    if (statusCode === 400 || statusCode === 422) {
        return new GariAuthError(
            'INVALID_REGISTRATION_DATA',
            detail || 'Dữ liệu đăng ký không hợp lệ. Vui lòng kiểm tra lại thông tin.',
            detail,
            code || `HTTP_${statusCode}`
        );
    }

    // 6. Profile creation failure
    if (code === 'PROFILE_CREATION_FAILED') {
        return new GariAuthError(
            'PROFILE_CREATION_ERROR',
            'Tài khoản xác thực đã tạo nhưng chưa thể khởi tạo hồ sơ nông trại. Vui lòng thử lại.',
            detail,
            code
        );
    }

    // 7. Unexpected server error (HTTP 500)
    if (statusCode >= 500) {
        return new GariAuthError(
            'UNEXPECTED_SERVER_ERROR',
            'Hệ thống gặp sự cố nội bộ máy chủ (500). Đội ngũ kỹ thuật đã ghi nhận lỗi.',
            detail,
            code || `HTTP_${statusCode}`
        );
    }

    return new GariAuthError(
        'UNEXPECTED_SERVER_ERROR',
        detail || fallback,
        detail,
        code || `HTTP_${statusCode}`
    );
}

function mapFirebaseError(error) {
    const code = (error?.code || '').toLowerCase();
    const rawMessage = error?.message || '';

    // 1. Firebase configuration failure
    if (code.includes('api-key') || code === 'auth/invalid-api-key' || code === 'auth/app-not-authorized' || code === 'auth/unauthorized-domain') {
        return new GariAuthError(
            'FIREBASE_CONFIG_ERROR',
            code === 'auth/unauthorized-domain'
                ? 'Tên miền chưa được cấp phép xác thực Firebase. Vui lòng cấu hình Authorized Domains trong Firebase Console.'
                : 'Cấu hình khóa Firebase API chưa hợp lệ hoặc thiếu biến môi trường trên Vercel. Vui lòng kiểm tra cấu hình hệ thống.',
            rawMessage,
            code
        );
    }

    // 2. Duplicate email
    if (code === 'auth/email-already-in-use') {
        return new GariAuthError(
            'DUPLICATE_EMAIL',
            'Địa chỉ email này đã được đăng ký tài khoản. Vui lòng đăng nhập hoặc chọn Quên mật khẩu.',
            rawMessage,
            code
        );
    }

    // 3. Invalid registration data
    if (code === 'auth/weak-password') {
        return new GariAuthError(
            'INVALID_REGISTRATION_DATA',
            'Mật khẩu phải có ít nhất 6 ký tự.',
            rawMessage,
            code
        );
    }
    if (code === 'auth/invalid-email') {
        return new GariAuthError(
            'INVALID_REGISTRATION_DATA',
            'Địa chỉ email không đúng định dạng.',
            rawMessage,
            code
        );
    }

    // 4. Firebase authentication failure
    if (code === 'auth/user-not-found' || code === 'auth/wrong-password' || code === 'auth/invalid-credential') {
        return new GariAuthError(
            'FIREBASE_AUTH_ERROR',
            'Email hoặc mật khẩu không chính xác.',
            rawMessage,
            code
        );
    }
    if (code === 'auth/user-disabled') {
        return new GariAuthError(
            'FIREBASE_AUTH_ERROR',
            'Tài khoản này đã bị tạm khóa. Vui lòng liên hệ quản trị viên Gari.',
            rawMessage,
            code
        );
    }
    if (code === 'auth/too-many-requests') {
        return new GariAuthError(
            'FIREBASE_AUTH_ERROR',
            'Đã thử đăng nhập sai quá nhiều lần. Vui lòng đợi vài phút rồi thử lại.',
            rawMessage,
            code
        );
    }
    if (code === 'auth/operation-not-allowed') {
        return new GariAuthError(
            'FIREBASE_CONFIG_ERROR',
            'Phương thức đăng nhập bằng Email/Password chưa được kích hoạt trong Firebase Console Authentication.',
            rawMessage,
            code
        );
    }
    if (code === 'auth/popup-closed-by-user') {
        return new GariAuthError(
            'FIREBASE_AUTH_ERROR',
            'Cửa sổ xác thực đã bị đóng trước khi hoàn tất.',
            rawMessage,
            code
        );
    }

    // Network / timeout reaching Firebase
    if (code.includes('network') || code.includes('timeout')) {
        return new GariAuthError(
            'FIREBASE_AUTH_ERROR',
            'Không thể kết nối đến máy chủ xác thực Firebase. Vui lòng kiểm tra kết nối mạng và thử lại.',
            rawMessage,
            code
        );
    }

    return new GariAuthError(
        'FIREBASE_AUTH_ERROR',
        'Không thể xác thực tài khoản qua Firebase. Vui lòng thử lại sau.',
        rawMessage,
        code
    );
}

// Global singleton instance
window.gariAuth = new GariAuthClient();
window.GariAuthError = GariAuthError;
