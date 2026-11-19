import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist';
import mammoth from 'mammoth/mammoth.browser';
import { strFromU8, unzipSync } from 'fflate';
import type { Language, ParsedDocument } from '../types';

GlobalWorkerOptions.workerSrc = '/assets/pdf.worker.min.js';

const MAX_FILE_BYTES = 20 * 1024 * 1024;
const ALLOWED_MIME: Record<string, string[]> = {
  pdf: ['application/pdf'],
  docx: ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
  txt: ['text/plain', 'text/markdown'],
};

function message(language: Language, en: string, fr: string): string {
  return language === 'fr' ? fr : en;
}

const WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';

/** Extract only explicit Word page breaks; never infer a visual page layout. */
function extractExplicitDocxPages(buffer: ArrayBuffer): string[] | null {
  const archive = unzipSync(new Uint8Array(buffer));
  const documentXml = archive['word/document.xml'];
  if (!documentXml) return null;
  const xml = new DOMParser().parseFromString(strFromU8(documentXml), 'application/xml');
  if (xml.getElementsByTagName('parsererror').length) return null;
  const body = xml.getElementsByTagNameNS(WORD_NS, 'body')[0];
  if (!body) return null;

  const pages: string[] = [];
  let current = '';
  let explicitBreaks = 0;
  const flushPage = (): void => {
    if (current.trim()) pages.push(current.trim());
    current = '';
    explicitBreaks += 1;
  };
  const appendNode = (node: Node): void => {
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const element = node as Element;
    const local = element.localName;
    if (element.namespaceURI !== WORD_NS) return;
    if (local === 't') { current += element.textContent || ''; return; }
    if (local === 'tab') { current += ' '; return; }
    if (local === 'br' && element.getAttributeNS(WORD_NS, 'type') === 'page') {
      flushPage(); return;
    }
    if (local === 'lastRenderedPageBreak') { flushPage(); return; }
    if (local === 'pageBreakBefore') {
      if (current.trim()) flushPage();
      return;
    }
    if (local === 'cr') { current += '\n'; return; }
    for (const child of Array.from(element.childNodes)) appendNode(child);
    if (local === 'p') current += '\n';
    else if (local === 'tc') current += ' | ';
    else if (local === 'tr') current += '\n';
  };
  for (const child of Array.from(body.childNodes)) appendNode(child);
  if (!explicitBreaks) return null;
  if (current.trim()) pages.push(current.trim());
  return pages.map((page) => page.trim()).filter(Boolean);
}

export function validateDocumentFile(file: File, language: Language = 'en'): string | null {
  const extension = file.name.split('.').pop()?.toLowerCase() || '';
  if (!['pdf', 'docx', 'txt'].includes(extension)) {
    return message(language, 'Only PDF, DOCX and TXT files are supported.', 'Seuls les fichiers PDF, DOCX et TXT sont pris en charge.');
  }
  if (file.size === 0) {
    return message(language, 'The selected file is empty.', 'Le fichier sélectionné est vide.');
  }
  if (file.size > MAX_FILE_BYTES) {
    return message(language, 'The file is larger than the 20 MB upload limit.', 'Le fichier dépasse la limite de 20 Mo.');
  }
  const mime = file.type.toLowerCase();
  if (mime && mime !== 'application/octet-stream' && !ALLOWED_MIME[extension].includes(mime)) {
    return message(language, 'The file type does not match its extension.', 'Le type de fichier ne correspond pas à son extension.');
  }
  return null;
}

export async function extractDocument(file: File, language: Language = 'en'): Promise<ParsedDocument> {
  const validation = validateDocumentFile(file, language);
  if (validation) throw new Error(validation);
  const extension = file.name.split('.').pop()?.toLowerCase();

  if (extension === 'pdf') {
    try {
      const data = new Uint8Array(await file.arrayBuffer());
      const pdf = await getDocument({ data }).promise;
      const pages: ParsedDocument['pages'] = [];
      for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
        const page = await pdf.getPage(pageNumber);
        const content = await page.getTextContent();
        const text = content.items
          .map((item) => ('str' in item ? item.str : ''))
          .join(' ')
          .replace(/\s+/g, ' ')
          .trim();
        if (text) pages.push({ pageNumber, text });
      }
      if (!pages.length) {
        throw new Error(message(language,
          'No selectable text was found in this PDF. Scanned PDFs require OCR, which is not enabled in this release.',
          'Aucun texte sélectionnable n’a été trouvé dans ce PDF. Les PDF numérisés nécessitent une reconnaissance optique (OCR), qui n’est pas activée dans cette version.',
        ));
      }
      return { fileName: file.name, pages, notes: [] };
    } catch (error) {
      if (error instanceof Error && (error.message.includes('No selectable text') || error.message.includes('Aucun texte sélectionnable'))) throw error;
      throw new Error(message(language,
        'The PDF could not be read. It may be corrupted or password-protected.',
        'Le PDF n’a pas pu être lu. Il peut être endommagé ou protégé par un mot de passe.',
      ));
    }
  }

  if (extension === 'docx') {
    try {
      const arrayBuffer = await file.arrayBuffer();
      const result = await mammoth.extractRawText({ arrayBuffer });
      const raw = result.value.replace(/\r/g, '').trim();
      if (!raw) throw new Error(message(language, 'No readable text was found in this DOCX file.', 'Aucun texte lisible n’a été trouvé dans ce fichier DOCX.'));

      let pages: ParsedDocument['pages'];
      let notes: string[];
      const explicitPages = extractExplicitDocxPages(arrayBuffer);
      if (explicitPages?.length) {
        pages = explicitPages.map((text, index) => ({ pageNumber: index + 1, sectionLabel: `DOCX explicit page break ${index + 1}`, text }));
        notes = [message(language,
          'Page references use explicit page breaks stored in the DOCX. Documents without explicit page breaks cannot expose Word’s rendered pagination in a browser.',
          'Les références de page utilisent les sauts de page explicites du DOCX. Les documents sans saut explicite ne permettent pas de récupérer la pagination affichée par Word dans un navigateur.',
        )];
      } else {
        const sections = raw.split(/\n{2,}/).map((part) => part.trim()).filter(Boolean);
        pages = [{ pageNumber: null, sectionLabel: 'DOCX text (pagination unavailable)', text: sections.join('\n\n') }];
        notes = [message(language,
          'This DOCX has no explicit page-break markers. Exact excerpts are retained, but page numbers are not invented.',
          'Ce DOCX ne contient aucun marqueur explicite de saut de page. Les extraits exacts sont conservés, mais aucun numéro de page n’est inventé.',
        )];
      }
      return { fileName: file.name, pages, notes };
    } catch (error) {
      if (error instanceof Error && (error.message.includes('No readable text') || error.message.includes('Aucun texte lisible'))) throw error;
      throw new Error(message(language, 'The DOCX file could not be read.', 'Le fichier DOCX n’a pas pu être lu.'));
    }
  }

  const text = (await file.text()).replace(/\r/g, '').trim();
  if (!text) throw new Error(message(language, 'The text file is empty or unreadable.', 'Le fichier texte est vide ou illisible.'));
  return {
    fileName: file.name,
    pages: [{ pageNumber: null, sectionLabel: 'TXT text', text }],
    notes: [message(language,
      'TXT files do not contain page metadata. Citations refer to the extracted text.',
      'Les fichiers TXT ne contiennent pas de métadonnées de page. Les citations renvoient au texte extrait.',
    )],
  };
}
