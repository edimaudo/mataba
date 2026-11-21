# Mataba 2.9.6 UI and legal reference update

## Interface
- Replaced header quick controls with a Settings navigation item. Language, text size and light/dark theme controls are available in Settings and persist in local storage.
- Removed the Contracts Library and Reference Materials navigation items and their associated views from the application flow.
- Renamed Recent Reviews to Reviews. Reviews are shown as a simple list, with a New Review action in the page header.
- Removed the reference-material selector, privacy-protection and verifiable-source side panels, Local Privacy Shield section, and Save as draft action from New Review.
- Personal-information masking starts automatically after document extraction. The sanitized content is used for processing; no separate privacy panel or manual scan button is shown.
- Removed Firebase and Python API configuration details from user-facing settings and progress copy.
- Flattened navigation, panels, buttons and review rows; removed the blue vertical active marker and elevated card treatment.

## Employment-law references
- Maintained the federal, provincial and territorial official employment-law source registry, using the supplied official links. The Alberta URL is the Employment Standards Regulation (under the Employment Standards Code). The Nova Scotia URL is stored without the supplied anti-bot tracking query.
- Added `LAWYER_DIRECTORIES` for all 13 provinces and territories, including the CBA Alberta Labour & Employment Section and Ontario referral/specialist resources.
- Added `GET /api/legal-qa/lawyer-directories` to expose the curated directory information to authenticated application clients.

## Validation
- Python test suite: 109 passed.
- Python compilation: passed.
- Native JavaScript syntax checks: passed.
- Static asset validation: passed.
- Browser UX script updated for the revised navigation and Settings controls. Browser execution remains blocked by the current environment's navigation policy (`ERR_BLOCKED_BY_ADMINISTRATOR`).
