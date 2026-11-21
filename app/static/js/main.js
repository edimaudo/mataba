import { onAuthStateChanged, signInAnonymously } from 'firebase/auth';
import { auth, appCheckConfigured, firebaseConfigured } from './lib/firebase.js';
import { backendApiBaseUrl, callBackend, getBackendBlockReason } from './lib/backend.js';
import { extractDocument, validateDocumentFile } from './lib/documents.js';
import { redactDocument, rehydrateText } from './lib/redaction.js';
import { deletePiiTokenMap, loadPiiTokenMap, savePiiTokenMap } from './lib/piiVault.js';
import { answerOfflineQuestion, answerOnlineQuestion, generateContractAnalysis, makeSourcePages } from './lib/ai.js';
import { createDocumentId, deleteReference, deleteReview, listFolders, listReferences, listReviews, saveFolder, saveReference, saveReview } from './lib/repository.js';
import { translate as t, setDocumentLanguage } from './i18n.js';
import { CONTRACT_TYPES, supportsHrReport } from './contract-types.js';
const app = document.querySelector('#app');
if (!app)
    throw new Error('Mataba application root is missing.');
const defaultContractType = 'General';
const state = {
    user: null, authReady: false,
    language: (localStorage.getItem('mataba-language') === 'fr' ? 'fr' : 'en'),
    theme: (localStorage.getItem('mataba-theme') === 'dark' ? 'dark' : 'light'),
    fontSize: (['small', 'medium', 'large'].includes(localStorage.getItem('mataba-font-size') || '') ? localStorage.getItem('mataba-font-size') : 'medium'),
    section: (window.location.pathname === '/qa' ? 'legalQa' : 'recent'), mobileNavOpen: false, search: '', reviews: [], references: [], folders: [], activeReviewId: null,
    reportTab: 'lawyer', tokenMaps: {}, notice: null, showFolderForm: false, folderName: '', folderKind: 'contracts',
    draft: { inputMode: 'file', pastedText: '', file: null, parsed: null, redaction: null, manualValues: [], manualConfirmed: false, contractType: defaultContractType, language: (localStorage.getItem('mataba-language') === 'fr' ? 'fr' : 'en'), selectedReferences: [], folderId: '', busy: false, progress: '', error: '' },
    referenceDraft: { file: null, parsed: null, redaction: null, title: '', manualValues: [], manualConfirmed: false, folderId: '', busy: false, progress: '', error: '' },
    question: '', qaBusy: false, qaProgress: '', qaAnswer: null, qaHistory: [],
    legalQuestion: '', legalJurisdiction: 'ON', legalJurisdictionLevel: 'provincial', legalMunicipalityName: '', legalLawType: 'employment', legalQaBusy: false, legalQaResult: null,
};
const contractLabel = (type, lang = state.language) => {
    const map = {
        en: { 'Employment Agreement': 'Employment Agreement', 'Job Offer': 'Job Offer', 'Severance Agreement': 'Severance Agreement', 'Service/Vendor Contract': 'Service/Vendor Contract', Lease: 'Lease', General: 'General' },
        fr: { 'Employment Agreement': 'Contrat de travail', 'Job Offer': 'Offre d’emploi', 'Severance Agreement': 'Entente de départ', 'Service/Vendor Contract': 'Contrat de services/fournisseur', Lease: 'Bail', General: 'Général' },
    };
    return map[lang][type];
};
const statusLabel = (status) => t(state.language, status === 'analyzed' ? 'analyzed' : 'draft');
const hrTopicLabels = {
    en: { probation: 'Probation', termination_notice: 'Termination notice', severance: 'Severance', non_compete: 'Non-compete', non_solicit: 'Non-solicitation', ip_assignment: 'Intellectual property assignment', benefits: 'Benefits' },
    fr: { probation: 'Période de probation', termination_notice: 'Préavis de cessation d’emploi', severance: 'Indemnité de départ', non_compete: 'Non-concurrence', non_solicit: 'Non-sollicitation', ip_assignment: 'Cession de propriété intellectuelle', benefits: 'Avantages sociaux' },
};
const hrStatusLabels = {
    en: { FOUND: 'Found in submitted documents', NOT_FOUND_IN_SUBMITTED_DOCUMENTS: 'Not found in submitted documents', REQUIRES_JURISDICTIONAL_REVIEW: 'Requires jurisdictional review' },
    fr: { FOUND: 'Trouvé dans les documents soumis', NOT_FOUND_IN_SUBMITTED_DOCUMENTS: 'Non trouvé dans les documents soumis', REQUIRES_JURISDICTIONAL_REVIEW: 'Examen juridictionnel requis' },
};
const dateLabel = (stamp) => new Intl.DateTimeFormat(state.language === 'fr' ? 'fr-CA' : 'en-CA', { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(stamp));
const uid = () => crypto.randomUUID();
function localGuestIdentity() {
    let localId = '';
    try {
        localId = localStorage.getItem('mataba-local-guest-id') || '';
        if (!localId) {
            localId = crypto.randomUUID();
            localStorage.setItem('mataba-local-guest-id', localId);
        }
    }
    catch {
        localId = crypto.randomUUID();
    }
    return { uid: `local-${localId}`, email: '', displayName: 'Mataba' };
}
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char] || char));
const nl2br = (value) => esc(value).replace(/\n/g, '<br>');
const activeReview = () => state.reviews.find((review) => review.id === state.activeReviewId) || null;
const notice = (kind, text) => { state.notice = { kind, text }; render(); window.setTimeout(() => { if (state.notice?.text === text) {
    state.notice = null;
    render();
} }, 6000); };
function setPreferences() {
    document.documentElement.dataset.theme = state.theme;
    document.documentElement.dataset.fontSize = state.fontSize;
    setDocumentLanguage(state.language);
    const skipLink = document.querySelector('#skip-to-main');
    if (skipLink)
        skipLink.textContent = t(state.language, 'skipToMainContent');
    localStorage.setItem('mataba-theme', state.theme);
    localStorage.setItem('mataba-font-size', state.fontSize);
    localStorage.setItem('mataba-language', state.language);
}
function resetDraft() {
    state.draft = { inputMode: 'file', pastedText: '', file: null, parsed: null, redaction: null, manualValues: [], manualConfirmed: false, contractType: defaultContractType, language: state.language, selectedReferences: [], folderId: '', busy: false, progress: '', error: '' };
}
function resetReferenceDraft() {
    state.referenceDraft = { file: null, parsed: null, redaction: null, title: '', manualValues: [], manualConfirmed: false, folderId: '', busy: false, progress: '', error: '' };
}
async function loadUserData() {
    if (!state.user)
        return;
    const userId = state.user.uid;
    const [reviews, references, folders] = await Promise.all([listReviews(userId), listReferences(userId), listFolders(userId)]);
    if (!state.user || state.user.uid !== userId)
        return;
    state.reviews = reviews.sort((a, b) => b.updatedAt - a.updatedAt);
    const vaultResults = await Promise.allSettled(reviews.map((review) => loadPiiTokenMap(userId, review.id)));
    state.tokenMaps = {};
    let vaultUnavailable = false;
    vaultResults.forEach((result, index) => {
        if (result.status === 'fulfilled')
            state.tokenMaps[reviews[index].id] = result.value;
        else
            vaultUnavailable = true;
    });
    if (vaultUnavailable) {
        state.notice = {
            kind: 'info',
            text: state.language === 'fr'
                ? 'Certaines données de confidentialité locales ne sont pas accessibles sur cet appareil. Les rapports expurgés restent disponibles.'
                : 'Some local privacy data could not be opened on this device. Sanitized reports remain available.',
        };
    }
    state.references = references;
    state.folders = folders;
    render();
}
async function refreshData() { await loadUserData(); }
function navItem(id, label, shortIcon) {
    return `<button type="button" class="nav-item ${state.section === id && !state.activeReviewId ? 'active' : ''}" aria-current="${state.section === id && !state.activeReviewId ? 'page' : 'false'}" data-action="navigate" data-section="${id}"><span class="nav-symbol" aria-hidden="true">${shortIcon}</span><span>${t(state.language, label)}</span>${id === 'new' ? '<span class="nav-plus">+</span>' : ''}</button>`;
}
function layoutView() {
    const user = state.user;
    const isReview = Boolean(state.activeReviewId && state.section === 'recent');
    const title = isReview ? activeReview()?.title || t(state.language, 'review') : t(state.language, state.section === 'recent' ? 'recent' : state.section === 'library' ? 'library' : state.section === 'new' ? 'newReview' : state.section === 'references' ? 'references' : state.section === 'legalQa' ? 'legalQa' : 'settings');
    return `<div class="app-shell app-shell-horizontal">
      <header class="site-header"><div class="site-header-inner">
        <a class="site-brand" href="/app">mataba</a>
        <nav class="primary-nav app-primary-nav" aria-label="${state.language === 'fr' ? 'Navigation principale' : 'Main navigation'}">
          ${navItem('recent', 'recent', '')}${navItem('library', 'library', '')}${navItem('new', 'newReview', '')}${navItem('references', 'references', '')}${navItem('legalQa', 'legalQa', '')}
        </nav>
        <div class="header-controls"><button type="button" class="header-control" data-action="toggle-language">${state.language.toUpperCase()}</button><button type="button" class="header-control" data-action="navigate" data-section="settings">Aa</button><button type="button" class="header-control" data-action="toggle-theme">${state.theme === 'dark' ? (state.language === 'fr' ? 'Mode clair' : 'Light mode') : (state.language === 'fr' ? 'Mode sombre' : 'Dark mode')}</button></div>
      </div></header>
      <main class="main-area" id="main-content" tabindex="-1">
        ${state.notice ? `<div class="notice notice-${state.notice.kind}" role="status" aria-live="polite" aria-atomic="true"><span>${esc(state.notice.text)}</span><button data-action="dismiss-notice" aria-label="${t(state.language, 'close')}">×</button></div>` : ''}
        <div class="page-content"><div class="app-page-title"><h1>${esc(title)}</h1>${state.section === 'library' ? `<label class="top-search"><input data-field="search" value="${esc(state.search)}" placeholder="${t(state.language, 'search')}" aria-label="${t(state.language, 'search')}"></label>` : ''}</div>${pageView()}</div>
      </main>
    </div>`;
}
function pageView() {
    if (state.section === 'recent' && state.activeReviewId)
        return reviewDetailView();
    if (state.section === 'recent')
        return recentView();
    if (state.section === 'library')
        return libraryView();
    if (state.section === 'new')
        return newReviewView();
    if (state.section === 'references')
        return referencesView();
    if (state.section === 'legalQa')
        return legalQaView();
    return settingsView();
}
function recentView() {
    const employment = state.reviews.filter((r) => supportsHrReport(r.contractType)).length;
    return `<section class="page-heading"><div><h1>${state.language === 'fr' ? 'Bonjour' : 'Welcome back'}</h1><p>${t(state.language, 'recentIntro')}</p></div><button class="button button-primary" data-action="start-review">＋ ${t(state.language, 'startReview')}</button></section>
    <section class="stat-grid"><div class="stat-item"><span>${t(state.language, 'totalReviews')}</span><strong>${state.reviews.length}</strong></div><div class="stat-item"><span>${t(state.language, 'employmentReviews')}</span><strong>${employment}</strong></div><div class="stat-item"><span>${t(state.language, 'referencesCount')}</span><strong>${state.references.length}</strong></div></section>
    <section class="section-heading"><div><h2>${t(state.language, 'recent')}</h2><p>${t(state.language, 'recentIntro')}</p></div><button class="text-button" data-action="navigate" data-section="library">${t(state.language, 'viewAll')} →</button></section>
    ${state.reviews.length ? `<div class="review-list">${state.reviews.slice(0, 5).map(reviewRow).join('')}</div>` : `<div class="empty-state"><div class="empty-symbol">▤</div><h3>${t(state.language, 'noReviews')}</h3><p>${t(state.language, 'noReviewsText')}</p><button class="button button-primary" data-action="start-review">${t(state.language, 'startReview')}</button></div>`}`;
}
function reviewRow(review) {
    return `<article class="review-row"><button class="review-row-main" data-action="open-review" data-id="${esc(review.id)}"><span class="file-mark">PDF</span><span class="review-row-copy"><strong>${esc(review.title)}</strong><small>${contractLabel(review.contractType)} · ${dateLabel(review.updatedAt)}</small></span><span class="status-pill status-${review.status}">${statusLabel(review.status)}</span><span class="row-arrow">→</span></button><button class="icon-button row-delete" data-action="delete-review" data-id="${esc(review.id)}" aria-label="${t(state.language, 'delete')}">×</button></article>`;
}
function libraryView() {
    const q = state.search.trim().toLocaleLowerCase();
    const list = state.reviews.filter((review) => !q || review.title.toLocaleLowerCase().includes(q) || review.contractType.toLocaleLowerCase().includes(q));
    const folders = state.folders.filter((folder) => folder.kind !== 'references');
    return `<section class="page-heading"><div><h1>${t(state.language, 'library')}</h1><p>${t(state.language, 'libraryIntro')}</p></div><button class="button button-primary" data-action="start-review">＋ ${t(state.language, 'newReview')}</button></section>
    <div class="toolbar"><span class="muted">${list.length} ${state.language === 'fr' ? 'documents' : 'documents'}</span><button class="button button-secondary button-small" data-action="show-folder" data-kind="contracts">＋ ${t(state.language, 'createFolder')}</button></div>
    ${state.showFolderForm && state.folderKind !== 'references' ? folderForm() : ''}
    ${folders.length ? `<div class="folder-strip">${folders.map((folder) => `<span class="folder-chip">▱ ${esc(folder.name)}</span>`).join('')}</div>` : ''}
    ${list.length ? `<div class="review-list">${list.map(reviewRow).join('')}</div>` : `<div class="empty-state compact"><h3>${t(state.language, 'noLibrary')}</h3><p>${t(state.language, 'noReviewsText')}</p></div>`}`;
}
function folderForm() {
    return `<form class="inline-form" data-form="folder"><label class="field-label">${t(state.language, 'folderName')}<input name="folderName" required maxlength="80" value="${esc(state.folderName)}"></label><div class="form-actions compact-actions"><button class="button button-secondary button-small" type="button" data-action="hide-folder">${t(state.language, 'cancel')}</button><button class="button button-primary button-small" type="submit">${t(state.language, 'create')}</button></div></form>`;
}
function newReviewView() {
    const d = state.draft;
    const blockReason = getBackendBlockReason();
    const references = state.references;
    return `<section class="page-heading"><div><h1>${t(state.language, 'newReview')}</h1><p>${state.language === 'fr' ? 'Téléversez un contrat ou collez son texte, vérifiez les renseignements expurgés et examinez les conditions.' : 'Upload a contract or paste its text, review masked personal information and examine the terms.'}</p></div></section>
  <div class="review-form-layout"><div class="form-main">
    <section class="panel"><div class="panel-step"><span>01</span><div><h2>${t(state.language, 'uploadContract')}</h2><p>${t(state.language, 'uploadHint')}</p></div></div>
      <div class="contract-input-tabs" role="group" aria-label="${state.language === 'fr' ? 'Mode de saisie du contrat' : 'Contract input method'}"><button type="button" class="${d.inputMode === 'file' ? 'active' : ''}" data-action="contract-input-mode" data-value="file" aria-pressed="${d.inputMode === 'file'}">${state.language === 'fr' ? 'Téléverser un document' : 'Upload document'}</button><button type="button" class="${d.inputMode === 'text' ? 'active' : ''}" data-action="contract-input-mode" data-value="text" aria-pressed="${d.inputMode === 'text'}">${state.language === 'fr' ? 'Coller le texte' : 'Paste text'}</button></div>
      ${d.inputMode === 'file' ? `<label class="upload-zone ${d.file ? 'has-file' : ''}" for="contract-file"><input id="contract-file" type="file" data-file-kind="contract" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"><span class="upload-symbol">↑</span><strong>${d.file ? esc(d.file.name) : t(state.language, 'selectFile')}</strong><span>${d.file ? `${(d.file.size / 1048576).toFixed(2)} MB` : t(state.language, 'browseFiles')}</span></label>` : `<label class="field-label paste-contract-label" for="pasted-contract-text">${state.language === 'fr' ? 'Texte du contrat' : 'Contract text'}<textarea id="pasted-contract-text" data-field="pasted-contract-text" rows="12" maxlength="300000" placeholder="${state.language === 'fr' ? 'Collez le texte du contrat ici…' : 'Paste the contract text here…'}">${esc(d.pastedText)}</textarea></label><div class="form-actions compact-actions"><span class="subtle-note">${state.language === 'fr' ? 'Le texte reste dans le navigateur jusqu’à l’analyse expurgée.' : 'Text stays in the browser until you review the sanitized version.'}</span><button type="button" class="button button-secondary" data-action="prepare-pasted-contract" ${!d.pastedText.trim() || d.busy ? 'disabled' : ''}>${state.language === 'fr' ? 'Utiliser ce texte' : 'Use this text'}</button></div>`}
      ${d.parsed ? `<p class="subtle-note">${d.parsed.pages.length} ${state.language === 'fr' ? 'sections extraites' : 'sections extracted'} · ${d.parsed.pages.reduce((n, p) => n + p.text.length, 0).toLocaleString()} ${state.language === 'fr' ? 'caractères' : 'characters'}</p>` : ''}${d.parsed?.notes.map((n) => `<p class="subtle-note">${esc(n)}</p>`).join('') || ''}
      <div class="field-grid"><label class="field-label">${t(state.language, 'contractType')}<select data-field="contractType">${CONTRACT_TYPES.map((type) => `<option value="${esc(type)}" ${d.contractType === type ? 'selected' : ''}>${contractLabel(type)}</option>`).join('')}</select></label><label class="field-label">${t(state.language, 'reviewLanguage')}<select data-field="draftLanguage"><option value="en" ${d.language === 'en' ? 'selected' : ''}>English</option><option value="fr" ${d.language === 'fr' ? 'selected' : ''}>Français</option></select></label></div>
      ${state.folders.some((f) => f.kind !== 'references') ? `<label class="field-label">${t(state.language, 'folder')}<select data-field="draftFolder"><option value="">${t(state.language, 'uncategorized')}</option>${state.folders.filter((f) => f.kind !== 'references').map(f => `<option value="${esc(f.id)}" ${d.folderId === f.id ? 'selected' : ''}>${esc(f.name)}</option>`).join('')}</select></label>` : ''}
    </section>
    <section class="panel"><div class="panel-step"><span>02</span><div><h2>${t(state.language, 'selectReferences')} <small>${t(state.language, 'optional')}</small></h2><p>${t(state.language, 'chooseReferences')}</p></div></div>
      ${references.length ? `<div class="reference-select-list">${references.map((ref) => `<label class="reference-select"><input type="checkbox" data-ref-select="${esc(ref.id)}" ${d.selectedReferences.includes(ref.id) ? 'checked' : ''}><span class="mini-file">▤</span><span><strong>${esc(ref.title)}</strong><small>${ref.pages.length} ${state.language === 'fr' ? 'extraits' : 'excerpts'}</small></span></label>`).join('')}</div>` : `<p class="subtle-note">${state.language === 'fr' ? 'Aucun document de référence. Ajoutez-en dans la section Documents de référence.' : 'No reference materials yet. Add them in Reference Materials.'}</p>`}
    </section>
    <section class="panel"><div class="panel-step"><span>03</span><div><h2>${t(state.language, 'privacyShield')}</h2><p>${t(state.language, 'privacyHint')}</p></div></div>
      <div class="privacy-summary"><div class="privacy-symbol">◈</div><div><strong>${state.language === 'fr' ? 'Traitement local avant l’analyse' : 'Local processing before analysis'}</strong><p>${state.language === 'fr' ? 'Les fichiers originaux ne sont jamais téléversés. Le texte expurgé est présenté pour vérification avant toute requête infonuagique.' : 'Original files are never uploaded. Sanitized text is shown for review before any cloud request.'}</p></div></div>
      <div class="privacy-actions"><button class="button button-secondary" data-action="scan-contract" ${!d.parsed || d.busy ? 'disabled' : ''}>◈ ${t(state.language, 'runPrivacyScan')}</button>${d.redaction ? `<span class="scan-source ${d.redaction.method === 'GEMINI_NANO' ? 'scan-local' : 'scan-manual'}">${d.redaction.method === 'GEMINI_NANO' ? 'Gemini Nano · On device' : 'Pattern scan · Manual review required'}</span>` : ''}</div>
      ${d.progress ? `<div class="progress-line" role="status" aria-live="polite"><span class="spinner" aria-hidden="true"></span>${esc(d.progress)}</div>` : ''}${d.error ? `<div class="inline-error" role="alert">${esc(d.error)}</div>` : ''}
      ${d.redaction ? `<div class="redaction-counts">${Object.entries(d.redaction.categories).map(([category, count]) => `<span>${esc(category.toLowerCase())} <strong>${count}</strong></span>`).join('') || `<span>${state.language === 'fr' ? 'Aucun renseignement détecté automatiquement' : 'No identifiers detected automatically'}</span>`}</div>${d.redaction.warnings.map((w) => `<div class="inline-warning">${esc(w)}</div>`).join('')}
        <div class="manual-redaction-row"><label class="sr-only" for="manual-contract-value">${t(state.language, 'addManualRedaction')}</label><input id="manual-contract-value" aria-label="${t(state.language, 'addManualRedaction')}" placeholder="${t(state.language, 'addManualRedaction')}"><button class="button button-tertiary button-small" data-action="add-manual-contract">＋ ${t(state.language, 'add')}</button></div>
        ${d.manualValues.length ? `<div class="manual-value-list">${d.manualValues.map((v, i) => `<span>${esc(v)} <button data-action="remove-manual-contract" data-index="${i}" aria-label="${t(state.language, 'remove')}">×</button></span>`).join('')}</div>` : ''}
        <div class="text-preview-grid"><div class="text-preview"><div class="preview-title">${t(state.language, 'originalText')}<span>${state.language === 'fr' ? 'Non transmis' : 'Not transmitted'}</span></div><pre>${esc(d.parsed?.pages.map(p => p.text).join('\n\n').slice(0, 5000) || '')}</pre></div><div class="text-preview sanitized"><div class="preview-title">${t(state.language, 'sanitizedText')}<span>${state.language === 'fr' ? 'À vérifier' : 'Review before sending'}</span></div><pre>${esc(d.redaction.pages.map(p => p.text).join('\n\n').slice(0, 5000))}</pre></div></div>
        <label class="confirm-row"><input type="checkbox" data-field="manual-confirm" ${d.manualConfirmed ? 'checked' : ''}><span>${t(state.language, 'manualCheck')}</span></label>` : `<p class="subtle-note">${t(state.language, 'manualReviewNeeded')}</p>`}
    </section>
    ${blockReason ? `<div class="inline-warning region-warning"><strong>${t(state.language, 'regionalNotice')}</strong><span>${esc(blockReason)}</span></div>` : ''}
    <div class="form-actions"><button class="button button-secondary" data-action="save-draft" ${!d.redaction || !d.manualConfirmed || d.busy ? 'disabled' : ''}>${t(state.language, 'saveDraft')}</button><button class="button button-primary" data-action="analyze-contract" ${!d.redaction || !d.manualConfirmed || d.busy ? 'disabled' : ''}>${d.busy ? `<span class="spinner light"></span>${t(state.language, 'analyzing')}` : `${t(state.language, 'analyzeContract')} →`}</button></div>
  </div><aside class="review-aside"><div class="aside-card aside-privacy"><div class="aside-card-icon">◈</div><h3>${state.language === 'fr' ? 'Protection des données' : 'Privacy protection'}</h3><ul><li>${state.language === 'fr' ? 'Extraction dans le navigateur' : 'Extraction in the browser'}</li><li>${state.language === 'fr' ? 'Masquage local des renseignements personnels' : 'Personal information masked locally'}</li><li>${state.language === 'fr' ? 'Texte expurgé seulement pour l’IA' : 'Sanitized text only for AI'}</li><li>${state.language === 'fr' ? 'Aucune cote de risque' : 'No risk score'}</li></ul></div><div class="aside-card"><div class="aside-card-icon amber">▤</div><h3>${state.language === 'fr' ? 'Sources vérifiables' : 'Verifiable sources'}</h3><p>${state.language === 'fr' ? 'Chaque constat doit être lié à un extrait exact du contrat ou d’un document de référence.' : 'Each finding must link to an exact excerpt from the contract or reference material.'}</p></div>${supportsHrReport(d.contractType) ? `<div class="aside-card"><div class="aside-card-icon violet">H</div><h3>${t(state.language, 'hrReport')}</h3><p>${state.language === 'fr' ? 'Ce type de contrat active aussi le rapport RH.' : 'This contract type also enables the HR report.'}</p></div>` : ''}</aside></div>`;
}
function referencesView() {
    const d = state.referenceDraft;
    return `<section class="page-heading"><div><h1>${t(state.language, 'references')}</h1><p>${t(state.language, 'referenceIntro')}</p></div><button class="button button-secondary" data-action="show-folder" data-kind="references">＋ ${t(state.language, 'createFolder')}</button></section>
    ${state.showFolderForm && state.folderKind === 'references' ? folderForm() : ''}
    <section class="panel reference-upload-panel"><h2>${t(state.language, 'addReference')}</h2><form data-form="reference"><div class="field-grid"><label class="field-label">${t(state.language, 'title')}<input name="referenceTitle" maxlength="100" required value="${esc(d.title)}"></label><label class="field-label">${t(state.language, 'folder')}<select name="referenceFolder" data-field="reference-folder"><option value="">${t(state.language, 'uncategorized')}</option>${state.folders.filter(f => f.kind !== 'contracts').map(f => `<option value="${esc(f.id)}" ${d.folderId === f.id ? 'selected' : ''}>${esc(f.name)}</option>`).join('')}</select></label></div><label class="upload-zone compact-upload ${d.file ? 'has-file' : ''}" for="reference-file"><input id="reference-file" type="file" data-file-kind="reference" accept=".pdf,.docx,.txt"><strong>${d.file ? esc(d.file.name) : t(state.language, 'selectFile')}</strong><span>${t(state.language, 'uploadHint')}</span></label><div class="privacy-actions"><button class="button button-secondary" type="button" data-action="scan-reference" ${!d.parsed || d.busy ? 'disabled' : ''}>${t(state.language, 'runPrivacyScan')}</button>${d.redaction ? `<span class="scan-source">${d.redaction.method === 'GEMINI_NANO' ? 'Gemini Nano · On device' : 'Pattern scan · Manual review required'}</span>` : ''}</div>${d.progress ? `<div class="progress-line">${esc(d.progress)}</div>` : ''}${d.error ? `<div class="inline-error" role="alert">${esc(d.error)}</div>` : ''}${d.redaction ? `<div class="text-preview sanitized"><div class="preview-title">${t(state.language, 'sanitizedText')}</div><pre>${esc(d.redaction.pages.map(p => p.text).join('\n\n').slice(0, 3500))}</pre></div><div class="manual-redaction-row"><label class="sr-only" for="manual-reference-value">${t(state.language, 'addManualRedaction')}</label><input id="manual-reference-value" aria-label="${t(state.language, 'addManualRedaction')}" placeholder="${t(state.language, 'addManualRedaction')}"><button class="button button-tertiary button-small" type="button" data-action="add-manual-reference">${t(state.language, 'add')}</button></div><label class="confirm-row"><input type="checkbox" data-field="reference-manual-confirm" ${d.manualConfirmed ? 'checked' : ''}><span>${t(state.language, 'manualCheck')}</span></label>` : ''}<button class="button button-primary" type="submit" ${!d.redaction || !d.manualConfirmed || d.busy ? 'disabled' : ''}>${t(state.language, 'saveReference')}</button></form></section>
    <section class="section-heading"><div><h2>${state.language === 'fr' ? 'Documents enregistrés' : 'Saved reference materials'}</h2></div><span class="muted">${state.references.length}</span></section>
    ${state.references.length ? `<div class="reference-cards">${state.references.map((ref) => `<article class="reference-card"><span class="file-mark amber-mark">REF</span><div class="reference-card-copy"><strong>${esc(ref.title)}</strong><small>${ref.pages.length} ${state.language === 'fr' ? 'extraits' : 'excerpts'} · ${dateLabel(ref.createdAt)}</small></div><button class="icon-button" data-action="delete-reference" data-id="${esc(ref.id)}" aria-label="${t(state.language, 'delete')}">×</button></article>`).join('')}</div>` : `<div class="empty-state compact"><h3>${t(state.language, 'noReferences')}</h3></div>`}`;
}
function settingsView() {
    const blocked = getBackendBlockReason();
    return `<section class="page-heading"><div><h1>${t(state.language, 'settings')}</h1><p>${state.language === 'fr' ? 'Préférences d’affichage et langue.' : 'Display preferences and language.'}</p></div></section>
    <section class="settings-section"><div class="settings-copy"><h2>${t(state.language, 'appearance')}</h2><p>${state.language === 'fr' ? 'Choisissez le thème et la taille du texte.' : 'Choose your display theme and text size.'}</p></div><div class="settings-controls"><div class="setting-row"><span>${t(state.language, 'appearance')}</span><div class="segmented-control" role="group" aria-label="${t(state.language, 'appearance')}"><button type="button" aria-pressed="${state.theme === 'light'}" data-action="set-theme" data-value="light" class="${state.theme === 'light' ? 'selected' : ''}">${t(state.language, 'light')}</button><button type="button" aria-pressed="${state.theme === 'dark'}" data-action="set-theme" data-value="dark" class="${state.theme === 'dark' ? 'selected' : ''}">${t(state.language, 'dark')}</button></div></div><div class="setting-row"><span>${t(state.language, 'fontSize')}</span><div class="segmented-control" role="group" aria-label="${t(state.language, 'fontSize')}"><button type="button" aria-pressed="${state.fontSize === 'small'}" data-action="set-font" data-value="small" class="${state.fontSize === 'small' ? 'selected' : ''}">${t(state.language, 'small')}</button><button type="button" aria-pressed="${state.fontSize === 'medium'}" data-action="set-font" data-value="medium" class="${state.fontSize === 'medium' ? 'selected' : ''}">${t(state.language, 'medium')}</button><button type="button" aria-pressed="${state.fontSize === 'large'}" data-action="set-font" data-value="large" class="${state.fontSize === 'large' ? 'selected' : ''}">${t(state.language, 'large')}</button></div></div><div class="setting-row"><span>${state.language === 'fr' ? 'Langue' : 'Language'}</span><div class="segmented-control" role="group" aria-label="${state.language === 'fr' ? 'Langue' : 'Language'}"><button type="button" aria-pressed="${state.language === 'en'}" data-action="set-language" data-value="en" class="${state.language === 'en' ? 'selected' : ''}">English</button><button type="button" aria-pressed="${state.language === 'fr'}" data-action="set-language" data-value="fr" class="${state.language === 'fr' ? 'selected' : ''}">Français</button></div></div></div></section>
    <section class="settings-section"><div class="settings-copy"><h2>${state.language === 'fr' ? 'Traitement et résidence des données' : 'AI processing and data residency'}</h2><p>${state.language === 'fr' ? 'L’état de configuration de l’IA et de la protection de l’application.' : 'AI and application-protection configuration status.'}</p></div><div class="settings-controls"><div class="config-status"><span class="status-dot ${firebaseConfigured ? 'green' : 'amber'}"></span><div><strong>Firebase ${firebaseConfigured ? 'configured' : 'not configured'}</strong><small>${firebaseConfigured ? 'Guest session, Firestore and Storage SDK initialized' : 'Add web app settings in app/static/config.js'}</small></div></div><div class="config-status"><span class="status-dot ${appCheckConfigured ? 'green' : 'amber'}"></span><div><strong>App Check ${appCheckConfigured ? 'configured' : 'required'}</strong><small>${appCheckConfigured ? 'reCAPTCHA Enterprise provider initialized' : 'Set recaptchaEnterpriseSiteKey and enforce in Firebase Console'}</small></div></div><div class="config-status"><span class="status-dot amber"></span><div><strong>Python API ${backendApiBaseUrl ? 'configured' : 'not configured'}</strong><small>${esc(blocked || `API endpoint: ${backendApiBaseUrl}`)}</small></div></div></div></section>`;
}
function reportCitation(citation, tokenMap) {
    const label = citation.sourceType === 'CONTRACT' ? t(state.language, 'sourceLabelContract') : t(state.language, 'sourceLabelReference');
    const excerpt = rehydrateText(citation.verbatimExcerpt, tokenMap);
    return `<div class="citation ${citation.sourceType === 'CONTRACT' ? 'citation-contract' : 'citation-reference'}"><div class="citation-heading"><span class="source-pill ${citation.sourceType === 'CONTRACT' ? 'source-blue' : 'source-amber'}">${label}</span><span>${esc(citation.documentName)}${citation.pageNumber ? ` · ${t(state.language, 'page')} ${citation.pageNumber}` : ''}</span></div><blockquote>${esc(excerpt)}</blockquote></div>`;
}
function reviewDetailView() {
    const review = activeReview();
    if (!review) {
        state.activeReviewId = null;
        return recentView();
    }
    const a = review.analysis;
    const tokenMap = state.tokenMaps[review.id] || {};
    const tab = state.reportTab;
    const reportText = a ? (tab === 'hr' ? a.hrReport || '' : a.lawyerReport) : '';
    return `<div class="detail-heading"><button class="text-button" data-action="back-to-reviews">← ${t(state.language, 'recent')}</button><div class="detail-actions"><span class="status-pill status-${review.status}">${statusLabel(review.status)}</span><button class="button button-secondary button-small" data-action="delete-review" data-id="${esc(review.id)}">${t(state.language, 'delete')}</button></div></div>
    <section class="detail-title"><h1>${esc(review.title)}</h1><p>${dateLabel(review.updatedAt)} · ${review.pages.length} ${state.language === 'fr' ? 'extraits de source' : 'source excerpts'}</p></section>
    ${a ? `<section class="report-summary"><div><h2>${t(state.language, 'summary')}</h2><p>${nl2br(rehydrateText(a.executiveSummary, tokenMap))}</p><div class="evidence-list">${(a.executiveSummaryCitations || []).map(c => reportCitation(c, tokenMap)).join('')}</div></div></section><div class="report-tabs" role="tablist" aria-label="${t(state.language, 'report')}"><button type="button" role="tab" id="report-tab-lawyer" aria-controls="report-panel" aria-selected="${tab === 'lawyer'}" tabindex="${tab === 'lawyer' ? 0 : -1}" class="${tab === 'lawyer' ? 'active' : ''}" data-action="report-tab" data-value="lawyer">${t(state.language, 'lawyerReport')}</button>${supportsHrReport(review.contractType) && a.hrReport ? `<button type="button" role="tab" id="report-tab-hr" aria-controls="report-panel" aria-selected="${tab === 'hr'}" tabindex="${tab === 'hr' ? 0 : -1}" class="${tab === 'hr' ? 'active' : ''}" data-action="report-tab" data-value="hr">${t(state.language, 'hrReport')}</button>` : ''}</div>
      <section class="report-content" id="report-panel" role="tabpanel" tabindex="0" aria-labelledby="report-tab-${tab}"><h2>${tab === 'hr' ? t(state.language, 'hrReport') : t(state.language, 'lawyerReport')}</h2><div class="report-prose">${nl2br(rehydrateText(reportText || a.executiveSummary, tokenMap))}</div>${tab === 'lawyer' ? `<div class="evidence-list">${(a.lawyerReportCitations || []).map(c => reportCitation(c, tokenMap)).join('')}</div>` : (a.hrSections || []).map(section => `<article class="hr-topic"><div class="finding-meta">${esc(hrTopicLabels[state.language][section.topic] || section.topic)} · ${esc(hrStatusLabels[state.language][section.status] || section.status)}</div><p>${nl2br(rehydrateText(section.analysis, tokenMap))}</p>${section.practicalConsiderations ? `<p>${nl2br(rehydrateText(section.practicalConsiderations, tokenMap))}</p>` : ''}<div class="evidence-list">${(section.citations || []).map(c => reportCitation(c, tokenMap)).join('')}</div></article>`).join('')}</section>
      <section class="section-heading"><div><h2>${t(state.language, 'findings')}</h2><p>${state.language === 'fr' ? 'Constats liés aux extraits vérifiés des documents.' : 'Findings linked to verified document excerpts.'}</p></div></section>
      ${a.findings.length ? `<div class="finding-list">${a.findings.map((finding, index) => `<article class="finding"><div class="finding-index">${String(index + 1).padStart(2, '0')}</div><div class="finding-body"><div class="finding-meta">${esc(finding.category)}</div><h3>${esc(rehydrateText(finding.title, tokenMap))}</h3><p>${nl2br(rehydrateText(finding.explanation, tokenMap))}</p>${finding.practicalEffect ? `<div class="finding-sub"><strong>${state.language === 'fr' ? 'Effet pratique' : 'Practical effect'}</strong><p>${nl2br(rehydrateText(finding.practicalEffect, tokenMap))}</p></div>` : ''}${finding.negotiationConsideration ? `<div class="finding-sub"><strong>${t(state.language, 'negotiation')}</strong><p>${nl2br(rehydrateText(finding.negotiationConsideration, tokenMap))}</p></div>` : ''}${finding.suggestedWording ? `<div class="suggested-wording"><strong>${t(state.language, 'suggestedWording')}</strong><p>${nl2br(rehydrateText(finding.suggestedWording, tokenMap))}</p></div>` : ''}<div class="evidence-list">${finding.citations.length ? finding.citations.map(c => reportCitation(c, tokenMap)).join('') : `<p class="subtle-note">${t(state.language, 'noCitation')}</p>`}</div></div></article>`).join('')}</div>` : `<div class="empty-state compact"><p>${t(state.language, 'noFindings')}</p></div>`}
      ${a.obligations.length ? `<section class="detail-block"><h2>${t(state.language, 'obligations')}</h2><ul>${a.obligations.map(o => `<li>${nl2br(rehydrateText(o.text, tokenMap))}<div class="evidence-list">${o.citations.map(c => reportCitation(c, tokenMap)).join('')}</div></li>`).join('')}</ul></section>` : ''}${a.terminationOverview ? `<section class="detail-block"><h2>${t(state.language, 'termination')}</h2><p>${nl2br(rehydrateText(a.terminationOverview, tokenMap))}</p><div class="evidence-list">${(a.terminationCitations || []).map(c => reportCitation(c, tokenMap)).join('')}</div></section>` : ''}` : `<div class="empty-state compact"><h3>${t(state.language, 'draft')}</h3><p>${state.language === 'fr' ? 'Le texte expurgé est enregistré. Effectuez l’analyse lorsque le traitement infonuagique est autorisé.' : 'Sanitized text is saved. Run the analysis when cloud processing is approved.'}</p></div>`}
    <section class="qa-panel"><div><h2>${state.language === 'fr' ? 'Questions sur le contrat' : 'Contract Q&A'}</h2><p>${navigator.onLine ? (state.language === 'fr' ? 'En ligne : le texte expurgé est traité par le service Python de Mataba.' : 'Online: sanitized text is processed by the Mataba Python API.') : (state.language === 'fr' ? 'Hors ligne : Gemini Nano répond sur cet appareil lorsque disponible.' : 'Offline: Gemini Nano answers on this device when available.')}</p></div><form data-form="qa"><label class="field-label">${t(state.language, 'askQuestion')}<textarea name="question" rows="2" placeholder="${t(state.language, 'askPlaceholder')}" required>${esc(state.question)}</textarea></label><div class="form-actions"><span class="muted">${state.qaProgress ? esc(state.qaProgress) : ''}</span><button class="button button-primary" type="submit" ${state.qaBusy ? 'disabled' : ''}>${state.qaBusy ? '…' : t(state.language, 'ask')}</button></div></form>${state.qaAnswer ? `<div class="qa-answer"><p>${nl2br(rehydrateText(state.qaAnswer.answer, tokenMap))}</p>${state.qaAnswer.citations.map(c => reportCitation(c, tokenMap)).join('')}</div>` : ''}</section>`;
}
const legalJurisdictions = [
    { code: 'AB', en: 'Alberta', fr: 'Alberta' },
    { code: 'BC', en: 'British Columbia', fr: 'Colombie-Britannique' },
    { code: 'MB', en: 'Manitoba', fr: 'Manitoba' },
    { code: 'NB', en: 'New Brunswick', fr: 'Nouveau-Brunswick' },
    { code: 'NL', en: 'Newfoundland and Labrador', fr: 'Terre-Neuve-et-Labrador' },
    { code: 'NS', en: 'Nova Scotia', fr: 'Nouvelle-Écosse' },
    { code: 'NT', en: 'Northwest Territories', fr: 'Territoires du Nord-Ouest' },
    { code: 'NU', en: 'Nunavut', fr: 'Nunavut' },
    { code: 'ON', en: 'Ontario', fr: 'Ontario' },
    { code: 'PE', en: 'Prince Edward Island', fr: 'Île-du-Prince-Édouard' },
    { code: 'QC', en: 'Quebec', fr: 'Québec' },
    { code: 'SK', en: 'Saskatchewan', fr: 'Saskatchewan' },
    { code: 'YT', en: 'Yukon', fr: 'Yukon' },
];
function legalCitationView(citation) {
    const location = citation.sectionLabel || (citation.pageNumber ? `${t(state.language, 'page')} ${citation.pageNumber}` : '');
    return `<article class="legal-citation"><div class="legal-citation-head"><strong>${esc(citation.actTitle)}</strong>${location ? `<span>${esc(location)}</span>` : ''}<a href="${esc(citation.officialUrl)}" target="_blank" rel="noopener noreferrer">${t(state.language, 'legalQaSourceOpen')} ↗</a></div><blockquote>${esc(citation.verbatimExcerpt)}</blockquote></article>`;
}
function legalQaView() {
    const result = state.legalQaResult;
    const isFederal = state.legalJurisdictionLevel === 'federal';
    const isMunicipal = state.legalJurisdictionLevel === 'municipal';
    const jurisdictionField = isFederal
        ? '<input type="hidden" name="jurisdictionCode" value="CA">'
        : `<label class="field-label" for="legal-jurisdiction">${t(state.language, 'legalQaProvince')}<select id="legal-jurisdiction" name="jurisdictionCode" data-field="legalJurisdiction">${legalJurisdictions.map(item => `<option value="${item.code}" ${state.legalJurisdiction === item.code ? 'selected' : ''}>${esc(state.language === 'fr' ? item.fr : item.en)}</option>`).join('')}</select></label>`;
    const municipalField = isMunicipal
        ? `<label class="field-label" for="legal-municipality">${t(state.language, 'legalQaMunicipality')}<input id="legal-municipality" name="municipalityName" data-field="legalMunicipalityName" aria-describedby="legal-qa-municipal-note" type="text" maxlength="120" required value="${esc(state.legalMunicipalityName)}" placeholder="${t(state.language, 'legalQaMunicipalityPlaceholder')}"></label><p id="legal-qa-municipal-note" class="legal-qa-location-note">${t(state.language, 'legalQaMunicipalNote')}</p>`
        : '';
    const resultContext = result ? `<p class="legal-qa-source-context">${result.municipalityName ? `${t(state.language, 'legalQaMunicipality')}: ${esc(result.municipalityName)} · ` : ''}${t(state.language, 'legalQaSourceLevel')}: ${t(state.language, `legalQaLevel_${result.sourceLevel}`)}</p>` : '';
    return `<section class="page-heading"><div><h1>${t(state.language, 'legalQa')}</h1><p>${t(state.language, 'legalQaIntro')}</p></div></section>
    <section class="legal-qa-layout" aria-labelledby="legal-qa-form-title">
      <div class="legal-qa-form-panel">
        <h2 id="legal-qa-form-title">${state.language === 'fr' ? 'Que souhaitez-vous savoir?' : 'What would you like to know?'}</h2>
        <p class="legal-qa-intro">${t(state.language, 'legalQaScope')}</p><p class="legal-qa-privacy-note">${t(state.language, 'legalQaPrivacyNote')}</p>
        <form data-form="legal-qa" class="legal-qa-form">
          <label class="field-label" for="legal-law-type">${state.language === 'fr' ? 'Type de droit' : 'Type of law'}<select id="legal-law-type" name="lawType" data-field="legalLawType"><option value="employment" selected>${state.language === 'fr' ? 'Droit du travail' : 'Employment law'}</option></select></label>
          <label class="field-label" for="legal-jurisdiction-level">${t(state.language, 'legalQaJurisdictionLevel')}<select id="legal-jurisdiction-level" name="jurisdictionLevel" data-field="legalJurisdictionLevel"><option value="federal" ${isFederal ? 'selected' : ''}>${t(state.language, 'legalQaFederalLevel')}</option><option value="provincial" ${state.legalJurisdictionLevel === 'provincial' ? 'selected' : ''}>${t(state.language, 'legalQaProvincialLevel')}</option><option value="municipal" ${isMunicipal ? 'selected' : ''}>${t(state.language, 'legalQaMunicipalLevel')}</option></select></label>
          ${jurisdictionField}
          ${municipalField}
          <label class="field-label" for="legal-question">${t(state.language, 'legalQaQuestion')}<textarea id="legal-question" name="question" rows="5" maxlength="2000" required placeholder="${t(state.language, 'legalQaPlaceholder')}">${esc(state.legalQuestion)}</textarea></label>
          <div class="legal-qa-actions"><p class="subtle-note">${state.language === 'fr' ? 'Aucun contrat ni document à téléverser.' : 'No contract or uploaded document is required.'}</p><button class="button button-primary" type="submit" ${state.legalQaBusy ? 'disabled' : ''}>${state.legalQaBusy ? t(state.language, 'legalQaSubmitting') : t(state.language, 'legalQaSubmit')}</button></div>
        </form>
      </div>
      ${result ? `<section class="legal-qa-result" aria-live="polite" aria-labelledby="legal-qa-answer-title"><h2 id="legal-qa-answer-title" tabindex="-1">${t(state.language, 'legalQaAnswer')}</h2>${resultContext}${!result.evidenceFound ? `<p class="legal-qa-no-evidence">${t(state.language, 'legalQaNoEvidence')}</p>` : `<div class="legal-qa-answer">${nl2br(result.answer)}</div><div class="legal-qa-sources"><h3>${t(state.language, 'legalQaSources')}</h3><p class="legal-qa-act"><strong>${esc(result.actTitle)}</strong> · ${esc(result.jurisdiction)} · <a href="${esc(result.officialUrl)}" target="_blank" rel="noopener noreferrer">${t(state.language, 'legalQaSourceOpen')} ↗</a></p>${result.citations.map(legalCitationView).join('')}</div>`}<p class="legal-qa-disclaimer">${esc(result.disclaimer)}</p><p class="subtle-note">${t(state.language, 'legalQaSourceDate')}: ${esc(new Intl.DateTimeFormat(state.language === 'fr' ? 'fr-CA' : 'en-CA', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(result.sourceCheckedAt)))}</p></section>` : ''}
    </section>`;
}
function render() {
    setPreferences();
    app.innerHTML = !state.authReady ? `<div class="boot-screen"><span class="brand-mark">m</span><span>Mataba</span></div>` : layoutView();
    app.querySelectorAll('button:not([type])').forEach((button) => { button.type = 'button'; });
    document.body.style.overflow = '';
}
function focusMainHeading() {
    const heading = app.querySelector('#main-content h1');
    if (heading) {
        heading.tabIndex = -1;
        heading.focus();
    }
    else {
        app.querySelector('#main-content')?.focus();
    }
}
async function selectDocument(file, kind) {
    const lang = state.language;
    const error = validateDocumentFile(file, lang);
    if (error) {
        notice('error', error);
        return;
    }
    const draft = kind === 'contract' ? state.draft : state.referenceDraft;
    draft.file = file;
    draft.parsed = null;
    draft.redaction = null;
    draft.manualConfirmed = false;
    draft.error = '';
    draft.progress = t(lang, 'processing');
    render();
    try {
        draft.parsed = await extractDocument(file, lang);
        if (kind === 'reference' && !state.referenceDraft.title)
            state.referenceDraft.title = file.name.replace(/\.[^.]+$/, '').slice(0, 100);
        draft.progress = '';
    }
    catch (error) {
        draft.error = error instanceof Error ? error.message : t(lang, 'fileError');
        draft.progress = '';
    }
    render();
}
async function runRedaction(kind) {
    const draft = kind === 'contract' ? state.draft : state.referenceDraft;
    if (!draft.parsed)
        return;
    draft.busy = true;
    draft.error = '';
    draft.progress = state.language === 'fr' ? 'Analyse locale en cours…' : 'Local privacy scan in progress…';
    render();
    try {
        draft.redaction = await redactDocument(draft.parsed, state.language, draft.manualValues, (message) => { draft.progress = message; render(); });
        draft.manualConfirmed = false;
    }
    catch (error) {
        draft.error = error instanceof Error ? error.message : 'Privacy scan failed.';
    }
    finally {
        draft.busy = false;
        draft.progress = '';
        render();
    }
}
function safeReviewTitle(type, language) {
    const en = { 'Employment Agreement': 'Employment agreement review', 'Job Offer': 'Job offer review', 'Severance Agreement': 'Severance agreement review', 'Service/Vendor Contract': 'Service agreement review', Lease: 'Lease review', General: 'Contract review' };
    const fr = { 'Employment Agreement': 'Examen du contrat de travail', 'Job Offer': 'Examen de l’offre d’emploi', 'Severance Agreement': 'Examen de l’entente de départ', 'Service/Vendor Contract': 'Examen du contrat de services', Lease: 'Examen du bail', General: 'Examen du contrat' };
    return (language === 'fr' ? fr : en)[type];
}
async function persistReview(analyze) {
    const d = state.draft;
    if (!state.user || !d.file || !d.parsed || !d.redaction || !d.manualConfirmed) {
        d.error = t(state.language, 'manualReviewNeeded');
        render();
        return;
    }
    if (analyze && getBackendBlockReason()) {
        notice('error', getBackendBlockReason() || t(state.language, 'cloudBlocked'));
        return;
    }
    d.busy = true;
    d.progress = analyze ? t(state.language, 'analyzing') : t(state.language, 'save');
    d.error = '';
    render();
    try {
        const id = await createDocumentId();
        const contractSourceName = d.inputMode === 'text' ? 'Pasted contract text' : (d.file?.name || 'Uploaded contract');
        const contractPages = makeSourcePages(d.redaction.pages, `${id}-contract`, contractSourceName, 'CONTRACT');
        const selected = state.references.filter((ref) => d.selectedReferences.includes(ref.id));
        const referencePages = selected.flatMap((ref) => ref.pages.map((page, index) => ({ ...page, sourceId: `${id}-ref-${ref.id}-${index}`, sourceType: 'REFERENCE' })));
        const pages = [...contractPages, ...referencePages];
        let analysis;
        if (analyze) {
            analysis = await generateContractAnalysis({ contractType: d.contractType, language: d.language, contractPages, referencePages, privacyConfirmed: d.manualConfirmed, onProgress: (message) => { d.progress = message; render(); } });
        }
        const now = Date.now();
        const review = { id, userId: state.user.uid, title: safeReviewTitle(d.contractType, d.language), fileName: contractSourceName, contractType: d.contractType, folderId: d.folderId || null, language: d.language, status: analysis ? 'analyzed' : 'draft', createdAt: now, updatedAt: now, pages, analysis };
        await saveReview(review);
        const combinedTokenMap = { ...d.redaction.tokenMap };
        for (const reference of selected) {
            const referenceMap = await loadPiiTokenMap(state.user.uid, reference.id);
            Object.assign(combinedTokenMap, referenceMap);
        }
        await savePiiTokenMap(state.user.uid, review.id, combinedTokenMap);
        state.tokenMaps[review.id] = combinedTokenMap;
        await refreshData();
        state.activeReviewId = review.id;
        state.section = 'recent';
        state.reportTab = 'lawyer';
        resetDraft();
        notice('success', t(state.language, 'contractSaved'));
    }
    catch (error) {
        d.error = error instanceof Error ? error.message : 'Unable to save this review.';
    }
    finally {
        d.busy = false;
        d.progress = '';
        render();
    }
}
async function persistReference(form) {
    const d = state.referenceDraft;
    const formData = new FormData(form);
    const title = String(formData.get('referenceTitle') || d.title).trim();
    const folderId = String(formData.get('referenceFolder') || d.folderId || '');
    if (!state.user || !title || !d.file || !d.redaction || !d.manualConfirmed)
        return;
    d.busy = true;
    d.error = '';
    render();
    try {
        const id = await createDocumentId();
        const pages = makeSourcePages(d.redaction.pages, id, title, 'REFERENCE');
        const record = { id, userId: state.user.uid, title, fileName: 'Reference material', folderId: folderId || null, language: state.language, createdAt: Date.now(), pages };
        await saveReference(record);
        await savePiiTokenMap(state.user.uid, id, d.redaction.tokenMap);
        await refreshData();
        resetReferenceDraft();
        notice('success', t(state.language, 'referenceSaved'));
    }
    catch (error) {
        d.error = error instanceof Error ? error.message : 'Unable to save reference.';
    }
    finally {
        d.busy = false;
        render();
    }
}
async function createFolderFromForm(form) {
    if (!state.user)
        return;
    const name = String(new FormData(form).get('folderName') || '').trim();
    if (!name)
        return;
    const folder = { id: uid(), userId: state.user.uid, name, kind: state.folderKind, createdAt: Date.now() };
    await saveFolder(folder);
    state.folderName = '';
    state.showFolderForm = false;
    await refreshData();
    notice('success', t(state.language, 'createFolder'));
}
function relevantPagesForQuestion(question, pages) {
    const words = question.toLocaleLowerCase().split(/[^\p{L}\p{N}]+/u).filter((word) => word.length > 2);
    return pages.map((page) => ({ page, score: words.reduce((score, word) => score + (page.text.toLocaleLowerCase().includes(word) ? 1 : 0), 0) })).sort((a, b) => b.score - a.score).slice(0, 8).map((row) => row.page);
}
async function askOffline(form) {
    const review = activeReview();
    if (!review)
        return;
    const question = String(new FormData(form).get('question') || '').trim();
    if (!question)
        return;
    const online = navigator.onLine && !getBackendBlockReason();
    state.question = question;
    state.qaBusy = true;
    state.qaProgress = online
        ? (state.language === 'fr' ? 'Envoi au service Python…' : 'Sending to the Python API…')
        : (state.language === 'fr' ? 'Préparation de Gemini Nano…' : 'Preparing Gemini Nano…');
    state.qaAnswer = null;
    render();
    try {
        const relevant = relevantPagesForQuestion(question, review.pages);
        const progress = (message) => { state.qaProgress = message; render(); };
        const result = online
            ? await answerOnlineQuestion({ question, language: review.language, relevantPages: relevant })
            : await answerOfflineQuestion({ question, language: review.language, relevantPages: relevant, previousTurns: state.qaHistory, onProgress: progress });
        state.qaAnswer = { answer: result.answer, citations: result.citations };
        state.qaHistory.push({ question, answer: result.answer });
    }
    catch (error) {
        notice('error', error instanceof Error ? error.message : t(state.language, 'noOfflineModel'));
    }
    finally {
        state.qaBusy = false;
        state.qaProgress = '';
        render();
    }
}
async function handleClick(button) {
    const action = button.dataset.action;
    if (!action)
        return;
    if (action === 'toggle-language' || action === 'set-language') {
        state.language = action === 'set-language' ? button.dataset.value : state.language === 'fr' ? 'en' : 'fr';
        state.draft.language = state.language;
        render();
        app.querySelector('[data-action="toggle-language"]')?.focus();
    }
    else if (action === 'navigate') {
        const nextSection = button.dataset.section;
        if (nextSection === 'legalQa' && window.location.pathname !== '/qa')
            history.pushState({ section: 'legalQa' }, '', '/qa');
        else if (nextSection !== 'legalQa' && window.location.pathname === '/qa')
            history.pushState({ section: nextSection }, '', '/app');
        state.section = nextSection;
        state.activeReviewId = null;
        state.mobileNavOpen = false;
        state.search = '';
        render();
        focusMainHeading();
    }
    else if (action === 'start-review') {
        resetDraft();
        state.section = 'new';
        state.activeReviewId = null;
        render();
        focusMainHeading();
    }
    else if (action === 'open-review') {
        state.activeReviewId = button.dataset.id || null;
        state.section = 'recent';
        state.reportTab = 'lawyer';
        state.qaAnswer = null;
        state.question = '';
        state.qaHistory = [];
        render();
        focusMainHeading();
    }
    else if (action === 'back-to-reviews') {
        state.activeReviewId = null;
        state.section = 'recent';
        render();
        focusMainHeading();
    }
    else if (action === 'open-nav') {
        state.mobileNavOpen = true;
        render();
        app.querySelector('.sidebar-close')?.focus();
    }
    else if (action === 'close-nav') {
        state.mobileNavOpen = false;
        render();
        app.querySelector('.mobile-menu')?.focus();
    }
    else if (action === 'dismiss-notice') {
        state.notice = null;
        render();
    }
    else if (action === 'contract-input-mode') {
        state.draft.inputMode = button.dataset.value;
        state.draft.file = null;
        state.draft.parsed = null;
        state.draft.redaction = null;
        state.draft.manualValues = [];
        state.draft.manualConfirmed = false;
        state.draft.error = '';
        render();
    }
    else if (action === 'prepare-pasted-contract') {
        const text = state.draft.pastedText.trim();
        if (text.length < 30) {
            notice('error', state.language === 'fr' ? 'Collez davantage de texte du contrat.' : 'Paste more contract text before continuing.');
            return;
        }
        const file = new File([text], 'pasted-contract.txt', { type: 'text/plain' });
        await selectDocument(file, 'contract');
    }
    else if (action === 'scan-contract')
        await runRedaction('contract');
    else if (action === 'scan-reference')
        await runRedaction('reference');
    else if (action === 'add-manual-contract') {
        const input = document.querySelector('#manual-contract-value');
        const value = input?.value.trim() || '';
        if (value && !state.draft.manualValues.includes(value)) {
            state.draft.manualValues.push(value);
            state.draft.redaction = null;
            state.draft.manualConfirmed = false;
            render();
        }
    }
    else if (action === 'add-manual-reference') {
        const input = document.querySelector('#manual-reference-value');
        const value = input?.value.trim() || '';
        if (value && !state.referenceDraft.manualValues.includes(value)) {
            state.referenceDraft.manualValues.push(value);
            state.referenceDraft.redaction = null;
            state.referenceDraft.manualConfirmed = false;
            render();
        }
    }
    else if (action === 'remove-manual-contract') {
        state.draft.manualValues.splice(Number(button.dataset.index), 1);
        state.draft.redaction = null;
        state.draft.manualConfirmed = false;
        render();
    }
    else if (action === 'save-draft')
        await persistReview(false);
    else if (action === 'analyze-contract')
        await persistReview(true);
    else if (action === 'show-folder') {
        state.showFolderForm = true;
        state.folderKind = button.dataset.kind || 'contracts';
        state.folderName = '';
        render();
    }
    else if (action === 'hide-folder') {
        state.showFolderForm = false;
        render();
    }
    else if (action === 'report-tab') {
        state.reportTab = button.dataset.value;
        render();
        app.querySelector(`[data-action="report-tab"][data-value="${state.reportTab}"]`)?.focus();
    }
    else if (action === 'delete-review') {
        const id = button.dataset.id || state.activeReviewId;
        if (id && confirm(state.language === 'fr' ? 'Supprimer cet examen?' : 'Delete this review?')) {
            await deleteReview(state.user.uid, id);
            await deletePiiTokenMap(state.user.uid, id);
            delete state.tokenMaps[id];
            state.reviews = state.reviews.filter(r => r.id !== id);
            if (state.activeReviewId === id)
                state.activeReviewId = null;
            notice('success', t(state.language, 'deleted'));
            render();
        }
    }
    else if (action === 'delete-reference') {
        const id = button.dataset.id;
        if (id && confirm(state.language === 'fr' ? 'Supprimer cette référence?' : 'Delete this reference?')) {
            await deleteReference(state.user.uid, id);
            await deletePiiTokenMap(state.user.uid, id);
            state.references = state.references.filter(r => r.id !== id);
            notice('success', t(state.language, 'deleted'));
            render();
        }
    }
    else if (action === 'set-theme') {
        state.theme = button.dataset.value;
        render();
        app.querySelector(`[data-action="set-theme"][data-value="${state.theme}"]`)?.focus();
    }
    else if (action === 'set-font') {
        state.fontSize = button.dataset.value;
        render();
        app.querySelector(`[data-action="set-font"][data-value="${state.fontSize}"]`)?.focus();
    }
}
app.addEventListener('click', (event) => {
    const target = event.target;
    const button = target.closest('[data-action]');
    if (button)
        void handleClick(button).catch((error) => notice('error', error instanceof Error ? error.message : 'Action failed.'));
});
app.addEventListener('change', (event) => {
    const target = event.target;
    if (target.matches('[data-file-kind]') && target instanceof HTMLInputElement && target.files?.[0])
        void selectDocument(target.files[0], target.dataset.fileKind);
    else if (target.matches('[data-ref-select]')) {
        const id = target.dataset.refSelect;
        if (target.checked && !state.draft.selectedReferences.includes(id))
            state.draft.selectedReferences.push(id);
        else
            state.draft.selectedReferences = state.draft.selectedReferences.filter(v => v !== id);
    }
    else if (target.matches('[data-field="contractType"]')) {
        state.draft.contractType = target.value;
        render();
    }
    else if (target.matches('[data-field="draftLanguage"]')) {
        state.draft.language = target.value;
    }
    else if (target.matches('[data-field="draftFolder"]')) {
        state.draft.folderId = target.value;
    }
    else if (target.matches('[data-field="reference-folder"]')) {
        state.referenceDraft.folderId = target.value;
    }
    else if (target.matches('[data-field="legalJurisdiction"]')) {
        state.legalJurisdiction = target.value;
    }
    else if (target.matches('[data-field="legalJurisdictionLevel"]')) {
        state.legalJurisdictionLevel = target.value;
        if (state.legalJurisdictionLevel === 'federal')
            state.legalJurisdiction = 'CA';
        else if (state.legalJurisdiction === 'CA')
            state.legalJurisdiction = 'ON';
        state.legalQaResult = null;
        render();
        app.querySelector('[data-field="legalJurisdictionLevel"]')?.focus();
    }
    else if (target.matches('[data-field="legalLawType"]')) {
        state.legalLawType = 'employment';
    }
    else if (target.matches('[data-field="manual-confirm"]')) {
        state.draft.manualConfirmed = target.checked;
        render();
    }
    else if (target.matches('[data-field="reference-manual-confirm"]')) {
        state.referenceDraft.manualConfirmed = target.checked;
        render();
    }
});
app.addEventListener('input', (event) => {
    const target = event.target;
    if (target.matches('[name="referenceTitle"]'))
        state.referenceDraft.title = target.value;
    if (target.matches('[data-field="legalMunicipalityName"]'))
        state.legalMunicipalityName = target.value;
    if (target.matches('[data-field="pasted-contract-text"]')) {
        const textarea = target;
        state.draft.pastedText = textarea.value;
        if (state.draft.file?.name === 'pasted-contract.txt') {
            state.draft.file = null;
            state.draft.parsed = null;
            state.draft.redaction = null;
            state.draft.manualConfirmed = false;
            const cursor = textarea.selectionStart;
            render();
            const replacement = app.querySelector('[data-field="pasted-contract-text"]');
            replacement?.focus();
            replacement?.setSelectionRange(cursor, cursor);
        }
    }
    if (target.matches('[data-field="search"]')) {
        state.search = target.value;
        const cursor = target.selectionStart;
        render();
        const replacement = document.querySelector('[data-field="search"]');
        replacement?.focus();
        if (cursor !== null)
            replacement?.setSelectionRange(cursor, cursor);
    }
});
app.addEventListener('submit', (event) => {
    const form = event.target;
    if (!form.matches('form[data-form]'))
        return;
    event.preventDefault();
    const kind = form.dataset.form;
    if (kind === 'reference')
        void persistReference(form).catch((error) => notice('error', error instanceof Error ? error.message : 'Unable to save reference.'));
    else if (kind === 'folder')
        void createFolderFromForm(form).catch((error) => notice('error', error instanceof Error ? error.message : 'Unable to create folder.'));
    else if (kind === 'qa')
        void askOffline(form);
    else if (kind === 'legal-qa')
        void askLegalQuestion(form);
});
async function askLegalQuestion(form) {
    const data = new FormData(form);
    const question = String(data.get('question') || '').trim();
    const jurisdictionLevel = String(data.get('jurisdictionLevel') || state.legalJurisdictionLevel);
    const jurisdictionCode = String(data.get('jurisdictionCode') || (jurisdictionLevel === 'federal' ? 'CA' : state.legalJurisdiction));
    const municipalityName = String(data.get('municipalityName') || '').trim();
    if (jurisdictionLevel === 'municipal' && !municipalityName) {
        notice('error', state.language === 'fr' ? 'Indiquez la municipalité.' : 'Enter a municipality.');
        return;
    }
    if (question.length < 8) {
        notice('error', state.language === 'fr' ? 'Veuillez saisir une question plus détaillée.' : 'Enter a more specific question.');
        return;
    }
    state.legalQuestion = question;
    state.legalJurisdiction = jurisdictionCode;
    state.legalJurisdictionLevel = jurisdictionLevel;
    state.legalMunicipalityName = jurisdictionLevel === 'municipal' ? municipalityName : state.legalMunicipalityName;
    state.legalLawType = 'employment';
    state.legalQaBusy = true;
    state.legalQaResult = null;
    render();
    try {
        state.legalQaResult = await callBackend('/api/legal-qa', {
            question,
            lawType: state.legalLawType,
            jurisdictionCode,
            jurisdictionLevel: jurisdictionLevel === 'federal' ? 'federal' : jurisdictionLevel === 'municipal' ? 'municipal' : ['NT', 'NU', 'YT'].includes(jurisdictionCode) ? 'territorial' : 'provincial',
            ...(jurisdictionLevel === 'municipal' ? { municipalityName } : {}),
            language: state.language,
        });
    }
    catch (error) {
        notice('error', error instanceof Error ? error.message : t(state.language, 'legalQaUnavailable'));
    }
    finally {
        state.legalQaBusy = false;
        render();
        if (state.legalQaResult)
            app.querySelector('#legal-qa-answer-title')?.focus();
    }
}
if (auth) {
    let anonymousSignInStarted = false;
    onAuthStateChanged(auth, (firebaseUser) => {
        if (firebaseUser) {
            const priorId = state.user?.uid;
            state.user = { uid: firebaseUser.uid, email: '', displayName: 'Mataba' };
            if (priorId && priorId !== firebaseUser.uid)
                state.tokenMaps = {};
            state.authReady = true;
            render();
            void loadUserData().catch((error) => notice('error', error instanceof Error ? error.message : 'Unable to load saved data.'));
            return;
        }
        if (anonymousSignInStarted)
            return;
        anonymousSignInStarted = true;
        void signInAnonymously(auth).catch(async () => {
            state.user = localGuestIdentity();
            state.authReady = true;
            render();
            await loadUserData().catch((error) => notice('error', error instanceof Error ? error.message : 'Unable to load saved data.'));
            notice('info', state.language === 'fr'
                ? 'La session invitée sécurisée est indisponible. Les brouillons sont conservés sur cet appareil; les fonctions infonuagiques ne sont pas disponibles.'
                : 'A secure guest session is unavailable. Drafts remain on this device; cloud features are unavailable.');
        });
    });
}
else {
    state.user = localGuestIdentity();
    state.authReady = true;
    render();
    void loadUserData().catch((error) => notice('error', error instanceof Error ? error.message : 'Unable to load saved data.'));
}
document.addEventListener('keydown', (event) => {
    const tab = event.target?.closest('[role="tab"][data-action="report-tab"]');
    if (tab && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
        const tabs = [...(tab.closest('[role="tablist"]')?.querySelectorAll('[role="tab"]') || [])];
        if (tabs.length > 1) {
            event.preventDefault();
            const current = tabs.indexOf(tab);
            const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
            tabs[next].click();
        }
    }
});
window.addEventListener('popstate', () => { state.section = window.location.pathname === '/qa' ? 'legalQa' : 'recent'; state.activeReviewId = null; state.mobileNavOpen = false; render(); focusMainHeading(); });
window.addEventListener('online', () => render());
window.addEventListener('offline', () => render());
setPreferences();
render();
