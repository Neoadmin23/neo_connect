# PowerTire sandbox acceptance — 30 October 2026

[Dashboard guide](MAGENTO_DASHBOARD.md) · [API contract](POWERTIRE_API.md)

## Scope

Tests ran on `powertire-sandbox.alphaxerp.com`, with NeoConnect 1.2.0, Frappe/ERPNext 15.124.x. Production `powertire.alphaxerp.com` was not changed. The new v1.3.0 dashboard was implemented and checked on an isolated local ERPNext site; it still requires deployment to the sandbox. No Frappe Cloud account or hosting configuration was changed.

## Core invoice acceptance

The live Postman suite passed **13 requests, 33 assertions, zero failures**: connection, direct REST/RPC denial, unknown SKU and partial-invoice rejection, wrong endpoint, invalid secret, dry-run submission, draft creation, draft submission, same-content retry, changed-content rejection, and direct create-and-submit.

Submitted test invoices `ACC-SINV-2026-02187` and `ACC-SINV-2026-02188` are SAR 2,070 each (subtotal 1,800 + VAT 270). The first invoice's ledger was independently checked: debit 2,070 equals credits 1,800 + 270. These remain unpaid; payment metadata is informational. ZATCA status was **Not Submitted**. No stock movement or payment posting was tested.

## Extended live security acceptance

A disposable dedicated user was added with explicit approval, exercised, removed, re-added, and removed again. The original acceptance user's credentials were preserved.

| Check | Observed result |
| --- | --- |
| Add dedicated user and connection | 200; user and configuration history recorded |
| Create-only user dry run | 200, Validated; no invoice persisted |
| Create-only user attempting submit | 403 |
| Creation permission disabled | 403 |
| Configuration-wide submit disabled while user can submit | 403 |
| Entire integration disabled | 401; dedicated native users disabled |
| Credential-management route / `cmd` override | 403 |
| Rotate API secret | Previous token 401; current token 200 |
| HMAC missing / invalid | 401 / 401 |
| HMAC valid over exact raw invoice body | 200, Validated |
| IP deny range | Ping and push both 403 |
| Explicit observed source IP allow rule | Ping 200 |
| Rate limit 1/minute | First ping 200; second ping and push 429 |
| Revoke access | Token 401 |
| Remove membership | Token 401; native User and activity retained |
| Re-add same dedicated user | Removed token still 401; current token 200 |
| Final cleanup | Test membership removed again; token 401 |
| Original acceptance user after restoration | Ping 200; direct Sales Invoice REST still 403 |

There are **23 distinct extended HTTP checks**: 21 passed both expected status and trace-header assertions. The two rate rejections returned the correct 429 but failed the trace-header assertion because the hosted response was replaced with an HTML **Daily Usage Limit Reached** page. Do not call the external JSON/trace contract fully passed.

Both rate events were independently verified in Magento API Activity: ping trace `ac12v12q4h` (correlation `b98bbbf641044e4898dfb279ef6ec416`) and push trace `0c1s7jcv3m` (correlation `0b4d5d1bfaa94223938b76bd15738b71`, request log `0c1s0n850d`). Thus application rate enforcement and persisted audit passed; proxy response preservation remains a deployment follow-up. The report's HTTP 429 filter returned exactly these two rows. Earlier exploratory runs before the numeric setting actually saved are retained as evidence and are not counted as successful rate tests.

## Live-site changes made

- Installed the complete-order invoice endpoint and its three Magento Sales Invoice fields; configured synchronous processing, native permissions, one record/request, draft creation and authorized submission.
- Created **PowerTire Magento Sandbox** with dedicated gateway-only API users, native roles, company restriction and encrypted API credentials. A disabled bootstrap partner was used for pack installation.
- Repaired four stale Sales Invoice **Fetch From** references to existing Customer fields: plate number → `customer.custom_plate_number`, model → `customer.custom_model`, year → `customer.custom_year`, car details → `customer.custom_car_details`. Only references changed; fields and customer values were retained.
- Set the mandatory sandbox sales representative default to the existing option **المغسلة**. This is a test business default and must be confirmed for production.
- Selected the existing enabled non-group cost center **Power Tire - PTR** for the invoice header and items. The previously considered **Main - PTR** was disabled; no cost-center master was enabled or created.
- Appended `neo_connect.handlers.commerce.ensure_cost_center` after `prepare_invoice`, set `cost_center_default` to **Power Tire - PTR**, and set `create_cost_center=0`. This supplies tax-row cost centers after tax rows are generated.
- Used the existing **output vat 15% - PTR** tax template; created a synthetic test customer/address and the two submitted acceptance invoices above.
- Temporarily varied security-test membership, create/submit flags, integration enable/submit switches, HMAC, IP rules and rate limit. Restored enabled integration, allow-submit enabled, HMAC off, blank IP rules and **120 requests/minute**. The disposable security user's final access is removed; the main acceptance user retains its original token. Signing secrets generated during the HMAC test remain encrypted but inactive when HMAC is off.
- Retained all success, denied, failed and management trace records. Failed records include intentional negatives and the earlier configuration failures; they were not deleted to make the report appear clean.

## What administrators should expect for other clients

- Each client needs a separate configuration/endpoint and dedicated users. Confirm its company, tax template, enabled non-group cost center, existing SKUs and required custom fields before sharing credentials.
- Check stale Fetch From references after renaming Customer fields. The dashboard flags these; an admin must verify and repair the real mappings.
- Supply tax-row cost centers after charge generation. Do not rely only on invoice-header defaults or copy a disabled company default.
- Confirm sales representative and other mandatory custom defaults with that client. The dashboard validates supported custom Select/Link values and never copies PowerTire's business defaults automatically.
- Enable HMAC/IP rules only after Magento has the signing secret and stable outbound addresses. The IP recorded by the trusted hosting proxy is the relevant value. Set limits appropriate to bursts; implement 429 backoff.
- Import collection plus environment; edit the sample SKU and financial totals; run dry-run validation before write tests. Protect private environments as credentials, rotate on handoff changes and keep old tokens out of developer tooling.
- Review actual invoice docstatus, VAT, ledger and trace links. API submission does not automatically mean paid, stock-posted or ZATCA accepted.
- Deploy the dashboard release and migrate/clear cache before expecting the new page. Deployment alone does not create clients, users or credentials.

## Dashboard validation

- Existing app regression suite: 46 cases passed before adding six export regressions; final suite results recorded in release notes.
- New real local HTTP suite: 12 cases passed covering bootstrap/readiness, disabled-client creation, duplicate refusal, aggregate totals/pagination/filters, managed-user denial, private/blank bundles, no-store/audit redaction, invalid settings without mutation, saved setup/user permissions, Accounts Manager read versus write denial, date limits and synthetic exports.
- Dashboard-generated Postman validation with HMAC: 2 requests, 4 assertions, zero failures, against the isolated ERPNext site.
- Browser: page and client details rendered, setup/user controls visible, filters and chart/table populated, blank/private export flow exercised. Collection and private environment were downloaded by Edge and parsed from disk; API key, API secret and HMAC secret were present only in the private environment.
- Browser review used an explicitly approved disposable local reviewer account, separate from the sandbox. Its access is disabled at cleanup.

## Remaining acceptance boundaries

The hosted 429 response/header rewrite needs hosting review. The dashboard has not yet been deployed to the customer sandbox. Shipping charges, discounts/returns/partial invoices, multi-company customer migration, stock/payment posting, and external ZATCA transmission are not certified by these results. Cross-user/concurrent invoice deduplication has prior isolated-site coverage, not new live-site coverage in this run.
