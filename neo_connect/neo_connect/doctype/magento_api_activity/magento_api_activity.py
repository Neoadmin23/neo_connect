import frappe
from frappe.model.document import Document

class MagentoAPIActivity(Document):
    def before_insert(self):
        if not getattr(frappe.flags, 'magento_audit_write', False):
            frappe.throw('Activity records are created by the integration audit service only', frappe.PermissionError)
    def before_save(self):
        if not self.is_new():
            frappe.throw('Magento activity records cannot be edited', frappe.PermissionError)
    def on_trash(self):
        frappe.throw('Magento activity history cannot be deleted through the application', frappe.PermissionError)
