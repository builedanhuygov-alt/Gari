/**
 * GARI Unified Auth Client Adapter (frontend2/firebase-client.js)
 * 
 * Re-exports GariAuthServiceClient directly to the authoritative FastAPI backend
 * (Vercel Python Serverless + Neon PostgreSQL) while preserving backwards compatibility
 * for all frontend2 pages importing /frontend2/firebase-client.js.
 */
import { GariAuthServiceClient } from '/frontend2/auth-service-client.js';

export class GariAuthError extends Error {
    constructor(code, message, detail = null, userMessage = null) {
        super(message);
        this.name = 'GariAuthError';
        this.code = code;
        this.detail = detail;
        this.userMessage = userMessage || message;
    }
}

// Ensure singleton instance on window
const gariAuth = window.gariAuth || new GariAuthServiceClient();
window.gariAuth = gariAuth;
window.GariAuthServiceClient = GariAuthServiceClient;
window.GariAuthClient = GariAuthServiceClient;
window.GariAuthError = GariAuthError;

export { gariAuth, GariAuthServiceClient };
export default gariAuth;
