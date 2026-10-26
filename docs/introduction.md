# NeoConnect introduction

[README](../README.md) | [Configuration](MAGENTO_CONFIGURATION.md) | [Development](DEVELOPMENT.md) | [Changelog](../CHANGELOG.md)

NeoConnect is a Frappe custom app for controlled integration with ERPNext. Release 1.2.0 provides a verified Magento complete-order Sales Invoice flow, central access administration, encrypted credential management and correlated activity reporting. The source also contains generic mapping, sample-analysis and outbound capabilities inherited from the supplied 1.0.0 sample; those capabilities do not expand the verified PowerTire contract.

## Contents

- [Architecture overview](#architecture-overview)
- [DocType model](#doctype-model)
- [Central configuration and user access](#central-configuration-and-user-access)
- [Credential lifecycle](#credential-lifecycle)
- [Invoice creation and submission](#invoice-creation-and-submission)
- [Traceability and reporting](#traceability-and-reporting)
- [Extension points](#extension-points)
- [Operational boundaries](#operational-boundaries)

## Architecture overview

```mermaid
flowchart TB
    magentoClient["Magento client"] --> tokenAuth["Frappe token authentication"]
    tokenAuth --> accessPolicy["access.py: managed user and route policy"]
    configDoc["Magento Integration Settings"] --> accessPolicy
    accessPolicy --> gatewayApi["api.py: ping, push, submit"]
    gatewayApi --> securityGate["engine/security.py: partner, endpoint, IP, rate and HMAC"]
    securityGate --> invoiceEngine["engine/inbound.py and engine/submission.py"]
    invoiceEngine --> invoiceHooks["handlers/powertire.py: contract and saved invoice checks"]
    invoiceEngine --> referenceStore["API External Reference: order reservation and source hash"]
    invoiceHooks --> erpInvoice["ERPNext Sales Invoice and native submit"]
    erpInvoice --> generalLedger["ERPNext General Ledger"]
    gatewayApi --> auditService["audit.py: correlated activity snapshots"]
    invoiceEngine --> auditService
    auditService --> activityStore["Magento API Activity"]
    invoiceEngine --> requestStore["API Request Log"]
    activityStore --> activityReport["Magento API Activity Report"]
    configDoc --> managementApi["management.py: users and credentials"]
    managementApi --> auditService
```

`hooks.py` registers authentication and request hooks plus install/migrate role setup. Generic transformations stay in `engine/mapper.py`; customer-specific business validation belongs in handlers. The managed integration must retain synchronous processing and native ERPNext permissions.

## DocType model

```mermaid
erDiagram
    MAGENTO_INTEGRATION_SETTINGS ||--o{ MAGENTO_API_USER : contains
    MAGENTO_INTEGRATION_SETTINGS ||--|| API_ENDPOINT : controls
    MAGENTO_INTEGRATION_SETTINGS ||--o{ API_PARTNER : manages
    MAGENTO_INTEGRATION_SETTINGS ||--o{ MAGENTO_API_ACTIVITY : records
    USER ||--o| MAGENTO_API_USER : assigned
    USER ||--o| API_PARTNER : authenticates
    MAGENTO_API_USER }o--|| API_PARTNER : identifies
    API_ENDPOINT ||--o{ API_ENDPOINT_PARTNER : allows
    API_PARTNER ||--o{ API_ENDPOINT_PARTNER : member
    API_ENDPOINT ||--o{ API_EXTERNAL_REFERENCE : scopes
    API_PARTNER ||--o{ API_EXTERNAL_REFERENCE : first_sender
    API_EXTERNAL_REFERENCE }o--o| SALES_INVOICE : resolves
    API_REQUEST_LOG ||--o{ MAGENTO_API_ACTIVITY : details
    SALES_INVOICE ||--o{ MAGENTO_API_ACTIVITY : traced
    MAGENTO_INTEGRATION_SETTINGS {
        string integration_name PK
        string company FK
        string endpoint FK
        boolean enabled
        boolean allow_submit
    }
    MAGENTO_API_USER {
        string parent FK
        string user FK
        string partner FK
        boolean enabled
        boolean can_create
        boolean can_submit
    }
    API_EXTERNAL_REFERENCE {
        string name PK
        string magento_integration FK
        string external_id
        string payload_hash
        string reference_name FK
    }
    MAGENTO_API_ACTIVITY {
        string name PK
        string integration FK
        string api_user FK
        string actor FK
        string correlation_id
        string request_log FK
        string reference_name FK
    }
```

The diagram shows logical relationships. Invoice references use a DocType plus Dynamic Link, and Frappe application Links are not database foreign-key constraints. One endpoint belongs to one central configuration. A dedicated API user can belong to one central configuration. Multiple assigned users share the same integration/endpoint/order namespace, so changing sender does not create another invoice.

## Central configuration and user access

**Purpose:** administer the company's Magento access in one form. Open the **Magento Integration** workspace, select **Configurations**, and create **Magento Integration Settings** against the reviewed PowerTire endpoint. See the [configuration guide](MAGENTO_CONFIGURATION.md) for every field and button.

**Key components:** Settings controller, child **Magento API User**, **API Partner**, native **User**, Company **User Permission**, `management.add_user`, `management.remove_user`, `access.enforce_managed_user`, and `install.after_migrate`.

```mermaid
sequenceDiagram
    actor systemManager as System Manager
    participant settingsForm as Configuration form
    participant managementService as Management service
    participant userStore as Frappe users and roles
    participant policyStore as Partner and endpoint
    participant auditStore as Activity history
    systemManager->>settingsForm: Save company, endpoint and access settings
    settingsForm->>managementService: Add dedicated user with capabilities
    managementService->>userStore: Create user and restricted roles
    managementService->>policyStore: Sync membership, IP, rate and signing policy
    managementService->>userStore: Apply Company User Permission
    managementService->>auditStore: Record actor, target user and capability changes
    managementService-->>settingsForm: User ready for credential provisioning
```

**Edge cases:** personal ERP users and Administrator/Guest cannot be adopted. Company/endpoint identity is fixed after creation. Removing a user preserves historical documents while disabling native access and replacing its secret. Disabling the configuration disables assigned users. Create and submit capabilities are independent, while the global submission switch also applies. Dedicated users can call only their configured gateway's ping/push/submit paths; native REST and general RPC paths are denied.

## Credential lifecycle

**Purpose:** allow System Managers to create, retrieve, rotate and revoke API credentials without managing secrets in spreadsheets or source files. Use **Credentials** on the configuration. `management.credentials` supports `get_or_create`, `get`, `rotate` and `revoke`; the native User Password field stores the encrypted secret. When HMAC is enabled, signing secrets live in API Partner Password storage.

```mermaid
sequenceDiagram
    actor systemManager as System Manager
    participant configForm as Configuration form
    participant managementService as management.credentials
    participant passwordStore as Encrypted Password storage
    participant auditStore as Activity history
    systemManager->>configForm: Get/create or rotate credentials
    configForm->>managementService: Authenticated administration request
    managementService->>managementService: Check System Manager and membership
    managementService->>passwordStore: Retrieve or replace native secret
    managementService->>auditStore: Record action and target without secret
    managementService-->>configForm: Private credentials with no-store response
    systemManager->>configForm: Revoke access
    configForm->>managementService: Revoke member
    managementService->>passwordStore: Disable native user access
    managementService->>auditStore: Record revocation
```

**Edge cases:** rotation replaces the secret while preserving the key identifier. Revocation disables membership and native login; removal also changes the secret. Retrieval itself is audited. Existing managed partners cannot bypass the configuration with legacy partner credential buttons. Full Postman runner exports can contain credentials and must remain private.

## Invoice creation and submission

**Purpose:** import one issued invoice for each complete Magento order, then submit through ERPNext's native controller. Use the [API contract](POWERTIRE_API.md), bundled `powertire_complete_order_invoice.json` pack and [Postman collection](powertire.postman_collection.json).

| Method | Behavior |
| --- | --- |
| `GET neo_connect.api.ping` | Confirm credentials and permitted endpoint |
| `POST neo_connect.api.push?endpoint=<slug>` | Validate and create a draft |
| `POST neo_connect.api.push?endpoint=<slug>&submit=1` | Create and submit, or promote the identical existing draft |
| `POST neo_connect.api.submit?endpoint=<slug>` | Submit the imported draft identified only by `order_number` |

Add `dry_run=1` to validate without persisting invoice changes. All paths include `/api/method/` before the dotted method.

```mermaid
sequenceDiagram
    participant magentoClient as Magento
    participant gatewayApi as Gateway API
    participant policy as Access and security checks
    participant referenceStore as External order reservation
    participant hooks as PowerTire validation
    participant invoice as ERPNext Sales Invoice
    participant auditStore as Request and activity logs
    magentoClient->>gatewayApi: Complete-order JSON with token
    gatewayApi->>policy: Membership, capabilities, endpoint, IP, rate, signature
    gatewayApi->>hooks: Validate complete-order invoice contract
    gatewayApi->>referenceStore: Lock shared integration/order reference
    alt Identical order already imported
        referenceStore-->>gatewayApi: Existing invoice and source hash
        gatewayApi->>invoice: Read and validate current document
    else New order
        gatewayApi->>invoice: Insert draft under native permissions
    end
    opt Submission requested and permitted
        gatewayApi->>hooks: Reconcile stored source, items, tax and totals
        gatewayApi->>invoice: Native submit with native permission check
    end
    gatewayApi->>auditStore: Save linked result and correlated activity
    gatewayApi->>referenceStore: Commit invoice, reference and successful audit together
    gatewayApi-->>magentoClient: Result, request ID and trace header
```

**Edge cases:** changed retries, cancelled/deleted targets, edited financial values, incomplete quantities and unsupported discounts/refunds require rejection or reconciliation. The reference lock precedes creation and serializes simultaneous deliveries. Legacy references are adopted safely into the central namespace; conflicting historical targets block configuration saving. Customer-specific workflows and e-invoicing hooks still run during native submission and require customer staging acceptance.

## Traceability and reporting

**Purpose:** connect a sender and request to the resulting accounting document or rejection. Open **Activity Report**, **Trace Logs**, or **User Activity** from configuration. The workspace also exposes report and log shortcuts.

**Key components:** `audit.before_request`, `audit.from_log`, `audit.after_request`, **Magento API Activity**, **API Request Log**, and **Magento API Activity Report**.

```mermaid
sequenceDiagram
    participant caller as API caller
    participant requestHooks as Request hooks
    participant gatewayApi as Gateway API
    participant activityStore as Activity history
    actor reviewer as System or Accounts Manager
    participant report as Filtered report
    caller->>requestHooks: Authenticated or recognizable-key request
    requestHooks->>requestHooks: Assign trace ID and identify managed user
    requestHooks->>gatewayApi: Process or reject request
    gatewayApi->>activityStore: Persist successful linked audit atomically
    opt Authentication or early authorization rejection
        requestHooks->>activityStore: Persist denial with attempted user and actor
    end
    requestHooks-->>caller: X-NeoConnect-Trace-ID
    reviewer->>report: Filter dates, integration, user, order or trace
    report->>activityStore: Permission-aware query with bounded rows
    activityStore-->>report: Outcomes and links to detailed traces/invoices
    reviewer->>activityStore: Open request/response and available error details
```

**Edge cases:** structured credential values are redacted. Unknown keys cannot be attributed to an integration. Activity records reject edits/deletion through the application; database administrators remain able to alter database contents. Managed activity and linked detail logs have no automatic expiry. The report summarizes its displayed rows, has a default 1,000-row limit and maximum 5,000, and asks reviewers to narrow filters when capped.

## Extension points

Follow [DEVELOPMENT.md](DEVELOPMENT.md) and [CONTRIBUTING.md](../CONTRIBUTING.md). Keep request dispatch in `api.py`, policy in `access.py` and `engine/security.py`, reusable mechanics in `engine/`, business hooks in `handlers/`, and standard metadata under `neo_connect/doctype`, `report` and `workspace`. New integrations should use a pack or handler rather than weakening the PowerTire contract. Store schema changes in the repository and migrate them through Frappe.

## Operational boundaries

The verified release is 1.2.0 on Frappe 15.118.0 / ERPNext 15.119.3. Version 16 has not been tested. The customer site has not been deployed. The PowerTire flow records payment metadata without creating payment or stock postings and rejects discounts, refunds and partial invoices. Generic inherited presets have different contracts; read their configuration and test them separately before use. See [verification](VERIFICATION.md), [release notes](RELEASE_v1.2.0.md) and [changelog](../CHANGELOG.md).
