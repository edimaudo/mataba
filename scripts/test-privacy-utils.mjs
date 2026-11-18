import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

const sourcePath = new URL('../src/lib/privacy-utils.ts', import.meta.url);
const source = await readFile(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  reportDiagnostics: true,
});
const errors = (compiled.diagnostics || []).filter((item) => item.category === ts.DiagnosticCategory.Error);
if (errors.length) throw new Error(ts.formatDiagnostics(errors, {
  getCanonicalFileName: (name) => name,
  getCurrentDirectory: () => process.cwd(),
  getNewLine: () => '\n',
}));

const tempDir = await mkdtemp(join(tmpdir(), 'mataba-privacy-test-'));
try {
  const compiledPath = join(tempDir, 'privacy-utils.mjs');
  await writeFile(compiledPath, compiled.outputText, 'utf8');
  const privacy = await import(pathToFileURL(compiledPath).href);

  assert.equal(privacy.isValidCanadianSinCandidate('130 692 544'), true);
  assert.equal(privacy.isValidCanadianSinCandidate('123 456 789'), false);
  assert.equal(privacy.isValidCanadianSinCandidate('130 692 54'), false);

  const sourceText = 'Employee Jane Tremblay SIN 130 692 544; email jane.tremblay@example.ca; phone 416-555-0134; salary $125,000.';
  const matches = privacy.collectPatternMatches(sourceText);
  assert.ok(matches.some((item) => item.category === 'SIN'));
  assert.ok(matches.some((item) => item.category === 'EMAIL'));
  assert.ok(matches.some((item) => item.category === 'PHONE'));
  assert.ok(matches.some((item) => item.category === 'COMPENSATION'));

  const page = { pageNumber: 1, text: sourceText };
  const contract = privacy.maskMatchedValues([page], [
    ...matches,
    { value: 'Jane Tremblay', category: 'NAME' },
  ], 'contract-a1');
  const reference = privacy.maskMatchedValues([page], [
    { value: 'Jane Tremblay', category: 'NAME' },
  ], 'reference-b2');

  assert.ok(contract.pages[0].text.includes('[CONTRACTA1_SIN_1]'));
  assert.ok(contract.pages[0].text.includes('[CONTRACTA1_EMAIL_1]'));
  assert.ok(contract.pages[0].text.includes('[CONTRACTA1_NAME_1]'));
  assert.equal(contract.tokenMap['[CONTRACTA1_SIN_1]'], '130 692 544');
  assert.notEqual(
    Object.keys(contract.tokenMap).find((key) => key.includes('_NAME_')),
    Object.keys(reference.tokenMap).find((key) => key.includes('_NAME_')),
  );
  assert.ok(!contract.pages[0].text.includes('jane.tremblay@example.ca'));
  assert.ok(!contract.pages[0].text.includes('130 692 544'));

  console.log('Mataba local privacy logic: 14 assertions passed.');
} finally {
  await rm(tempDir, { recursive: true, force: true });
}
