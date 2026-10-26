app_name = "neo_connect"
app_title = "NeoConnect"
app_publisher = "AlphaX SAAS"
app_description = "NeoConnect: configurable inbound/outbound API gateway connecting e-commerce platforms and partners to ERPNext"
app_license = "MIT"

required_apps = ["erpnext"]

scheduler_events = {
    "daily": [
        "neo_connect.neo_connect.doctype.api_request_log.api_request_log.delete_old_logs",
    ],
}

# API Request Log and API External Reference are operational data - not exported as fixtures.

after_install = "neo_connect.install.after_install"
after_migrate = "neo_connect.install.after_migrate"
before_request = ["neo_connect.audit.before_request"]
auth_hooks = ["neo_connect.access.enforce_managed_user"]
after_request = ["neo_connect.audit.after_request"]
