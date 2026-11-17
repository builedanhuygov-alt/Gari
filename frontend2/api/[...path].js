const https = require('https');
const http = require('http');

module.exports.config = { api: { bodyParser: false } };

function sendJson(res, statusCode, code, message, extra = {}) {
  if (res.headersSent) {
    try { res.end(); } catch (_) {}
    return;
  }
  res.statusCode = statusCode;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Gari-API-Key, X-Client-Id');
  res.end(JSON.stringify({ success: statusCode >= 200 && statusCode < 300, code, detail: message, ...extra }));
}

function readRawBody(req, limit = 1024 * 1024) {
  // 1. If body is already parsed or buffered by Vercel serverless runtime
  if (req && req.body) {
    if (Buffer.isBuffer(req.body)) return Promise.resolve(req.body);
    if (typeof req.body === 'string') return Promise.resolve(Buffer.from(req.body));
    if (typeof req.body === 'object') {
      try {
        return Promise.resolve(Buffer.from(JSON.stringify(req.body)));
      } catch (_) {}
    }
  }
  if (req && req.readableEnded) {
    return Promise.resolve(Buffer.alloc(0));
  }

  // 2. Read from stream with bounded timeout to strictly prevent hanging
  return new Promise((resolve) => {
    const chunks = [];
    let size = 0;
    let settled = false;

    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        resolve(Buffer.concat(chunks));
      }
    }, 4000);

    req.on('data', chunk => {
      if (settled) return;
      size += chunk.length;
      if (size > limit) {
        settled = true;
        clearTimeout(timer);
        req.destroy();
        resolve(null);
      } else {
        chunks.push(chunk);
      }
    });
    req.on('end', () => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        resolve(Buffer.concat(chunks));
      }
    });
    req.on('error', () => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        resolve(Buffer.alloc(0));
      }
    });
  });
}

/**
 * Safely probes an upstream HTTP/HTTPS endpoint for health checks with bounded timeout.
 * Never throws unhandled exceptions; resolves with status and parsed JSON data if valid.
 */
function probeEndpoint(urlStr, timeoutMs = 2000) {
  return new Promise((resolve) => {
    try {
      const url = new URL(urlStr);
      if (!['https:', 'http:'].includes(url.protocol)) {
        return resolve({ ok: false, statusCode: 500, data: null, error: 'INVALID_PROTOCOL' });
      }
      const transport = url.protocol === 'https:' ? https : http;
      const req = transport.request({
        protocol: url.protocol,
        hostname: url.hostname,
        port: url.port || undefined,
        method: 'GET',
        path: `${url.pathname.replace(/\/$/, '')}/api/health`,
        headers: { 'Accept': 'application/json', 'User-Agent': 'GARI-Gateway-HealthCheck/2.6' },
        timeout: timeoutMs,
      }, (res) => {
        const chunks = [];
        res.on('data', c => chunks.push(c));
        res.on('end', () => {
          let data = null;
          try {
            data = JSON.parse(Buffer.concat(chunks).toString('utf-8'));
          } catch (_) {}
          resolve({ ok: res.statusCode >= 200 && res.statusCode < 300, statusCode: res.statusCode, data });
        });
      });
      req.on('timeout', () => {
        req.destroy();
        resolve({ ok: false, statusCode: 504, data: null, error: 'TIMEOUT' });
      });
      req.on('error', (err) => {
        resolve({ ok: false, statusCode: 503, data: null, error: err.code || 'CONN_ERR' });
      });
      req.end();
    } catch (_) {
      resolve({ ok: false, statusCode: 500, data: null, error: 'INVALID_URL' });
    }
  });
}

/**
 * Multi-layer health status handler that independently evaluates:
 * - Gateway
 * - Auth Server
 * - AI Bridge
 * - AI Worker
 * - Model Readiness
 * - Inference Readiness
 * Strictly conceals all secrets, tokens, tunnel hostnames, and internal network addresses.
 */
async function handleHealthCheck(req, res) {
  if (res.headersSent) {
    try { res.end(); } catch (_) {}
    return;
  }

  const authUrl = process.env.AUTH_SERVER_URL;
  const aiBackendUrl = process.env.AI_BRIDGE_URL || process.env.VERCEL_BACKEND_API_URL ||
    (process.env.NODE_ENV !== 'production' && !process.env.VERCEL_ENV ? 'http://127.0.0.1:8000' : '');

  const [authProbe, aiProbe] = await Promise.all([
    authUrl ? probeEndpoint(authUrl, 2000) : Promise.resolve(null),
    aiBackendUrl ? probeEndpoint(aiBackendUrl, 2000) : Promise.resolve(null)
  ]);

  const gateway = {
    status: 'healthy',
    uptime_sec: Math.floor(process.uptime())
  };

  let authServer = { status: 'not_configured' };
  if (authUrl) {
    authServer = {
      status: (authProbe && authProbe.ok) ? 'healthy' : 'degraded'
    };
  }

  let aiBridge = { status: 'not_configured' };
  let aiWorker = { status: 'not_configured' };
  let modelReadiness = { status: 'not_configured' };
  let inferenceReadiness = { status: 'standby' };

  if (aiBackendUrl) {
    if (aiProbe && aiProbe.ok && aiProbe.data) {
      const probeData = aiProbe.data;
      const workerHealthy = probeData.status === 'healthy' ||
                            (probeData.services && probeData.services.backend_runtime === 'healthy');
      const modelHealthy = Boolean(probeData.services && probeData.services.ai_inference === 'healthy');

      aiBridge = {
        status: 'healthy',
        configured: true
      };
      aiWorker = {
        status: workerHealthy ? 'healthy' : 'degraded'
      };
      modelReadiness = {
        status: modelHealthy ? 'ready' : 'standby'
      };
      inferenceReadiness = {
        status: (workerHealthy && modelHealthy) ? 'ready' : 'standby'
      };
    } else {
      aiBridge = {
        status: process.env.AI_BRIDGE_URL ? 'degraded' : 'standby',
        configured: true
      };
      aiWorker = { status: 'offline' };
      modelReadiness = { status: 'standby' };
      inferenceReadiness = { status: 'standby' };
    }
  }

  // Aggregate health status:
  // If inference is ready and auth is not degraded -> healthy
  // If inference is in standby or auth is degraded -> degraded
  // If both are completely down/failing -> unhealthy
  let overallStatus = 'healthy';
  if (inferenceReadiness.status !== 'ready' || authServer.status === 'degraded') {
    overallStatus = 'degraded';
  }
  if (inferenceReadiness.status === 'standby' && (authServer.status === 'degraded' || (authServer.status === 'not_configured' && !aiBackendUrl))) {
    overallStatus = 'unhealthy';
  }

  res.statusCode = 200;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');

  return res.end(JSON.stringify({
    status: overallStatus,
    service: 'Gari AI Lab AgriTech Platform (Edge Gateway)',
    environment: process.env.NODE_ENV || 'production',
    version: '2.6.0',
    timestamp: new Date().toISOString(),
    services: {
      gateway,
      auth_server: authServer,
      ai_bridge: aiBridge,
      ai_worker: aiWorker,
      model_readiness: modelReadiness,
      inference_readiness: inferenceReadiness
    }
  }));
}

/**
 * Controlled Fail-Closed response when the authoritative backend is unavailable.
 * Strictly avoids issuing synthetic sessions, creating ephemeral users, or minting tokens.
 */
function handleBackendUnavailable(pathStr, res, err = null) {
  if (res.headersSent) {
    try { res.end(); } catch (_) {}
    return;
  }

  // 1. Health check route fallback
  if (pathStr === 'health' || pathStr === 'v1/health') {
    return handleHealthCheck(null, res);
  }

  const isTimeout = Boolean(err && (err.message === 'Upstream timeout' || err.code === 'ETIMEDOUT'));

  // 2. Quota route fallback: accurately informs the client that quota service is offline
  if (pathStr === 'user/quota' || pathStr.startsWith('user/quota')) {
    return sendJson(
      res,
      isTimeout ? 504 : 503,
      isTimeout ? 'QUOTA_SERVICE_TIMEOUT' : 'QUOTA_SERVICE_UNAVAILABLE',
      isTimeout
        ? 'Yêu cầu kiểm tra hạn mức chẩn đoán vượt quá thời gian chờ (Gateway Timeout). Vui lòng thử lại sau.'
        : 'Máy chủ quản lý hạn ngạch hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát.'
    );
  }

  // 3. AI Inference routes when backend is not connected
  if (pathStr.startsWith('predict') || pathStr.startsWith('diagnose') || pathStr.includes('inference') || pathStr.includes('diagnose') || pathStr.startsWith('plant/')) {
    return sendJson(
      res,
      isTimeout ? 504 : 503,
      isTimeout ? 'AI_INFERENCE_TIMEOUT' : 'AI_INFERENCE_STANDBY',
      isTimeout
        ? 'Quá trình chẩn đoán AI nông nghiệp vượt quá thời gian chờ (Gateway Timeout). Vui lòng thử lại sau.'
        : 'Dịch vụ phân tích hiện không khả dụng. Máy chủ chẩn đoán AI nông nghiệp đang trong trạng thái chờ hoặc đang nâng cấp mô hình. Vui lòng thử lại sau giây lát.'
    );
  }

  // 4. Fail-Closed for all authentication and application routes:
  // Never create unverified accounts, never issue synthetic tokens, never bypass credentials.
  return sendJson(
    res,
    isTimeout ? 504 : 503,
    isTimeout ? 'BACKEND_TIMEOUT' : 'BACKEND_UNAVAILABLE',
    isTimeout
      ? 'Yêu cầu đến máy chủ xác thực vượt quá thời gian chờ (Gateway Timeout). Vui lòng thử lại sau.'
      : 'Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát.'
  );
}

async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.statusCode = 204;
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Gari-API-Key, X-Client-Id');
    return res.end();
  }

  let segments = [];
  if (Array.isArray(req.query.path)) {
    segments = req.query.path;
  } else if (typeof req.query.path === 'string') {
    segments = req.query.path.split('/').filter(Boolean);
  }
  const pathStr = segments.join('/');

  // Direct Vercel Serverless handler for Health Check
  if (pathStr === 'health' || pathStr === 'v1/health') {
    return handleHealthCheck(req, res);
  }

  // Direct Vercel Serverless handler for /api/auth/firebase-config (Public config bootstrap)
  if (pathStr === 'auth/firebase-config') {
    const apiKey = (process.env.FIREBASE_API_KEY || process.env.VITE_FIREBASE_API_KEY || '').trim();
    const projectId = (process.env.FIREBASE_PROJECT_ID || process.env.VITE_FIREBASE_PROJECT_ID || '').trim();
    const authDomain = (process.env.FIREBASE_AUTH_DOMAIN || process.env.VITE_FIREBASE_AUTH_DOMAIN || (projectId ? `${projectId}.firebaseapp.com` : '')).trim();
    const storageBucket = (process.env.FIREBASE_STORAGE_BUCKET || process.env.VITE_FIREBASE_STORAGE_BUCKET || (projectId ? `${projectId}.appspot.com` : '')).trim();
    const messagingSenderId = (process.env.FIREBASE_MESSAGING_SENDER_ID || process.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '').trim();
    const appId = (process.env.FIREBASE_APP_ID || process.env.VITE_FIREBASE_APP_ID || '').trim();
    const measurementId = (process.env.FIREBASE_MEASUREMENT_ID || process.env.VITE_FIREBASE_MEASUREMENT_ID || '').trim();

    const configured = Boolean(apiKey && projectId);

    res.statusCode = 200;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 'public, max-age=60, s-maxage=300');
    res.setHeader('Access-Control-Allow-Origin', '*');
    return res.end(JSON.stringify({
      success: true,
      configured,
      config: {
        apiKey,
        authDomain,
        projectId,
        storageBucket,
        messagingSenderId,
        appId,
        measurementId
      }
    }));
  }

  const isAuthRoute = pathStr.startsWith('auth/') || pathStr.startsWith('v1/auth/') ||
                      pathStr === 'user/profile' || pathStr === 'profile' || pathStr === 'v1/profile' ||
                      pathStr === 'ready' || pathStr === 'v1/ready' ||
                      pathStr.startsWith('admin/') || pathStr.startsWith('v1/admin/');

  // Auth routing priority: Use dedicated AUTH_SERVER_URL if configured, otherwise fall back to AI backend URL
  const aiBackendStr = process.env.AI_BRIDGE_URL || process.env.VERCEL_BACKEND_API_URL || 
    (process.env.NODE_ENV !== 'production' && !process.env.VERCEL_ENV ? 'http://127.0.0.1:8000' : '');

  let targetOriginStr = '';
  if (isAuthRoute && process.env.AUTH_SERVER_URL) {
    targetOriginStr = process.env.AUTH_SERVER_URL;
  } else {
    targetOriginStr = aiBackendStr;
  }

  if (!targetOriginStr) {
    return handleBackendUnavailable(pathStr, res);
  }

  let origin;
  try {
    origin = new URL(targetOriginStr);
    if (!['https:', 'http:'].includes(origin.protocol)) throw new Error('Unsupported protocol');
  } catch (_) {
    return handleBackendUnavailable(pathStr, res);
  }

  // Read and buffer request payload safely before proxying to strictly prevent stream consumption deadlock
  let bufferedBody = null;
  if (['POST', 'PUT', 'PATCH'].includes(req.method)) {
    bufferedBody = await readRawBody(req, 10 * 1024 * 1024);
    if (bufferedBody === null) {
      return sendJson(res, 413, 'PAYLOAD_TOO_LARGE', 'Kích thước dữ liệu vượt quá giới hạn cho phép (10MB).');
    }
  }

  const upstreamPath = pathStr.startsWith('uploads/')
    ? `${origin.pathname.replace(/\/$/, '')}/${segments.map(encodeURIComponent).join('/')}${req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : ''}`
    : `${origin.pathname.replace(/\/$/, '')}/api/${segments.map(encodeURIComponent).join('/')}${req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : ''}`;
  const headers = { ...req.headers, host: origin.host };
  delete headers.connection;

  // Preserve client IP and forwarding protocol headers
  if (!headers['x-forwarded-for']) {
    headers['x-forwarded-for'] = req.socket?.remoteAddress || '127.0.0.1';
  }
  if (!headers['x-forwarded-proto']) {
    headers['x-forwarded-proto'] = origin.protocol === 'https:' ? 'https' : 'http';
  }

  if (bufferedBody !== null) {
    headers['content-length'] = String(Buffer.byteLength(bufferedBody));
  }

  const transport = origin.protocol === 'https:' ? https : http;
  let upstream;
  try {
    upstream = transport.request({
      protocol: origin.protocol,
      hostname: origin.hostname,
      port: origin.port || undefined,
      method: req.method,
      path: upstreamPath,
      headers,
      timeout: isAuthRoute ? 25000 : Number(process.env.VERCEL_BACKEND_TIMEOUT_MS || 25000),
    }, (upstreamResponse) => {
      res.statusCode = upstreamResponse.statusCode || 502;
      for (const [key, value] of Object.entries(upstreamResponse.headers)) {
        if (value !== undefined) res.setHeader(key, value);
      }
      if (typeof upstreamResponse.pipe === 'function' && typeof res.once === 'function') {
        upstreamResponse.pipe(res);
      } else {
        upstreamResponse.on('data', (chunk) => {
          if (typeof res.write === 'function') res.write(chunk);
          else if (res.bodyChunks) res.bodyChunks.push(chunk);
        });
        upstreamResponse.on('end', () => {
          if (typeof res.end === 'function') res.end();
        });
      }
    });

    upstream.on('timeout', () => {
      upstream.destroy(new Error('Upstream timeout'));
    });

    upstream.on('error', (err) => {
      handleBackendUnavailable(pathStr, res, err);
    });

    if (bufferedBody !== null) {
      upstream.write(bufferedBody);
      upstream.end();
    } else {
      upstream.end();
    }
  } catch (err) {
    handleBackendUnavailable(pathStr, res, err);
  }
}

module.exports = handler;
module.exports.config = { api: { bodyParser: false } };
