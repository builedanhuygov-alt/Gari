/**
 * CORS hardening tests for server/src/index.ts
 *
 * Framework: Jest (ts-jest) using native Node http module
 * Pattern: tests/server/**\/*.test.(ts|js)
 *
 * These tests validate the CORS middleware behavior:
 * - Allowed origin reflection
 * - Disallowed origin rejection without 500
 * - Origin: "null" rejection
 * - Requests without Origin header allowed (browser same-origin / non-browser)
 * - Preflight OPTIONS handling
 * - Startup fail-closed in production when ALLOWED_ORIGINS is empty
 * - Startup rejection when ALLOWED_ORIGINS contains "*"
 */

import http from 'http';

interface TestResponse {
  status: number;
  headers: http.IncomingHttpHeaders;
}

function sendRequest(
  app: any,
  options: {
    method?: string;
    path?: string;
    headers?: Record<string, string>;
  }
): Promise<TestResponse> {
  return new Promise((resolve, reject) => {
    const server = http.createServer(app);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      const port = typeof address === 'object' && address ? address.port : 0;
      const req = http.request(
        {
          hostname: '127.0.0.1',
          port,
          path: options.path ?? '/',
          method: options.method ?? 'GET',
          headers: options.headers ?? {},
        },
        (res) => {
          res.resume();
          res.on('end', () => {
            server.close(() => {
              resolve({
                status: res.statusCode ?? 0,
                headers: res.headers,
              });
            });
          });
        }
      );
      req.on('error', (err) => {
        server.close(() => reject(err));
      });
      req.end();
    });
  });
}

// Module isolation helper: reset module cache, set env, then re-import app.
async function loadApp(allowedOrigins: string): Promise<any> {
  jest.resetModules();
  process.env.ALLOWED_ORIGINS = allowedOrigins;
  const mod = await import('../../server/src/index');
  return mod.default ?? mod;
}

const PROBE_PATH = '/';

afterEach(() => {
  delete process.env.NODE_ENV;
  delete process.env.ALLOWED_ORIGINS;
});

// ---------------------------------------------------------------------------
// 1. Allowed origin
// ---------------------------------------------------------------------------
describe('CORS – allowed origin', () => {
  it('reflects the exact whitelisted origin in Access-Control-Allow-Origin', async () => {
    const app = await loadApp('http://localhost:5173');
    const res = await sendRequest(app, {
      path: PROBE_PATH,
      headers: { Origin: 'http://localhost:5173' },
    });
    expect(res.headers['access-control-allow-origin']).toBe('http://localhost:5173');
    expect(res.status).toBe(200);
  });

  it('accepts the correct origin when multiple are configured', async () => {
    const app = await loadApp('http://localhost:5173,http://localhost:3000');
    const res = await sendRequest(app, {
      path: PROBE_PATH,
      headers: { Origin: 'http://localhost:3000' },
    });
    expect(res.headers['access-control-allow-origin']).toBe('http://localhost:3000');
  });
});

// ---------------------------------------------------------------------------
// 2. Rejected origin
// ---------------------------------------------------------------------------
describe('CORS – rejected origin', () => {
  it('does NOT set Access-Control-Allow-Origin for an unlisted origin', async () => {
    const app = await loadApp('http://localhost:5173');
    const res = await sendRequest(app, {
      path: PROBE_PATH,
      headers: { Origin: 'http://evil.example.com' },
    });
    expect(res.headers['access-control-allow-origin']).toBeUndefined();
  });

  it('returns 200 (not 500) for a rejected origin — server-side succeeds, browser blocks CORS', async () => {
    const app = await loadApp('http://localhost:5173');
    const res = await sendRequest(app, {
      path: PROBE_PATH,
      headers: { Origin: 'http://evil.example.com' },
    });
    expect(res.status).not.toBe(500);
    expect(res.status).toBe(200);
  });
});

// ---------------------------------------------------------------------------
// 3. Origin: null
// ---------------------------------------------------------------------------
describe('CORS – Origin: null', () => {
  it('does NOT grant Access-Control-Allow-Origin for the literal string "null"', async () => {
    const app = await loadApp('http://localhost:5173');
    const res = await sendRequest(app, {
      path: PROBE_PATH,
      headers: { Origin: 'null' },
    });
    expect(res.headers['access-control-allow-origin']).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// 4. Missing Origin header (documented policy: allow, no CORS header set)
// ---------------------------------------------------------------------------
describe('CORS – missing Origin header', () => {
  it('allows the request and returns 200 when no Origin header is present', async () => {
    const app = await loadApp('http://localhost:5173');
    const res = await sendRequest(app, { path: PROBE_PATH });
    expect(res.status).toBe(200);
  });

  it('does NOT set Access-Control-Allow-Origin when no Origin header is present', async () => {
    const app = await loadApp('http://localhost:5173');
    const res = await sendRequest(app, { path: PROBE_PATH });
    expect(res.headers['access-control-allow-origin']).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// 5. Preflight
// ---------------------------------------------------------------------------
describe('CORS – preflight (OPTIONS)', () => {
  it('returns 204 with CORS headers for an allowlisted origin preflight', async () => {
    const app = await loadApp('http://localhost:5173');
    const res = await sendRequest(app, {
      method: 'OPTIONS',
      path: PROBE_PATH,
      headers: {
        Origin: 'http://localhost:5173',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type',
      },
    });
    expect(res.status).toBe(204);
    expect(res.headers['access-control-allow-origin']).toBe('http://localhost:5173');
    expect(res.headers['access-control-allow-methods']).toMatch(/POST/);
    expect(res.headers['access-control-allow-headers']).toMatch(/Content-Type/i);
  });

  it('does NOT include allow-origin in preflight for a non-allowlisted origin', async () => {
    const app = await loadApp('http://localhost:5173');
    const res = await sendRequest(app, {
      method: 'OPTIONS',
      path: PROBE_PATH,
      headers: {
        Origin: 'http://evil.example.com',
        'Access-Control-Request-Method': 'POST',
      },
    });
    expect(res.headers['access-control-allow-origin']).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// 6. Wildcard in allowlist is forbidden at startup
// ---------------------------------------------------------------------------
describe('CORS – wildcard in ALLOWED_ORIGINS is rejected at startup', () => {
  it('calls process.exit(1) when ALLOWED_ORIGINS contains "*"', async () => {
    jest.resetModules();
    process.env.ALLOWED_ORIGINS = '*';
    const mockExit = jest.spyOn(process, 'exit').mockImplementation(((code: number) => {
      throw new Error(`process.exit(${code})`);
    }) as any);

    await expect(import('../../server/src/index')).rejects.toThrow('process.exit(1)');
    mockExit.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// 7. Production fail-closed: empty allowlist must not start
// ---------------------------------------------------------------------------
describe('CORS – production fail-closed', () => {
  it('calls process.exit(1) when NODE_ENV=production and ALLOWED_ORIGINS is empty', async () => {
    jest.resetModules();
    process.env.ALLOWED_ORIGINS = '';
    process.env.NODE_ENV = 'production';
    const mockExit = jest.spyOn(process, 'exit').mockImplementation(((code: number) => {
      throw new Error(`process.exit(${code})`);
    }) as any);

    await expect(import('../../server/src/index')).rejects.toThrow('process.exit(1)');
    mockExit.mockRestore();
    delete process.env.NODE_ENV;
  });
});

// ---------------------------------------------------------------------------
// 8. No wildcard Access-Control-Allow-Origin header ever sent
// ---------------------------------------------------------------------------
describe('CORS – never sends wildcard Access-Control-Allow-Origin', () => {
  it('does not return Access-Control-Allow-Origin: * for an allowlisted origin', async () => {
    const app = await loadApp('http://localhost:5173');
    const res = await sendRequest(app, {
      path: PROBE_PATH,
      headers: { Origin: 'http://localhost:5173' },
    });
    expect(res.headers['access-control-allow-origin']).not.toBe('*');
  });
});
