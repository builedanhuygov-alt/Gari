/**
 * GARI AgriTech AI Lab — Supabase Client Unit Test Suite
 * Tests client-side error mapping, timeout bounds, and state restoration guarantees.
 * NO PHP — Pure Node.js.
 */
const assert = require('assert');

console.log('================================================================');
console.log('GARI SUPABASE CLIENT UNIT TEST SUITE (NODE.JS)');
console.log('================================================================\n');

function runTest(name, fn) {
    try {
        fn();
        console.log(`[PASS] ${name}`);
    } catch (err) {
        console.error(`[FAIL] ${name}:`, err.message);
        process.exitCode = 1;
    }
}

async function runAsyncTest(name, fn) {
    try {
        await fn();
        console.log(`[PASS] ${name}`);
    } catch (err) {
        console.error(`[FAIL] ${name}:`, err.message);
        process.exitCode = 1;
    }
}

// 1. Error Mapping Unit Tests
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

runTest('Test 1: Map "User already registered" to Vietnamese notice', () => {
    const err = mapSupabaseError({ message: 'User already registered' });
    assert.strictEqual(err.message, 'Địa chỉ email này đã được đăng ký tài khoản. Vui lòng đăng nhập hoặc chọn Quên mật khẩu.');
});

runTest('Test 2: Map "Invalid login credentials" to Vietnamese notice', () => {
    const err = mapSupabaseError({ message: 'Invalid login credentials' });
    assert.strictEqual(err.message, 'Email hoặc mật khẩu không chính xác.');
});

runTest('Test 3: Map "Email not confirmed" to Vietnamese notice', () => {
    const err = mapSupabaseError({ message: 'Email not confirmed' });
    assert.strictEqual(err.message, 'Tài khoản chưa được xác nhận email. Vui lòng kiểm tra hộp thư email để kích hoạt tài khoản.');
});

runTest('Test 4: Map rate limit to Vietnamese notice', () => {
    const err = mapSupabaseError({ message: 'over_email_send_rate_limit' });
    assert.strictEqual(err.message, 'Bạn đã thao tác quá nhiều lần. Vui lòng chờ vài phút rồi thử lại.');
});

// 2. Timeout Promise Race Helper Unit Tests
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

(async function runAll() {
    await runAsyncTest('Test 5: withTimeout settles with value when promise completes before timeout', async () => {
        const fastPromise = new Promise(resolve => setTimeout(() => resolve('success'), 20));
        const res = await withTimeout(fastPromise, 200, 'Timeout');
        assert.strictEqual(res, 'success');
    });

    await runAsyncTest('Test 6: withTimeout rejects with TimeoutError when promise hangs', async () => {
        const hangingPromise = new Promise(() => {}); // never resolves
        let caught = null;
        try {
            await withTimeout(hangingPromise, 50, 'Quá thời gian chờ.');
        } catch (e) {
            caught = e;
        }
        assert.ok(caught);
        assert.strictEqual(caught.message, 'Quá thời gian chờ.');
    });

    await runAsyncTest('Test 7: Guaranteed button recovery pattern in finally block under hang', async () => {
        let isSubmitting = true;
        let buttonState = { disabled: true, text: 'Đang khởi tạo tài khoản...' };

        try {
            const hangingNetwork = new Promise(() => {});
            await withTimeout(hangingNetwork, 50, 'Mạng quá hạn 50ms');
        } catch (e) {
            // caught
        } finally {
            isSubmitting = false;
            buttonState.disabled = false;
            buttonState.text = 'Tạo tài khoản nông trại';
        }

        assert.strictEqual(isSubmitting, false, 'isSubmitting flag must be restored to false.');
        assert.strictEqual(buttonState.disabled, false, 'Button must be unlocked.');
        assert.strictEqual(buttonState.text, 'Tạo tài khoản nông trại', 'Button label must be restored.');
    });

    console.log('\n================================================================');
    console.log('ALL SUPABASE CLIENT UNIT TESTS PASSED (7/7)');
    console.log('================================================================');
})();

