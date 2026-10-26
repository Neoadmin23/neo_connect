"""Strict, pure-Python validation for the proposed PowerTire invoice event.

PowerTire confirmed one invoice per complete order. Ordered quantities are used
only on the explicit invoice.created event; partial invoicing is rejected.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from .mapper import MappingError

CENT = Decimal("0.01")


def number(value, path, *, positive=False):
    if isinstance(value, bool) or value is None:
        raise MappingError(f"{path}: a finite number is required")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise MappingError(f"{path}: a finite number is required") from None
    if not result.is_finite() or result < 0 or (positive and result <= 0):
        raise MappingError(f"{path}: must be {'positive' if positive else 'non-negative'} and finite")
    return result


def text(record, key):
    value = record.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > 140:
        raise MappingError(f"{key}: a non-empty string up to 140 characters is required")
    return value


def same(actual, expected, path):
    if abs(actual - expected) > CENT:
        raise MappingError(f"{path}: {actual} does not reconcile with {expected}")


def validate_invoice(record):
    if not isinstance(record, dict):
        raise MappingError("Each invoice must be a JSON object")
    for key in ("order_number",):
        text(record, key)
    for key in ("invoice_id", "invoice_number"):
        if key in record:
            text(record, key)
    if record.get("event") != "invoice.created":
        raise MappingError("event must be invoice.created; updates, cancellations and refunds use a separate flow")
    for key in ("invoice_date", "order_date"):
        try:
            value = datetime.fromisoformat(text(record, key).replace("Z", "+00:00"))
            if value.utcoffset() is None:
                raise ValueError("missing timezone")
        except (ValueError, TypeError):
            raise MappingError(f"{key}: ISO 8601 datetime with timezone is required") from None
    if record.get("order_currency_code") != "SAR":
        raise MappingError("This prototype accepts order_currency_code SAR only")
    if record.get("status") in ("canceled", "cancelled"):
        raise MappingError("A cancelled order cannot create an invoice")
    if number(record.get("total_refunded", 0), "total_refunded"):
        raise MappingError("Refunds require the separate credit-note flow")
    customer = record.get("customer")
    if not isinstance(customer, dict) or not isinstance(customer.get("email"), str) or "@" not in customer["email"]:
        raise MappingError("customer.email is required for customer matching")
    text(customer, "firstname")
    items = record.get("items")
    if not isinstance(items, list) or not items or len(items) > 500:
        raise MappingError("items must contain between 1 and 500 invoice lines")
    subtotal = Decimal(0)
    tax = Decimal(0)
    for i, item in enumerate(items):
        path = f"items[{i}]"
        if not isinstance(item, dict):
            raise MappingError(f"{path}: must be an object")
        text(item, "sku")
        qty = number(item.get("qty_ordered"), f"{path}.qty_ordered", positive=True)
        if "qty_invoiced" in item and number(item["qty_invoiced"], f"{path}.qty_invoiced") != qty:
            raise MappingError(f"{path}: qty_invoiced must equal qty_ordered; partial invoicing is unsupported")
        price = number(item.get("price"), f"{path}.price")
        if number(item.get("discount_amount", 0), f"{path}.discount_amount"):
            raise MappingError("Discount allocation must be agreed before importing discounted invoices")
        net = number(item.get("row_total"), f"{path}.row_total")
        same(net, (qty * price).quantize(CENT), f"{path}.row_total")
        line_tax = number(item.get("tax_amount"), f"{path}.tax_amount")
        if item.get("row_total_incl_tax") is not None:
            same(number(item["row_total_incl_tax"], f"{path}.row_total_incl_tax"), net + line_tax,
                 f"{path}.row_total_incl_tax")
        subtotal += net
        tax += line_tax
    totals = record.get("totals")
    if not isinstance(totals, dict):
        raise MappingError("totals is required and must contain this invoice's amounts")
    for key in ("subtotal", "shipping_amount", "tax_amount", "grand_total"):
        number(totals.get(key), f"totals.{key}")
    if number(totals.get("discount_amount", 0), "totals.discount_amount"):
        raise MappingError("Discount allocation must be agreed before importing discounted invoices")
    shipping = number(totals["shipping_amount"], "totals.shipping_amount")
    shipping_tax = number(totals.get("shipping_tax_amount", 0), "totals.shipping_tax_amount")
    if not shipping and shipping_tax:
        raise MappingError("shipping_tax_amount must be zero when shipping_amount is zero")
    same(number(totals["subtotal"], "totals.subtotal"), subtotal, "totals.subtotal")
    same(number(totals["tax_amount"], "totals.tax_amount"), tax + shipping_tax, "totals.tax_amount")
    grand_total = number(totals["grand_total"], "totals.grand_total")
    same(grand_total, subtotal + shipping + tax + shipping_tax, "totals.grand_total")
    payment = record.get("payment", {})
    if not isinstance(payment, dict):
        raise MappingError("payment must be an object")
    paid = number(payment.get("amount_paid", 0), "payment.amount_paid")
    if paid > grand_total:
        raise MappingError("payment.amount_paid must be allocated to this invoice and cannot exceed its total")
    return record
