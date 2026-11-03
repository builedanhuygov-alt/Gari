/**
 * GARI AI LAB — CORS Verification Suite
 * Tests actual compiled server (server/dist/index.js) and CORS middleware logic.
 */

import http from 'http';
import assert from 'assert';
import { spawn } from 'child_process';
import path from 'path';

function runProcessCheck(env) {
  return new Promise((resolve) => {
    const child = spawn(
      process.execPath,
      ['server/dist/index.js'],
      {
        cwd: process.cwd(),
        env: { ...process.env, ...env },
        stdio: 'pipe',
      }
    );
    let stderr = '';
    child.stderr.on('data', (d) => { stderr += d.toString(); });
    child.on('close', (code) => {
      resolve({ code, stderr });
    });
  });
}

function makeRequest(port, options = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        hostname: '127.0.0.1',
        port,
        path: options.path ?? '/',
        method: options.method ?? 'GET',
        headers: options.headers ?? {},
      },
      (res) => {
        let body = '';
        res.on('data', (c) => { body += c; });
        res.on('end', () => {
          resolve({
            status: res.statusCode,
            headers: res.headers,
            body,
          });
        });
      }
    );
    req.on('error', reject);
    req.end();
  });
}

async function main() {
  console.log('🧪 Starting GARI AI LAB CORS Verification...\n');

  // 1. Startup Guard: Wildcard in ALLOWED_ORIGINS
  {
    const res = await runProcessCheck({ ALLOWED_ORIGINS: '*' });
    assert.strictEqual(res.code, 1, 'Should exit with code 1 when ALLOWED_ORIGINS contains "*"');
    assert.match(res.stderr, /contains "\*" which is forbidden/, 'Should report wildcard rejection in stderr');
    console.log('✅ Test 1 Passed: Wildcard "*" in ALLOWED_ORIGINS rejected at startup');
  }

  // 2. Startup Guard: NODE_ENV=production fail-closed
  {
    const res = await runProcessCheck({ NODE_ENV: 'production', ALLOWED_ORIGINS: '' });
    assert.strictEqual(res.code, 1, 'Should exit with code 1 when NODE_ENV=production and ALLOWED_ORIGINS is empty');
    assert.match(res.stderr, /Production mode detected/, 'Should report production empty allowlist rejection');
    console.log('✅ Test 2 Passed: NODE_ENV=production fail-closed when ALLOWED_ORIGINS is empty');
  }

  // 3. Startup Guard: APP_ENV=production fail-closed (prevent mismatch bypass)
  {
    const res = await runProcessCheck({ APP_ENV: 'production', NODE_ENV: '', ALLOWED_ORIGINS: '' });
    assert.strictEqual(res.code, 1, 'Should exit with code 1 when APP_ENV=production and ALLOWED_ORIGINS is empty');
    assert.match(res.stderr, /Production mode detected/, 'Should report production empty allowlist rejection via APP_ENV');
    console.log('✅ Test 3 Passed: APP_ENV=production fail-closed guard prevents variable mismatch bypass');
  }

  // 4. Live Server CORS Tests
  const TEST_PORT = 8991;
  const serverProcess = spawn(
    process.execPath,
    ['server/dist/index.js'],
    {
      cwd: process.cwd(),
      env: {
        ...process.env,
        PORT: String(TEST_PORT),
        ALLOWED_ORIGINS: 'http://localhost:5173,https://app.gari.ai',
        NODE_ENV: 'development',
      },
      stdio: 'pipe',
    }
  );

  let started = false;
  serverProcess.stdout.on('data', (d) => {
    if (d.toString().includes('Máy Chủ Gari AI Lab Đã Khởi Động')) {
      started = true;
    }
  });

  // Wait for server to start
  for (let i = 0; i < 40; i++) {
    if (started) break;
    await new Promise((r) => setTimeout(r, 250));
  }

  try {
    // 4a. Allowed Origin
    {
      const res = await makeRequest(TEST_PORT, {
        headers: { Origin: 'http://localhost:5173' },
      });
      assert.strictEqual(res.headers['access-control-allow-origin'], 'http://localhost:5173');
      assert.strictEqual(res.status, 200);
      console.log('✅ Test 4a Passed: Allowed origin reflected correctly');
    }

    // 4b. Second Allowed Origin in list
    {
      const res = await makeRequest(TEST_PORT, {
        headers: { Origin: 'https://app.gari.ai' },
      });
      assert.strictEqual(res.headers['access-control-allow-origin'], 'https://app.gari.ai');
      assert.strictEqual(res.status, 200);
      console.log('✅ Test 4b Passed: Second allowed origin in comma list reflected');
    }

    // 4c. Disallowed Origin
    {
      const res = await makeRequest(TEST_PORT, {
        headers: { Origin: 'http://evil.com' },
      });
      assert.strictEqual(res.headers['access-control-allow-origin'], undefined);
      assert.notStrictEqual(res.status, 500, 'Should not return 500 for disallowed origin');
      console.log('✅ Test 4c Passed: Disallowed origin does not get CORS header, status != 500');
    }

    // 4d. Origin: "null"
    {
      const res = await makeRequest(TEST_PORT, {
        headers: { Origin: 'null' },
      });
      assert.strictEqual(res.headers['access-control-allow-origin'], undefined);
      console.log('✅ Test 4d Passed: Literal origin "null" denied');
    }

    // 4e. Missing Origin Header
    {
      const res = await makeRequest(TEST_PORT);
      assert.strictEqual(res.status, 200);
      assert.strictEqual(res.headers['access-control-allow-origin'], undefined);
      console.log('✅ Test 4e Passed: Missing Origin allowed for same-origin/non-browser, no CORS header');
    }

    // 4f. Preflight OPTIONS for Allowed Origin
    {
      const res = await makeRequest(TEST_PORT, {
        method: 'OPTIONS',
        headers: {
          Origin: 'http://localhost:5173',
          'Access-Control-Request-Method': 'POST',
          'Access-Control-Request-Headers': 'Content-Type,Authorization',
        },
      });
      assert.strictEqual(res.status, 204);
      assert.strictEqual(res.headers['access-control-allow-origin'], 'http://localhost:5173');
      assert.match(res.headers['access-control-allow-methods'], /POST/);
      assert.match(res.headers['access-control-allow-headers'], /Content-Type/i);
      console.log('✅ Test 4f Passed: Preflight OPTIONS returns 204 with allow-origin and methods');
    }

    // 4g. Preflight OPTIONS for Disallowed Origin
    {
      const res = await makeRequest(TEST_PORT, {
        method: 'OPTIONS',
        headers: {
          Origin: 'http://evil.com',
          'Access-Control-Request-Method': 'POST',
        },
      });
      assert.strictEqual(res.headers['access-control-allow-origin'], undefined);
      console.log('✅ Test 4g Passed: Preflight OPTIONS for disallowed origin omits allow-origin');
    }

    // 4h. No Wildcard CORS header ever
    {
      const res = await makeRequest(TEST_PORT, {
        headers: { Origin: 'http://localhost:5173' },
      });
      assert.notStrictEqual(res.headers['access-control-allow-origin'], '*');
      assert.notStrictEqual(res.headers['access-control-allow-credentials'], 'true');
      console.log('✅ Test 4h Passed: Credentials false maintained, wildcard never sent');
    }

    console.log('\n🎉 ALL CORS TESTS PASSED SUCCESSFULLY!');
  } finally {
    serverProcess.kill();
  }
}

main().catch((err) => {
  console.error('❌ Verification failed:', err);
  process.exit(1);
});
