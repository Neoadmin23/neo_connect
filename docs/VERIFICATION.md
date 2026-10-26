# PowerTire submission verification and deployment

Updated 24 October 2026, version 1.2.0. Central management is covered in [MAGENTO_CONFIGURATION.md](MAGENTO_CONFIGURATION.md): 25 additional real HTTP/database tests and the 12-request / 34-assertion Newman run passed. The client confirmed one Sales Invoice for each complete Magento order. Native invoice submission is implemented and tested locally; the customer site has not been changed.

## Verified behavior

The test site `neo-connect-api-test.local` runs Frappe 15.118.0 and ERPNext 15.119.3 against a private socket-only MariaDB database. It uses fake customers, items, a Saudi Arabia/SAR test company, a test tax template and dedicated API users. Real loopback HTTP requests exercised Frappe token authentication, native invoice controllers and GL posting. Tests did not mock the database, invoice submission or general ledger.

All 23 HTTP/database integration tests passed. They cover:

- Token authentication and anonymous rejection.
- Draft creation without a ledger posting.
- Create-and-submit, submit an existing draft, and promote a draft by retrying its original payload with `submit=1`.
- Correct `docstatus: 1` and balanced receivable, sales and tax GL entries: SAR 2,070 debit equals SAR 2,070 credit for the supplied SAR 1,800 net example.
- Identical retries returning the existing invoice without another posting; changed source under the same order number rejected.
- Both dry-run paths leaving no submission or ledger changes.
- ERP total mismatch rolling back the invoice, external reference and newly created customer/contact.
- Unknown SKUs and partial invoicing rejected.
- Denial without native submit permission or endpoint submission opt-in.
- Another API partner unable to submit the imported order; arbitrary ERPNext document identifiers rejected.
- A draft changed after import rejected before submission.
- A cancelled invoice not recreated or resubmitted.
- Shipping with a service item and cash on delivery remaining unpaid.
- Five simultaneous create-and-submit requests returning the same invoice with one balanced posting.
- Five simultaneous submit calls against one existing draft returning the same submitted invoice.
- Automatic submission through the endpoint's Document Action setting.

The separate unit/mock regression suite and Python syntax checks are recorded in [TEST_RESULTS.txt](TEST_RESULTS.txt). The real HTTP run is recorded in [HTTP_TEST_RESULTS.txt](HTTP_TEST_RESULTS.txt).

## Issues resolved during testing

The pack importer now serializes JSON Code fields before saving. Saved-document validation runs before submission, including existing drafts. Submission always checks native ERPNext permissions, regardless of a generic endpoint's insert permission setting.

Idempotency uses a no-op database UPSERT to take an exclusive reference-row lock before creating an invoice. This avoids duplicate-key lock upgrades under concurrent requests. Current locking reads prevent an earlier transaction snapshot from treating the committed target as missing. Audit logs do not revalidate an already checked target through a stale snapshot. No business-document permission or validation check is skipped for this fix.

The shared Python environment had incompatible TLS dependencies, so the isolated test process used a private cryptography overlay. The shared bench environment and existing tenant databases were not modified. The private test server was stopped after the suite.

## Deploy to customer staging

1. Back up staging. Register the reviewed source as a managed app and install it with the normal Bench workflow, or update its existing NeoConnect checkout after reconciling local changes. The candidate version is 1.2.0. No source was pushed or deployed by this task.
2. Run `bench --site <staging-site> migrate`, then clear cache and restart the relevant web/workers through the normal deployment procedure. Migration creates Magento Integration Settings, Magento API User and Magento API Activity; installs the report/workspace and dedicated roles; and adds central integration links to partner, endpoint and references. Schema changes also include API Endpoint `allow_submit` and `pre_submit_hook`, and API External Reference `payload_hash` and `reservation_token`.
3. Re-import `powertire_complete_order_invoice.json` using API Partner → Install Integration Pack. Keep the same partner and endpoint identity. The pack enables Allow Partner Submission and keeps Document Action as Save as Draft, so Magento explicitly requests `submit=1`. For automatic posting, an administrator can choose Document Action Submit.
4. Confirm Saved Document Validation Hooks is `neo_connect.handlers.powertire.reconcile_invoice`, Pre-process Hooks is `neo_connect.handlers.powertire.prepare_invoice`, and the old `reconcile_draft` post-process hook is removed. Re-importing the updated pack applies these values.
5. Keep Ignore Permissions and Process Async off. Create Magento Integration Settings for this endpoint/company and add dedicated users with the central form actions. Select create/submit capabilities, then issue credentials there. The app assigns native roles and the company restriction. Do not give Administrator or System Manager roles to integration users. Run the management and Postman acceptance cases as well as invoice tests.
6. Set the actual company, SAR selling price list, tax template, receivable and income accounts, cost center and invoice numbering. Configure a non-stock shipping item if needed. Resolve the customer's existing mandatory custom fields and customer tax identifiers through mappings/defaults. Match Magento SKUs to the correct existing items.
7. Test real client samples for every fulfillment/payment method, shipping and tax variation; repeat the draft, submission, retry, concurrent-delivery and rejection cases. Verify the client's ledger, any enabled workflows and e-invoicing/ZATCA hooks. Local tests do not establish customer-specific compliance or hook behavior.
8. Agree and implement discount allocation and a payment accounting flow before sending those cases to this endpoint. Current discounts/refunds/partial invoices are rejected; source payment data is retained without settling the ERPNext invoice. Stock posting remains disabled.
9. Issue customer credentials privately and share the [API guide](POWERTIRE_API.md), [Postman collection](powertire.postman_collection.json) and [OpenAPI contract](openapi.json). The production URLs are not activated by preparing these files.

Previously imported references without a source hash must be reconciled rather than automatically adopted. Do not change partner or endpoint IDs to bypass an existing order reference. Test compatibility on the customer's installed Frappe/ERPNext version; the real verification here used v15, not v16.

## Reproduce the local verification

The scripts used are retained under `validation/powertire_api_review` in this workspace. `test_http_integration.py` starts a loopback-only server, runs the real HTTP suite, and stops that server. It verifies the private database/site identity before any direct fixture access. Its fixture credentials are stored in a mode-0600 runtime file and are excluded from the app archive and handoff.

Run the unit suite from the app directory with the bench Python: `python -m unittest discover -s neo_connect/tests -v`. The test site's fake accounting documents are retained for inspection. Do not run its setup scripts against an existing client site.
