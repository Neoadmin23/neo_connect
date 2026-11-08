/* One Desk entry point for client setup, credential delivery and trace navigation. */
frappe.pages['magento-dashboard'].on_page_load = function(wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __('Magento Integration'), single_column: true});
    wrapper.magento_dashboard = new MagentoDashboard(page);
};
frappe.pages['magento-dashboard'].on_page_show = function(wrapper) {
    if (wrapper.magento_dashboard) wrapper.magento_dashboard.open_route();
};

class MagentoDashboard {
    constructor(page) {
        this.page = page; this.offset = 0; this.filters = {}; this.controls = {};
        this.root = $('<div class="magento-dashboard"></div>').appendTo(page.main);
        this.root.html(`<style>
            .magento-dashboard{padding:20px;max-width:1500px;margin:auto}
            .mg-hero{background:var(--subtle-fg);border:1px solid var(--border-color);border-radius:12px;padding:24px;margin-bottom:20px}
            .mg-hero h2{margin:0 0 8px}.mg-muted{color:var(--text-muted);font-size:13px}
            .mg-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}
            .mg-panel{background:var(--card-bg);border:1px solid var(--border-color);border-radius:10px;padding:18px;margin-bottom:18px;min-width:0}
            .mg-panel h4{margin:0 0 16px}.mg-actions{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
            .mg-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px;margin:18px 0}
            .mg-kpi{border:1px solid var(--border-color);border-radius:10px;padding:16px}.mg-kpi strong{display:block;font-size:26px;margin-top:6px}
            .mg-scroll{overflow:auto}.mg-table{width:100%;font-size:12px}.mg-table th,.mg-table td{padding:10px 9px;border-bottom:1px solid var(--border-color);white-space:nowrap}
            .mg-check{padding:9px 0;border-bottom:1px solid var(--border-color)}.mg-check b{display:inline-block;min-width:80px}
            .mg-filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:10px}
            .mg-tag{border-radius:12px;padding:3px 9px;background:var(--subtle-fg)}.mg-chart{min-height:230px}
            .mg-status .chart-legend{display:none}.mg-status-legend{display:flex;flex-wrap:wrap;gap:8px 14px;font-size:12px;margin:0 12px 12px}.mg-status-legend i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
            .mg-error{color:var(--red-600)}.mg-ok{color:var(--green-600)}
            @media(max-width:700px){.magento-dashboard{padding:10px}.mg-hero{padding:16px}}
        </style><section class="mg-hero"><div class="mg-muted">NEOCONNECT · COMPLETE ORDER INVOICES</div><h2>Magento client console</h2><p>Set up a client, deliver API credentials, and follow every request through to its invoice.</p><div class="mg-selector"></div><div class="mg-actions mg-client-actions"></div></section>
        <div class="mg-client"></div><section class="mg-panel"><h4>Activity monitor</h4><div class="mg-filters"></div><div class="mg-actions mg-monitor-actions"></div><div class="mg-kpis"></div><div class="mg-grid"><div class="mg-chart mg-status"></div><div class="mg-chart mg-daily"></div><div class="mg-chart mg-http"></div></div><div class="mg-user-summary mg-muted"></div><div class="mg-scroll mg-results"></div><div class="mg-actions mg-pagination"></div></section>`);
        page.set_secondary_action(__('Refresh'), () => this.reload());
        this.init();
    }
    esc(value) { return frappe.utils.escape_html(String(value ?? '')); }
    async api(method,args={}) { const r = await frappe.call({method:'neo_connect.dashboard.'+method,args}); return r.message; }
    button(target,label,action,primary=false) {
        return $('<button type="button" class="btn btn-sm"></button>').addClass(primary?'btn-primary':'btn-default').text(__(label)).appendTo(target).on('click',action);
    }
    control(parent,df) {
        const c=frappe.ui.form.make_control({parent,df,render_input:true}); c.refresh(); return c;
    }
    async init() {
        try {
            this.boot=await this.api('bootstrap');
            this.selector=this.control(this.root.find('.mg-selector'),{fieldname:'client',fieldtype:'Select',label:__('Client configuration'),options:['',...this.boot.clients.map(c=>c.name)].join('\n'),change:()=>this.select_client()});
            if(this.boot.can_manage) this.button(this.root.find('.mg-client-actions'),'Set up new client',()=>this.setup(),true);
            const fields=[['from_date','From','Date',this.boot.from_date],['to_date','To','Date',this.boot.today],['api_user','API user','Link','', 'User'],['status','Status','Select','','\nSuccess\nDenied\nFailed\nDuplicate\nDry Run'],['http_status','HTTP status','Int',''],['external_order_id','Magento order','Data',''],['reference_name','ERP document','Data',''],['correlation_id','Trace ID','Data',''],['action','Action','Data','']];
            fields.forEach(([fieldname,label,fieldtype,value,options])=>{
                this.controls[fieldname]=this.control(this.root.find('.mg-filters'),{fieldname,label:__(label),fieldtype,options});
                this.controls[fieldname].set_value(value);
            });
            this.button(this.root.find('.mg-monitor-actions'),'Apply filters',()=>{this.offset=0;this.monitor();},true);
            this.button(this.root.find('.mg-monitor-actions'),'Activity report',()=>frappe.set_route('query-report','Magento API Activity Report',this.filter_values()));
            this.button(this.root.find('.mg-monitor-actions'),'Trace logs',()=>frappe.set_route('List','Magento API Activity',this.selector.get_value()?{integration:this.selector.get_value()}:{}));
            this.ready=true; await this.open_route();
        } catch(e) { this.root.find('.mg-client').text(__('Unable to load the dashboard. Check your System Manager or Accounts Manager role.')); }
    }
    async open_route() {
        if(!this.ready)return;
        const route=frappe.route_options || {}; const name=route.integration;
        if(name && this.boot.clients.some(c=>c.name===name)){frappe.route_options=null;await this.selector.set_value(name);}
        else if(!this.selector.get_value() && this.boot.clients.length===1) await this.selector.set_value(this.boot.clients[0].name);
        await this.select_client();
    }
    async reload() {
        if(!this.ready)return;
        this.boot=await this.api('bootstrap');
        this.selector.df.options=['',...this.boot.clients.map(c=>c.name)].join('\n');this.selector.refresh();
        await this.select_client();
    }
    async select_client() {
        if(!this.ready)return;
        const name=this.selector.get_value(); const serial=this.client_serial=(this.client_serial||0)+1;
        this.offset=0;
        if(name){const data=await this.api('client',{config:name});if(serial!==this.client_serial)return;this.current=data;this.render_client();}
        else {this.current=null;this.root.find('.mg-client').html('<p class="mg-muted">Select a client to review setup and API users. The monitor below covers all configurations you can read.</p>');}
        await this.monitor();
    }
    render_client() {
        const c=this.current, e=v=>this.esc(v), box=this.root.find('.mg-client').empty();
        const grid=$('<div class="mg-grid"></div>').appendTo(box);
        const setup=$('<section class="mg-panel"></section>').appendTo(grid);
        setup.html(`<h4>${e(c.name)} <span class="mg-tag">${c.security.enabled?'Enabled':'Disabled'}</span></h4><p>${e(c.company)} · ${e(c.endpoint)}</p><p class="mg-muted">HMAC: ${c.security.require_signature?'Required':'Off'} · Rate: ${e(c.security.rate_limit_per_minute||'Unlimited')}/minute</p><p class="mg-muted">IP rules: ${e(c.security.allowed_ips||'Any source IP')}</p><div class="mg-actions"></div><details><summary>API URLs</summary><p style="overflow-wrap:anywhere">${e(c.push_url)}</p><p style="overflow-wrap:anywhere">${e(c.submit_url)}</p></details>`);
        const actions=setup.find('.mg-actions');
        if(this.boot.can_manage)this.button(actions,'Edit setup & security',()=>this.edit_client());
        this.button(actions,'Configuration form',()=>frappe.set_route('Form','Magento Integration Settings',c.name));
        const readiness=$('<section class="mg-panel"><h4>Setup checks</h4></section>').appendTo(grid);
        c.readiness.forEach(r=>readiness.append(`<div class="mg-check"><b class="${r.status==='Pass'?'mg-ok':'mg-error'}">${e(r.status)}</b>${e(r.label)}<div class="mg-muted">${e(r.detail)}</div></div>`));
        readiness.append('<p class="mg-muted" style="margin-top:12px">These are static checks. Run the exported Postman validation against real client SKUs and agreed tax totals before enabling production traffic.</p>');
        const users=$('<section class="mg-panel"><h4>Dedicated API users</h4><div class="mg-actions"></div><div class="mg-scroll"></div></section>').appendTo(box);
        if(this.boot.can_manage)this.button(users.find('.mg-actions'),'Add API user',()=>this.add_user());
        const table=$('<table class="mg-table"><thead><tr><th>User</th><th>Enabled</th><th>Create</th><th>Submit</th><th>Actions</th></tr></thead><tbody></tbody></table>').appendTo(users.find('.mg-scroll'));
        c.users.forEach(u=>{
            const row=$('<tr></tr>').appendTo(table.find('tbody'));
            row.append(`<td>${e(u.user)}</td><td>${u.enabled?'Yes':'No'}</td><td>${u.can_create?'Yes':'No'}</td><td>${u.can_submit?'Yes':'No'}</td>`);
            const cell=$('<td><div class="mg-actions"></div></td>').appendTo(row).find('div');
            this.button(cell,'Activity',()=>{this.controls.api_user.set_value(u.user);this.offset=0;this.monitor();});
            if(this.boot.can_manage){
                this.button(cell,'Access',()=>this.edit_user(u));
                this.button(cell,'Postman downloads',()=>this.downloads(u));
                this.button(cell,'Rotate secret',()=>frappe.confirm(__('Rotate this user’s API secret? Existing API tokens will stop working.'),async()=>{await frappe.call({method:'neo_connect.management.credentials',args:{config:c.name,user:u.user,action:'rotate'}});frappe.msgprint(__('Secret rotated. Download a new private environment and update the Magento client.'));await this.select_client();}));
                this.button(cell,'Revoke',()=>frappe.confirm(__('Disable this user’s API access?'),()=>this.manage('credentials',{user:u.user,action:'revoke'})));
                this.button(cell,'Remove',()=>frappe.confirm(__('Remove this user from the integration and invalidate its token? User and activity history are retained.'),()=>this.manage('remove_user',{user:u.user})));
            }
        });
        if(!c.users.length) users.find('.mg-scroll').append('<p class="mg-muted">No API users yet. Add a dedicated user before downloading credentials.</p>');
    }
    security_fields(values={}) {
        return [
            {fieldname:'enabled',fieldtype:'Check',label:__('Enable API access'),default:values.enabled||0},
            {fieldname:'allow_submit',fieldtype:'Check',label:__('Allow invoice submission'),default:values.allow_submit??1},
            {fieldname:'require_signature',fieldtype:'Check',label:__('Require HMAC signature'),default:values.require_signature||0},
            {fieldname:'allowed_ips',fieldtype:'Small Text',label:__('Allowed IPs / CIDR'),description:__('One per line. Blank permits any source IP; confirm the IP seen by your hosting proxy.'),default:values.allowed_ips||''},
            {fieldname:'rate_limit_per_minute',fieldtype:'Int',label:__('Requests per minute per user'),default:values.rate_limit_per_minute??120,description:__('0 means unlimited. Shared across gateway routes within each minute.')}
        ];
    }
    business_fields(company,defaults={}) {
        return [
            {fieldname:'cost_center',fieldtype:'Link',options:'Cost Center',label:__('Cost center'),reqd:1,default:defaults.cost_center,get_query:()=>({filters:{company:typeof company==='function'?company():company,is_group:0,disabled:0}})},
            {fieldname:'tax_template',fieldtype:'Link',options:'Sales Taxes and Charges Template',label:__('Sales tax template'),reqd:1,default:defaults.taxes_and_charges,get_query:()=>({filters:{company:typeof company==='function'?company():company,disabled:0}})},
            {fieldname:'custom_defaults',fieldtype:'Code',options:'JSON',label:__('Client custom field defaults'),default:JSON.stringify(Object.fromEntries(Object.entries(defaults).filter(([k])=>k.startsWith('custom_'))),null,2),description:__('Required Sales Invoice custom fields must be supplied here, for example {"custom_sales_representative_name": "EXACT EXISTING VALUE"}. Use the exact existing record name for Link fields or an allowed Select option. Values are client-specific; do not copy sandbox defaults without confirmation.')}
        ];
    }
    setup() {
        const dialog=new frappe.ui.Dialog({title:__('Set up Magento client'),size:'large',fields:[
            {fieldtype:'HTML',options:'<p>Create a separate configuration and endpoint for each client. New clients start disabled. The current complete-order contract supports SAR invoices.</p>'},
            {fieldname:'integration_name',fieldtype:'Data',label:__('Client name'),reqd:1},
            {fieldname:'company',fieldtype:'Link',options:'Company',label:__('Company'),reqd:1},
            {fieldname:'endpoint',fieldtype:'Data',label:__('Unique endpoint slug'),reqd:1,description:__('Lowercase letters, digits and hyphens; for example client-magento-invoices.')},
            ...this.business_fields(()=>dialog.get_value('company')),
            ...this.security_fields().filter(f=>f.fieldname!=='enabled')],primary_action_label:__('Create disabled client'),primary_action:async values=>{
                dialog.disable_primary_action();try{const r=await this.api('create_client',{values:JSON.stringify(values)});dialog.hide();await this.reload();await this.selector.set_value(r.name);frappe.msgprint(r.message);}catch(error){
                    // frappe.call already displays the server validation message. Keep entered values for correction.
                }finally{dialog.enable_primary_action();}
            }});dialog.show();
    }
    edit_client() {
        const c=this.current;
        const dialog=new frappe.ui.Dialog({title:__('Client setup & security'),size:'large',fields:[...this.business_fields(c.company,c.defaults),...this.security_fields(c.security)],primary_action_label:__('Save setup'),primary_action:async values=>{
            dialog.disable_primary_action();try{await this.api('save_client',{config:c.name,values:JSON.stringify(values)});dialog.hide();await this.select_client();}catch(error){
                // frappe.call displays validation failures; the dialog remains available for correction.
            }finally{dialog.enable_primary_action();}
        }});dialog.show();
    }
    async manage(method,args) {await frappe.call({method:'neo_connect.management.'+method,args:{config:this.current.name,...args},freeze:true});await this.select_client();}
    add_user() {
        const d=new frappe.ui.Dialog({title:__('Add dedicated API user'),fields:[
            {fieldname:'email',fieldtype:'Data',options:'Email',label:__('Email'),reqd:1},
            {fieldname:'first_name',fieldtype:'Data',label:__('Display name'),reqd:1},
            {fieldname:'can_create',fieldtype:'Check',label:__('Create invoices'),default:1},
            {fieldname:'can_submit',fieldtype:'Check',label:__('Submit invoices'),default:0}],primary_action_label:__('Add user'),primary_action:async v=>{d.disable_primary_action();try{await this.manage('add_user',v);d.hide();}finally{d.enable_primary_action();}}});d.show();
    }
    edit_user(u) {
        const d=new frappe.ui.Dialog({title:__('API user access'),fields:['enabled','can_create','can_submit'].map((k,i)=>({fieldname:k,fieldtype:'Check',label:__([ 'Enabled','Create invoices','Submit invoices'][i]),default:u[k]})),primary_action_label:__('Save access'),primary_action:async v=>{await this.api('set_user',{config:this.current.name,user:u.user,...v});d.hide();await this.select_client();}});d.show();
    }
    downloads(u) {
        const config=this.current.name;
        const d=new frappe.ui.Dialog({title:__('Download Postman files'),fields:[
            {fieldtype:'HTML',options:'<p>The collection contains a validation folder and a separate folder that creates/submits invoices. Set the sample SKU and tax totals before running it.</p><p><b>A private environment contains reusable API credentials.</b> Share it only with the intended Magento developer through an approved secure channel.</p>'},
            {fieldname:'include_secrets',fieldtype:'Check',label:__('Include API key, secret and HMAC secret in private environment'),default:0}],primary_action_label:__('Generate downloads'),primary_action:async v=>{
                d.disable_primary_action();try{
                    const bundle=await this.api('postman_bundle',{config,user:u.user,include_secrets:v.include_secrets});
                    const body=$('<div></div>');
                    const links=[];
                    [['Collection',bundle.collection,'postman_collection.json'],['Environment',bundle.environment,bundle.contains_secrets?'PRIVATE.postman_environment.json':'postman_environment.json']].forEach(([label,data,suffix])=>{
                        const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));links.push(url);
                        $('<a class="btn btn-primary btn-sm" style="margin:8px"></a>').text(__('Download ')+label).attr({href:url,download:config.replace(/[^a-z0-9-]/gi,'_')+'.'+suffix}).appendTo(body);
                    });
                    const ready=new frappe.ui.Dialog({title:__('Postman files ready'),fields:[{fieldname:'downloads',fieldtype:'HTML'}]});
                    ready.fields_dict.downloads.$wrapper.append(body);ready.onhide=()=>{links.forEach(url=>URL.revokeObjectURL(url));body.empty();};
                    d.hide();ready.show();
                }finally{d.enable_primary_action();}
            }});d.show();
    }
    filter_values() {
        const f=Object.fromEntries(Object.entries(this.controls).map(([k,c])=>[k,c.get_value()]).filter(([,v])=>v!=='' && v!=null));
        if(this.selector.get_value())f.integration=this.selector.get_value();return f;
    }
    async monitor() {
        const serial=this.monitor_serial=(this.monitor_serial||0)+1;
        const result=await this.api('overview',{filters:JSON.stringify(this.filter_values()),start:this.offset,page_length:25});
        if(serial!==this.monitor_serial)return;
        const counts=Object.fromEntries(result.statuses.map(x=>[x.status,x.count]));
        this.root.find('.mg-kpis').html([['Activities',result.total],['Success',counts.Success||0],['Denied',counts.Denied||0],['Failed',counts.Failed||0],['Duplicate',counts.Duplicate||0],['Average ms',Math.round(result.average_ms)]].map(([k,v])=>`<div class="mg-kpi"><span class="mg-muted">${this.esc(k)}</span><strong>${this.esc(v)}</strong></div>`).join(''));
        const statusColors={Success:'#318565',Denied:'#c34c4c',Failed:'#d59025',Duplicate:'#7863ae','Dry Run':'#3478b5'};
        const chart=(selector,title,labels,values,type)=>{
            const el=this.root.find(selector).empty()[0];
            if(!labels.length){$(el).text(__('No matching activity'));return;}
            new frappe.Chart(el,{title,type,height:230,data:{labels,datasets:[{name:__('Activities'),values}]},colors:selector==='.mg-status'?labels.map(s=>statusColors[s]||'#3478b5'):['#3478b5'],axisOptions:{xIsSeries:1}});
        };
        chart('.mg-status','Outcome distribution',result.statuses.map(x=>x.status||'Unknown'),result.statuses.map(x=>x.count),'donut');
        this.root.find('.mg-status').append('<div class="mg-status-legend">'+result.statuses.map(x=>`<span><i style="background:${statusColors[x.status]||'#3478b5'}"></i>${this.esc(x.status)}: ${this.esc(x.count)}</span>`).join('')+'</div>');
        chart('.mg-daily','Activity by day',result.daily.map(x=>x.day),result.daily.map(x=>x.count),result.daily.length>1?'line':'bar');
        chart('.mg-http','HTTP responses',result.http.filter(x=>x.http_status).map(x=>String(x.http_status)),result.http.filter(x=>x.http_status).map(x=>x.count),'bar');
        this.root.find('.mg-user-summary').text('Top users: '+result.users.map(x=>(x.api_user||'Administrative activity')+' ('+x.count+')').join(' · '));
        const link=(dt,name,label)=>name?`<a href="/app/${frappe.router.slug(dt)}/${encodeURIComponent(name)}">${this.esc(label||name)}</a>`:'';
        this.root.find('.mg-results').html(`<table class="mg-table"><thead><tr>${['Time','User / actor','Action','Outcome','HTTP','ms','Order','Invoice','Trace','Request log','Source IP'].map(h=>'<th>'+this.esc(h)+'</th>').join('')}</tr></thead><tbody>${result.rows.map(r=>`<tr><td>${this.esc(r.creation)}</td><td>${this.esc(r.api_user||r.actor)}</td><td>${this.esc(r.action)}</td><td>${this.esc(r.status)}</td><td>${this.esc(r.http_status||'')}</td><td>${Math.round(r.duration_ms||0)}</td><td>${this.esc(r.external_order_id)}</td><td>${link(r.reference_doctype,r.reference_name)}</td><td>${link('Magento API Activity',r.name,r.correlation_id)}</td><td>${link('API Request Log',r.request_log)}</td><td>${this.esc(r.request_ip)}</td></tr>`).join('')}</tbody></table>`);
        const nav=this.root.find('.mg-pagination').empty();
        this.button(nav,'Previous',()=>{this.offset=Math.max(0,this.offset-25);this.monitor();}).prop('disabled',!this.offset);
        $('<span class="mg-muted"></span>').text(result.total?`${this.offset+1}–${this.offset+result.rows.length} of ${result.total}`:'No matching activity').appendTo(nav);
        this.button(nav,'Next',()=>{this.offset+=25;this.monitor();}).prop('disabled',this.offset+25>=result.total);
        $('<span class="mg-muted"></span>').text('Charts and totals cover all matching activity, including administrative events.').appendTo(nav);
    }
}
