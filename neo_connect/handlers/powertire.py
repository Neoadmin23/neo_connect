"""PowerTire complete-order invoice validation before any accounting submission."""
import json
from collections import Counter
import frappe
from neo_connect.engine.invoice_contract import number, same, validate_invoice
from neo_connect.engine.mapper import MappingError
from neo_connect.handlers.commerce import apply_charges, ensure_customer


def prepare_invoice(ctx):
    validate_invoice(ctx.record)
    if ctx.endpoint.document_action not in ('Save as Draft', 'Submit') or ctx.endpoint.process_async:
        raise MappingError('PowerTire requires synchronous draft or submit processing')
    if ctx.endpoint.ignore_permissions:
        raise MappingError('PowerTire requires ERPNext permissions to remain enabled')
    if ctx.doc.get('update_stock') or ctx.doc.get('is_pos'):
        raise MappingError('Stock and POS posting are outside this endpoint')
    if not ctx.doc.get('taxes_and_charges'):
        raise MappingError("Configure the company's validated Sales Taxes and Charges Template first")
    if number(ctx.record['totals']['shipping_amount'], 'totals.shipping_amount') and not ctx.settings.get('shipping_item'):
        raise MappingError('Configure a non-stock shipping_item before importing shipping charges')
    ensure_customer(ctx)
    if ctx.errors:
        return
    apply_charges(ctx)
    ctx.doc['custom_magento_payload'] = json.dumps(ctx.record, ensure_ascii=False, allow_nan=False)
    ctx.warnings.append('Magento payment data is retained; no ERPNext payment is posted by this endpoint.')


def reconcile_invoice(ctx):
    """Validate the saved draft, including changes made after its original import."""
    validate_invoice(ctx.record)
    doc = ctx.document
    totals = ctx.record['totals']
    if doc.docstatus != 0 or doc.currency != 'SAR':
        raise MappingError('An SAR draft invoice is required before submission')
    if not ctx.partner.company or doc.company != ctx.partner.company:
        raise MappingError('Invoice does not belong to the API partner company')
    if doc.get('is_return') or doc.get('update_stock') or doc.get('is_pos') or doc.get('payments'):
        raise MappingError('Returns, stock and POS payments are outside this endpoint')
    if doc.get('custom_magento_order_number') != ctx.record['order_number']:
        raise MappingError('ERPNext invoice order identity differs from the imported order')
    if number(doc.get('discount_amount') or 0, 'ERPNext discount_amount'):
        raise MappingError('Discounted invoices require the agreed discount allocation flow')
    try:
        stored = json.loads(doc.get('custom_magento_payload') or 'null')
    except ValueError:
        stored = None
    if stored != ctx.record:
        raise MappingError('Stored source invoice data was changed; manual reconciliation required')
    same(number(doc.grand_total, 'ERPNext grand_total'), number(totals['grand_total'], 'totals.grand_total'), 'ERPNext grand_total')
    same(number(doc.net_total, 'ERPNext net_total'), number(totals['subtotal'], 'totals.subtotal') + number(totals['shipping_amount'], 'totals.shipping_amount'), 'ERPNext net_total')
    same(number(doc.total_taxes_and_charges, 'ERPNext taxes'), number(totals['tax_amount'], 'totals.tax_amount'), 'ERPNext taxes')
    expected = []
    for item in ctx.record['items']:
        code = frappe.db.get_value('Item', {'item_code': item['sku']}, 'name')
        expected.append((code, number(item['qty_ordered'], 'qty'), number(item['price'], 'price')))
    shipping = number(totals['shipping_amount'], 'shipping_amount')
    if shipping:
        expected.append((ctx.settings.get('shipping_item'), number(1, 'qty'), shipping))
    actual = [(item.item_code, number(item.qty, 'ERPNext qty'), number(item.rate, 'ERPNext rate')) for item in doc.items]
    if Counter(actual) != Counter(expected):
        raise MappingError('ERPNext item codes, quantities or rates differ from the complete imported order')


# Compatibility for a previously configured draft-only pack. Reinstall the new
# pack to move this validation into the saved-document/pre-submit hook.
reconcile_draft = reconcile_invoice
