"""Managed Magento credentials are restricted to their configured gateway."""
import frappe
from frappe.utils import cint

ALLOWED={'neo_connect.api.ping','neo_connect.api.push','neo_connect.api.submit'}


def identity(user=None,api_key=None):
    if not frappe.db.exists('DocType','Magento Integration Settings'):
        return None
    user=user or (getattr(frappe.session,'user',None) if getattr(frappe.local,'session',None) else None)
    if (not user or user=='Guest') and api_key:
        user=frappe.db.get_value('User',{'api_key':api_key},'name')
    if not user or user=='Guest': return None
    partner=frappe.db.get_value('API Partner',{'user':user,'magento_integration':['is','set']},
                                ['name','magento_integration','company'],as_dict=True)
    if not partner: return None
    row=frappe.db.get_value('Magento API User',{'parent':partner.magento_integration,'user':user},
                            ['name','enabled','can_create','can_submit'],as_dict=True)
    return frappe._dict(user=user,partner=partner.name,integration=partner.magento_integration,company=partner.company,row=row)


def enforce_managed_user():
    info=identity()
    if not info: return
    frappe.local.magento_identity=info
    config=frappe.get_cached_doc('Magento Integration Settings',info.integration)
    if not config.enabled or not info.row or not info.row.enabled:
        frappe.throw('Magento API access is disabled for this user or integration',frappe.PermissionError)
    method=frappe.request.path.removeprefix('/api/method/')
    if method not in ALLOWED or frappe.form_dict.get('cmd'):
        frappe.throw('Dedicated Magento users may only call the configured gateway methods',frappe.PermissionError)
    if method!='neo_connect.api.ping' and frappe.request.args.get('endpoint')!=config.endpoint:
        frappe.throw('This API user cannot access that endpoint',frappe.PermissionError)
    if method=='neo_connect.api.push' and not info.row.can_create:
        frappe.throw('Invoice creation is disabled for this API user',frappe.PermissionError)
    ep=frappe.get_cached_doc('API Endpoint',config.endpoint)
    submitting=(method=='neo_connect.api.submit' or (method=='neo_connect.api.push' and
                (frappe.request.args.get('submit')=='1' or ep.document_action=='Submit')))
    if submitting and (not config.allow_submit or not info.row.can_submit):
        frappe.throw('Invoice submission is disabled for this API user',frappe.PermissionError)
    if method=='neo_connect.api.ping':
        from neo_connect.engine.security import check_ip,check_rate_limit
        partner=frappe.get_cached_doc('API Partner',info.partner)
        check_ip(partner)
        check_rate_limit(partner)


def enforce_endpoint(endpoint,partner):
    config=getattr(endpoint,'magento_integration',None)
    if config:
        info=identity(partner.user)
        if not info or info.integration!=config or not info.row or not info.row.enabled:
            from neo_connect.engine.security import GatewayError
            raise GatewayError('This user is not active in the endpoint configuration',403)
        settings=frappe.get_cached_doc('Magento Integration Settings',config)
        if not settings.enabled:
            from neo_connect.engine.security import GatewayError
            raise GatewayError('Magento integration is disabled',403)


def reference_scope(partner):
    config=getattr(partner,'magento_integration',None)
    return f'integration:{config}' if config else partner.name
