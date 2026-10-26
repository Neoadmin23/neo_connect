"""Central management of dedicated Magento API users and encrypted credentials."""
import json
import frappe
from frappe.utils import cint


def manager(config):
    frappe.only_for('System Manager')
    doc=frappe.get_doc('Magento Integration Settings',config)
    doc.check_permission('write')
    return doc


def member(doc,user):
    row=next((r for r in doc.users if r.user==user),None)
    if not row:
        frappe.throw('This user is not assigned to this integration',frappe.PermissionError)
    return row


@frappe.whitelist(methods=['POST'])
def add_user(config,email,first_name=None,can_create=1,can_submit=0):
    doc=manager(config)
    email=(email or '').strip().lower()
    if not email or '@' not in email or email in ('administrator','guest'):
        frappe.throw('Enter a dedicated API user email address')
    partner_name=frappe.db.get_value('API Partner',{'user':email,'magento_integration':doc.name},'name')
    if frappe.db.exists('User',email) and not partner_name:
        frappe.throw('Use a new email or an existing dedicated user from this integration; personal ERP users cannot be adopted')
    if any(r.user==email for r in doc.users):
        frappe.throw('This API user is already in the configuration')
    if not frappe.db.exists('User',email):
        user=frappe.get_doc(dict(doctype='User',email=email,first_name=first_name or 'Magento API',enabled=0,
                                user_type='System User',send_welcome_email=0))
        user.flags.no_welcome_mail=True
        user.insert(ignore_permissions=True)
    if not partner_name:
        partner=frappe.get_doc(dict(doctype='API Partner',partner_name=f'Magento {doc.name} {email}'[:140],
                                  user=email,magento_integration=doc.name,company=doc.company,platform='Magento',enabled=0,roles=''))
        partner.insert(ignore_permissions=True)
        partner_name=partner.name
    doc.append('users',dict(user=email,partner=partner_name,enabled=1,can_create=cint(can_create),can_submit=cint(can_submit)))
    doc.save()
    from neo_connect.audit import record_activity
    record_activity(doc.name,action='User Added',target_user=email,details=dict(can_create=bool(cint(can_create)),can_submit=bool(cint(can_submit))))
    return {'user':email,'configuration':doc.name}


@frappe.whitelist(methods=['POST'])
def remove_user(config,user):
    doc=manager(config)
    member(doc,user)
    doc.set('users',[r for r in doc.users if r.user!=user])
    doc.save()
    return {'user':user,'removed':True,'history_retained':True}


@frappe.whitelist(methods=['POST'])
def credentials(config,user,action='get_or_create'):
    doc=manager(config)
    member(doc,user)
    if action not in ('get_or_create','get','rotate','revoke'):
        frappe.throw('Unsupported credential action')
    from neo_connect.audit import record_activity
    if action=='revoke':
        row=member(doc,user)
        row.enabled=0
        doc.save()
        record_activity(doc.name,action='Credentials Revoked',target_user=user)
        return {'user':user,'revoked':True}
    account=frappe.get_doc('User',user)
    secret=account.get_password('api_secret',raise_exception=False)
    created=not account.api_key or not secret
    if created or action=='rotate':
        if not account.api_key:
            account.api_key=frappe.generate_hash(length=20)
        secret=frappe.generate_hash(length=40)
        account.api_secret=secret
        account.save(ignore_permissions=True)
        frappe.db.set_value('Magento API User',{'parent':doc.name,'user':user},'api_key',account.api_key)
        frappe.db.set_value('API Partner',member(doc,user).partner,'api_key',account.api_key)
    label='Credentials Created' if created else 'Credentials Rotated' if action=='rotate' else 'Credentials Revealed'
    record_activity(doc.name,action=label,target_user=user,details={'key_hint':account.api_key[-6:]})
    frappe.local.magento_no_store=True
    result=dict(user=user,api_key=account.api_key,api_secret=secret,
                authorization_header=f'token {account.api_key}:{secret}')
    partner=frappe.get_doc('API Partner',member(doc,user).partner)
    if partner.require_signature:
        result['signing_secret']=partner.get_password('signing_secret',raise_exception=False)
    return result
