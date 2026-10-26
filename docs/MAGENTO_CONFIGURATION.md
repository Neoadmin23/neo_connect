# Central Magento integration configuration

Version 1.2.0, 24 October 2026. Verified on the isolated Frappe 15.118.0 / ERPNext 15.119.3 test site. The PowerTire customer site has not been deployed or tested.

## Open the integration

After installing/updating NeoConnect and running `bench --site <site> migrate`, open the **Magento Integration** workspace. It provides **Configurations**, **Activity Report**, and **Trace Logs** shortcuts. You can also search for **Magento Integration Settings** in ERPNext.

A System Manager creates one configuration per company and Sales Invoice endpoint. Accounts Managers can read the configuration and activity report, but cannot manage users or reveal secrets.

1. Install the bundled **PowerTire complete-order invoice** pack through an API Partner to provision the endpoint and required custom fields. Do not use the older generic Magento preset for this contract.
2. Review the endpoint's actual company, price list, tax accounts/template, cost center, item mappings and shipping item. Keep **Ignore Permissions** off and **Process Async** off. Preserve `neo_connect.handlers.powertire.prepare_invoice` and `neo_connect.handlers.powertire.reconcile_invoice` as the validation hooks.
3. Create **Magento Integration Settings** with an integration name, company and that endpoint. Enable the configuration. Company and endpoint are fixed after creation; use another configuration for another company/endpoint.
4. Set **Allow Invoice Submission**, the IP/CIDR allowlist, requests per minute per user (0 disables the limit), and optional HMAC signing. Save configuration changes to apply them to all assigned users. HMAC secrets are generated per dedicated user when signing is enabled.
5. Choose **Users > Add API User**. Enter a new dedicated email and name, and select **Create Invoices** and **Submit Invoices** independently. Existing personal ERP users cannot be adopted. The configuration assigns native roles and a Company User Permission automatically.
6. Choose **Credentials > Get / Create Credentials** to retrieve the key/secret privately. **Rotate Secret** invalidates the previous secret immediately. **Revoke Access** disables that user's access. **Remove API User** disables the user, replaces its secret and removes membership while preserving its User, API Partner and audit history. A removed dedicated user can be added back to the same integration, then issued credentials again.
7. The form shows the create/submit URLs. Use **Activity Report**, **Trace Logs**, or **Users > User Activity** to navigate directly to filtered history.

The two per-user capabilities and global submission setting must all permit the requested operation. Disabling the integration disables its users. Dedicated users can call only the configured gateway's ping/push/submit methods; direct REST resources, Desk and generic RPC access are blocked. Secrets remain in ERPNext's encrypted Password storage. Only a System Manager can retrieve/create/rotate them, and each reveal/rotation/revocation is audited. Credential responses use `Cache-Control: no-store`.

## Invoice API

See [POWERTIRE_API.md](POWERTIRE_API.md) for the complete JSON contract. One complete Magento order produces one invoice. Use `push?endpoint=<slug>` for a draft, `push?endpoint=<slug>&submit=1` to create and submit, or `submit?endpoint=<slug>` with `{"order_number":"..."}` to submit a previously imported draft. Both draft/create-and-submit dry runs are supported.

All users within the same configuration share the order reference namespace. An identical order delivered by another assigned user returns the same invoice. A changed order under an existing number is rejected. When a legacy endpoint is assigned to a configuration, its references are adopted into that namespace without editing Sales Invoices. Conflicting historical invoice targets or references from another company block configuration saving and require reconciliation. References without a source hash still require reconciliation before retry/submission.

Submission calls native ERPNext `submit()`, checks current permissions and validates the source against the saved invoice. The integration does not create Payment Entries or Stock Ledger Entries. Discounts, refunds and partial invoices remain outside this contract.

## Traceability and report

**Magento API Activity** records configuration, API user, authenticated actor, affected user, action, outcome, method/route/query, IP address, duration, HTTP status, trace ID, Magento order, linked Sales Invoice, request-log reference, source hash, request/response snapshots and available error trace. Authentication failures with a recognized key are attributed to the key's owner and have Guest as actor if authentication failed. Requests with an unknown key cannot be attributed to a configuration.

Successful invoice actions and their audit record commit together. Rejected requests and authentication/authorization failures get separate audit records. Every recognized user's HTTP response includes **X-NeoConnect-Trace-ID** for support correlation. A ping, denied direct REST request, failed invoice, duplicate, dry run, user change and credential-management action are traceable. Configuration changes include before/after access settings and user capabilities. Secrets and Authorization values in structured snapshots are redacted. No raw Authorization header is stored.

Activity records cannot be edited/deleted through the app, even by System Managers. There is no automatic purge of activity records or managed partners' linked API Request Logs. Normal database administrators can still change database contents; this is application audit history, not an external tamper-evident archive. Request snapshots are capped at 2,000,000 characters and retain a hash/truncation indicator where applicable. Existing primary request logs follow their legacy behavior outside managed integrations.

**Magento API Activity Report** filters by date range, configuration, company, user, endpoint, action, status, Magento order, Sales Invoice, HTTP status and trace ID. It includes status totals and a chart for the displayed records, plus links to configuration, invoice and detailed trace. The row limit defaults to 1,000 and can be raised to 5,000; a truncation message asks you to narrow filters. Trace forms link back to the configuration, source request log, resulting document and user's report.

## Run the Postman collection

Import [powertire.postman_collection.json](powertire.postman_collection.json) and [powertire.postman_environment.json](powertire.postman_environment.json). The exported environment contains no credentials. Set `base_url` to a staging URL and `endpoint` to its configured slug.

For the complete 12-request suite, add three dedicated users in the configuration:

| Environment variables | User access |
| --- | --- |
| `api_key`, `api_secret` | Create + submit |
| `second_api_key`, `second_api_secret` | A different user with create + submit |
| `draft_api_key`, `draft_api_secret` | Create only |

Use the collection runner in its numbered order. Each run generates unique order numbers and creates real test documents, including submitted invoices. The collection checks connectivity, dry run, draft creation, saved draft submission, retry, direct submission, cross-user deduplication, submit denial, draft-only creation, unknown-SKU rejection, changed-source rejection and direct REST denial. It expects **422** for record-validation failures and **403** for access denial, and checks the trace header. The supplied collection assumes HMAC is disabled; when enabled, add `X-Signature` calculated from the exact transmitted body using that user's signing secret, as specified in the API guide.

Equivalent command after configuring a private environment:

```text
newman run powertire.postman_collection.json -e your-private-environment.json
```

Keep environment files and full runner reports private because they may contain credentials. The supplied [Postman results](POSTMAN_TEST_RESULTS.txt) are sanitized.

## Management RPC reference (System Manager only)

The ERPNext configuration buttons call authenticated POST methods below. These are administration methods, not methods to share with Magento's dedicated users.

| Method after `/api/method/` | JSON arguments |
| --- | --- |
| `neo_connect.management.add_user` | `config`, `email`, `first_name`, `can_create`, `can_submit` |
| `neo_connect.management.remove_user` | `config`, `user` |
| `neo_connect.management.credentials` | `config`, `user`, `action`: `get_or_create`, `get`, `rotate`, `revoke` |

Use normal ERPNext document forms for creating/updating the configuration. No production secrets are included in the app or Postman handoff.

## Verification

The latest results are [46 unit tests](UNIT_TEST_RESULTS.txt), [23 invoice HTTP/database tests](HTTP_TEST_RESULTS.txt), [25 management HTTP/database tests](MANAGEMENT_TEST_RESULTS.txt), and [12 actual Newman requests / 34 assertions](POSTMAN_TEST_RESULTS.txt), all passing. The management tests cover configuration controls, real credential actions, roles, cross-user concurrency, native API bypass denial, signed requests, IP/rate rules, legacy reference adoption, redaction, immutable activity records, report filtering and workspace metadata. UI JavaScript is syntax checked; browser interaction with the configuration dialogs has not been acceptance tested.

Customer staging acceptance remains necessary for actual masters, mandatory fields, workflows and e-invoicing hooks before issuing production credentials. See [VERIFICATION.md](VERIFICATION.md).
