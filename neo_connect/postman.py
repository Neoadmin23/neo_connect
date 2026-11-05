"""Portable Postman documents. Credentials are supplied only for explicit private export."""
import copy


def build_bundle(base_url, endpoint, config, user, sample, credentials=None, require_signature=False):
    payload=copy.deepcopy(sample)
    payload.update(order_number='{{order_number}}',invoice_number='{{invoice_number}}',
                   order_date='{{invoice_date}}',invoice_date='{{invoice_date}}')
    if payload.get('items'):
        payload['items'][0]['sku']='{{item_code}}'
    import json
    raw=json.dumps(payload,indent=2,ensure_ascii=False)
    def request(name,method,path,body=None):
        req={'method':method,'header':[{'key':'Content-Type','value':'application/json'}],
             'url':'{{base_url}}/api/method/neo_connect.api.'+path}
        if body is not None:req['body']={'mode':'raw','raw':body,'options':{'raw':{'language':'json'}}}
        return {'name':name,'request':req,'event':[{'listen':'test','script':{'type':'text/javascript','exec':[
            "pm.test('HTTP 200', () => pm.response.to.have.status(200));",
            "pm.test('Trace ID present', () => pm.expect(pm.response.headers.get('X-NeoConnect-Trace-ID')).to.be.ok);"
        ]}}]}
    script=[
        "if (!pm.environment.get('order_number')) pm.environment.set('order_number', 'MAGENTO-TEST-' + Date.now());",
        "if (!pm.environment.get('invoice_number')) pm.environment.set('invoice_number', 'INV-' + pm.environment.get('order_number'));",
        "if (!pm.environment.get('invoice_date')) pm.environment.set('invoice_date', new Date().toISOString());",
        "if (pm.request.body && pm.request.body.mode === 'raw') {",
        "  const body = pm.variables.replaceIn(pm.request.body.raw); pm.request.body.update(body);",
        "  if (String(pm.environment.get('require_signature')) === '1') {",
        "    const secret = pm.environment.get('signing_secret'); if (!secret) throw new Error('Set signing_secret');",
        "    const CryptoJS = require('crypto-js');",
        "    pm.request.headers.upsert({key:'X-Signature', value:CryptoJS.HmacSHA256(body, secret).toString(CryptoJS.enc.Hex)});",
        "  } else { pm.request.headers.remove('X-Signature'); }",
        "}",
    ]
    collection={'info':{'name':config+' — Magento invoices','schema':'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
        'description':'One invoice per complete order. Set item_code to an existing SKU and adjust sample quantities, prices and totals to match the client tax template. Run Validation first. The Write invoice folder creates/submits accounting documents. Payment metadata does not post payments. Change order_number, invoice_number and invoice_date together for a new order; retain them for retries.'},
        'auth':{'type':'apikey','apikey':[{'key':'key','value':'Authorization','type':'string'},{'key':'value','value':'token {{api_key}}:{{api_secret}}','type':'string'},{'key':'in','value':'header','type':'string'}]},
        'event':[{'listen':'prerequest','script':{'type':'text/javascript','exec':script}}],
        'item':[{'name':'Validation — no invoice saved','item':[
            request('Connection','GET','ping'),request('Validate complete order','POST','push?endpoint={{endpoint}}&dry_run=1',raw)]},
            {'name':'Write invoice — creates accounting documents','item':[
            request('Create draft','POST','push?endpoint={{endpoint}}',raw),
            request('Submit draft','POST','submit?endpoint={{endpoint}}',json.dumps({'order_number':'{{order_number}}'})),
            request('Create and submit / identical retry','POST','push?endpoint={{endpoint}}&submit=1',raw)]}]}
    values={'base_url':base_url.rstrip('/'),'endpoint':endpoint,'api_user':user,'api_key':'','api_secret':'',
            'require_signature':'1' if require_signature else '0','signing_secret':'','item_code':'REPLACE_WITH_EXISTING_SKU',
            'order_number':'','invoice_number':'','invoice_date':''}
    for key in ('api_key','api_secret','signing_secret'):
        if credentials:values[key]=credentials.get(key) or ''
    environment={'name':config+(' — PRIVATE credentials' if credentials else ' — template'),
        '_postman_variable_scope':'environment','values':[{'key':key,'value':value,'enabled':True,
         'type':'secret' if key in ('api_key','api_secret','signing_secret') else 'default'} for key,value in values.items()]}
    return {'collection':collection,'environment':environment,'contains_secrets':bool(credentials)}
