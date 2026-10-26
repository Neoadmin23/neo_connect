# Release v1.2.0

Date: 24 October 2026.

[README](../README.md) | [Changelog](../CHANGELOG.md) | [Architecture](introduction.md)

This initial repository publication packages the supplied 1.0.0 sample plus the locally developed 1.1.0 invoice submission and 1.2.0 central Magento administration features. The published source version and annotated release tag are 1.2.0; documentation preparation adds no additional version bump.

## Upgrade and deployment

1. Back up the staging site and reconcile any local NeoConnect modifications before updating.
2. Install or update from `AlphaX-SAAS/neo_connect`, then run `bench --site <site> migrate`, clear cache and restart web/workers through the normal deployment procedure.
3. Migration creates central configuration, API user membership and activity DocTypes, adds integration links, installs the report/workspace and creates restricted native API roles. Existing standard permissions are preserved.
4. Re-import the bundled complete-order PowerTire pack and review actual company, accounts, tax template, price list, items and shipping defaults. Keep native permissions enabled and background processing off.
5. Create Magento Integration Settings for the company/endpoint, add dedicated users and issue credentials there. Central management is opt-in; existing generic partners remain outside it until deliberately configured. Personal ERP users cannot be adopted.
6. Assigning a legacy endpoint adopts its order references without rewriting invoices. Conflicting targets/company histories block the save. References without an original source hash require reconciliation. Back up and inspect historical imports before adoption.
7. Run the documented Postman and customer staging acceptance checks before production credentials are used. Customer workflows and e-invoicing hooks need their own acceptance.

## Verification and limits

The recorded local verification passed 46 unit/mock tests, 23 invoice HTTP/database tests, 25 management HTTP/database tests and 12 Newman requests with 34 assertions. Python and JavaScript syntax checks passed. Versions: Frappe 15.118.0, ERPNext 15.119.3, Python 3.11.14 and private MariaDB. See [results](TEST_RESULTS.txt).

No customer production deployment occurred. Browser interaction acceptance for configuration dialogs and v16 compatibility remain pending. PowerTire imports one invoice per complete order, retains payment metadata, and does not post payments or stock. Discounts, refunds and partial invoices remain unsupported by this contract. App permissions protect activity history; an external tamper-evident archive is not provided.
