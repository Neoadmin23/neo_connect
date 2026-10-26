Version 1.2.0. For central configuration, user access, credentials, activity logs and reports, see [MAGENTO_CONFIGURATION.md](MAGENTO_CONFIGURATION.md).

# PowerTire Magento sales invoice API

Updated 24 October 2026. Verified locally with real Frappe HTTP requests, token authentication, MariaDB and ERPNext ledger posting. The API has not been deployed to the PowerTire customer site. Use the customer URL below only after its app installation and configuration are confirmed.

PowerTire confirmed **one invoice for each complete order, sent order by order**. Magento must send the order when its invoice is issued, with the full ordered quantities. Partial invoices and ordinary order-update notifications are rejected.

## Create and submit in one call

```http
POST https://powertire.alphaxerp.com/api/method/neo_connect.api.push?endpoint=powertire-sales-invoice&submit=1
Authorization: token <dedicated_api_key>:<dedicated_api_secret>
Content-Type: application/json
```

Send the complete [example JSON](powertire_invoice.example.json). Successful creation returns the ERPNext invoice name and **`docstatus: 1`**, confirming native ERPNext submission. A normal push without `submit=1` creates a draft when the endpoint's Document Action is Save as Draft. An administrator can instead set Document Action to Submit for automatic submission of every accepted push.

The endpoint must have **Allow Partner Submission** enabled, and the API user must have Sales Invoice read and submit permissions. The bundled PowerTire pack enables partner submission and keeps draft creation as the default action. Ignore Permissions must remain disabled. Native ERPNext document, accounting and user-permission checks still apply.

## Submit a previously imported draft

```http
POST https://powertire.alphaxerp.com/api/method/neo_connect.api.submit?endpoint=powertire-sales-invoice
Authorization: token <dedicated_api_key>:<dedicated_api_secret>
Content-Type: application/json
```

```json
{"order_number": "PT-289335"}
```

The server resolves the invoice using the authenticated integration configuration (or legacy partner), endpoint and order number. It accepts no arbitrary ERPNext document name or DocType. It revalidates the stored source, company, items, quantities, rates and totals before submitting the draft. Changed source data, changed financial values, deleted targets and cancelled invoices require reconciliation.

A successful submission has this response shape:

```json
{
  "message": {
    "request_id": "<request-log-id>",
    "dry_run": false,
    "status": "Success",
    "summary": {"total": 1, "Submitted": 1},
    "results": [{
      "external_id": "PT-289335",
      "status": "Submitted",
      "doctype": "Sales Invoice",
      "name": "<ERPNext invoice name>",
      "docstatus": 1,
      "grand_total": 2070.0
    }]
  }
}
```

The initial create-and-submit response reports record status `Created` with `docstatus: 1`. Repeating either submission call returns `Duplicate` with the same invoice name and `docstatus: 1`, without posting another set of ledger entries. Repeating the original complete payload with `submit=1` can also promote its existing draft.

## Credentials and dry runs

Use `GET /api/method/neo_connect.api.ping` to check token credentials. Manage dedicated ERPNext API users, their native roles and company restriction through Magento Integration Settings. Multiple users in the same configuration share order deduplication. Share secrets separately through a private channel. Optional HMAC signing requires `X-Signature` when enabled for the partner.

Add `&dry_run=1` to either POST URL to validate without retaining invoice changes or creating ledger entries. Dry runs validate draft data and submit permission; they do not execute native submission, workflow transitions or external e-invoicing integrations. Test actual submission on staging before enabling production traffic.

Send one invoice object per push, at most 2,000,000 UTF-8 bytes. The [Postman collection](powertire.postman_collection.json) contains draft, create-and-submit, existing-draft submit and dry-run requests. The [OpenAPI file](openapi.json) documents both methods.

## Payload agreement

Use the nested JSON field names below. The vendor specification's tables and examples use some different paths. The supplied Markdown examples contain trailing commas and the separate JSON Markdown includes escapes; use the accompanying valid JSON for HTTP requests.

| Field | Rule |
|---|---|
| `event` | Required `invoice.created`; an order notification cannot be mistaken for an invoice. |
| `order_number` | Required, stable and unique across the stores handled by this integration configuration; duplicate key. Maximum 140 characters. |
| `invoice_date` | Actual issued-invoice timestamp with `Z` or UTC offset; determines ERPNext posting date/time. |
| `invoice_number` | Recommended Magento invoice number, retained separately. |
| `order_date` | Original order timestamp including timezone. |
| `order_currency_code` | Required `SAR`. |
| `customer.firstname`, `customer.email` | Required name and matching email. New customers, contacts and addresses require the API user's normal create permissions. |
| `billing_address` | Nested billing address; `street` is a string in this contract. |
| `items[].sku` | An existing ERPNext Item Code. Unknown SKUs are rejected. |
| `items[].qty_ordered` | Positive full-order quantity. If `qty_invoiced` is supplied, it must equal this quantity. |
| `items[].price` | Non-negative unit price excluding tax. |
| `items[].row_total`, `items[].tax_amount` | Required net and tax amounts for each line. |
| `totals.subtotal`, `totals.shipping_amount`, `totals.tax_amount`, `totals.grand_total` | Required complete-invoice amounts; must reconcile. |
| `totals.shipping_tax_amount` | Shipping tax, included in `totals.tax_amount`; zero/omitted when none applies. |
| `payment.amount_paid` | Source amount allocated to this invoice, between zero and its total. Retained as source data; this API does not create an ERPNext payment. |

Vehicle, installer, appointment, fulfillment, executive code, tyre attributes, supplier code and payment references are preserved in the invoice's Magento Invoice Data JSON field. Existing PowerTire mandatory custom fields need explicit mappings or defaults.

Line amounts, source totals and the ERPNext draft's calculated totals are checked within SAR 0.01 **before submission**. Configure the company's actual tax template, selling price list, receivable/income accounts and cost center. Shipping requires a configured non-stock service item when it is charged.

**Current scope:** SAR, one complete invoice per order, native invoice submission. Discounts, partial invoices, refunds/credit notes and invoice edits are rejected. Stock movements and payment posting are excluded. A submitted paid Magento order remains outstanding in ERPNext until a separate payment/accounting flow records its payment; gateway source data alone does not settle it. Customer-specific e-invoicing/ZATCA hooks have not been tested on PowerTire.

## Errors and retries

| HTTP status | Meaning |
|---|---|
| 200 | Created, submitted, validated dry run or duplicate. Inspect `message.results` and `docstatus`. |
| 400 | Bad request or invalid query parameter. |
| 401 / 403 | Authentication, endpoint policy or submit/read permission failure. Per-record ERPNext permission validation may also be reported in a failed push record. |
| 404 | No invoice imported for this integration, endpoint and order. |
| 409 | Existing invoice cancelled/deleted or its stored source changed; reconcile manually. |
| 413 | Push too large or more than one invoice. |
| 422 | Business validation failed; inspect the record or error. No partial posting is retained. |
| 429 | Rate limited. |
| 500 | Unexpected framework/server error. Invalid JSON can be rejected by Frappe before app logging. |

Persist and retry the **same source JSON** with the same order number after network timeouts or transient failures, using backoff. Changed content under the same order number is rejected. Five concurrent identical create-and-submit requests and five concurrent submissions of an existing draft were tested locally: every request returned the same invoice, with one balanced posting.

## Deployment requirement

Install or update NeoConnect, migrate the customer staging site, and re-import the updated PowerTire complete-order pack so Saved Document Validation Hooks points to `neo_connect.handlers.powertire.reconcile_invoice`. Review company defaults, mappings and restricted credentials, then run actual PowerTire acceptance tests. See [deployment and verification](VERIFICATION.md).
