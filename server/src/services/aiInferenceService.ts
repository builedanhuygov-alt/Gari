import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROJECT_ROOT = path.resolve(__dirname, '../../../');
const VENV_PYTHON = path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe');
const ENGINE_SCRIPT = path.join(PROJECT_ROOT, 'gari_inference_engine.py');
const INFERENCE_PORT = Number.parseInt(process.env.GARI_INFERENCE_PORT || '8766', 10);
const INFERENCE_URL = `http://127.0.0.1:${INFERENCE_PORT}`;

let pythonProcess: ChildProcess | null = null;
let isStarting = false;

// Fallback to model_inventory.json if present
let cachedInventory: any = null;

function getInventoryFromFile() {
    if (cachedInventory) return cachedInventory;
    const invPath = path.join(PROJECT_ROOT, 'model_inventory.json');
    try {
        if (fs.existsSync(invPath)) {
            const raw = fs.readFileSync(invPath, 'utf-8');
            cachedInventory = JSON.parse(raw);
            return cachedInventory;
        }
    } catch (e) {
        console.warn('⚠️ Could not load model_inventory.json:', e);
    }
    return null;
}

export async function isEngineHealthy(): Promise<boolean> {
    try {
        const fetchFn = (globalThis as any).fetch;
        if (!fetchFn) return false;
        const res = await fetchFn(`${INFERENCE_URL}/api/health`, {
            method: 'GET',
            headers: { Accept: 'application/json' },
            signal: AbortSignal.timeout(2000),
        });
        if (res.ok) {
            const data = await res.json();
            return data.status === 'healthy';
        }
    } catch {
        // Not running or timed out
    }
    return false;
}

export async function ensureEngineRunning(): Promise<boolean> {
    if (await isEngineHealthy()) {
        return true;
    }

    if (isStarting) {
        // Wait for starting instance
        for (let i = 0; i < 20; i++) {
            await new Promise(r => setTimeout(r, 500));
            if (await isEngineHealthy()) return true;
        }
        return false;
    }

    isStarting = true;
    console.log(`🤖 [Gari Inference Engine] Starting local AI inference service on port ${INFERENCE_PORT}...`);

    const pythonBin = fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : 'python';
    console.log(`   Python binary: ${pythonBin}`);
    console.log(`   Engine script: ${ENGINE_SCRIPT}`);

    try {
        pythonProcess = spawn(pythonBin, [ENGINE_SCRIPT, '--port', String(INFERENCE_PORT)], {
            cwd: PROJECT_ROOT,
            stdio: ['ignore', 'pipe', 'pipe'],
            env: { ...process.env, PYTHONUNBUFFERED: '1' },
            detached: false,
        });

        pythonProcess.stdout?.on('data', data => {
            const str = data.toString().trim();
            if (str) console.log(`   [AI Engine stdout] ${str}`);
        });

        pythonProcess.stderr?.on('data', data => {
            const str = data.toString().trim();
            if (str && !str.includes('INFO:')) {
                console.log(`   [AI Engine stderr] ${str}`);
            }
        });

        pythonProcess.on('exit', (code, signal) => {
            console.warn(`⚠️ [AI Engine] Process exited with code ${code}, signal ${signal}`);
            pythonProcess = null;
        });

        // Poll until ready
        for (let i = 0; i < 30; i++) {
            await new Promise(r => setTimeout(r, 500));
            if (await isEngineHealthy()) {
                console.log(`✅ [Gari Inference Engine] AI Inference Service is ready on ${INFERENCE_URL}`);
                isStarting = false;
                return true;
            }
        }
    } catch (err) {
        console.error('❌ [AI Engine] Failed to spawn Python process:', err);
    }

    isStarting = false;
    return false;
}

// Cleanup child process on exit
process.on('exit', () => {
    if (pythonProcess) {
        pythonProcess.kill();
    }
});
process.on('SIGINT', () => {
    if (pythonProcess) {
        pythonProcess.kill();
    }
    process.exit();
});
process.on('SIGTERM', () => {
    if (pythonProcess) {
        pythonProcess.kill();
    }
    process.exit();
});

export async function getModels(): Promise<any> {
    const running = await ensureEngineRunning();
    if (running) {
        const fetchFn = (globalThis as any).fetch;
        const res = await fetchFn(`${INFERENCE_URL}/api/models`);
        if (res.ok) {
            return await res.json();
        }
    }

    // Fallback: load discovered inventory from disk
    const inv = getInventoryFromFile();
    if (inv) {
        return {
            success: true,
            total: inv.length,
            device: 'cpu',
            cuda_available: false,
            models: inv.map((m: any) => ({
                crop_id: m.crop_id,
                crop_name: m.crop_name,
                kind: m.kind,
                arch: m.arch,
                classes_count: m.classes_count,
                classes: m.classes,
                labels: m.labels,
                weight_file: m.weight_file,
                weight_size_mb: m.weight_size_mb,
                accuracy: m.accuracy,
                is_loaded: false,
                device: 'cpu'
            }))
        };
    }

    throw new Error('Inference engine not ready and model inventory not found.');
}

export async function getModel(cropId: string): Promise<any> {
    const running = await ensureEngineRunning();
    if (running) {
        const fetchFn = (globalThis as any).fetch;
        const res = await fetchFn(`${INFERENCE_URL}/api/models/${encodeURIComponent(cropId)}`);
        if (res.ok) {
            return await res.json();
        }
        if (res.status === 404) {
            return null;
        }
    }

    const inv = getInventoryFromFile();
    if (inv) {
        const item = inv.find((m: any) => m.crop_id.toLowerCase() === cropId.toLowerCase());
        if (item) return { success: true, model: item };
    }
    return null;
}

export async function loadModel(cropId: string): Promise<any> {
    const running = await ensureEngineRunning();
    if (!running) {
        throw new Error('Inference engine failed to start.');
    }
    const fetchFn = (globalThis as any).fetch;
    const res = await fetchFn(`${INFERENCE_URL}/api/models/${encodeURIComponent(cropId)}/load`, {
        method: 'POST',
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Failed to load model' }));
        throw new Error(err.detail || 'Failed to load model');
    }
    return await res.json();
}

export async function predictWithLocalModel(imageBuffer: Buffer, cropId?: string): Promise<any> {
    const running = await ensureEngineRunning();
    if (!running) {
        throw new Error('Gari Inference Engine is not available. Please ensure Python environment is configured.');
    }

    const fetchFn = (globalThis as any).fetch;
    const FormDataCtor = (globalThis as any).FormData;
    const BlobCtor = (globalThis as any).Blob;

    if (!fetchFn || !FormDataCtor || !BlobCtor) {
        throw new Error('Modern fetch/FormData runtime is not available in Node.');
    }

    const formData = new FormDataCtor();
    const blob = new BlobCtor([imageBuffer], { type: 'image/jpeg' });
    formData.append('image', blob, 'leaf.jpg');
    if (cropId && cropId.trim() !== '') {
        formData.append('crop', cropId.trim());
    }

    const res = await fetchFn(`${INFERENCE_URL}/api/predict`, {
        method: 'POST',
        body: formData,
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Model prediction failed' }));
        const message = err.detail || err.message || 'Model prediction failed';
        const error = new Error(message);
        (error as any).statusCode = res.status;
        throw error;
    }

    return await res.json();
}

export async function getEngineHealth(): Promise<any> {
    const healthy = await isEngineHealthy();
    if (healthy) {
        const fetchFn = (globalThis as any).fetch;
        const res = await fetchFn(`${INFERENCE_URL}/api/health`);
        if (res.ok) return await res.json();
    }
    return {
        status: healthy ? 'healthy' : 'stopped',
        inference_service_port: INFERENCE_PORT,
        python_path: VENV_PYTHON,
    };
}
