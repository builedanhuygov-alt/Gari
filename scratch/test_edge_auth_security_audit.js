/**
 * GARI AgriTech AI Lab — Edge Auth & Token Revocation Security Audit Runner
 * Mode: Safe isolated script with mock request/response streams.
 * Zero production database access. Zero real credentials.
 */

const assert = require('assert');
const crypto = require('crypto');
const { Readable } = require('stream');

// Load edge gateway handler
const edgeHandler = require('../api/[...path].js');

const SIGNING_SECRET = process.env.SESSION_SECRET || process.env.JWT_SECRET || 'gari_edge_auth_secret_2026_production_safe';

function callGatewayMock(method, pathSegments, bodyObj, headers = {}) {
    return new Promise((resolve) => {
        const bodyStr = bodyObj ? JSON.stringify(bodyObj) : '';
        const bodyBuf = Buffer.from(bodyStr, 'utf-8');

        const req = new Readable({
            read() {
                this.push(bodyBuf);
                this.push(null);
            }
        });

        req.method = method;
        req.url = `/api/${pathSegments.join('/')}`;
        req.query = { path: pathSegments };
        req.headers = {
            'content-type': 'application/json',
            'content-length': String(bodyBuf.length),
            ...headers
        };

        const res = {
            statusCode: 200,
            headers: {},
            headersSent: false,
            setHeader(k, v) { this.headers[k.toLowerCase()] = v; },
            end(data) {
                this.headersSent = true;
                let parsed = null;
                try { parsed = JSON.parse(data); } catch (_) { parsed = data; }
                resolve({ statusCode: this.statusCode, headers: this.headers, data: parsed });
            }
        };

        edgeHandler(req, res);
    });
}

async function runAudit() {
    console.log('================================================================');
    console.log('GARI EDGE AUTH & TOKEN REVOCATION SECURITY AUDIT');
    console.log('================================================================\n');

    const auditFindings = [];

    // Test 1: Backend unavailable during registration (Fail-Open vs Fail-Closed)
    console.log('[AUDIT TEST 1] Backend unavailable during registration...');
    const regRes = await callGatewayMock('POST', ['auth', 'register'], {
        name: 'Synthetic Farmer',
        email: `synth_${Date.now()}@test.gari.invalid`,
        password: 'Password123!',
        account_type: 'farmer'
    });
    console.log(`  -> Gateway response status: ${regRes.statusCode}`);
    console.log(`  -> Token issued: ${Boolean(regRes.data?.token)}`);
    if (regRes.statusCode === 200 && regRes.data?.token) {
        auditFindings.push({
            id: 'VULN-EDGE-01',
            severity: 'CRITICAL',
            title: 'Fail-Open Ephemeral Registration Bypass',
            description: 'Edge Gateway issues authenticated session when backend is down without persistent DB record.'
        });
        console.log('  [!] VULNERABILITY CONFIRMED: Gateway created ephemeral session without backend persistence.');
    }

    // Test 2: Backend unavailable during login (Arbitrary Login / Credential Bypass)
    console.log('\n[AUDIT TEST 2] Backend unavailable during login with arbitrary wrong credentials...');
    const victimEmail = 'target_executive@gari.vn';
    const loginRes = await callGatewayMock('POST', ['auth', 'login'], {
        email: victimEmail,
        password: 'CompletelyWrongPassword!999'
    });
    console.log(`  -> Gateway response status: ${loginRes.statusCode}`);
    console.log(`  -> Gateway code: ${loginRes.data?.code}`);
    console.log(`  -> Token issued: ${Boolean(loginRes.data?.token)}`);
    if (loginRes.statusCode === 200 && loginRes.data?.token) {
        auditFindings.push({
            id: 'VULN-EDGE-02',
            severity: 'CRITICAL',
            title: 'Unauthenticated Arbitrary Login Bypass (Dynamic Recovery Session)',
            description: 'Gateway lines 250-256 issue a valid signed token for ANY email with ANY wrong password when not in edgeUserStore.'
        });
        console.log('  [!] CRITICAL VULNERABILITY CONFIRMED: Gateway issued authenticated token for arbitrary unverified credentials!');
    }

    // Test 3: Backend unavailable during logout
    console.log('\n[AUDIT TEST 3] Backend unavailable during logout...');
    const logoutRes = await callGatewayMock('POST', ['auth', 'logout'], {}, {
        authorization: `Bearer ${loginRes.data?.token}`
    });
    console.log(`  -> Gateway logout response: ${logoutRes.statusCode} (${logoutRes.data?.detail})`);

    // Test 4: Expired token check
    console.log('\n[AUDIT TEST 4] Expired token rejection (>24h)...');
    const pastTime = Date.now() - (25 * 3600 * 1000);
    const expiredPayload = { uid: 'usr_past', email: 'expired@test.invalid', created: pastTime };
    const expData = Buffer.from(JSON.stringify(expiredPayload)).toString('base64url');
    const expHmac = crypto.createHmac('sha256', SIGNING_SECRET).update(expData).digest('base64url');
    const expiredToken = `gari_edge_${expData}.${expHmac}`;
    const expRes = await callGatewayMock('GET', ['user', 'profile'], null, {
        authorization: `Bearer ${expiredToken}`
    });
    console.log(`  -> Expired token response: ${expRes.statusCode} (Expected: 401)`);
    assert.strictEqual(expRes.statusCode, 401);

    // Test 5: Multiple Vercel instances & cold start revocation bypass
    console.log('\n[AUDIT TEST 5] Multiple Gateway instances / Cold start revocation bypass...');
    // Create an active token
    const tokenPayload = { uid: 'usr_valid', email: 'farmer@test.invalid', created: Date.now() };
    const validData = Buffer.from(JSON.stringify(tokenPayload)).toString('base64url');
    const validHmac = crypto.createHmac('sha256', SIGNING_SECRET).update(validData).digest('base64url');
    const tokenToRevoke = `gari_edge_${validData}.${validHmac}`;

    // Instance 1 revokes it
    await callGatewayMock('POST', ['auth', 'logout'], {}, {
        authorization: `Bearer ${tokenToRevoke}`
    });
    // Instance 1 checks it -> rejected (in its local Set)
    const inst1Check = await callGatewayMock('GET', ['user', 'profile'], null, {
        authorization: `Bearer ${tokenToRevoke}`
    });
    console.log(`  -> Instance 1 (same process) verification: HTTP ${inst1Check.statusCode}`);

    // Simulate Instance 2 (or cold restart: fresh process where revokedEdgeTokens is empty)
    // Clear the require cache to simulate a fresh serverless execution environment
    delete require.cache[require.resolve('../api/[...path].js')];
    const freshInstanceHandler = require('../api/[...path].js');

    const reqFresh = new Readable({ read() { this.push(null); } });
    reqFresh.method = 'GET';
    reqFresh.url = '/api/user/profile';
    reqFresh.query = { path: ['user', 'profile'] };
    reqFresh.headers = { authorization: `Bearer ${tokenToRevoke}` };
    const resFresh = {
        statusCode: 200,
        headers: {},
        setHeader(k, v) { this.headers[k.toLowerCase()] = v; },
        end(data) {
            this.data = JSON.parse(data);
        }
    };
    freshInstanceHandler(reqFresh, resFresh);

    console.log(`  -> Instance 2 (fresh container / cold start) verification: HTTP ${resFresh.statusCode}`);
    if (resFresh.statusCode === 200) {
        auditFindings.push({
            id: 'VULN-EDGE-03',
            severity: 'HIGH',
            title: 'Non-Durable Distributed Revocation (In-Memory Blacklist Reset)',
            description: 'revokedEdgeTokens Set is process-bound. Any new container, parallel worker, or cold start accepts previously revoked tokens.'
        });
        console.log('  [!] VULNERABILITY CONFIRMED: Revoked token was ACCEPTED on simulated second container / cold start!');
    }

    // Test 6: Invalid HMAC signature
    console.log('\n[AUDIT TEST 6] Tampered HMAC signature...');
    const tamperedToken = `${tokenToRevoke.slice(0, -6)}xxxxxx`;
    const tamperRes = await callGatewayMock('GET', ['user', 'profile'], null, {
        authorization: `Bearer ${tamperedToken}`
    });
    console.log(`  -> Tampered token response: HTTP ${tamperRes.statusCode} (Expected: 401)`);
    assert.strictEqual(tamperRes.statusCode, 401);

    // Test 7: Tampered claims payload
    console.log('\n[AUDIT TEST 7] Tampered payload claims...');
    const adminPayload = { uid: 'usr_admin', email: 'admin@gari.vn', created: Date.now() };
    const adminData = Buffer.from(JSON.stringify(adminPayload)).toString('base64url');
    // Pair with HMAC of original token
    const mismatchedToken = `gari_edge_${adminData}.${validHmac}`;
    const claimRes = await callGatewayMock('GET', ['user', 'profile'], null, {
        authorization: `Bearer ${mismatchedToken}`
    });
    console.log(`  -> Mismatched claim token response: HTTP ${claimRes.statusCode} (Expected: 401)`);
    assert.strictEqual(claimRes.statusCode, 401);

    console.log('\n================================================================');
    console.log(`AUDIT COMPLETE — ${auditFindings.length} VULNERABILITIES IDENTIFIED`);
    console.log('================================================================');
    auditFindings.forEach(f => {
        console.log(`- [${f.severity}] ${f.id}: ${f.title}`);
    });
}

runAudit().catch(console.error);

