import copy
import json
import unittest
from neo_connect.postman import build_bundle


class PostmanBundleTests(unittest.TestCase):
    def setUp(self):
        self.sample={'event':'invoice.created','items':[{'sku':'TEST','qty_ordered':1,'price':100}],'totals':{'grand_total':115}}
    def bundle(self,credentials=None,require_signature=False):
        return build_bundle('https://example.invalid/','client-invoices','Client','api@example.invalid',self.sample,credentials,require_signature)
    def test_template_has_no_credentials(self):
        b=self.bundle();v={x['key']:x for x in b['environment']['values']}
        self.assertFalse(b['contains_secrets'])
        for key in ('api_key','api_secret','signing_secret'):
            self.assertEqual(v[key]['value'],'');self.assertEqual(v[key]['type'],'secret')
    def test_private_secrets_only_in_environment(self):
        b=self.bundle({'api_key':'key-example','api_secret':'secret-example','signing_secret':'hmac-example'},True)
        for value in ('key-example','secret-example','hmac-example'):
            self.assertNotIn(value,json.dumps(b['collection']));self.assertIn(value,json.dumps(b['environment']))
    def test_does_not_mutate_input(self):
        before=copy.deepcopy(self.sample);self.bundle();self.assertEqual(before,self.sample)
    def test_validation_folder_never_writes_invoice(self):
        items=self.bundle()['collection']['item'][0]['item']
        self.assertEqual(len(items),2);self.assertEqual(items[0]['request']['method'],'GET');self.assertIn('dry_run=1',items[1]['request']['url'])
    def test_write_folder_explicitly_separated(self):
        folders=self.bundle()['collection']['item'];self.assertIn('creates accounting documents',folders[1]['name']);self.assertEqual(len(folders[1]['item']),3)
    def test_credential_environment_cannot_change_destination(self):
        b=self.bundle({'base_url':'https://evil.invalid','endpoint':'other','api_secret':'example'})
        v={x['key']:x['value'] for x in b['environment']['values']};self.assertEqual(v['base_url'],'https://example.invalid');self.assertEqual(v['endpoint'],'client-invoices')


if __name__=='__main__':unittest.main()
