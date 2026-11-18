import { initializeApp, type FirebaseApp } from 'firebase/app';
import { getAuth, type Auth } from 'firebase/auth';
import { getFirestore, type Firestore } from 'firebase/firestore';
import { getStorage, type FirebaseStorage } from 'firebase/storage';
import { initializeAppCheck, ReCaptchaEnterpriseProvider, type AppCheck } from 'firebase/app-check';

type MatabaConfig = {
  apiKey?: string; authDomain?: string; projectId?: string; storageBucket?: string;
  messagingSenderId?: string; appId?: string; recaptchaEnterpriseSiteKey?: string;
  appCheckDebugToken?: boolean;
  backendApiBaseUrl?: string; requireAppCheckForApi?: boolean;
};

declare global { interface Window { MATABA_CONFIG?: MatabaConfig } }
export const runtimeConfig = window.MATABA_CONFIG || {};
const firebaseConfig = {
  apiKey: runtimeConfig.apiKey || '', authDomain: runtimeConfig.authDomain || '',
  projectId: runtimeConfig.projectId || '', storageBucket: runtimeConfig.storageBucket || '',
  messagingSenderId: runtimeConfig.messagingSenderId || '', appId: runtimeConfig.appId || '',
};
export const firebaseConfigured = Boolean(firebaseConfig.apiKey && firebaseConfig.projectId && firebaseConfig.appId);
export const firebaseApp: FirebaseApp | null = firebaseConfigured ? initializeApp(firebaseConfig) : null;
export const auth: Auth | null = firebaseApp ? getAuth(firebaseApp) : null;
export const db: Firestore | null = firebaseApp ? getFirestore(firebaseApp) : null;
export const storage: FirebaseStorage | null = firebaseApp ? getStorage(firebaseApp) : null;

if (runtimeConfig.appCheckDebugToken) {
  (self as typeof self & { FIREBASE_APPCHECK_DEBUG_TOKEN?: boolean }).FIREBASE_APPCHECK_DEBUG_TOKEN = true;
}
const siteKey = runtimeConfig.recaptchaEnterpriseSiteKey || '';
export const appCheck: AppCheck | null = firebaseApp && siteKey
  ? initializeAppCheck(firebaseApp, { provider: new ReCaptchaEnterpriseProvider(siteKey), isTokenAutoRefreshEnabled: true })
  : null;
export const appCheckConfigured = Boolean(appCheck);
