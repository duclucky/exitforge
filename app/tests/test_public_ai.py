import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch

from exitforge import public_ai
from exitforge.importer import recover_archive
from exitforge.process_fixtures import process_case
from exitforge.providers import ProviderFailure, BASETEN_MODEL
from exitforge.sample import sample_archive


class PublicAllowanceTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/'quota.sqlite3'
        self.now=100000
        self.store=public_ai.Ledger(self.path,lambda:self.now)
        self.client=self.store.client('192.0.2.10')
        self.token,self.quota=self.store.session('',self.client)

    def test_random_secure_session_and_hashed_identity(self):
        self.assertEqual(self.quota['remaining'],2)
        self.assertGreater(len(self.token),32)
        self.assertEqual(self.store.session(self.token,self.client)[0],self.token)
        other=self.store.client('192.0.2.11')
        with self.assertRaises(public_ai.AdmissionError):self.store.reserve(self.token,other,'request-000000001')
        data=self.path.read_bytes()
        self.assertNotIn(self.token.encode(),data)
        self.assertNotIn(b'192.0.2.10',data)

    def test_failed_unknown_and_repeated_calls_keep_reservations(self):
        call=self.store.reserve(self.token,self.client,'request-000000001')
        self.store.finish(call,False)
        self.now+=21
        reopened=public_ai.Ledger(self.path,lambda:self.now)
        self.assertEqual(reopened.remaining_global(),3)
        with self.assertRaisesRegex(public_ai.AdmissionError,'already attempted'):
            reopened.reserve(self.token,self.client,'request-000000001')
        second=reopened.reserve(self.token,self.client,'request-000000002')
        self.assertTrue(second)
        self.assertEqual(reopened.session(self.token,self.client)[1]['remaining'],0)

    def test_network_limit_cannot_be_reset_by_new_cookies(self):
        for number in range(3):
            token,_=self.store.session('',self.client)
            call=self.store.reserve(token,self.client,f'request-network-{number}')
            self.store.finish(call,True)
            self.now+=21
        token,quota=self.store.session('',self.client)
        self.assertEqual(quota['remaining'],0)
        with self.assertRaises(public_ai.AdmissionError):self.store.reserve(token,self.client,'request-network-four')

    def test_lifetime_limit_survives_day_change_and_reopen(self):
        for number in range(4):
            client=self.store.client(f'192.0.2.{number+30}')
            token,_=self.store.session('',client)
            call=self.store.reserve(token,client,f'request-global-{number:04d}')
            self.store.finish(call,True)
            self.now+=21
        self.now+=86401
        reopened=public_ai.Ledger(self.path,lambda:self.now)
        token,quota=reopened.session('',self.client)
        self.assertEqual(quota['remaining'],0)
        self.assertEqual(reopened.remaining_global(),0)
        with self.assertRaises(public_ai.AdmissionError):reopened.reserve(token,self.client,'request-global-fifth')

    def test_owner_one_attempt_extension_preserves_history_and_blocks_sixth(self):
        for number in range(4):
            client=self.store.client(f'192.0.2.{number+40}');token,_=self.store.session('',client)
            call=self.store.reserve(token,client,f'authorized-history-{number}')
            self.store.finish(call,True);self.now+=21
        self.assertEqual(self.store.remaining_global(),0)
        with patch.dict(os.environ,{'EXITFORGE_AI_ALLOWANCE_MICROUSD':'750000'}):
            reopened=public_ai.Ledger(self.path,lambda:self.now)
            self.assertEqual(reopened.remaining_global(),1)
            client=reopened.client('192.0.2.60');token,_=reopened.session('',client)
            call=reopened.reserve(token,client,'one-authorized-extra-attempt');reopened.finish(call,True)
            self.now+=21
            self.assertEqual(public_ai.Ledger(self.path,lambda:self.now).remaining_global(),0)
            client=reopened.client('192.0.2.61');token,_=reopened.session('',client)
            with self.assertRaises(public_ai.AdmissionError):reopened.reserve(token,client,'forbidden-sixth-attempt')

    def test_invalid_owner_allowance_cannot_enable_unbounded_spending(self):
        for value in ('999999999','-1','750001','not-a-number','0'):
            with self.subTest(value=value),patch.dict(os.environ,{'EXITFORGE_AI_ALLOWANCE_MICROUSD':value}):
                with self.assertRaises(public_ai.AdmissionError):public_ai.Ledger(self.path,lambda:self.now)

    def test_atomic_single_admission_under_concurrent_requests(self):
        barrier=threading.Barrier(2)
        def attempt(number):
            client=self.store.client(f'198.51.100.{number}')
            token,_=self.store.session('',client)
            barrier.wait()
            try:return self.store.reserve(token,client,f'request-concurrent-{number}')
            except public_ai.AdmissionError:return None
        with ThreadPoolExecutor(2) as executor:results=list(executor.map(attempt,[1,2]))
        self.assertEqual(sum(bool(x) for x in results),1)
        self.assertEqual(self.store.remaining_global(),3)

    def test_pending_after_crash_expires_without_refunding_budget(self):
        self.store.reserve(self.token,self.client,'request-before-crash')
        self.now+=181
        client=self.store.client('198.51.100.50');token,_=self.store.session('',client)
        self.assertTrue(self.store.reserve(token,client,'request-after-crash'))
        self.assertEqual(self.store.remaining_global(),2)

    def test_cooldown_and_untrusted_forwarded_identity(self):
        call=self.store.reserve(self.token,self.client,'request-cooldown-1');self.store.finish(call,True)
        with self.assertRaisesRegex(public_ai.AdmissionError,'20 seconds'):
            self.store.reserve(self.token,self.client,'request-cooldown-2')
        with patch.dict(os.environ,{'EXITFORGE_TRUST_TUNNEL':'1'}),patch('socket.getaddrinfo',return_value=[(None,None,None,None,('172.18.0.9',0))]):
            headers={'CF-Connecting-IP':'203.0.113.3','X-Forwarded-For':'203.0.113.99'}
            self.assertEqual(public_ai.client_address({'client':('192.0.2.50',55)},headers),'192.0.2.50')
            self.assertEqual(public_ai.client_address({'client':('172.18.0.9',55)},headers),'203.0.113.3')

    def test_real_core_text_route_single_call_no_retry_or_confirmation(self):
        project=recover_archive(sample_archive())
        spec={'workspace_name':'New input','status_field':'Status','states':['Review','Delivered'],
              'delivery_state':'Delivered','followup':'Check {project}','require_checklist':True,
              'rationale':'Observed source stages','evidence_sources':[project['databases'][0]['source']],'unknowns':['Original permissions unknown']}
        calls=[]
        def fake(provider,url,key,packet):
            calls.append(packet)
            return {'choices':[{'message':{'content':json.dumps(spec)}}],'usage':{'prompt_tokens':22,'completion_tokens':12}}
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'fake-unused'}):
            result=public_ai.run('/api/enhance',{'project':project,'consent':True},self.store,self.token,self.client,'request-text-live-1',fake)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['model'],BASETEN_MODEL)
        self.assertEqual(calls[0]['reasoning_effort'],'low')
        self.assertTrue(result['requires_user_confirmation'])
        self.assertEqual(len(result['calls']),1)
        self.assertEqual(result['trial']['remaining'],1)
        self.assertFalse(project['workflow']['confirmed'])

    def test_actual_vision_mapping_and_model_failure_do_not_retry(self):
        project,spec,_,_=process_case()
        raw=(Path('examples/process-observations/delivery/frame-1.png')).read_bytes()
        frames=[{'data_url':'data:image/png;base64,'+base64.b64encode(raw).decode()} for _ in range(4)]
        calls=[]
        def fake(*args):
            calls.append(1)
            return {'choices':[{'message':{'content':json.dumps(spec)}}]}
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'fake-unused'}):
            result=public_ai.run('/api/reconstruct-process',{'project':project,'observations':frames,'consent':True},self.store,self.token,self.client,'request-vision-1',fake)
        self.assertFalse(result['process']['confirmed']);self.assertEqual(calls,[1])
        self.now+=21
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'fake-unused'}):
            with self.assertRaises(ProviderFailure):
                public_ai.run('/api/reconstruct-process',{'project':project,'observations':frames,'consent':True},self.store,self.token,self.client,'request-vision-2',lambda *args:(_ for _ in ()).throw(ProviderFailure('Provider timeout')))
        self.assertEqual(self.store.remaining_global(),2)

    def test_invalid_consent_input_and_packet_size_do_not_spend(self):
        project=recover_archive(sample_archive())
        with self.assertRaises(public_ai.AdmissionError):
            public_ai.run('/api/enhance',{'project':project,'consent':False},self.store,self.token,self.client,'request-invalid-1')
        packet={'model':BASETEN_MODEL,'max_tokens':3000,'messages':[{'content':'x'*40001}]}
        with self.assertRaises(public_ai.AdmissionError):public_ai.bounded_payload(packet)
        packet['messages']=[{'content':[{'type':'image_url','image_url':{'url':'https://attacker.invalid/image'}}]}]
        with self.assertRaises(public_ai.AdmissionError):public_ai.bounded_payload(packet)
        self.assertEqual(self.store.remaining_global(),4)

    def test_missing_or_unwritable_configuration_fails_closed(self):
        with patch.dict(os.environ,{'EXITFORGE_PUBLIC_AI':'1','EXITFORGE_ALLOW_CLOUD':'1','EXITFORGE_BASETEN_KEY_FILE':str(Path(self.folder.name)/'absent'),'EXITFORGE_AI_LEDGER':str(self.path)}):
            self.assertFalse(public_ai.configured())
            with self.assertRaises(public_ai.AdmissionError):public_ai.ledger()

    def test_missing_source_relations_are_rejected_without_reserving_credit(self):
        project,spec,_,_=process_case()
        child=next(p for p in project['pages'] if p['id']==spec['links'][0]['child'])
        child['links']=[]
        transport=Mock()
        frames=[{'data_url':'data:image/png;base64,'+base64.b64encode(Path('examples/process-observations/delivery/frame-1.png').read_bytes()).decode()}]
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'fake-unused'}):
            with self.assertRaisesRegex(ProviderFailure,'complete source-linked'):
                public_ai.run('/api/reconstruct-process',{'project':project,'observations':frames,'consent':True},self.store,self.token,self.client,'request-unresolved-source',transport)
        transport.assert_not_called()
        self.assertEqual(self.store.remaining_global(),4)
