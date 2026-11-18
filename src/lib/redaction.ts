import type { ParsedDocument, RedactionResult } from '../types';
import { detectPiiWithNano } from './ai';
import { collectPatternMatches, maskMatchedValues } from './privacy-utils';

export async function redactDocument(
  document: ParsedDocument,
  language: 'en' | 'fr',
  manualValues: string[] = [],
  onProgress?: (message: string) => void,
  namespace = crypto.randomUUID().replace(/-/g, '').slice(0, 8).toUpperCase(),
): Promise<RedactionResult> {
  const allText = document.pages.map((page) => page.text).join('\n');
  const matches = collectPatternMatches(allText);
  const warnings: string[] = [...document.notes];
  let method: RedactionResult['method'] = 'PATTERN_ONLY';

  try {
    onProgress?.(language === 'fr' ? 'Recherche des noms et renseignements personnels sur cet appareil…' : 'Scanning names and personal identifiers on this device…');
    const detectedEntities = await detectPiiWithNano(allText, language, onProgress);
    detectedEntities.forEach((entity) => {
      if (entity.value.trim() && allText.toLocaleLowerCase().includes(entity.value.toLocaleLowerCase())) {
        matches.push({ value: entity.value, category: entity.category });
      }
    });
    method = 'GEMINI_NANO';
  } catch {
    warnings.push(language === 'fr'
      ? 'Gemini Nano n’était pas disponible. Les motifs locaux ont été masqués; vérifiez manuellement les noms et autres renseignements personnels avant de continuer.'
      : 'Gemini Nano was unavailable. Pattern-based identifiers were masked; manually check names and other personal information before continuing.');
  }

  manualValues.filter((value) => value.trim().length >= 2).forEach((value) => {
    if (allText.toLocaleLowerCase().includes(value.toLocaleLowerCase())) {
      matches.push({ value, category: 'OTHER' });
    }
  });

  const masked = maskMatchedValues(document.pages, matches, namespace);
  return { ...masked, method, warnings };
}

export function rehydrateText(text: string, tokenMap: Record<string, string>): string {
  return Object.entries(tokenMap).reduce((result, [token, original]) => result.replaceAll(token, original), text);
}
