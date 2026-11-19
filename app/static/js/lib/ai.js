import { getAI, getGenerativeModel, GoogleAIBackend, InferenceMode, Schema } from 'firebase/ai';
import { firebaseApp } from './firebase.js';
import { callBackend } from './backend.js';
import { supportsHrReport } from '../contract-types.js';
const piiSchema = {
    type: 'object',
    properties: {
        entities: {
            type: 'array',
            items: {
                type: 'object',
                properties: {
                    value: { type: 'string' },
                    category: { type: 'string', enum: ['NAME', 'ADDRESS', 'EMAIL', 'PHONE', 'SIN', 'COMPENSATION', 'OTHER'] },
                },
                required: ['value', 'category'],
            },
        },
    },
    required: ['entities'],
};
const citationSchema = Schema.object({
    properties: {
        sourceId: Schema.string(),
        excerpt: Schema.string(),
    },
});
const qaSchema = Schema.object({
    properties: {
        answer: Schema.string(),
        citations: Schema.array({ items: citationSchema }),
    },
});
function cleanJson(raw) {
    const cleaned = raw.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
    return JSON.parse(cleaned);
}
function getOnDeviceAiService() {
    if (!firebaseApp)
        throw new Error('Firebase is not configured.');
    // This Firebase AI Logic instance is used only with InferenceMode.ONLY_ON_DEVICE.
    // GoogleAIBackend is a provider configuration required by the SDK; the ONLY_ON_DEVICE
    // mode prevents any cloud inference. All cloud model generation is handled by the
    // Python FastAPI backend through Firebase AI Logic server prompt templates.
    return getAI(firebaseApp, { backend: new GoogleAIBackend() });
}
function chunkText(text, maxLength = 5500) {
    const chunks = [];
    let remaining = text;
    while (remaining.length > maxLength) {
        let cut = remaining.lastIndexOf('\n', maxLength);
        if (cut < maxLength * 0.65)
            cut = remaining.lastIndexOf(' ', maxLength);
        if (cut < maxLength * 0.65)
            cut = maxLength;
        chunks.push(remaining.slice(0, cut));
        remaining = remaining.slice(cut);
    }
    if (remaining.trim())
        chunks.push(remaining);
    return chunks;
}
export async function detectPiiWithNano(text, language, onProgress) {
    const ai = getOnDeviceAiService();
    const model = getGenerativeModel(ai, {
        mode: InferenceMode.ONLY_ON_DEVICE,
        onDeviceParams: { promptOptions: { responseConstraint: piiSchema } },
    });
    onProgress?.(language === 'fr' ? 'Préparation du modèle de confidentialité local…' : 'Preparing the on-device privacy model…');
    await model.initializeDeviceModel((progress) => {
        onProgress?.(language === 'fr' ? `Téléchargement du modèle local : ${Math.round(progress * 100)} %` : `Downloading local privacy model: ${Math.round(progress * 100)}%`);
    });
    const chunks = chunkText(text);
    const entities = new Map();
    for (let index = 0; index < chunks.length; index += 1) {
        onProgress?.(language === 'fr' ? `Vérification de la section ${index + 1} sur ${chunks.length} sur cet appareil…` : `Checking document section ${index + 1} of ${chunks.length} on this device…`);
        const prompt = language === 'fr'
            ? `Vous êtes un détecteur de renseignements personnels. Repérez uniquement les valeurs exactes des noms de personnes, adresses, courriels, numéros de téléphone, numéros d'assurance sociale et montants précis de rémunération dans le texte. N'inventez aucune valeur. Ignorez les noms d'entreprises, les rôles génériques et les autorités publiques. Répondez selon le schéma JSON.\n\nTEXTE:\n${chunks[index]}`
            : `You are a personal-information detector. Identify only exact values for individual person names, street addresses, email addresses, phone numbers, Social Insurance Numbers, and exact compensation amounts in the text. Do not invent values. Ignore company names, generic role labels, and public authorities. Respond using the required JSON schema.\n\nTEXT:\n${chunks[index]}`;
        const result = await model.generateContent(prompt);
        if (result.response.inferenceSource !== 'ON_DEVICE') {
            throw new Error('Privacy scan did not run on-device. The source text was not approved for cloud processing.');
        }
        const parsed = cleanJson(result.response.text());
        for (const entity of parsed.entities || []) {
            if (typeof entity.value !== 'string' || !entity.value.trim())
                continue;
            const validCategories = ['NAME', 'ADDRESS', 'EMAIL', 'PHONE', 'SIN', 'COMPENSATION', 'OTHER'];
            const category = validCategories.includes(entity.category) ? entity.category : 'OTHER';
            const value = entity.value.trim();
            const key = value.toLocaleLowerCase();
            if (!entities.has(key))
                entities.set(key, { value, category });
        }
    }
    return [...entities.values()];
}
function normalizeEvidence(value) {
    return value.replace(/\s+/g, ' ').trim().toLocaleLowerCase();
}
function verifyLocalCitations(rawCitations, sourceMap) {
    const citations = [];
    for (const raw of rawCitations || []) {
        const source = sourceMap.get(raw.sourceId);
        const excerpt = String(raw.excerpt || '').trim();
        if (!source || excerpt.length < 12)
            continue;
        if (!normalizeEvidence(source.text).includes(normalizeEvidence(excerpt)))
            continue;
        citations.push({
            sourceId: source.sourceId,
            sourceType: source.sourceType,
            documentName: source.documentName,
            pageNumber: source.pageNumber,
            sectionLabel: source.sectionLabel,
            verbatimExcerpt: excerpt,
            verified: true,
        });
    }
    return citations;
}
export async function generateContractAnalysis(args) {
    if (!args.privacyConfirmed)
        throw new Error('Review the sanitized text before sending it to cloud analysis.');
    const totalLength = [...args.contractPages, ...args.referencePages].reduce((sum, page) => sum + page.text.length, 0);
    if (totalLength > 150_000)
        throw new Error('The extracted text exceeds the 150,000-character review limit. Split the document into smaller files and review them separately.');
    args.onProgress?.(args.language === 'fr'
        ? 'Analyse sécurisée via le serveur Mataba…'
        : 'Running secure analysis through the Mataba backend…');
    const report = await callBackend('/api/analyze', {
        contractType: args.contractType,
        language: args.language,
        contractPages: args.contractPages,
        referencePages: args.referencePages,
        privacyConfirmed: true,
    });
    if (report.inferenceSource !== 'IN_CLOUD') {
        throw new Error('The backend did not confirm a cloud-generated report. No report was saved.');
    }
    if (!supportsHrReport(args.contractType))
        delete report.hrReport;
    args.onProgress?.(args.language === 'fr' ? 'Analyse terminée et citations vérifiées.' : 'Analysis complete and citations verified.');
    return report;
}
export async function answerOnlineQuestion(args) {
    return callBackend('/api/follow-up', {
        question: args.question,
        language: args.language,
        pages: args.relevantPages,
    });
}
export async function answerOfflineQuestion(args) {
    const model = getGenerativeModel(getOnDeviceAiService(), {
        mode: InferenceMode.ONLY_ON_DEVICE,
        onDeviceParams: { promptOptions: { responseConstraint: qaSchema } },
    });
    args.onProgress?.(args.language === 'fr' ? 'Préparation des questions-réponses hors ligne sur cet appareil…' : 'Preparing offline Q&A on this device…');
    await model.initializeDeviceModel((progress) => {
        args.onProgress?.(args.language === 'fr' ? `Préparation du modèle local : ${Math.round(progress * 100)} %` : `Preparing local model: ${Math.round(progress * 100)}%`);
    });
    const sourceMap = new Map(args.relevantPages.map((page) => [page.sourceId, page]));
    const context = args.relevantPages.map((page) => `[${page.sourceId} | ${page.sourceType} | page ${page.pageNumber ?? 'not available'}]\n${page.text}`).join('\n\n');
    const history = (args.previousTurns || []).slice(-3).map((turn) => `Q: ${turn.question}\nA: ${turn.answer}`).join('\n');
    const prompt = args.language === 'fr'
        ? `Répondez uniquement à partir des extraits fournis. Si l'information n'y figure pas, dites-le clairement. Ne devinez pas et ne créez pas de règles juridiques. Citez les extraits exacts avec leur sourceId.\n\nCONTEXTE:\n${context}\n\nHISTORIQUE RÉCENT:\n${history}\n\nQUESTION:\n${args.question}`
        : `Answer using only the supplied excerpts. If the information is not present, say so clearly. Do not guess or create legal rules. Cite exact excerpts with their sourceId.\n\nCONTEXT:\n${context}\n\nRECENT CONVERSATION:\n${history}\n\nQUESTION:\n${args.question}`;
    const result = await model.generateContent(prompt);
    if (result.response.inferenceSource !== 'ON_DEVICE') {
        throw new Error('Offline Q&A did not run on-device. No request was sent to a cloud model.');
    }
    const raw = cleanJson(result.response.text());
    return {
        answer: String(raw.answer || ''),
        citations: verifyLocalCitations(raw.citations || [], sourceMap),
        inferenceSource: 'ON_DEVICE',
    };
}
export function makeSourcePages(pages, sourceId, documentName, sourceType) {
    return pages.map((page, index) => ({
        sourceId: `${sourceId}-${index + 1}`,
        documentName,
        sourceType,
        pageNumber: page.pageNumber,
        sectionLabel: page.sectionLabel,
        text: page.text,
    }));
}
