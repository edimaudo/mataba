/** Pure local-privacy helpers, kept separate so redaction logic can be tested without browser APIs. */
export type PiiCategory = 'NAME' | 'SIN' | 'ADDRESS' | 'EMAIL' | 'PHONE' | 'COMPENSATION' | 'OTHER';
export type PiiMatch = { value: string; category: PiiCategory };
export type TextPage = { pageNumber: number | null; sectionLabel?: string; text: string };

const PATTERNS: Array<{ category: PiiCategory; regex: RegExp }> = [
  { category: 'SIN', regex: /\b\d{3}[ -]?\d{3}[ -]?\d{3}\b/g },
  { category: 'EMAIL', regex: /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi },
  { category: 'PHONE', regex: /(?:\+?1[ .-]?)?(?:\(?[2-9]\d{2}\)?[ .-]?)\d{3}[ .-]\d{4}\b/g },
  { category: 'ADDRESS', regex: /\b\d{1,6}\s+[A-Z0-9.'-]+(?:\s+[A-Z0-9.'-]+){0,4}\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Crescent|Cres|Place|Pl|Way|Rue|Chemin|Ch|Route|Rang|Allée|Impasse|Terrasse|Montée)\b(?:,?\s*[A-Z][a-zÀ-ÿ]+(?:\s+[A-Z][a-zÀ-ÿ]+)?(?:,?\s+[A-Z]{2})?(?:\s+[A-Z]\d[A-Z]\s?\d[A-Z]\d)?)?/gi },
  { category: 'ADDRESS', regex: /\b[A-Z]\d[A-Z][ -]?\d[A-Z]\d\b/gi },
  { category: 'COMPENSATION', regex: /(?:\$\s?(?:\d{1,3}(?:,\d{3})+|\d{4,8})(?:\.\d{2})?|\b\d{2,3}(?:,\d{3})+\s?(?:CAD|per\s+(?:year|annum|hour)|\/\s?(?:year|annum|hour))\b)/gi },
];

/** Luhn check is diagnostic only; every nine-digit SIN candidate is still masked. */
export function isValidCanadianSinCandidate(value: string): boolean {
  const digits = value.replace(/\D/g, '');
  if (!/^\d{9}$/.test(digits) || digits[0] === '0') return false;
  let sum = 0;
  for (let index = 0; index < 8; index += 1) {
    const product = Number(digits[index]) * (index % 2 === 1 ? 2 : 1);
    sum += Math.floor(product / 10) + (product % 10);
  }
  return (sum + Number(digits[8])) % 10 === 0;
}

export function collectPatternMatches(text: string): PiiMatch[] {
  const matches: PiiMatch[] = [];
  for (const entry of PATTERNS) {
    const regex = new RegExp(entry.regex.source, entry.regex.flags);
    for (const match of text.matchAll(regex)) {
      if (match[0].trim()) matches.push({ value: match[0], category: entry.category });
    }
  }
  return matches;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Tokenize matching values with a document namespace to prevent cross-document collisions. */
export function maskMatchedValues(
  pagesInput: TextPage[],
  matches: PiiMatch[],
  namespace: string,
): { pages: TextPage[]; tokenMap: Record<string, string>; categories: Record<string, number> } {
  const unique = new Map<string, PiiCategory>();
  for (const match of matches) {
    const normalized = match.value.trim();
    const key = normalized.toLocaleLowerCase();
    if (normalized && !unique.has(key)) unique.set(key, match.category);
  }

  const safeNamespace = namespace.replace(/[^A-Z0-9]/gi, '').slice(0, 10).toUpperCase() || 'DOC';
  const tokenMap: Record<string, string> = {};
  const counters: Record<PiiCategory, number> = {
    NAME: 0, SIN: 0, ADDRESS: 0, EMAIL: 0, PHONE: 0, COMPENSATION: 0, OTHER: 0,
  };
  const replacements: Array<{ value: string; token: string }> = [];
  for (const [key, category] of unique.entries()) {
    const original = matches.find((entry) => entry.value.trim().toLocaleLowerCase() === key)?.value.trim();
    if (!original) continue;
    counters[category] += 1;
    const token = `[${safeNamespace}_${category}_${counters[category]}]`;
    tokenMap[token] = original;
    replacements.push({ value: original, token });
  }

  replacements.sort((a, b) => b.value.length - a.value.length);
  const pages = pagesInput.map((page) => {
    let text = page.text;
    for (const replacement of replacements) {
      text = text.replace(new RegExp(escapeRegExp(replacement.value), 'gi'), replacement.token);
    }
    return { ...page, text };
  });

  const categories: Record<string, number> = {};
  for (const category of Object.keys(counters) as PiiCategory[]) {
    if (counters[category]) categories[category] = counters[category];
  }
  return { pages, tokenMap, categories };
}
