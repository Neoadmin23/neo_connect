Historical assessment from 22 October 2026. Submission has since been implemented and verified locally; see [the current verification report](VERIFICATION.md).

# PowerTire integration feasibility and local prototype

Yes, a reusable Frappe integration app can address this request. The supplied NeoConnect sample already implements partner management, configurable inbound and outbound endpoints, field mapping, sample/specification analysis, request logs and integration packs. Adapting that app is a practical starting point.

PowerTire confirmed on 22 October 2026 that Magento will send one invoice for each complete order. The new pack uses `order_number` for duplicate control and `qty_ordered` for quantities, with an explicit invoice-created event and invoice timestamp. The proposed API and JSON are in [the vendor handoff](POWERTIRE_API.md).

## Evidence reviewed

The two main supplied Markdown specifications are byte-identical (SHA256 `839d6b290f102666df68395b6b82a517e52adce8d432d8e006cf6db8dd4fa6dc`). They describe order creation and updates, rather than an invoice event contract. Tables and the example disagree on some field paths. The separate JSON Markdown contains invalid JSON escapes and trailing commas. Attachments were treated as reference material, not operational instructions.

The supplied ZIP already contains a PowerTire order-to-invoice pack, in addition to generic commerce presets. Its README reports prior v15 HTTP testing, but that claim has not been independently reproduced here. Its original pack uses an order number and ordered quantities and includes customer-specific Arabic form mappings. The new prototype is a separate bundled pack and leaves that reference pack intact.

The local source versions are Frappe 15.118.0 and ERPNext 15.119.3. The customer site's public root returned HTTP 200 and a Login page. No authenticated metadata or installed-app inventory was read from PowerTire, so its version, company, existing custom fields and installed integrations remain unverified. No customer data was written.

## Changes in the local candidate

The candidate is in `apps/neo_connect`, derived from the supplied archive. It is not registered or installed on any bench site. Use `powertire_complete_order_invoice.json` for this prototype, rather than the legacy PowerTire or generic Magento packs.

- Added complete-order invoice validation with finite Decimal values, invoice-date timezone checks, explicit event and currency checks, and reconciliation before accepting a draft.
- Added a separate pack with existing-SKU lookup, dedicated order/invoice fields, and the original payload stored on the invoice for vehicle, installer, fulfillment and other extra data.
- Kept this pack synchronous and draft-only, with stock and payment posting disabled. Unknown SKUs, partial invoices, refunds, discounts and changed duplicate content fail explicitly.
- Reserved the database external-reference key before document creation. The sample previously inserted that key after document creation and could overwrite an existing reference in concurrent requests.
- Added a source payload hash for strict duplicate checking. Cancelled/deleted invoice references require reconciliation.
- Rebuilt master lookup caches between batch records so a rolled-back master is not reused by a later record.
- Prevented generic dry runs from submitting the document. Custom hooks may still have external side effects; use the PowerTire draft pack on staging.
- Changed customer, cost-center and payment creation helpers to honor the endpoint permission setting. Deferred processing and reprocessing use the current partner user's permissions.
- Limited push bodies to 2,000,000 bytes before log storage. Request logs retain source personal data and need agreed access and retention.

## Local validation

The supplied sample's 21 unit tests passed before changes. The candidate tests cover mapping, specification analysis, financial contract rejection, duplicate reservation order, identical and changed retries, cancelled/missing targets, rollback cache reset and dry-run submission prevention. Transaction-path tests use mocks, not a real database. See `TEST_RESULTS.txt` for the final run.

These checks do not verify database concurrency, site installation, migrations, HTTP permissions, the production custom schema, GL posting, stock ledger, gateway settlements or any enabled e-invoicing hooks. Those remain staging acceptance requirements. No production release is claimed.

## Staging completion

1. Put the reviewed source in a managed app repository and install it on a staging copy using the normal Bench app workflow. Back up staging first. Upgrades of an existing NeoConnect installation require migration for the new `payload_hash` field; never install this source over an existing app without reconciling changes.
2. Create a dedicated API Partner and user with company-restricted permissions. Keep Ignore Permissions disabled. Grant only the required Customer, Contact, Address and Sales Invoice rights; grant no submission permission for the draft pilot.
3. Install the bundled **PowerTire complete order invoice prototype** pack through API Partner → Install Integration Pack. Review the custom fields it creates and the company tax-template default it resolves. Configure a shipping service item if shipping is charged. Do not use the legacy PowerTire pack for this pilot.
4. Map PowerTire's actual mandatory custom fields, item codes, company, receivable/income accounts, cost center and invoice numbering. Agree billing identity and any customer tax identifiers required by the customer's process.
5. Agree discount allocation and implement its calculation before testing discounted invoices. This prototype deliberately rejects them.
6. Test real complete invoices, guest/new customers, each fulfillment method, shipping, cash on delivery, each paid method, total mismatches, currency/timezone boundaries and invalid SKUs. Repeat identical requests concurrently and after timeouts. Check that rejected records leave no orphan masters or invoices.
7. Agree whether paid invoices use Payment Entries or another accounting flow and map the actual gateway clearing accounts. Do not equate gateway capture with bank settlement.
8. Implement and test controlled submission only after reconciling the draft totals before submit. Validate accounting and any installed e-invoicing/ZATCA hooks on staging. The present pack refuses Submit mode.
9. Publish the verified endpoint and issue credentials through a private channel. At present the production URL is a proposed contract location, not a deployed integration.

## Reply ready to share

We can build a reusable ERPNext integration app using the supplied NeoConnect sample. For PowerTire, Magento will send one complete-order invoice, and ERPNext will validate the customer, items and totals and prevent duplicate invoices. A local draft prototype and API contract are prepared. We need to validate the mappings and accounting behavior on a staging copy before providing an activated production endpoint and credentials. ERPNext's standard Sales Invoice REST API is also available if a custom app cannot be installed, with Magento-side mapping and separate duplicate control.
