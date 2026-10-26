"""Meaningful contract regression tests; no site or database required."""

import copy
import json
from pathlib import Path
import unittest

from neo_connect.engine.invoice_contract import validate_invoice
from neo_connect.engine.mapper import MappingError, map_inbound

APP = Path(__file__).resolve().parents[2]


class TestPowerTireInvoice(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads((APP / "docs/powertire_invoice.example.json").read_text(encoding="utf-8"))
        self.pack = json.loads((APP / "neo_connect/packs/powertire_complete_order_invoice.json").read_text(encoding="utf-8"))

    def test_complete_invoice(self):
        self.assertIs(validate_invoice(self.payload), self.payload)

    def test_order_snapshot_is_not_an_invoice(self):
        self.payload.pop("event")
        with self.assertRaisesRegex(MappingError, "invoice.created"):
            validate_invoice(self.payload)

    def test_partial_invoice_rejected(self):
        self.payload["items"][0]["qty_invoiced"] = 2
        with self.assertRaisesRegex(MappingError, "partial invoicing"):
            validate_invoice(self.payload)

    def test_order_number_required(self):
        self.payload.pop("order_number")
        with self.assertRaisesRegex(MappingError, "order_number"):
            validate_invoice(self.payload)

    def test_invoice_date_requires_timezone(self):
        self.payload["invoice_date"] = "2026-10-22T10:00:00"
        with self.assertRaisesRegex(MappingError, "timezone"):
            validate_invoice(self.payload)

    def test_tax_and_total_must_reconcile(self):
        for key in ("subtotal", "tax_amount", "grand_total"):
            with self.subTest(key=key):
                payload = copy.deepcopy(self.payload)
                payload["totals"][key] += 5
                with self.assertRaisesRegex(MappingError, "reconcile"):
                    validate_invoice(payload)

    def test_bad_numbers_rejected(self):
        for value in ("NaN", "Infinity", True, -1, None, "bad"):
            with self.subTest(value=value):
                payload = copy.deepcopy(self.payload)
                payload["items"][0]["price"] = value
                with self.assertRaises(MappingError):
                    validate_invoice(payload)

    def test_shipping_and_its_tax(self):
        self.payload["totals"].update(shipping_amount=20, shipping_tax_amount=3, tax_amount=273, grand_total=2093)
        validate_invoice(self.payload)

    def test_unpaid_cod_stays_unpaid(self):
        self.payload["payment"].update(method="cashondelivery", amount_paid=0)
        validate_invoice(self.payload)
        self.assertNotIn("add_invoice_payments", self.pack["endpoint"]["pre_process_hook"])
        self.assertNotIn("create_payment", self.pack["endpoint"]["post_process_hook"])

    def test_overpayment_rejected(self):
        self.payload["payment"]["amount_paid"] = 3000
        with self.assertRaisesRegex(MappingError, "cannot exceed"):
            validate_invoice(self.payload)

    def test_refund_cancel_and_discount_fail_closed(self):
        for patch in ({"total_refunded": 1}, {"status": "canceled"}, {"event": "invoice.updated"}):
            with self.subTest(patch=patch):
                with self.assertRaises(MappingError):
                    validate_invoice(dict(self.payload, **patch))
        self.payload["totals"]["discount_amount"] = 10
        with self.assertRaisesRegex(MappingError, "Discount"):
            validate_invoice(self.payload)

    def test_maps_actual_invoice_date_and_ordered_qty(self):
        endpoint = self.pack["endpoint"]
        doc, errors = map_inbound(self.payload, endpoint["field_maps"], lookup=lambda r, v, c=None: v,
                                  timezone="Asia/Riyadh")
        self.assertEqual(errors, [])
        self.assertEqual(doc["po_no"], "PT-289335")
        self.assertEqual(doc["items"][0]["qty"], 4)
        self.assertEqual(doc["posting_date"], "2026-09-16")
        self.assertEqual(doc["po_date"], "2026-09-15")
        self.assertEqual(endpoint["external_id_path"], "order_number")
        self.assertEqual(endpoint["document_action"], "Save as Draft")


if __name__ == "__main__":
    unittest.main()
