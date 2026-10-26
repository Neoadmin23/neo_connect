frappe.ui.form.on('Magento API Activity', {
    refresh(frm) {
        if(frm.doc.integration) frm.add_custom_button(__('Configuration'),()=>frappe.set_route('Form','Magento Integration Settings',frm.doc.integration));
        if(frm.doc.request_log) frm.add_custom_button(__('Request Log'),()=>frappe.set_route('Form','API Request Log',frm.doc.request_log));
        if(frm.doc.reference_doctype && frm.doc.reference_name) frm.add_custom_button(__('Document'),()=>frappe.set_route('Form',frm.doc.reference_doctype,frm.doc.reference_name));
        frm.add_custom_button(__('User Activity Report'),()=>frappe.set_route('query-report','Magento API Activity Report',{integration:frm.doc.integration,api_user:frm.doc.api_user}));
    }
});
