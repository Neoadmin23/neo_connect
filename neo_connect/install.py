"""Install dedicated API roles without replacing existing standard permissions."""
import frappe
from frappe.permissions import add_permission, update_permission_property

ROLES = {
    'Magento API Reader': {'Sales Invoice': ['read']},
    'Magento API Writer': {dt: ['read','create','write'] for dt in ('Sales Invoice','Customer','Contact','Address')},
    'Magento API Submitter': {'Sales Invoice': ['read','write','submit']},
}
READ_MASTERS = ('Company','Item','UOM','Item Group','Customer Group','Territory','Account','Currency','Cost Center',
                'Sales Taxes and Charges Template','Fiscal Year','Price List')

def after_install():
    after_migrate()

def after_migrate():
    for role, doctypes in ROLES.items():
        if not frappe.db.exists('Role',role):
            frappe.get_doc(dict(doctype='Role',role_name=role,desk_access=0)).insert(ignore_permissions=True)
        rights = dict(doctypes)
        if role == 'Magento API Reader':
            rights.update({dt:['read'] for dt in READ_MASTERS})
        for dt, permissions in rights.items():
            if not frappe.db.exists('Custom DocPerm',dict(parent=dt,role=role,permlevel=0)):
                add_permission(dt,role)
            for permission in ('read','create','write','submit','delete','cancel','amend','share','export'):
                update_permission_property(dt,role,0,permission,int(permission in permissions),validate=False)
        frappe.clear_cache()
    if frappe.db.table_exists('Magento API Activity'):
        for fields in (['integration','creation'],['api_user','creation'],['external_order_id'],['correlation_id']):
            frappe.db.add_index('Magento API Activity',fields)
