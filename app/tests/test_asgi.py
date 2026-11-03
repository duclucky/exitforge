import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from exitforge.asgi import app,public_origin,MAX_INPUT
from exitforge.sample import sample_archive


class PublicTransportTests(unittest.IsolatedAsyncioTestCase):
    async def call(self,path='/',method='GET',body=b'',headers=None,chunks=None):
        values={'host':'demo.trycloudflare.com',**(headers or {})}
        scope={'type':'http','method':method,'path':path,'raw_path':path.encode(),'query_string':b'',
            'server':('127.0.0.1',8000),'headers':[(k.encode(),v.encode()) for k,v in values.items()]}
        events=list(chunks) if chunks is not None else [{'type':'http.request','body':body,'more_body':False}]
        sent=[]
        async def receive():return events.pop(0)
        async def send(event):sent.append(event)
        with patch.dict(os.environ,{'EXITFORGE_PUBLIC_ORIGIN':'https://demo.trycloudflare.com','EXITFORGE_PUBLIC_ORIGIN_FILE':''}):
            await app(scope,receive,send)
        self.assertEqual(sent[0]['type'],'http.response.start')
        return sent[0]['status'],sent[-1]['body'],dict(sent[0]['headers'])

    async def test_health_exact_host_origin_and_server_disclosure(self):
        self.assertEqual((await self.call('/healthz'))[0],200)
        self.assertEqual((await self.call(headers={'host':'evil.trycloudflare.com'}))[0],403)
        self.assertEqual((await self.call(headers={'origin':'https://evil.test'}))[0],403)
        code,body,headers=await self.call();self.assertEqual(code,200);self.assertIn(b'VPS demo',body)
        self.assertIn(b"frame-ancestors 'none'",headers[b'content-security-policy'])

    async def test_chunked_import_and_package_reuse_validated_core(self):
        archive=sample_archive();headers={'origin':'https://demo.trycloudflare.com','x-exitforge':'studio-v1'}
        code,body,_=await self.call('/api/import','POST',headers=headers,chunks=[{'type':'http.request','body':archive[:20],'more_body':True},{'type':'http.request','body':archive[20:],'more_body':False}])
        self.assertEqual(code,200);project=json.loads(body);self.assertEqual(len(project['pages']),33)
        code,body,headers=await self.call('/api/package','POST',json.dumps({'project':project}).encode(),headers)
        self.assertEqual(code,200);self.assertIn(b"connect-src 'none'",body);self.assertIn(b'attachment',headers[b'content-disposition'])

    async def test_cloud_remains_unavailable_even_with_configured_environment(self):
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'fake-unused'}),patch('exitforge.server.enhance') as provider:
            for route in ('enhance','reconstruct-process','modal-package'):
                code,body,_=await self.call('/api/'+route,'POST',b'{}',{'x-exitforge':'studio-v1','origin':'https://demo.trycloudflare.com'})
                self.assertEqual(code,409);self.assertIn(b'disabled',body)
            provider.assert_not_called();code,body,_=await self.call('/api/status');self.assertEqual(code,200)
            result=json.loads(body);self.assertFalse(result['cloud_enabled']);self.assertTrue(all(not p['configured'] for p in result['providers']))

    async def test_framing_bounds_and_post_header_reject_before_core(self):
        self.assertEqual((await self.call('/api/import','POST',b'bad'))[0],403)
        self.assertEqual((await self.call('/api/import','POST',b'bad',{'x-exitforge':'studio-v1','content-length':'4'}))[0],400)
        self.assertEqual((await self.call('/api/import','POST',headers={'x-exitforge':'studio-v1','content-length':str(MAX_INPUT+1)},chunks=[]))[0],413)
        self.assertEqual((await self.call('/api/import','POST',b'bad',{'x-exitforge':'studio-v1','content-length':'not-a-number'}))[0],400)

    async def test_secret_paths_unknown_methods_and_head(self):
        self.assertEqual((await self.call('/.env'))[0],404)
        self.assertEqual((await self.call('/../exitforge/asgi.py'))[0],404)
        self.assertEqual((await self.call('/','DELETE'))[0],405)
        code,body,_=await self.call('/healthz','HEAD');self.assertEqual(code,200);self.assertEqual(body,b'')

    async def test_explicit_guarded_configuration_can_issue_customer_session(self):
        with tempfile.TemporaryDirectory() as folder:
            key=Path(folder)/'key';key.write_text('fake-unused-key')
            with patch.dict(os.environ,{'EXITFORGE_PUBLIC_AI':'1','EXITFORGE_ALLOW_CLOUD':'1',
                 'EXITFORGE_BASETEN_KEY_FILE':str(key),'EXITFORGE_AI_LEDGER':str(Path(folder)/'quota.sqlite3')}):
                code,body,headers=await self.call('/api/ai/session')
                self.assertEqual(code,200)
                self.assertIn(b'HttpOnly',headers[b'set-cookie'])
                self.assertTrue(json.loads(body)['available'])

    async def test_hosted_customer_text_request_and_duplicate_are_guarded(self):
        from http.cookies import SimpleCookie
        from exitforge.importer import recover_archive
        project=recover_archive(sample_archive())
        spec={'workspace_name':'Customer export','status_field':'Status','states':['Review','Delivered'],
              'delivery_state':'Delivered','followup':'Check {project}','require_checklist':True,
              'rationale':'Source-supported stages','evidence_sources':[project['databases'][0]['source']],'unknowns':[]}
        with tempfile.TemporaryDirectory() as folder:
            key=Path(folder)/'key';key.write_text('fake-never-exposed')
            env={'EXITFORGE_PUBLIC_AI':'1','EXITFORGE_ALLOW_CLOUD':'1','EXITFORGE_BASETEN_KEY_FILE':str(key),'EXITFORGE_AI_LEDGER':str(Path(folder)/'quota.sqlite3')}
            with patch.dict(os.environ,env),patch('exitforge.providers.post_json',return_value={'choices':[{'message':{'content':json.dumps(spec)}}]}) as transport:
                code,body,headers=await self.call('/api/ai/session');self.assertEqual(code,200)
                cookie=SimpleCookie();cookie.load(headers[b'set-cookie'].decode())
                values={'cookie':cookie.output(header='').strip(),'origin':'https://demo.trycloudflare.com','x-exitforge':'studio-v1','idempotency-key':'request-customer-asgi-1'}
                payload=json.dumps({'project':project,'consent':True,'route':'baseten'}).encode()
                code,body,_=await self.call('/api/enhance','POST',payload,values)
                self.assertEqual(code,200);result=json.loads(body)
                self.assertEqual(len(result['calls']),1);self.assertTrue(result['requires_user_confirmation'])
                self.assertNotIn(b'fake-never-exposed',body)
                self.assertEqual((await self.call('/api/enhance','POST',payload,values))[0],409)
                values.pop('origin')
                self.assertEqual((await self.call('/api/enhance','POST',payload,values))[0],403)
                values['origin']='https://demo.trycloudflare.com'
                self.assertEqual((await self.call('/api/modal-package','POST',payload,values))[0],409)
                self.assertEqual(transport.call_count,1)

    def test_origin_file_is_dynamic_and_invalid_origin_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'origin.txt'
            with patch.dict(os.environ,{'EXITFORGE_PUBLIC_ORIGIN_FILE':str(file)}):
                self.assertEqual(public_origin(),'')
                for value,expected in [('https://first.trycloudflare.com','https://first.trycloudflare.com'),('https://next.trycloudflare.com/','https://next.trycloudflare.com'),('http://demo.test',''),('https://user:password@demo.test',''),('https://demo.test/path','')]:
                    file.write_text(value,encoding='utf-8');self.assertEqual(public_origin(),expected)
