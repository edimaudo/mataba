import { getIdToken } from 'firebase/auth';
import { getToken } from 'firebase/app-check';
import { appCheck, auth, firebaseConfigured, appCheckConfigured, runtimeConfig } from './firebase.js';
export const backendApiBaseUrl = (runtimeConfig.backendApiBaseUrl || '').replace(/\/$/, '');
export function getBackendBlockReason() {
    if (!firebaseConfigured || !auth)
        return 'Configure Firebase Authentication before using cloud analysis.';
    if (!auth.currentUser)
        return 'Sign in with Firebase before using cloud analysis.';
    if (runtimeConfig.requireAppCheckForApi === true && !appCheckConfigured) {
        return 'Firebase App Check is required. Configure reCAPTCHA Enterprise in app/static/config.js.';
    }
    return null;
}
export async function callBackend(path, payload) {
    const blocked = getBackendBlockReason();
    if (blocked)
        throw new Error(blocked);
    if (!auth?.currentUser)
        throw new Error('Sign in with your Firebase account before using cloud analysis.');
    const idToken = await getIdToken(auth.currentUser, true);
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${idToken}`,
    };
    if (appCheck) {
        const appCheckToken = await getToken(appCheck, true);
        headers['X-Firebase-AppCheck'] = appCheckToken.token;
    }
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 180_000);
    try {
        const response = await fetch(`${backendApiBaseUrl}${path}`, {
            method: 'POST',
            headers,
            body: JSON.stringify(payload),
            signal: controller.signal,
        });
        const body = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(body.detail || `The Mataba API returned HTTP ${response.status}.`);
        }
        return body;
    }
    catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            throw new Error('The analysis request timed out. No report was saved. Please try again.');
        }
        throw error;
    }
    finally {
        window.clearTimeout(timeout);
    }
}
