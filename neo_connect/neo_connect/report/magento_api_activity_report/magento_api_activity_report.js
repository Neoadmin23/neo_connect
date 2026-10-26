frappe.query_reports['Magento API Activity Report'] = {
 filters: [
  {fieldname:'from_date',label:'From Date',fieldtype:'Date',default:frappe.datetime.add_days(frappe.datetime.get_today(),-7),reqd:1},
  {fieldname:'to_date',label:'To Date',fieldtype:'Date',default:frappe.datetime.get_today(),reqd:1},
  ...[['integration','Configuration','Magento Integration Settings'],['company','Company','Company'],['api_user','API User','User'],['endpoint','Endpoint','API Endpoint']].map(([fieldname,label,options])=>({fieldname,label,fieldtype:'Link',options})),
  {fieldname:'status',label:'Status',fieldtype:'Select',options:'\nSuccess\nDenied\nFailed\nDuplicate\nDry Run'},
  {fieldname:'action',label:'Action',fieldtype:'Data'},
  {fieldname:'external_order_id',label:'Magento Order',fieldtype:'Data'},
  {fieldname:'reference_name',label:'Sales Invoice',fieldtype:'Link',options:'Sales Invoice'},
  {fieldname:'http_status',label:'HTTP Status',fieldtype:'Int'},
  {fieldname:'correlation_id',label:'Trace ID',fieldtype:'Data'},
  {fieldname:'limit',label:'Maximum Rows',fieldtype:'Int',default:1000}
 ]
};
