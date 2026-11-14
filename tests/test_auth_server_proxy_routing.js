/**
 * GARI Gateway Auth Server Proxy Routing Verification Test
 * (tests/test_auth_server_proxy_routing.js)
 */
const http = require('http');
const assert = require('assert');
const gatewayHandler = require('../api/[...path].js');

function createMockReq(options = {}) {
  const {
    method = 'GET',
    url = '/api/health',
    query = {},
    headers = {},
    body = null
  } = options;

  const EventEmitter = require('events');
  const req = new EventEmitter();
  req.method = method;
  req.url = url;
  req.query = query;
  req.headers = { ...headers };

  process.nextTick(() => {
    if (body) {
      const buf = Buffer.isBuffer(body) ? body : Buffer.from(typeof body === 'string' ? body : JSON.stringify(body));
      req.emit('data', buf);
    }
    req.emit('end');
  });

  return req;
}

function createMockRes() {
  const EventEmitter = require('events');
  const res = new EventEmitter();
  res.statusCode = 200;
  res.headers = {};
  res.headersSent = false;
  let bodyChunks = [];

  res.setHeader = (k, v) => {
    res.headers[k.toLowerCase()] = v;
  };

  res.write = (chunk) => {
    if (chunk) bodyChunks.push(Buffer.from(chunk));
    return true;
  };

  res.end = (chunk) => {
    if (chunk) bodyChunks.push(Buffer.from(chunk));
    res.headersSent = true;
    res.body = Buffer.concat(bodyChunks).toString('utf8');
    res.emit('finish');
  };

  return res;
}

async function runTests() {
  console.log('================================================================');
  console.log('GARI AUTH_SERVER_URL GATEWAY PROXY ROUTING VERIFICATION');
  console.log('================================================================\n');

  let authServerCalls = [];
  let aiWorkerCalls = [];

  // 1. Mock Render Auth Server (port 9101)
  const authServer = http.createServer((req, res) => {
    authServerCalls.push({ method: req.method, url: req.url, headers: req.headers });
    if (req.url === '/api/v1/auth/login' || req.url === '/api/auth/login') {
      res.writeHead(200, {
        'content-type': 'application/json',
        'set-cookie': 'gari_auth_session=render_test_session_token_123; Path=/; HttpOnly; SameSite=Lax'
      });
      res.end(JSON.stringify({ success: true, user: { email: 'farmer@test.gari.vn', role: 'farmer' } }));
    } else {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok' }));
    }
  });
  await new Promise(r => authServer.listen(9101, r));

  // 2. Mock AI Worker (port 9102)
  const aiWorker = http.createServer((req, res) => {
    aiWorkerCalls.push({ method: req.method, url: req.url, headers: req.headers });
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ prediction: 'healthy', confidence: 0.98 }));
  });
  await new Promise(r => aiWorker.listen(9102, r));

  try {
    process.env.AUTH_SERVER_URL = 'http://127.0.0.1:9101';
    process.env.VERCEL_BACKEND_API_URL = 'http://127.0.0.1:9102';

    // [TEST 1] Auth route forwarded to AUTH_SERVER_URL with cookie forwarding and set-cookie propagation
    console.log('[TEST 1] /api/v1/auth/login forwarded to AUTH_SERVER_URL...');
    {
      const req = createMockReq({
        method: 'POST',
        url: '/api/v1/auth/login',
        query: { path: ['v1', 'auth', 'login'] },
        headers: { 'content-type': 'application/json', 'cookie': 'existing=val' },
        body: JSON.stringify({ email: 'farmer@test.gari.vn', password: 'password123' })
      });
      const res = createMockRes();

      await new Promise(resolve => {
        res.on('finish', resolve);
        gatewayHandler(req, res);
      });

      assert.strictEqual(res.statusCode, 200);
      assert.strictEqual(authServerCalls.length, 1);
      assert.strictEqual(authServerCalls[0].url, '/api/v1/auth/login');
      assert.strictEqual(authServerCalls[0].headers.cookie, 'existing=val');
      const setCookieStr = Array.isArray(res.headers['set-cookie'])
        ? res.headers['set-cookie'].join('; ')
        : (res.headers['set-cookie'] || '');
      assert.ok(setCookieStr.includes('gari_auth_session=render_test_session_token_123'));
      console.log('  -> PASS: Auth route routed to AUTH_SERVER_URL with 1st-party cookie propagation.');
    }

    // [TEST 2] AI Inference route forwarded to VERCEL_BACKEND_API_URL
    console.log('[TEST 2] /api/predict forwarded to VERCEL_BACKEND_API_URL...');
    {
      const req = createMockReq({
        method: 'POST',
        url: '/api/predict',
        query: { path: ['predict'] },
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ crop: 'rice' })
      });
      const res = createMockRes();

      await new Promise(resolve => {
        res.on('finish', resolve);
        gatewayHandler(req, res);
      });

      assert.strictEqual(res.statusCode, 200);
      assert.strictEqual(aiWorkerCalls.length, 1);
      assert.strictEqual(aiWorkerCalls[0].url, '/api/predict');
      console.log('  -> PASS: Non-auth route routed to VERCEL_BACKEND_API_URL.');
    }

    // [TEST 3] AI Worker offline (VERCEL_BACKEND_API_URL unset), Auth Server STILL works
    console.log('[TEST 3] AI Worker offline / unset; Auth Server still operates independently...');
    {
      delete process.env.VERCEL_BACKEND_API_URL;
      const req = createMockReq({
        method: 'POST',
        url: '/api/auth/login',
        query: { path: ['auth', 'login'] },
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ email: 'farmer@test.gari.vn', password: 'password123' })
      });
      const res = createMockRes();

      await new Promise(resolve => {
        res.on('finish', resolve);
        gatewayHandler(req, res);
      });

      assert.strictEqual(res.statusCode, 200);
      assert.strictEqual(authServerCalls.length, 2);
      console.log('  -> PASS: Auth succeeds independently while AI Worker is completely offline.');
    }

    // [TEST 4] AI Inference when AI Worker is unset returns fail-closed 503 standby
    console.log('[TEST 4] AI Inference when AI Worker is unset returns 503 standby...');
    {
      const req = createMockReq({
        method: 'POST',
        url: '/api/predict',
        query: { path: ['predict'] },
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ crop: 'rice' })
      });
      const res = createMockRes();

      await new Promise(resolve => {
        res.on('finish', resolve);
        gatewayHandler(req, res);
      });

      assert.strictEqual(res.statusCode, 503);
      const parsed = JSON.parse(res.body);
      assert.strictEqual(parsed.code, 'AI_INFERENCE_STANDBY');
      console.log('  -> PASS: Clean 503 standby returned for offline AI inference.');
    }

    console.log('\n================================================================');
    console.log('ALL 4 GATEWAY PROXY ROUTING TESTS PASSED (100%)');
    console.log('================================================================');
  } finally {
    await new Promise(r => authServer.close(r));
    await new Promise(r => aiWorker.close(r));
    delete process.env.AUTH_SERVER_URL;
    delete process.env.VERCEL_BACKEND_API_URL;
  }
}

runTests().catch(err => {
  console.error('Test failed with error:', err);
  process.exit(1);
});
