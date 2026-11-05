# Changelog

[README](README.md) · [Architecture](docs/introduction.md) · [Development](docs/DEVELOPMENT.md)

Changes follow semantic versioning. Versions 1.1.0 and 1.2.0 were developed locally from the supplied 1.0.0 sample before the initial repository publication. The first published release is 1.2.0.

## [1.3.0] - 2026-10-30

Magento client setup and monitoring dashboard. [Upgrade notes](docs/RELEASE_v1.3.0.md).

### Added

- Standard Desk page with disabled-by-default client onboarding, master/custom-field validation and setup readiness checks.
- User access controls and existing add/remove/rotate/revoke actions in one UI.
- Downloadable Postman collection and blank/private environment, exact-body HMAC script, synthetic sample customer and audited no-store credential exports.
- All-matching-row activity aggregates, outcome/daily/HTTP charts, top users and filtered paged trace/invoice tables.
- Workspace/configuration navigation, dashboard architecture/developer guide, sandbox change register and admin checklist.
- Six portable export regressions; twelve new isolated HTTP acceptance cases and generated HMAC Postman verification.

### Changed

- Dashboard-created endpoints populate invoice, item and generated tax-row cost centers using the existing handler, with automatic cost-center creation disabled.
- README distinguishes the locally tested dashboard from the deployed sandbox and production.

### Verification and limits

- 52 unit/mock tests, 12 new dashboard HTTP cases and generated Postman validation (2 requests / 4 assertions) passed locally; browser JSON downloads verified.
- Sandbox core suite: 13 requests / 33 assertions passed. Extended security controls exercised, with 21 full status/trace passes and two audited rate-limit rejections whose outgoing 429 response is rewritten by the hosting proxy.
- Dashboard deployment to sandbox, proxy response preservation, client-specific shipping and external ZATCA acceptance remain separate follow-ups.

## [1.2.0] - 2026-10-24

Central Magento administration and traceability. [Upgrade notes](docs/RELEASE_v1.2.0.md).

### Added

- Magento Integration Settings and child API-user membership, with global and per-user create/submit controls.
- Dedicated user creation/removal, encrypted native credential retrieval/rotation, access revocation, IP rules, per-user rate limits and HMAC.
- Gateway-only routing for managed users, restricted native roles and company permissions.
- Append-only Magento API Activity, correlated requests and management actions, a filtered Script Report, and workspace/form navigation.
- Postman v2.1 collection and blank environment with an actual 12-request / 34-assertion Newman run.
- Architecture and DocType diagrams, configuration and development guides, contribution/release rules and Frappe release highlights.

### Changed

- Managed users share a configuration-scoped order namespace; historical endpoint references are adopted after company/conflict checks.
- Managed activity/detail history has no automatic purge; legacy request retention remains configurable.
- Publisher metadata identifies AlphaX SAAS without retaining the sample's fake contact address.
- README distinguishes verified PowerTire behavior from inherited generic presets and links the developer documentation.
- Release source remains 1.2.0 for the initial publication; final documentation preparation does not introduce another functional version.

### Fixed

- Structured credential redaction in request/activity snapshots and no-store responses for credential retrieval.
- Correct HTTP statuses for IP/rate rejections raised during managed-user authentication hooks.
- Historical source/target checks and concurrent cross-user retries prevent duplicate invoices during central configuration adoption and normal delivery.

### Verification

- 46 unit/mock tests, 23 invoice HTTP/database tests and 25 management HTTP/database tests passed.
- 12 actual Newman requests and 34 assertions passed; Python compilation and JavaScript syntax checks passed.
- Customer deployment, customer-specific e-invoicing/workflow acceptance, browser-dialog acceptance and v16 compatibility remain pending.

## [1.1.0] - 2026-10-24

Complete-order invoice submission, developed locally before repository publication.

### Added

- Partner-authorized create-and-submit and submission of an imported Sales Invoice draft by Magento order number.
- Saved-document reconciliation before native submission, with native permissions and strict company/source validation.
- Updated complete-order pack, API guide, OpenAPI, sample and Postman requests.

### Fixed

- JSON Code-field serialization during pack import.
- Atomic reference locking, current reads and duplicate protection under concurrent delivery.

### Verification

- 46 unit/mock tests and 23 real HTTP/database tests passed, including native GL posting and concurrent retries.

## [1.0.0] - supplied sample baseline

### Added

- Inherited NeoConnect configurable gateway, mapping engine, generic presets, sample analysis and partner/endpoint DocTypes.

The source sample declared 1.0.0. Its original release date, Git history and claimed test coverage were not supplied as independently verified repository history.
