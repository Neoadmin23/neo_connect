import frappe
from frappe.utils import nowdate,add_days,getdate,cint


def execute(filters=None):
    frappe.has_permission('Magento API Activity','read',throw=True)
    f=frappe._dict(filters or {})
    start=f.from_date or add_days(nowdate(),-7)
    end=f.to_date or nowdate()
    if getdate(start)>getdate(end): frappe.throw('From date must not be after To date')
    query={'creation':['between',[str(start)+' 00:00:00',str(end)+' 23:59:59.999999']]}
    for field in ('integration','company','api_user','action','status','endpoint','external_order_id','reference_name','correlation_id'):
        if f.get(field): query[field]=f[field]
    if f.get('http_status'): query['http_status']=cint(f.http_status)
    limit=max(1,min(cint(f.limit or 1000),5000))
    fields=['name','creation','integration','api_user','actor','action','status','http_status','http_method','route','external_order_id','reference_doctype','reference_name','request_log','request_ip','duration_ms','correlation_id']
    data=frappe.get_list('Magento API Activity',filters=query,fields=fields,order_by='creation desc',limit_page_length=limit+1)
    message='Results limited. Narrow the filters for the remaining records.' if len(data)>limit else None
    data=data[:limit]
    specs=[('name','Trace Log','Link','Magento API Activity',150),('creation','Time','Datetime',None,160),('integration','Configuration','Link','Magento Integration Settings',160),('api_user','API User','Link','User',180),('actor','Actor','Link','User',150),('action','Action','Data',None,160),('status','Status','Data',None,90),('http_status','HTTP','Int',None,65),('http_method','Method','Data',None,75),('route','Route','Data',None,230),('external_order_id','Magento Order','Data',None,150),('reference_doctype','Document Type','Link','DocType',130),('reference_name','Document','Dynamic Link','reference_doctype',180),('request_log','Request Log','Link','API Request Log',150),('request_ip','IP Address','Data',None,130),('duration_ms','Duration (ms)','Float',None,110),('correlation_id','Trace ID','Data',None,250)]
    columns=[dict(fieldname=k,label=label,fieldtype=kind,options=opts,width=width) for k,label,kind,opts,width in specs]
    counts={s:sum(row.status==s for row in data) for s in ('Success','Denied','Failed','Duplicate','Dry Run')}
    chart=dict(data=dict(labels=list(counts),datasets=[dict(name='Activities shown',values=list(counts.values()))]),type='bar')
    summary=[dict(label='Activities shown',value=len(data),datatype='Int')]+[dict(label=k,value=v,datatype='Int') for k,v in counts.items()]
    return columns,data,message,chart,summary
