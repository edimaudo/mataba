import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from 'firebase/app-check';
export const runtimeConfig = window.MATABA_CONFIG || {};
const firebaseConfig = {
    apiKey: runtimeConfig.apiKey || '', authDomain: runtimeConfig.authDomain || '',
    projectId: runtimeConfig.projectId || '', storageBucket: runtimeConfig.storageBucket || '',
    messagingSenderId: runtimeConfig.messagingSenderId || '', appId: runtimeConfig.appId || '',
};
export const firebaseConfigured = Boolean(firebaseConfig.apiKey && firebaseConfig.projectId && firebaseConfig.appId);
export const firebaseApp = firebaseConfigured ? initializeApp(firebaseConfig) : null;
export const auth = firebaseApp ? getAuth(firebaseApp) : null;
export const db = firebaseApp ? getFirestore(firebaseApp) : null;
export const storage = firebaseApp ? getStorage(firebaseApp) : null;
if (runtimeConfig.appCheckDebugToken) {
    self.FIREBASE_APPCHECK_DEBUG_TOKEN = true;
}
const siteKey = runtimeConfig.recaptchaEnterpriseSiteKey || '';
export const appCheck = firebaseApp && siteKey
    ? initializeAppCheck(firebaseApp, { provider: new ReCaptchaEnterpriseProvider(siteKey), isTokenAutoRefreshEnabled: true })
    : null;
export const appCheckConfigured = Boolean(appCheck);
