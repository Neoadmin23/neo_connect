from frappe.model.document import Document

from neo_connect.engine.inbound import reference_name


class APIExternalReference(Document):
    def autoname(self):
        # deterministic key => the database primary key enforces one ERP document per external id
        scope = f"integration:{self.magento_integration}" if self.magento_integration else self.partner
        self.name = reference_name(scope, self.endpoint, self.external_id)
