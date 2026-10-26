"""Mocked transaction-path regressions. Real concurrency still needs staging."""

import hashlib
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from neo_connect.engine import inbound
from neo_connect.engine.mapper import MappingError


class TestInboundSafety(unittest.TestCase):
    def setUp(self):
        self.record = {"order_number": "PT-1", "amount": 10}
        self.proc = object.__new__(inbound.Processor)
        self.proc.endpoint = NS(name="powertire-sales-invoice", external_id_path="order_number",
                                on_duplicate="Skip", reference_doctype="Sales Invoice", document_action="Save as Draft",
                                ignore_permissions=0, post_process_hook="")
        self.proc.partner = NS(name="PowerTire")
        self.proc.settings = {"strict_invoice_identity": 1}
        self.proc.log_name = None
        self.proc.build = Mock(return_value=NS(errors=[], doc={}, warnings=[]))
        self.proc.save_reference = Mock()
        self.proc.claim_reference = Mock(return_value=None)
        self.db = Mock()
        self.db.get_value.return_value = None
        self.doc = Mock(doctype="Sales Invoice", docstatus=0)
        self.doc.name = "SINV-1"
        self.doc.meta.has_field.return_value = False
        self.reservation = Mock()
        self.db_patch = patch.object(inbound.frappe, "db", self.db)
        self.doc_patch = patch.object(inbound.frappe, "get_doc", side_effect=[self.doc])
        self.permission_patch = patch.object(inbound.frappe, "has_permission", return_value=True)
        self.permission_patch.start()
        self.addCleanup(self.permission_patch.stop)
        self.hook_patch = patch.object(inbound, "run_hooks")
        self.translate_patch = patch.object(inbound, "_", side_effect=lambda value: value)
        self.db_patch.start()
        self.doc_patch.start()
        self.hook_patch.start()
        self.translate_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.doc_patch.stop)
        self.addCleanup(self.hook_patch.stop)
        self.addCleanup(self.translate_patch.stop)

    def reference(self):
        digest = hashlib.sha256(json.dumps(self.record, sort_keys=True, ensure_ascii=False,
                                          allow_nan=False).encode()).hexdigest()
        return NS(reference_doctype="Sales Invoice", reference_name="SINV-1", payload_hash=digest)

    def test_reservation_precedes_document_creation(self):
        events = []
        self.proc.claim_reference.side_effect = lambda *args: events.append("reserve")
        self.doc.insert.side_effect = lambda: events.append("invoice")
        self.proc.process_record(self.record)
        self.assertEqual(events, ["reserve", "invoice"])

    def test_competing_reservation_cannot_create_invoice(self):
        self.proc.claim_reference.side_effect = RuntimeError("unique key collision")
        with self.assertRaisesRegex(RuntimeError, "collision"):
            self.proc.process_record(self.record)
        self.proc.build.assert_not_called()
        self.doc.insert.assert_not_called()

    def test_identical_retry_returns_existing_document(self):
        self.proc.claim_reference.return_value = self.reference()
        self.db.get_value.return_value = 0
        result = self.proc.process_record(self.record)
        self.assertEqual(result["status"], "Duplicate")
        self.proc.build.assert_not_called()

    def test_changed_retry_requires_reconciliation(self):
        ref = self.reference()
        self.proc.claim_reference.return_value = ref
        with self.assertRaisesRegex(MappingError, "different content"):
            self.proc.process_record(dict(self.record, amount=11))
        self.proc.build.assert_not_called()

    def test_cancelled_invoice_is_not_recreated(self):
        self.proc.claim_reference.return_value = self.reference()
        self.db.get_value.return_value = 2
        with self.assertRaisesRegex(MappingError, "cancelled"):
            self.proc.process_record(self.record)
        self.proc.build.assert_not_called()

    def test_missing_target_is_not_recreated(self):
        self.proc.claim_reference.return_value = self.reference()
        self.db.get_value.return_value = None
        with self.assertRaisesRegex(MappingError, "no target"):
            self.proc.process_record(self.record)
        self.proc.build.assert_not_called()

    def test_dry_run_never_submits_document(self):
        self.proc.endpoint.document_action = "Submit"
        self.proc.dry_run = True
        self.proc.process_record(self.record)
        self.doc.submit.assert_not_called()

    def test_batch_lookup_is_rebuilt_after_rollback(self):
        self.proc.company = "PowerTire"
        self.proc.endpoint.records_path = ""
        self.proc.endpoint.max_records_per_request = 2
        self.proc.process_record = Mock(side_effect=[{"status": "Failed"}, {"status": "Created"}])
        with patch.object(inbound, "make_lookup") as lookup, patch.object(inbound.frappe, "clear_messages"):
            result = self.proc.process_payload([self.record, self.record])
        self.assertEqual(lookup.call_count, 2)
        self.db.rollback.assert_called_once_with(save_point="cc_rec_0")
        self.assertEqual(result["status"], "Partial")


    def test_validation_runs_before_submit(self):
        events = []
        self.doc.submit.side_effect = lambda: events.append("submit")
        with patch.object(inbound, "run_hooks", side_effect=lambda *args: events.append("validate")):
            ctx = NS(document=self.doc, errors=[])
            self.proc.finalize_document(ctx, submit=True)
        self.assertEqual(events, ["validate", "submit"])

    def test_validation_failure_prevents_submission(self):
        with patch.object(inbound, "run_hooks", side_effect=MappingError("mismatched total")):
            with self.assertRaisesRegex(MappingError, "mismatched"):
                self.proc.finalize_document(NS(document=self.doc, errors=[]), submit=True)
        self.doc.submit.assert_not_called()

    def test_native_submit_permission_is_required(self):
        with patch.object(inbound.frappe, "has_permission", side_effect=inbound.frappe.PermissionError):
            with self.assertRaises(inbound.frappe.PermissionError):
                self.proc.finalize_document(NS(document=self.doc, errors=[]), submit=True)
        self.doc.submit.assert_not_called()

    def test_requested_submit_requires_endpoint_opt_in(self):
        from neo_connect.engine.security import GatewayError
        self.proc.endpoint.allow_submit = 0
        with self.assertRaisesRegex(GatewayError, "disabled"):
            self.proc.process_payload(self.record, submit=True)
        self.proc.build.assert_not_called()

    def test_submitted_status_counts_as_success(self):
        result = inbound.summarize([{"status": "Submitted"}])
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["http_status"], 200)

if __name__ == "__main__":
    unittest.main()
