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
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Gari-API-Key');
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
 * Controlled Fail-Closed response when the authoritative backend is unavailable.
 * Strictly avoids issuing synthetic sessions, creating ephemeral users, or minting tokens.
 */
function handleBackendUnavailable(pathStr, res, err = null) {
  if (res.headersSent) {
    try { res.end(); } catch (_) {}
    return;
  }

  // 1. Health check - public status only, does not grant authenticated access
  if (pathStr === 'health') {
    res.statusCode = 200;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Access-Control-Allow-Origin', '*');
    return res.end(JSON.stringify({
      status: 'healthy',
      service: 'Gari AI Lab AgriTech Platform (Edge Gateway)',
      environment: process.env.NODE_ENV || 'production',
      version: '2.6.0',
      services: {
        gateway: 'healthy',
        backend_runtime: process.env.VERCEL_BACKEND_API_URL ? 'standby' : 'not_configured',
        firebase_admin: process.env.FIREBASE_PROJECT_ID ? 'configured' : 'standby'
      }
    }));
  }

  const isTimeout = Boolean(err && (err.message === 'Upstream timeout' || err.code === 'ETIMEDOUT'));

  // 2. AI Inference routes when backend is not connected
  if (pathStr.startsWith('predict') || pathStr.startsWith('diagnose') || pathStr.includes('inference')) {
    return sendJson(
      res,
      isTimeout ? 504 : 503,
      isTimeout ? 'AI_INFERENCE_TIMEOUT' : 'AI_INFERENCE_STANDBY',
      isTimeout
        ? 'Quá trình chẩn đoán AI nông nghiệp vượt quá thời gian chờ (Gateway Timeout). Vui lòng thử lại sau.'
        : 'Hệ thống chẩn đoán AI nông nghiệp đang trong trạng thái chờ hoặc đang nâng cấp mô hình. Vui lòng thử lại sau giây lát.'
    );
  }

  // 3. Fail-Closed for all authentication and application routes:
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
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Gari-API-Key');
    return res.end();
  }

  let segments = [];
  if (Array.isArray(req.query.path)) {
    segments = req.query.path;
  } else if (typeof req.query.path === 'string') {
    segments = req.query.path.split('/').filter(Boolean);
  }
  const pathStr = segments.join('/');

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

  // Fast-path health check or fail-closed response if no backend is configured
  // In local development, fall back to localhost FastAPI if unset
  const configuredOrigin = process.env.VERCEL_BACKEND_API_URL || 
    (process.env.NODE_ENV !== 'production' && !process.env.VERCEL_ENV ? 'http://127.0.0.1:8000' : '');
  if (!configuredOrigin) {
    return handleBackendUnavailable(pathStr, res);
  }

  let origin;
  try {
    origin = new URL(configuredOrigin);
    if (!['https:', 'http:'].includes(origin.protocol)) throw new Error('Unsupported protocol');
  } catch (_) {
    return handleBackendUnavailable(pathStr, res);
  }

  const isAuthOrHealthRoute = pathStr === 'health' || pathStr.startsWith('auth/') || pathStr === 'user/profile';

  // Read and buffer request payload safely before proxying to strictly prevent stream consumption deadlock
  let bufferedBody = null;
  if (['POST', 'PUT', 'PATCH'].includes(req.method)) {
    bufferedBody = await readRawBody(req, 10 * 1024 * 1024);
    if (bufferedBody === null) {
      return sendJson(res, 413, 'PAYLOAD_TOO_LARGE', 'Kích thước dữ liệu vượt quá giới hạn cho phép (10MB).');
    }
  }

  const upstreamPath = `${origin.pathname.replace(/\/$/, '')}/api/${segments.map(encodeURIComponent).join('/')}${req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : ''}`;
  const headers = { ...req.headers, host: origin.host };
  delete headers.connection;
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
      timeout: isAuthOrHealthRoute ? 3500 : Number(process.env.VERCEL_BACKEND_TIMEOUT_MS || 10000),
    }, (upstreamResponse) => {
      res.statusCode = upstreamResponse.statusCode || 502;
      for (const [key, value] of Object.entries(upstreamResponse.headers)) {
        if (value !== undefined) res.setHeader(key, value);
      }
      upstreamResponse.pipe(res);
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
