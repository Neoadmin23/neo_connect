import json
import frappe
from frappe.model.document import Document
from frappe.utils import cint

class MagentoIntegrationSettings(Document):
    def validate(self):
        frappe.only_for('System Manager')
        if self.rate_limit_per_minute is not None and self.rate_limit_per_minute<0:
            frappe.throw('Rate limit cannot be negative')
        endpoint=frappe.get_doc('API Endpoint',self.endpoint)
        if endpoint.reference_doctype!='Sales Invoice' or endpoint.direction!='Inbound' or endpoint.ignore_permissions:
            frappe.throw('Select an inbound Sales Invoice endpoint with Ignore Permissions disabled')
        if endpoint.magento_integration and endpoint.magento_integration!=self.name:
            frappe.throw('The endpoint belongs to another Magento configuration')
        if endpoint.process_async:
            frappe.throw('Magento endpoints must process synchronously for invoice submission and complete traceability')
        defaults=json.loads(endpoint.defaults or '{}')
        if defaults.get('company') and defaults['company']!=self.company:
            frappe.throw('Endpoint defaults belong to another company')
        before=self.get_doc_before_save()
        if before and (before.company!=self.company or before.endpoint!=self.endpoint):
            frappe.throw('Company and endpoint cannot change; create a separate configuration')
        seen=set()
        for row in self.users:
            if row.user in seen or row.user in ('Administrator','Guest'):
                frappe.throw('Choose distinct dedicated API users')
            seen.add(row.user)
            partner=frappe.db.get_value('API Partner',{'user':row.user,'magento_integration':self.name},'name')
            if not partner:
                frappe.throw('Add users with the Add API User action; unrelated ERP users cannot be attached')
            row.partner=partner
            if frappe.db.exists('Magento API User',{'user':row.user,'parent':['!=',self.name]}):
                frappe.throw('A dedicated API user can belong to only one Magento configuration')
        base=frappe.utils.get_url()
        self.push_url=f'{base}/api/method/neo_connect.api.push?endpoint={self.endpoint}'
        self.submit_url=f'{base}/api/method/neo_connect.api.submit?endpoint={self.endpoint}'

    def on_update(self):
        from neo_connect.audit import record_activity
        before=self.get_doc_before_save()
        previous={r.user:r for r in before.users} if before else {}
        current={r.user:r for r in self.users}
        for user,row in previous.items():
            if user not in current:
                self.disable_user(user,row.partner)
                record_activity(self.name,action='User Removed',target_user=user,details={'history_retained':True})
        self.adopt_references()
        ep=frappe.get_doc('API Endpoint',self.endpoint)
        ep.magento_integration=self.name
        ep.allow_submit=cint(self.allow_submit)
        for row in self.users:
            self.sync_user(row)
            if row.partner not in [p.partner for p in ep.allowed_partners]:
                ep.append('allowed_partners',dict(partner=row.partner))
        ep.save(ignore_permissions=True)
        snapshot=lambda doc: {'enabled':cint(doc.enabled),'allow_submit':cint(doc.allow_submit),'company':doc.company,'endpoint':doc.endpoint,'allowed_ips':doc.allowed_ips,'rate_limit_per_minute':doc.rate_limit_per_minute,'require_signature':cint(doc.require_signature),
                              'users':[dict(user=r.user,enabled=cint(r.enabled),can_create=cint(r.can_create),can_submit=cint(r.can_submit)) for r in doc.users]}
        record_activity(self.name,action='Configuration Updated' if before else 'Configuration Created',
                        details={'before':snapshot(before) if before else None,'after':snapshot(self)})

    def sync_user(self,row):
        enabled=bool(cint(self.enabled) and cint(row.enabled))
        roles=['Magento API Reader']
        if enabled and row.can_create: roles.append('Magento API Writer')
        if enabled and self.allow_submit and row.can_submit: roles.append('Magento API Submitter')
        partner=frappe.get_doc('API Partner',row.partner)
        partner.update(dict(enabled=int(enabled),company=self.company,roles='\n'.join(roles),
                            allowed_ips=self.allowed_ips,rate_limit_per_minute=self.rate_limit_per_minute,
                            require_signature=self.require_signature))
        if self.require_signature and not partner.get_password('signing_secret',raise_exception=False):
            partner.signing_secret=frappe.generate_hash(length=40)
        partner.save(ignore_permissions=True)
        user=frappe.get_doc('User',row.user)
        user.enabled=int(enabled)
        user.set('roles',[dict(role=r) for r in roles] if enabled else [])
        user.save(ignore_permissions=True)
        row.api_key=user.api_key
        frappe.db.set_value('Magento API User',row.name,'api_key',user.api_key)
        if not frappe.db.exists('User Permission',dict(user=row.user,allow='Company',for_value=self.company)):
            frappe.get_doc(dict(doctype='User Permission',user=row.user,allow='Company',for_value=self.company,apply_to_all_doctypes=1)).insert(ignore_permissions=True)
        frappe.clear_cache(user=row.user)
        frappe.clear_document_cache('API Partner',partner.name)

    def disable_user(self,user_name,partner_name):
        if partner_name:
            frappe.db.set_value('API Partner',partner_name,'enabled',0)
            frappe.clear_document_cache('API Partner',partner_name)
        user=frappe.get_doc('User',user_name)
        user.enabled=0
        user.api_secret=frappe.generate_hash(length=40)
        user.set('roles',[])
        user.save(ignore_permissions=True)
        frappe.clear_cache(user=user_name)

    def adopt_references(self):
        from neo_connect.engine.inbound import reference_name
        legacy=frappe.get_all('API External Reference',filters={'endpoint':self.endpoint,'magento_integration':['is','not set']},
                              fields=['name','external_id','reference_doctype','reference_name'])
        changed=0
        for ref in legacy:
            if ref.reference_name:
                company=frappe.db.get_value(ref.reference_doctype,ref.reference_name,'company')
                if company and company!=self.company:
                    frappe.throw('This endpoint contains imports for another company; use a dedicated endpoint')
            new=reference_name(f'integration:{self.name}',self.endpoint,ref.external_id)
            existing=frappe.db.get_value('API External Reference',new,'reference_name')
            if existing and existing!=ref.reference_name:
                frappe.throw('An order has conflicting historical invoices; reconcile it before enabling central management')
            if new!=ref.name and not frappe.db.exists('API External Reference',new):
                frappe.db.set_value('API External Reference',ref.name,dict(name=new,magento_integration=self.name),update_modified=False)
            else:
                frappe.db.set_value('API External Reference',ref.name,'magento_integration',self.name,update_modified=False)
            changed+=1
        if changed:
            from neo_connect.audit import record_activity
            record_activity(self.name,action='References Adopted',details={'count':changed,'invoice_documents_changed':False})

    def on_trash(self):
        frappe.throw('Disable the configuration to retain its user and activity history',frappe.PermissionError)
