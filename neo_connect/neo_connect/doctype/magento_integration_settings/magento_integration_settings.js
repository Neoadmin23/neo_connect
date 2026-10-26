frappe.ui.form.on('Magento Integration Settings', {
    refresh(frm) {
        frm.fields_dict.users.grid.cannot_add_rows = true;
        if (frm.is_new()) return;
        frm.add_custom_button(__('Activity Report'), () => frappe.set_route('query-report','Magento API Activity Report',{integration:frm.doc.name}));
        frm.add_custom_button(__('Trace Logs'), () => frappe.set_route('List','Magento API Activity',{integration:frm.doc.name}));
        if (!frappe.user.has_role('System Manager')) return;
        const method='neo_connect.management.';
        frm.add_custom_button(__('Add API User'), () => {
            const dialog=new frappe.ui.Dialog({title:__('Add dedicated API user'),fields:[
                {fieldname:'email',fieldtype:'Data',options:'Email',label:__('Email'),reqd:1},
                {fieldname:'first_name',fieldtype:'Data',label:__('Name'),reqd:1},
                {fieldname:'can_create',fieldtype:'Check',label:__('Create Invoices'),default:1},
                {fieldname:'can_submit',fieldtype:'Check',label:__('Submit Invoices'),default:0}],
                primary_action_label:__('Add User'),primary_action:values=>frappe.call({method:method+'add_user',args:{config:frm.doc.name,...values},freeze:true,
                    callback:()=>{dialog.hide();frm.reload_doc();}})});
            dialog.show();
        },__('Users'));
        const choose=(title,callback)=>{
            const users=(frm.doc.users||[]).map(r=>r.user);
            if (!users.length) return frappe.msgprint(__('Add an API user first.'));
            frappe.prompt([{fieldname:'user',fieldtype:'Select',options:users.join('\n'),label:__('API User'),reqd:1}],values=>callback(values.user),title);
        };
        const credentials=(action)=>choose(__('API credentials'),user=>frappe.call({method:method+'credentials',args:{config:frm.doc.name,user,action},freeze:true,
            callback:r=>{
                if (action==='revoke') {frm.reload_doc();return frappe.msgprint(__('Access revoked. Activity history is retained.'));}
                const value=r.message;
                const dialog=new frappe.ui.Dialog({title:__('Private API credentials'),fields:[
                    {fieldtype:'HTML',options:'<p>'+__('These credentials are private. Close this dialog after copying them.')+'</p>'},
                    {fieldname:'api_key',fieldtype:'Data',label:__('API Key'),read_only:1,default:value.api_key},
                    {fieldname:'api_secret',fieldtype:'Data',label:__('API Secret'),read_only:1,default:value.api_secret},
                    ...(value.signing_secret?[{fieldname:'signing_secret',fieldtype:'Data',label:__('HMAC Secret'),read_only:1,default:value.signing_secret}]:[])],
                    primary_action_label:__('Copy Authorization'),primary_action:()=>{
                        navigator.clipboard.writeText(value.authorization_header).then(()=>frappe.show_alert(__('Copied')));
                    }});
                dialog.show();frm.reload_doc();
            }}));
        frm.add_custom_button(__('Get / Create Credentials'),()=>credentials('get_or_create'),__('Credentials'));
        frm.add_custom_button(__('Rotate Secret'),()=>credentials('rotate'),__('Credentials'));
        frm.add_custom_button(__('Revoke Access'),()=>credentials('revoke'),__('Credentials'));
        frm.add_custom_button(__('Remove API User'),()=>choose(__('Remove user from integration'),user=>frappe.call({method:method+'remove_user',args:{config:frm.doc.name,user},freeze:true,
            callback:()=>{frm.reload_doc();frappe.show_alert(__('User access removed; history retained.'));}})),__('Users'));
        frm.add_custom_button(__('User Activity'),()=>choose(__('View user activity'),user=>frappe.set_route('query-report','Magento API Activity Report',{integration:frm.doc.name,api_user:user})),__('Users'));
    }
});
