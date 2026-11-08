"""Permission-checked Magento onboarding, delivery bundles and operational metrics."""
from html import escape
import ipaddress
import json
import re

import frappe
from frappe.utils import add_days, cint, getdate, nowdate

from neo_connect.management import manager, member


def reader(config=None):
    frappe.only_for(['System Manager', 'Accounts Manager'])
    frappe.has_permission('Magento Integration Settings', 'read', throw=True)
    if config:
        doc=frappe.get_doc('Magento Integration Settings',config)
        doc.check_permission('read')
        return doc


def object_value(value):
    value=json.loads(value) if isinstance(value,str) else value
    if not isinstance(value,dict):frappe.throw('Expected a JSON object')
    return value


def security_values(values):
    result={k:cint(values.get(k)) for k in ('enabled','allow_submit','require_signature')}
    for k in result:
        if result[k] not in (0,1):frappe.throw('Security switches must be 0 or 1')
    rate=cint(values.get('rate_limit_per_minute',120))
    if not 0 <= rate <= 100000:frappe.throw('Requests per minute must be between 0 and 100000; 0 means unlimited')
    rules=[x.strip() for x in str(values.get('allowed_ips') or '').replace(',', '\n').splitlines() if x.strip()]
    for rule in rules:
        try:ipaddress.ip_network(rule,strict=False)
        except ValueError:frappe.throw('Invalid IP address or CIDR: '+rule)
    result.update(allowed_ips='\n'.join(rules),rate_limit_per_minute=rate)
    return result


def business_defaults(company,cost_center,tax_template,custom_defaults=None):
    cc=frappe.get_doc('Cost Center',cost_center)
    if cc.company!=company or cc.is_group or cc.disabled:frappe.throw('Choose an enabled non-group cost center in the selected company')
    tax=frappe.get_doc('Sales Taxes and Charges Template',tax_template)
    if tax.company!=company or tax.disabled:frappe.throw('Choose an enabled sales tax template in the selected company')
    if frappe.get_cached_value('Company',company,'default_currency')!='SAR':
        frappe.throw('The complete-order contract currently supports SAR companies only')
    custom=object_value(custom_defaults or {})
    meta=frappe.get_meta('Sales Invoice')
    for key,value in custom.items():
        df=meta.get_field(key)
        if not key.startswith('custom_') or not df or df.fieldtype not in ('Data','Select','Link','Int','Float','Currency','Check','Small Text','Text'):
            frappe.throw('Only scalar Sales Invoice custom-field defaults are supported: '+key)
        if isinstance(value,(dict,list)):frappe.throw('Custom defaults must be scalar values')
        if df.fieldtype=='Select' and value and str(value) not in (df.options or '').splitlines():frappe.throw('Invalid option for '+key)
        if df.fieldtype=='Link' and value and not frappe.db.exists(df.options,value):frappe.throw('Unknown link value for '+key)
    return dict(custom,company=company,cost_center=cost_center,**{'items.cost_center':cost_center,'taxes_and_charges':tax_template})


def readiness_for(company,defaults,ep=None):
    """Static checks complement (never replace) a native invoice dry run."""
    checks=[]
    def add(label,ok,detail):checks.append(dict(label=label,status='Pass' if ok else 'Attention',detail=detail))
    cc=frappe.db.get_value('Cost Center',defaults.get('cost_center'),['company','disabled','is_group'],as_dict=True)
    add('Cost center',bool(cc and cc.company==company and not cc.disabled and not cc.is_group),'Use an enabled, non-group cost center for this company.')
    tax=frappe.db.get_value('Sales Taxes and Charges Template',defaults.get('taxes_and_charges'),['company','disabled'],as_dict=True)
    add('Tax template',bool(tax and tax.company==company and not tax.disabled),'Confirm the template reconciles with Magento line and order totals.')
    meta=frappe.get_meta('Sales Invoice')
    mapped={m.erp_field for m in ep.field_maps} if ep else set()
    missing=[df for df in meta.fields if df.reqd and df.fieldname.startswith('custom_') and not df.default and not df.fetch_from and defaults.get(df.fieldname) in (None,'') and df.fieldname not in mapped]
    instructions=[]
    for df in missing:
        detail=f'{df.label or df.fieldname} ({df.fieldname})'
        if df.fieldtype=='Link':
            detail+=f': use the exact name of an existing {df.options} record'
        elif df.fieldtype=='Select':
            detail+=': choose one of '+', '.join(x for x in (df.options or '').splitlines() if x)
        else:
            detail+=': supply a value agreed with the client'
        instructions.append(detail)
    detail=('Set these required Sales Invoice fields in Client custom field defaults (JSON): '
        + '; '.join(instructions)+'. Example structure: '+json.dumps({df.fieldname:'REPLACE_WITH_VALID_VALUE' for df in missing})
        + '. Keep the fields mandatory; then retry Create disabled client.') if missing else 'No unconfigured mandatory header custom fields found.'
    add('Mandatory custom fields',not missing,detail)
    stale=[]
    for df in meta.fields:
        if not df.fetch_from or '.' not in df.fetch_from:continue
        link,field=df.fetch_from.split('.',1);source=meta.get_field(link)
        if source and source.fieldtype=='Link' and source.options and not frappe.get_meta(source.options).has_field(field):stale.append(df.fieldname+' → '+df.fetch_from)
    add('Fetch references',not stale,'; '.join(stale) or 'Static linked-field references resolve.')
    if ep:
        hooks=(ep.pre_process_hook or '').splitlines()
        prepare='neo_connect.handlers.powertire.prepare_invoice';center='neo_connect.handlers.commerce.ensure_cost_center'
        add('Tax-row cost center hook',prepare in hooks and center in hooks and hooks.index(center)>hooks.index(prepare),'ensure_cost_center must run after prepare_invoice.')
        add('Native permissions',not ep.ignore_permissions and not ep.process_async,'Synchronous processing with native ERP permissions is required.')
    return checks


@frappe.whitelist()
def bootstrap():
    reader()
    return dict(can_manage='System Manager' in frappe.get_roles(),
        clients=frappe.get_list('Magento Integration Settings',fields=['name','company','endpoint','enabled'],order_by='name',limit_page_length=0),
        today=nowdate(),from_date=add_days(nowdate(),-7))


@frappe.whitelist()
def client(config):
    doc=reader(config);ep=frappe.get_doc('API Endpoint',doc.endpoint)
    defaults=json.loads(ep.defaults or '{}')
    return dict(name=doc.name,company=doc.company,endpoint=doc.endpoint,
        security={k:doc.get(k) for k in ('enabled','allow_submit','allowed_ips','rate_limit_per_minute','require_signature')},
        users=[{k:r.get(k) for k in ('user','enabled','can_create','can_submit')} for r in doc.users],
        defaults={k:v for k,v in defaults.items() if k in ('cost_center','taxes_and_charges') or k.startswith('custom_')},
        readiness=readiness_for(doc.company,defaults,ep),push_url=doc.push_url,submit_url=doc.submit_url)


@frappe.whitelist(methods=['POST'])
def create_client(values):
    frappe.only_for('System Manager')
    frappe.has_permission('Magento Integration Settings','create',throw=True)
    v=object_value(values)
    name=(v.get('integration_name') or '').strip();slug=(v.get('endpoint') or '').strip()
    if not name or len(name)>100 or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,99}',slug):frappe.throw('Supply a client name and a unique lowercase endpoint slug (3–100 characters)')
    if frappe.db.exists('Magento Integration Settings',name) or frappe.db.exists('API Endpoint',slug):frappe.throw('Client or endpoint already exists; open its configuration instead')
    defaults=business_defaults(v.get('company'),v.get('cost_center'),v.get('tax_template'),v.get('custom_defaults'))
    checks=readiness_for(v['company'],defaults)
    if any(c['status']=='Attention' for c in checks):frappe.throw(escape('Resolve setup prerequisites first: '+ '; '.join(c['detail'] for c in checks if c['status']=='Attention')))
    security=security_values(dict(v,enabled=0))
    from neo_connect.engine.packs import load_bundled,install_pack
    pack=load_bundled('powertire_complete_order_invoice.json')
    pack['endpoint']['endpoint_title']=name+' sales invoice'
    pack['endpoint']['defaults'].update(defaults)
    pack['endpoint']['pre_process_hook']='neo_connect.handlers.powertire.prepare_invoice\nneo_connect.handlers.commerce.ensure_cost_center'
    pack['endpoint']['handler_settings'].update(cost_center_default=v['cost_center'],create_cost_center=0)
    # Disabled bootstrap has no user or credentials. The managed user is the only API principal.
    partner=frappe.get_doc(dict(doctype='API Partner',partner_name='Setup '+slug,company=v['company'],platform='Magento',enabled=0,roles='')).insert()
    install_pack(pack,partner.name,slug=slug)
    doc=frappe.get_doc(dict(doctype='Magento Integration Settings',integration_name=name,company=v['company'],endpoint=slug,**security)).insert()
    return dict(name=doc.name,enabled=False,message='Client created disabled. Add a dedicated user, review defaults, then enable access and run Validation in Postman.')


@frappe.whitelist(methods=['POST'])
def save_client(config,values):
    doc=manager(config);v=object_value(values)
    # Validate everything before mutating either document.
    security=security_values(v)
    ep=frappe.get_doc('API Endpoint',doc.endpoint)
    defaults=json.loads(ep.defaults or '{}')
    business=business_defaults(doc.company,v.get('cost_center'),v.get('tax_template'),v.get('custom_defaults'))
    for key in list(defaults):
        if key.startswith('custom_'):del defaults[key]
    defaults.update(business)
    ep.defaults=json.dumps(defaults)
    settings=json.loads(ep.handler_settings or '{}');settings.update(cost_center_default=v['cost_center'],create_cost_center=0)
    ep.handler_settings=json.dumps(settings)
    hooks=[h.strip() for h in (ep.pre_process_hook or '').splitlines() if h.strip() and h.strip()!='neo_connect.handlers.commerce.ensure_cost_center']
    if 'neo_connect.handlers.powertire.prepare_invoice' not in hooks:frappe.throw('This dashboard requires the complete-order prepare_invoice handler')
    hooks.append('neo_connect.handlers.commerce.ensure_cost_center');ep.pre_process_hook='\n'.join(hooks)
    ep.save();doc.update(security);doc.save()
    from neo_connect.audit import record_activity
    record_activity(config,action='Setup Updated',details={'cost_center':v['cost_center'],'tax_template':v['tax_template'],'custom_default_fields':list(object_value(v.get('custom_defaults') or {}))})
    return client(config)


@frappe.whitelist(methods=['POST'])
def set_user(config,user,enabled=1,can_create=1,can_submit=0):
    doc=manager(config);row=member(doc,user)
    for key,value in dict(enabled=enabled,can_create=can_create,can_submit=can_submit).items():
        if cint(value) not in (0,1):frappe.throw('User permissions must be 0 or 1')
        row.set(key,cint(value))
    doc.save()
    return {'user':user,'updated':True}


@frappe.whitelist(methods=['POST'])
def postman_bundle(config,user,include_secrets=0):
    # Even a blank bundle is manager-only: the sample payload can contain client data.
    doc=manager(config);member(doc,user)
    frappe.local.magento_no_store=True
    from neo_connect.postman import build_bundle
    from neo_connect.management import credentials
    from neo_connect.audit import record_activity
    creds=credentials(config,user) if cint(include_secrets) else None
    # Export a synthetic customer, never the endpoint's real customer/address/payment metadata.
    from neo_connect.engine.packs import load_bundled
    clean=load_bundled('powertire_complete_order_invoice.json')['sample_payloads'][0]
    clean={k:clean[k] for k in ('event','order_number','invoice_number','order_date','invoice_date','order_currency_code','items','totals')}
    clean['customer']={'email':'magento-test@example.invalid','firstname':'Magento integration test','is_guest':True}
    clean['billing_address']={'firstname':'Magento integration test','street':'Test address','city':'Riyadh','postcode':'12271','country_id':'SA'}
    result=build_bundle(frappe.utils.get_url(),doc.endpoint,doc.name,user,clean,creds,bool(doc.require_signature))
    record_activity(config,action='Postman Exported',target_user=user,details={'contains_secrets':bool(creds)})
    return result


def activity_filters(values):
    f=object_value(values or {})
    reader(f.get('integration'))
    start=getdate(f.get('from_date') or add_days(nowdate(),-7));end=getdate(f.get('to_date') or nowdate())
    if start>end or (end-start).days>366:frappe.throw('Choose a date range of up to 366 days')
    query={'creation':['between',[str(start)+' 00:00:00',str(end)+' 23:59:59.999999']]}
    for key in ('integration','company','api_user','endpoint','action','status','external_order_id','reference_name','correlation_id'):
        if f.get(key):query[key]=f[key]
    if f.get('http_status'):query['http_status']=cint(f['http_status'])
    return query


@frappe.whitelist()
def overview(filters=None,start=0,page_length=25):
    query=activity_filters(filters)
    frappe.has_permission('Magento API Activity','read',throw=True)
    size=max(1,min(cint(page_length),100));offset=max(0,cint(start))
    fields=['name','creation','integration','api_user','actor','action','status','http_status','duration_ms','external_order_id','reference_doctype','reference_name','request_log','correlation_id','request_ip']
    rows=frappe.get_list('Magento API Activity',filters=query,fields=fields,order_by='creation desc, name desc',limit_start=offset,limit_page_length=size)
    # Permission-aware SQL aggregation covers all matching rows, not only the displayed page.
    def grouped(field,limit=0,order=None):
        return frappe.get_list('Magento API Activity',filters=query,fields=[field,'count(name) as count'],group_by=field,order_by=order or field,limit_page_length=limit)
    totals=frappe.get_list('Magento API Activity',filters=query,fields=['count(name) as count','avg(duration_ms) as average_ms'],limit_page_length=1)[0]
    daily=frappe.get_list('Magento API Activity',filters=query,fields=['date(creation) as day','count(name) as count'],group_by='date(creation)',order_by='day',limit_page_length=0)
    return dict(rows=rows,total=totals['count'],average_ms=totals['average_ms'] or 0,statuses=grouped('status'),daily=daily,
        users=grouped('api_user',10,'count desc'),http=grouped('http_status'),start=offset,page_length=size)
