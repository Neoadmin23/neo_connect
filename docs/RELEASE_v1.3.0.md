# NeoConnect 1.3.0 — Magento client dashboard

## Changes

- One Desk page for client onboarding, configuration/security review, user access, secret rotation/revocation, Postman delivery and request monitoring.
- New clients start disabled; setup validates company-specific masters and custom defaults, detects stale fetch references and installs the tax-row cost-center hook.
- Downloadable Postman v2.1 collection and blank/private environment. Private exports include the selected user's native API key/secret and optional HMAC secret, use no-store responses and produce secret-free audit events.
- Permission-aware charts over all matching activity, filtered paged tables and links to configuration, report, traces, request logs and invoices.
- PowerTire sandbox change register, security results and admin guidance for other clients.

## Upgrade

Deploy the release through your normal bench/Frappe Cloud app process. Run `bench --site <site> migrate`, `bench --site <site> clear-cache` and restart/reload workers/Desk as required by your hosting process. Open **Magento Integration → Client Dashboard**.

Migration adds the Desk page/navigation; it does not create API users, credentials or client configurations, and does not rewrite existing endpoint defaults. Existing setups can be opened and reviewed in the dashboard. Company and endpoint identity remain immutable. Use a separate configuration for a new client.

## Verification

- 52 portable unit/mock tests passed (46 existing plus six export regressions).
- 12 new isolated-site HTTP tests passed for dashboard permissions, onboarding, aggregation, exports and invalid-input behavior.
- Generated HMAC Postman validation passed: 2 requests, 4 assertions.
- Browser verified the page, filters, client setup controls and actual collection/private-environment downloads; downloaded JSON parsed successfully.
- Customer sandbox v1.2.0 core flow: 13 Postman requests, 33 assertions passed. Extended security: 23 distinct HTTP checks, 21 full status/trace passes, plus two correctly enforced and audited 429s whose response bodies/headers were replaced by the hosting proxy.

The dashboard release itself has not yet been deployed to the customer sandbox. See [acceptance evidence and boundaries](SANDBOX_ACCEPTANCE_2026-10-30.md), [dashboard guide](MAGENTO_DASHBOARD.md), and [development guide](DEVELOPMENT.md). v16 and external ZATCA acceptance remain unverified.
