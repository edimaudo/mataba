# Mataba 2.9.10 — New Review jurisdiction and form validation

## Changes

- Added a required Jurisdiction level selection to New Review: Federal, Province or territory, and Municipal.
- Added conditional province/territory selection and a required municipality field for municipal reviews.
- Saved the selected jurisdiction with each review and displayed it in review listings and detail headings.
- Passed jurisdiction context to the FastAPI analysis request and included it in the analysis prompt. The prompt expressly prohibits claiming that legislation was checked unless a statutory source page is actually supplied.
- Added submit-time checks for jurisdiction hierarchy, municipality name, contract type, report language, a readable source document, and completed privacy processing.
- Removed the municipal-context explanation from Legal Q&A in English and French.

## Validation

Python unit and API tests, Python compilation, JavaScript syntax checks, static-asset validation, and ZIP integrity checks are run for this release. Browser-rendered UI testing remains environment-dependent.
