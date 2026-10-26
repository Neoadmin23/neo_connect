"""Append-only audit records, with no credential secrets in request snapshots."""
import hashlib,json,time,uuid
from urllib.parse import parse_qsl,urlencode
import frappe

SECRET_KEYS={'authorization','password','api_secret','apisecret','signing_secret','client_secret','access_token','refresh_token','api_key','cookie'}
MAX_CHARS=2_000_000


def redact(value):
    if isinstance(value,dict):
        return {k:('[REDACTED]' if str(k).lower().replace('-','_') in SECRET_KEYS else redact(v)) for k,v in value.items()}
    if isinstance(value,list): return [redact(v) for v in value]
    return value


def encoded(value):
    if isinstance(value,str):
        try: value=json.loads(value)
        except ValueError: return value[:MAX_CHARS]
    return json.dumps(redact(value),ensure_ascii=False,default=str)[:MAX_CHARS]


def credential_key():
    header=frappe.get_request_header('Authorization') or ''
    if header.lower().startswith('token '):
        return header[6:].split(':',1)[0]
    if header.lower().startswith('basic '):
        import base64
        try: return base64.b64decode(header[6:]).decode().split(':',1)[0]
        except (ValueError,UnicodeError): return None
    return None


def request_identity():
    info=getattr(frappe.local,'magento_identity',None)
    if info: return info
    from neo_connect.access import identity
    info=identity(api_key=credential_key())
    if info: frappe.local.magento_identity=info
    return info


def before_request():
    frappe.local.magento_trace_id=uuid.uuid4().hex
    frappe.local.magento_started=time.perf_counter()


def record_activity(integration,action='API Request',status='Success',api_user=None,target_user=None,**values):
    if not integration: return None
    info=getattr(frappe.local,'magento_identity',None)
    actor=getattr(frappe.local,'magento_audit_actor',None) or getattr(frappe.session,'user',None) or 'Guest'
    company=frappe.db.get_value('Magento Integration Settings',integration,'company')
    record=dict(doctype='Magento API Activity',integration=integration,company=company,action=action,status=status,
                api_user=api_user or target_user or (info.user if info else None),actor=actor,target_user=target_user,
                correlation_id=getattr(frappe.local,'magento_trace_id',None) or uuid.uuid4().hex)
    if getattr(frappe.local,'request',None):
        record.update(http_method=frappe.request.method,route=frappe.request.path,request_ip=getattr(frappe.local,'request_ip',None))
    record.update(values)
    for key in ('request_payload','response_payload','details'):
        if record.get(key) is not None: record[key]=encoded(record[key])
    if record.get('error_trace') is not None and not isinstance(record['error_trace'],str): record['error_trace']=encoded(record['error_trace'])
    if record.get('external_order_id'): record['external_order_id']=str(record['external_order_id'])[:140]
    flag=getattr(frappe.flags,'magento_audit_write',False)
    frappe.flags.magento_audit_write=True
    try:
        doc=frappe.get_doc(record)
        doc.flags.ignore_links=True
        doc.insert(ignore_permissions=True)
        return doc.name
    finally:
        frappe.flags.magento_audit_write=flag


def from_log(log):
    info=request_identity()
    if not info: return
    trace=getattr(frappe.local,'magento_trace_id',None) or uuid.uuid4().hex
    frappe.local.magento_trace_id=trace
    if frappe.db.exists('Magento API Activity',{'correlation_id':trace,'action':'API Request'}): return
    try: payload=json.loads(log.payload or '{}')
    except ValueError: payload={}
    try: response=json.loads(log.response or '{}')
    except ValueError: response={}
    results=response.get('results') or []
    first=results[0] if results else {}
    status='Denied' if log.http_status in (401,403) else 'Failed' if log.http_status>=400 else 'Dry Run' if log.dry_run else 'Duplicate' if log.status=='Duplicate' else 'Success'
    raw=frappe.request.get_data() or b''
    record_activity(info.integration,status=status,api_user=info.user,partner=info.partner,endpoint=log.endpoint,
                    http_status=log.http_status,http_method=log.http_method,route=frappe.request.path,
                    query_string=urlencode([(k,'[REDACTED]' if k.lower() in SECRET_KEYS else v) for k,v in parse_qsl(log.query_string or '')]),
                    request_ip=log.request_ip,duration_ms=log.duration_ms,request_log=log.name,
                    external_order_id=payload.get('order_number') if isinstance(payload,dict) else None,
                    reference_doctype=first.get('doctype') or log.reference_doctype,
                    reference_name=first.get('name') or log.reference_name,docstatus=first.get('docstatus'),
                    source_hash=hashlib.sha256(raw).hexdigest(),payload_truncated=int(len(raw)>MAX_CHARS),
                    request_payload=payload,response_payload=response,error_trace=log.error)


def after_request(request,response):
    if response is None: return
    if getattr(frappe.local,'magento_no_store',False): response.headers['Cache-Control']='no-store'
    if not frappe.db.exists('DocType','Magento API Activity'): return
    info=request_identity()
    if not info: return
    trace=getattr(frappe.local,'magento_trace_id',None) or uuid.uuid4().hex
    frappe.local.magento_trace_id=trace
    response.headers['X-NeoConnect-Trace-ID']=trace
    if frappe.db.exists('Magento API Activity',{'correlation_id':trace,'action':'API Request'}): return
    raw=request.get_data() or b''
    try: payload=json.loads(raw) if raw else {}
    except ValueError: payload={'invalid_json':True,'body_sha256':hashlib.sha256(raw).hexdigest()}
    try: body=response.get_json(silent=True) or {}
    except (ValueError,AttributeError): body={}
    status='Denied' if response.status_code in (401,403) else 'Failed' if response.status_code>=400 else 'Success'
    started=getattr(frappe.local,'magento_started',time.perf_counter())
    record_activity(info.integration,status=status,api_user=info.user,partner=info.partner,
                    endpoint=frappe.request.args.get('endpoint') if frappe.db.exists('API Endpoint',frappe.request.args.get('endpoint') or '') else None,
                    http_status=response.status_code,http_method=request.method,route=request.path,
                    query_string=urlencode([(k,'[REDACTED]' if k.lower() in SECRET_KEYS else v) for k,v in request.args.items()]),
                    request_ip=getattr(frappe.local,'request_ip',None),duration_ms=(time.perf_counter()-started)*1000,
                    external_order_id=payload.get('order_number') if isinstance(payload,dict) else None,
                    request_payload=payload,response_payload=body,source_hash=hashlib.sha256(raw).hexdigest(),
                    payload_truncated=int(len(raw)>MAX_CHARS),error_trace=body.get('exc') or body.get('message') if response.status_code>=400 else None)
    frappe.db.commit()
