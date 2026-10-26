import frappe
from frappe import _
from frappe.model.document import Document


class APIRequestLog(Document):
    pass


@frappe.whitelist()
def reprocess(log_name):
    """Re-run a failed/partial inbound request with its stored payload (duplicates are skipped)."""
    frappe.only_for("System Manager")
    from neo_connect.engine.inbound import process_log

    log = frappe.get_doc("API Request Log", log_name)
    if log.direction != "Inbound" or not log.endpoint or not log.partner:
        frappe.throw(_("Only inbound requests with a known endpoint and partner can be reprocessed"))
    log = process_log(log_name)
    return {"status": log.status, "response": log.response}


def delete_old_logs():
    """Daily: keep logs for `neo_connect_log_days` (site_config, default 90)."""
    days = frappe.conf.get("neo_connect_log_days") or 90
    filters={"creation": ("<", frappe.utils.add_days(frappe.utils.now(), -days))}
    # Managed integration history has no automatic expiry; keep linked detail logs.
    if frappe.db.exists('DocType','Magento Integration Settings'):
        managed=frappe.get_all('API Partner',filters={'magento_integration':['is','set']},pluck='name')
        if managed:
            # SQL NOT IN omits NULL too; preserve historical unassigned failures.
            filters['partner']=['not in',managed]
    frappe.db.delete('API Request Log',filters)
