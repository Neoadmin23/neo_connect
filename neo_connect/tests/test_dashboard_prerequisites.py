"""Regression coverage for mandatory custom fields during client onboarding."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from neo_connect import dashboard


def field(name='custom_sales_representative_name', **values):
    return NS(**dict(dict(fieldname=name, label='Sales Representative', fieldtype='Link',
                         options='Sales Person', reqd=1, default=None, fetch_from=None), **values))


def validation_error(message):
    raise ValueError(message)


class DashboardPrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.fields = [field()]
        self.meta = NS(fields=self.fields, get_field=lambda key: next((f for f in self.fields if f.fieldname == key), None))
        self.db = Mock()
        self.db.get_value.return_value = NS(company='Test', disabled=0, is_group=0)
        self.db.exists.return_value = True
        self.defaults = {'cost_center': 'Main - T', 'taxes_and_charges': 'VAT - T'}
        for target, value in [('db', self.db), ('get_meta', Mock(return_value=self.meta)),
                              ('get_cached_value', Mock(return_value='SAR')),
                              ('get_doc', Mock(return_value=NS(company='Test', disabled=0, is_group=0))),
                              ('throw', Mock(side_effect=validation_error))]:
            p = patch.object(dashboard.frappe, target, value)
            p.start(); self.addCleanup(p.stop)

    def mandatory_check(self, defaults=None, ep=None):
        return next(c for c in dashboard.readiness_for('Test', defaults or self.defaults, ep)
                    if c['label'] == 'Mandatory custom fields')

    def test_missing_link_has_actionable_guidance(self):
        c = self.mandatory_check()
        self.assertEqual(c['status'], 'Attention')
        for text in ('Sales Representative', 'custom_sales_representative_name', 'Sales Person',
                     'Client custom field defaults', 'REPLACE_WITH_VALID_VALUE', 'retry'):
            self.assertIn(text, c['detail'])

    def test_valid_link_default_clears_prerequisite(self):
        d = dashboard.business_defaults('Test', 'Main - T', 'VAT - T',
            {'custom_sales_representative_name': 'Approved Rep'})
        self.assertEqual(self.mandatory_check(d)['status'], 'Pass')
        self.db.exists.assert_called_with('Sales Person', 'Approved Rep')

    def test_unknown_link_is_rejected(self):
        self.db.exists.return_value = False
        with self.assertRaisesRegex(ValueError, 'Unknown link value'):
            dashboard.business_defaults('Test', 'Main - T', 'VAT - T',
                {'custom_sales_representative_name': 'Unknown Rep'})

    def test_select_guidance_and_invalid_option(self):
        self.fields[:] = [field(fieldtype='Select', options='\nRetail\nOnline')]
        self.assertIn('Retail, Online', self.mandatory_check()['detail'])
        with self.assertRaisesRegex(ValueError, 'Invalid option'):
            dashboard.business_defaults('Test', 'Main - T', 'VAT - T',
                {'custom_sales_representative_name': 'Unknown'})

    def test_default_fetch_and_mapping_remain_supported(self):
        for values in ({'default': 'Approved'}, {'fetch_from': 'customer.rep'}):
            self.fields[:] = [field(**values)]
            self.assertEqual(self.mandatory_check()['status'], 'Pass')
        self.fields[:] = [field()]
        ep = NS(field_maps=[NS(erp_field='custom_sales_representative_name')], pre_process_hook='',
                ignore_permissions=0, process_async=0)
        self.assertEqual(self.mandatory_check(ep=ep)['status'], 'Pass')

    def test_metadata_is_escaped_for_message_rendering(self):
        self.fields[:] = [field(label='<img src=x onerror=alert(1)>')]
        self.db.exists.return_value = False
        with patch.object(dashboard.frappe, 'only_for'), patch.object(dashboard.frappe, 'has_permission'):
            with self.assertRaises(ValueError) as error:
                dashboard.create_client.__wrapped__({'integration_name': 'Client', 'endpoint': 'test-client',
                    'company': 'Test', 'cost_center': 'Main - T', 'tax_template': 'VAT - T'})
        self.assertNotIn('<img', str(error.exception))
        self.assertIn('&lt;img', str(error.exception))

    def test_failed_onboarding_does_not_create_documents(self):
        self.db.exists.return_value = False
        with patch.object(dashboard.frappe, 'only_for'), patch.object(dashboard.frappe, 'has_permission'):
            with self.assertRaisesRegex(ValueError, 'Client custom field defaults'):
                dashboard.create_client.__wrapped__({'integration_name': 'Client', 'endpoint': 'test-client',
                    'company': 'Test', 'cost_center': 'Main - T', 'tax_template': 'VAT - T',
                    'custom_defaults': {}})
        self.assertEqual(dashboard.frappe.get_doc.call_count, 2)  # only the two master validations


if __name__ == '__main__':
    unittest.main()
