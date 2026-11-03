import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from exitforge.server import Handler


class ServerBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start();cls.base=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def call(self,path='/',body=None,headers=None):
        request=urllib.request.Request(self.base+path,data=body,headers=headers or {})
        try:
            with urllib.request.urlopen(request,timeout=5) as response:return response.status,response.read()
        except urllib.error.HTTPError as exc:return exc.code,exc.read()

    def test_foreign_host_and_origin_are_rejected(self):
        self.assertEqual(self.call(headers={'Host':'attacker.test'})[0],403)
        self.assertEqual(self.call('/api/import',b'abc',{'X-ExitForge':'studio-v1','Origin':'https://attacker.test'})[0],403)

    def test_post_without_studio_header_and_invalid_archive_fail_safely(self):
        self.assertEqual(self.call('/api/import',b'abc')[0],403)
        code,body=self.call('/api/import',b'abc',{'X-ExitForge':'studio-v1'})
        self.assertEqual(code,400);self.assertIn('ZIP',json.loads(body)['error'])

    def test_status_never_returns_credential_values(self):
        code,body=self.call('/api/status');self.assertEqual(code,200)
        providers=json.loads(body)['providers'];self.assertEqual(len(providers),4)
        self.assertTrue(all(isinstance(p['configured'],bool) for p in providers))
        self.assertTrue(all(set(p)=={'name','role','configured','model','setting'} for p in providers))

    def test_public_demo_cannot_enable_paid_routes_through_environment_mistake(self):
        from unittest.mock import patch
        import os
        from exitforge.sample import sample_archive
        from exitforge.importer import recover_archive
        body=json.dumps({'project':recover_archive(sample_archive()),'consent':True}).encode()
        with patch.dict(os.environ,{'EXITFORGE_DEPLOYMENT_MODE':'public-demo','EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'fake-unused-key'}),patch('exitforge.server.enhance',return_value={'unsafe':'provider was called'}) as provider:
            code,payload=self.call('/api/enhance',body,{'X-ExitForge':'studio-v1'})
            self.assertEqual(code,409)
            provider.assert_not_called()
            status=json.loads(self.call('/api/status')[1]);self.assertFalse(status['cloud_enabled'])
            self.assertTrue(all(not p['configured'] for p in status['providers']))

    def test_arbitrary_files_are_not_served(self):
        self.assertEqual(self.call('/.env')[0],404)
        self.assertEqual(self.call('/../exitforge/server.py')[0],404)

    def test_recorded_meta_example_is_synthetic_and_never_preapproved(self):
        code,body=self.call('/api/meta-example');self.assertEqual(code,200)
        project=json.loads(body)
        self.assertTrue(project['provenance']['sample'])
        self.assertEqual(project['provenance']['recorded_example']['new_live_calls_on_open'],0)
        self.assertFalse(project['workflow']['confirmed'])
        self.assertEqual(project['workflow']['field'],'Release phase')
        self.assertEqual(len(project['ai_review']['calls']),2)

    def test_linked_example_is_unconfirmed_and_process_endpoint_requires_consent(self):
        from unittest.mock import patch
        import os
        code,body=self.call('/api/process-example');self.assertEqual(code,200)
        project=json.loads(body);self.assertFalse(project['process']['confirmed']);self.assertIsNone(project['process']['parent_revision'])
        code,image=self.call('/process-example/delivery/frame-1.png');self.assertEqual(code,200);self.assertTrue(image.startswith(b'\x89PNG'))
        self.assertEqual(self.call('/process-example/delivery/../../.env')[0],404)
        payload=json.dumps({'project':project,'consent':False,'observations':[]}).encode()
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'fake-local-no-network'}):
            code,body=self.call('/api/reconstruct-process',payload,{'X-ExitForge':'studio-v1'})
        self.assertEqual(code,409);self.assertIn('consent',json.loads(body)['error'])

    def test_sample_transport_is_json_and_contains_a_real_importable_archive(self):
        import base64
        from exitforge.importer import recover_archive
        with urllib.request.urlopen(self.base+'/api/sample',timeout=5) as response:
            self.assertEqual(response.status,200)
            self.assertIn('application/json',response.headers['Content-Type'])
            self.assertIsNone(response.headers.get('Content-Disposition'))
            payload=json.loads(response.read())
        workspace=recover_archive(base64.b64decode(payload['archive_base64'],validate=True),payload['filename'])
        self.assertEqual(len(workspace['pages']),33)
        self.assertEqual(len(workspace['databases'][0]['rows']),30)
        self.assertFalse(workspace['workflow']['confirmed'])

    def test_recorded_process_examples_preserve_current_source_bound_proposals(self):
        for domain in ('delivery','editorial'):
            with self.subTest(domain=domain):
                code,body=self.call('/api/process-example?domain='+domain)
                self.assertEqual(code,200)
                project=json.loads(body);review=project['process_review']
                self.assertIn('model_proposal',review)
                self.assertNotIn('links',review['model_proposal'])
                self.assertEqual(review['binding_resolution']['relationship_count'],4)
                self.assertEqual(len(review['proposal']['links']),4)
                self.assertTrue(review['recorded'])
                self.assertFalse(project['process']['confirmed'])
                self.assertIsNone(project['process']['parent_revision'])
                self.assertEqual(project['provenance']['recorded_example']['new_live_calls_on_open'],0)

    def test_empty_input_has_an_accurate_error(self):
        code,body=self.call('/api/import',b'',{'X-ExitForge':'studio-v1'})
        self.assertEqual(code,400)
        self.assertIn('empty',json.loads(body)['error'].lower())

    def test_selected_handoff_scenario_and_unknown_scenario(self):
        import base64
        from exitforge.importer import recover_archive
        code,body=self.call('/api/sample?scenario=client-handoff')
        self.assertEqual(code,200)
        payload=json.loads(body)
        project=recover_archive(base64.b64decode(payload['archive_base64']),payload['filename'])
        self.assertEqual(len(project['pages']),7)
        self.assertEqual(self.call('/api/sample?scenario=unknown')[0],400)


if __name__=='__main__':unittest.main()
