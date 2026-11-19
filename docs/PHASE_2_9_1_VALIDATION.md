# Mataba 2.9.1 validation — legal category and pasted contract mode

## Implemented
- Legal Q&A exposes a law-type dropdown with Employment law as the only option. The FastAPI request schema rejects unsupported categories.
- Contract review offers Upload document and Paste text modes. Pasted text is converted to a local TXT File and enters the existing extraction, PII redaction, manual confirmation, source-page construction, persistence and analysis path.
- PDF and DOCX upload processing was not replaced or bypassed.

## Local checks
- Python test suite: 90 passed.
- Python compileall: passed.
- TypeScript transpile/syntax parse: 12 files, zero syntax diagnostics.
- JSON configuration validation: passed.

## Not run
- Full TypeScript type-check and production bundle: frontend dependencies are not installed in this environment.
- Playwright visual/interaction run and axe-core audit: not run.
- Live Firebase AI Logic inference and official legislation retrieval: require client Firebase configuration and network-enabled staging.

## Document extraction behavior
- PDF.js extracts selectable text per PDF page. Image-only/scanned PDFs are rejected with an OCR-not-enabled message.
- Mammoth extracts DOCX text. Explicit page breaks can be used as page boundaries; otherwise the full extracted content is retained as a section without fabricated page numbers.
- Legacy binary `.doc` files are not supported; accepted formats are PDF, DOCX and TXT.
