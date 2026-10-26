# PowerTire integration status

Updated 24 October 2026, version 1.2.0. Central user/credential configuration, activity records, filtered reporting and navigation are implemented. The actual Postman run passed 12 requests and 34 assertions. See [Magento configuration](docs/MAGENTO_CONFIGURATION.md). The complete-order invoice API now supports draft creation, create-and-submit and submission of a previously imported draft. Real local HTTP/database tests verified native ERPNext submission, balanced ledger entries, permissions, rollback and concurrent retries. See [verification and deployment](docs/VERIFICATION.md) and the [API guide](docs/POWERTIRE_API.md).

The customer site has not been changed. Payment posting, stock movement, discounts, refunds and partial invoices remain outside this endpoint's current scope. Existing customer-specific fields and e-invoicing hooks require customer staging acceptance.

This app is derived from the supplied NeoConnect sample. Other presets and the original README describe inherited behavior beyond the verified PowerTire flow. Publisher metadata now identifies AlphaX SAAS. The supplied sample license notice is preserved; its original attribution was not reconstructed. See the [release notes](docs/RELEASE_v1.2.0.md) and [development guide](docs/DEVELOPMENT.md).
