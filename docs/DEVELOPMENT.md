# Development guide

[README](../README.md) | [Architecture](introduction.md) | [Contributing](../CONTRIBUTING.md) | [Changelog](../CHANGELOG.md)

## Repository layout

```text
neo_connect/
  api.py                   Gateway request dispatch and response envelopes
  access.py                Managed-user route and capability policy
  management.py            System Manager user and credential actions
  audit.py                 Correlation, redaction and activity persistence
  install.py               Idempotent dedicated roles, permissions and indexes
  hooks.py                 Frappe lifecycle, authentication and request hooks
  engine/                  Mapping, reference locking, submission, packs, analysis
  handlers/                Business rules, including powertire.py
  packs/                   Installable integration definitions
  presets/                 Inherited generic mapping presets
  neo_connect/
    doctype/<name>/         Standard JSON schema, controller and form JavaScript
    report/<name>/          Script Report metadata, query and filters
    workspace/<name>/       Desk workspace metadata
  tests/                   Discoverable unit and mock regressions
  patches.txt              Ordered future data migrations
  change_log/v1/           Frappe release highlights
docs/                      Contract, configuration, architecture, verification
CONTRIBUTING.md            Contribution and release checklist
CHANGELOG.md               Versioned changes and upgrade links
```

The outer `neo_connect/` is the importable app package. Its inner `neo_connect/` is the Frappe module named **Neo Connect**, not a second app.

## Local setup

Use a development bench with ERPNext installed. The verified versions are Frappe 15.118.0 and ERPNext 15.119.3, with Python 3.11.14. The dependency declaration permits v15/v16, but v16 compatibility is not verified.

```bash
cd /path/to/frappe-bench
bench get-app git@github.com:AlphaX-SAAS/neo_connect.git --branch main
bench --site development.local install-app neo_connect
bench --site development.local migrate
bench --site development.local clear-cache
```

Use your own authorized SSH configuration. The developer workstation alias `github.com-kpneotec` authenticates as `kishan-dev1`; it is not required by other contributors. Do not copy workstation keys or site configuration into this repository. Configure fake company/accounts/items and a staging endpoint using [MAGENTO_CONFIGURATION.md](MAGENTO_CONFIGURATION.md). Runtime credentials belong in a private Postman environment.

## Where to make changes

| Requirement | Location and expectation |
| --- | --- |
| Another source field | Pack/field mapping, with payload and schema examples updated |
| Customer invoice rule | `handlers/`, raising `MappingError` or appending `ctx.errors` |
| Shared mapping operation | `engine/mapper.py` and focused mapping regressions |
| Managed access rule | `access.py`, configuration controller and real denial cases |
| Credential action | `management.py`; native Password storage, no-store response, secret-free audit |
| DocType field | Standard JSON/controller; run migrate; explicit data patch when needed |
| Report filter or result | Report Python/JavaScript and a permission-aware query test |
| Navigation | Configuration/trace form JavaScript and workspace JSON |
| Endpoint behavior | `api.py`/engine, API contract, OpenAPI, Postman assertions and upgrade notes |

Hooks receive `ctx` with endpoint, partner, record, mapped document, settings, errors, warnings and external ID; saved-document validation also receives `ctx.document`. Preserve pre-process validation and saved-document reconciliation. Do not move customer rules into the mapping engine or implement customer accounting logic in form JavaScript.

## Invariants to preserve

- Complete-order source identity and source hash must match for retries; all users of one central configuration share that namespace.
- Acquire the external-reference lock before inserting an invoice. Avoid a plain duplicate INSERT followed by a lock upgrade; concurrent deliveries previously exposed deadlocks through that pattern.
- Keep native invoice permissions and validation enabled. Never impersonate Administrator to make a partner invoice succeed.
- Submission must validate the saved document before calling native `submit()`. A dry run must not persist accounting changes.
- Gate managed users by route, configuration, membership and capabilities; native roles alone do not prevent direct RPC/REST access.
- Keep successful invoice/reference/activity writes in the same transaction. Record rejected attempts and management actions with the correct actor/target and trace.
- Preserve Company User Permissions and dedicated-user isolation. Do not adopt personal ERP users or share privileged keys.
- Store secrets only through native Password fields. Do not print credentials, commit private environments, or include secrets in audit snapshots.
- Activity records and historical references are operational evidence. Do not export them as fixtures, bypass their protections, or automatically purge managed history.
- Do not silently add payment/stock posting, discount allocation, partial invoices or return flows to the PowerTire contract.

## Schema and migration rules

Standard metadata belongs in the module directory and uses `is_standard` where appropriate. Use snake_case directory/file names matching the DocType/report name. Keep installation/migration role setup idempotent and preserve existing standard permissions. Use `patches.txt` plus a versioned patch module for future data migrations that cannot be expressed by schema sync. Do not run ad hoc production SQL as an undocumented deployment step.

When changing central identity or reference scope, test migration from existing references, conflicts across invoice targets, changed source hashes and company boundaries. Additive fields do not justify changing a previously imported order's accounting document.

## Verification

From the app directory, using the bench environment:

```bash
../../env/bin/python -m unittest discover -s neo_connect/tests -v
../../env/bin/python -m compileall -q neo_connect
find neo_connect -name '*.js' -exec node --check {} \;
```

The shipped unit/mock suite has 46 cases. [TEST_RESULTS.txt](TEST_RESULTS.txt) records the separate isolated-site runs: 23 invoice and 25 management HTTP/database cases, plus 12 actual Newman requests and 34 assertions. These results do not imply browser-dialog or customer e-invoicing acceptance.

For repeatable API acceptance on your own staging site, follow the three-user environment setup in [MAGENTO_CONFIGURATION.md](MAGENTO_CONFIGURATION.md), then run:

```bash
newman run docs/powertire.postman_collection.json -e /private/path/staging-environment.json
```

The original local HTTP harness and private database bootstrap live in the bench's `validation/powertire_api_review` review area and are not portable app tests. The repository includes their sanitized results and a portable Postman acceptance suite. Do not rely on that workstation's private database, tokens, Python overlay or hard-coded site identity. New reusable integration tests belong under `neo_connect/tests/` and should build disposable fixtures for an explicitly selected test site; document prerequisites before claiming they are reproducible.

For accounting/security changes, additionally verify native GL balancing, rollback, concurrent duplicate deliveries, edited/cancelled targets, another user's retry, invalid/revoked credentials, company isolation, global/per-user denials and trace correlation. Reproduce customer-specific mandatory fields, workflows and e-invoicing behavior in customer staging. Add focused regressions for the changed behavior rather than snapshotting the implementation.

## Releases

See [CONTRIBUTING.md](../CONTRIBUTING.md). `neo_connect/__init__.py` is the version source; `pyproject.toml` uses Flit's dynamic version and has no static version field. The supplied sample was 1.0.0; local features progressed through 1.1.0 and 1.2.0 before the initial repository publication. The initial tag publishes 1.2.0 without an extra docs-only bump. Future breaking changes require a major version, compatible features a minor version, and fixes a patch version. Documentation-only changes do not require a bump.
