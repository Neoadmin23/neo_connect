"""Submission of an imported invoice, resolved by partner and order identity."""
import hashlib
import json
import frappe
from frappe.utils import cint
from neo_connect.access import reference_scope
from .inbound import Processor, reference_name, summarize
from .security import GatewayError


def submit_imported(endpoint, partner, request, log_name=None, dry_run=False):
    if not cint(endpoint.allow_submit):
        raise GatewayError('Partner submission is disabled for this endpoint', 403)
    if endpoint.reference_doctype != 'Sales Invoice' or endpoint.external_id_path != 'order_number':
        raise GatewayError('This submit method supports complete-order Sales Invoice endpoints only', 400)
    if endpoint.process_async:
        raise GatewayError('Invoice submission requires a synchronous endpoint', 400)
    if not isinstance(request, dict) or set(request) != {'order_number'}:
        raise GatewayError('Send only an order_number; arbitrary ERPNext document names are not accepted', 400)
    order = request['order_number']
    if not isinstance(order, str) or not order.strip() or len(order) > 140:
        raise GatewayError('A non-empty order_number up to 140 characters is required', 400)
    key = reference_name(reference_scope(partner), endpoint.name, order)
    ref = frappe.db.get_value('API External Reference', key,
                              ['reference_doctype', 'reference_name', 'payload_hash'], as_dict=True, for_update=True)
    if not ref or not ref.reference_name or ref.reference_doctype != 'Sales Invoice':
        raise GatewayError('No imported invoice was found for this partner, endpoint and order', 404)
    try:
        doc = frappe.get_doc(ref.reference_doctype, ref.reference_name, for_update=True)
    except frappe.DoesNotExistError:
        raise GatewayError('Imported invoice was deleted; manual reconciliation required', 409) from None
    frappe.has_permission(doc.doctype, 'read', doc=doc, throw=True)
    frappe.has_permission(doc.doctype, 'submit', doc=doc, throw=True)
    if not partner.company or doc.company != partner.company:
        raise GatewayError('Invoice does not belong to the API partner company', 403)
    if doc.docstatus == 2:
        raise GatewayError('Imported invoice was cancelled; manual reconciliation required', 409)
    try:
        payload = json.loads(doc.get('custom_magento_payload') or 'null')
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    except (ValueError, TypeError):
        raise GatewayError('Stored source invoice is invalid; manual reconciliation required', 409) from None
    if not isinstance(payload, dict) or payload.get('order_number') != order or digest != ref.payload_hash:
        raise GatewayError('Stored source invoice differs from the imported payload; manual reconciliation required', 409)
    if doc.docstatus == 1:
        return summarize([dict(status='Duplicate', external_id=order, doctype=doc.doctype,
                               name=doc.name, docstatus=1, grand_total=doc.grand_total, message='Already submitted')])
    processor = Processor(endpoint, partner, log_name)
    processor.dry_run = bool(dry_run)
    result = processor.submit_existing(payload, order, key, doc.name)
    return summarize([result])
