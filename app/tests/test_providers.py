import copy
import json
import os
import unittest
from unittest.mock import patch

from exitforge.importer import recover_archive
from exitforge.providers import ProviderFailure, enhance, status
from exitforge.sample import sample_archive


class ProviderBoundaryTests(unittest.TestCase):
    def test_modal_rejects_stale_runtime_instead_of_returning_an_older_application(self):
        import sys
        from types import SimpleNamespace
        from exitforge.compiler import compile_application
        from exitforge.providers import package_with_modal
        def run_remote(result):
            fake=SimpleNamespace(Function=SimpleNamespace(from_name=lambda *args:SimpleNamespace(remote=lambda project:result)))
            with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1'}),patch.dict(sys.modules,{'modal':fake}),patch('exitforge.providers.status',return_value={'providers':[{'name':'Modal','configured':True}]}):
                return package_with_modal(self.project,True)
        with self.assertRaisesRegex(ProviderFailure,'out of date|current compiler'):
            run_remote('<!doctype html><p>Old worker without current rule checks</p>')
        self.assertEqual(run_remote(compile_application(self.project)),compile_application(self.project))

    def setUp(self):
        self.project=recover_archive(sample_archive())
        self.environment={'EXITFORGE_ALLOW_CLOUD':'1','MODEL_API_KEY':'test-only-meta',
                          'BASETEN_API_KEY':'test-only-baseten','FIREWORKS_API_KEY':'test-only-fireworks'}
        self.spec={'workspace_name':'Recovered studio','status_field':'Status',
                   'states':['In progress','Review','Delivered'],'delivery_state':'Delivered',
                   'followup':'Check delivery','require_checklist':True,'rationale':'Client delivery workflow',
                   'evidence_sources':[self.project['databases'][0]['source']],
                   'unknowns':['The original automation is not present in the export.']}

    def fake_transport(self,provider,url,key,payload):
        self.requests.append((provider,url,payload))
        if provider=='Fireworks':return {'data':[{'index':0,'relevance_score':0.9}]}
        value=self.spec if provider=='Meta' else {'primary_view':'board','template_id':'delivery',
             'database_id':self.project['databases'][0]['id'],'explanation':'Preserve project stages'}
        return {'choices':[{'message':{'content':json.dumps(value)}}]}

    def test_consent_and_server_enablement_are_required_before_any_network_call(self):
        self.requests=[]
        with patch.dict(os.environ,self.environment):
            with self.assertRaises(ProviderFailure):enhance(self.project,False,transport=self.fake_transport)
        self.assertEqual(self.requests,[])
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'0'}):
            with self.assertRaises(ProviderFailure):enhance(self.project,True,transport=self.fake_transport)
        self.assertEqual(self.requests,[])

    def test_valid_contract_runs_all_three_stages_but_never_confirms_a_rule(self):
        self.requests=[];original=copy.deepcopy(self.project)
        with patch.dict(os.environ,self.environment):
            result=enhance(self.project,True,transport=self.fake_transport)
        self.assertEqual([x[0] for x in self.requests],['Meta','Fireworks','Baseten'])
        self.assertEqual(result['presentation']['primary_view'],'board')
        self.assertTrue(result['requires_user_confirmation'])
        self.assertEqual(self.project,original)
        self.assertEqual(self.requests[0][2]['model'],'muse-spark-1.3')
        self.assertEqual(self.requests[-1][2]['model'],'meta-models/muse-spark-open-1026')

    def test_model_cannot_invent_source_evidence_or_workflow_states(self):
        self.requests=[];self.spec['states'].append('Hidden approval')
        with patch.dict(os.environ,self.environment):
            with self.assertRaisesRegex(ProviderFailure,'unsupported states'):
                enhance(self.project,True,transport=self.fake_transport)
        self.assertEqual(len(self.requests),1)

    def test_event_key_is_used_instead_of_public_workspace_key(self):
        self.requests=[];seen=[]
        def transport(provider,url,key,payload):
            if provider=='Baseten':seen.append(key)
            return self.fake_transport(provider,url,key,payload)
        with patch.dict(os.environ,{**self.environment,'BASETEN_HACKATHON_API_KEY':'test-only-event'}):
            result=enhance(self.project,True,transport=transport)
            self.assertTrue(next(p for p in status()['providers'] if p['name']=='Baseten')['configured'])
        self.assertEqual(seen,['test-only-event'])
        self.assertEqual(result['calls'][-1]['model'],'meta-models/muse-spark-open-1026')

    def test_screenshot_must_be_a_bounded_image(self):
        self.requests=[]
        with patch.dict(os.environ,self.environment):
            with self.assertRaises(ProviderFailure):
                enhance(self.project,True,'https://example.test/no-fetch',transport=self.fake_transport)
        self.assertEqual(self.requests,[])

    def test_explicit_open_weight_route_needs_only_baseten_and_keeps_rules_unconfirmed(self):
        requests=[];original=copy.deepcopy(self.project)
        def transport(provider,url,key,payload):
            requests.append((provider,url,key,payload))
            value=self.spec if len(requests)==1 else {'primary_view':'board','template_id':'delivery',
                'database_id':self.project['databases'][0]['id'],'explanation':'Preserve stages'}
            return {'choices':[{'message':{'content':json.dumps(value)}}]}
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'test-only-event'},clear=True):
            result=enhance(self.project,True,transport=transport,route='baseten')
        self.assertEqual([r[0] for r in requests],['Baseten','Baseten'])
        self.assertTrue(all(r[2]=='test-only-event' for r in requests))
        self.assertTrue(all(r[3]['model']=='meta-models/muse-spark-open-1026' for r in requests))
        self.assertEqual(result['route'],'baseten')
        self.assertEqual(result['template_selection'],'curated_unranked')
        self.assertTrue(result['requires_user_confirmation'])
        self.assertEqual(original,self.project)

    def test_direct_route_does_not_fall_back_to_baseten_when_credentials_are_missing(self):
        self.requests=[]
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'test-only-event'},clear=True):
            with self.assertRaisesRegex(ProviderFailure,'credentials'):
                enhance(self.project,True,transport=self.fake_transport)
            with self.assertRaisesRegex(ProviderFailure,'route'):
                enhance(self.project,True,transport=self.fake_transport,route='unrecognized')
        self.assertEqual(self.requests,[])

    def test_unpackageable_stage_lists_stop_before_later_provider_calls(self):
        for stages in ([f'Stage {i}' for i in range(9)], ['Review','Review'], ['x'*101]):
            with self.subTest(stages=stages):
                project=copy.deepcopy(self.project)
                for page,state in zip(project['pages'],stages):page['properties']['Status']=state
                self.spec['states']=stages;self.spec['delivery_state']=stages[-1]
                self.requests=[]
                with patch.dict(os.environ,self.environment):
                    with self.assertRaisesRegex(ProviderFailure,'eight|unique|100'):
                        enhance(project,True,transport=self.fake_transport)
                self.assertEqual(len(self.requests),1)

    def test_view_failure_keeps_validated_interpretation_without_retry_or_fallback(self):
        requests=[];original=copy.deepcopy(self.project)
        def transport(provider,url,key,payload):
            requests.append(provider)
            if len(requests)>1:raise ProviderFailure('Baseten request failed (HTTP 503).')
            return {'choices':[{'message':{'content':json.dumps(self.spec)}}],'usage':{'total_tokens':150}}
        with patch.dict(os.environ,self.environment):
            result=enhance(self.project,True,transport=transport,route='baseten')
        self.assertEqual(requests,['Baseten','Baseten'])
        self.assertEqual(result['outcome'],'partial')
        self.assertEqual(result['failed_stage'],'configure_view')
        self.assertEqual(result['specification'],self.spec)
        self.assertIsNone(result['presentation'])
        self.assertTrue(result['requires_user_confirmation'])
        self.assertEqual(result['calls'][0]['usage'],{'total_tokens':150})
        self.assertEqual(result['calls'][-1]['status'],'failed')
        self.assertEqual(self.project,original)

    def test_failed_ranking_does_not_claim_templates_or_call_view_provider(self):
        requests=[]
        def transport(provider,url,key,payload):
            requests.append(provider)
            if provider=='Fireworks':return {'data':[],'usage':{'total_tokens':4}}
            return {'choices':[{'message':{'content':json.dumps(self.spec)}}]}
        with patch.dict(os.environ,self.environment):
            result=enhance(self.project,True,transport=transport)
        self.assertEqual(requests,['Meta','Fireworks'])
        self.assertEqual(result['outcome'],'partial')
        self.assertEqual(result['failed_stage'],'rerank')
        self.assertEqual(result['template_selection'],'not_completed')
        self.assertIsNone(result['presentation'])
        self.assertEqual(result['calls'][-1]['usage'],{'total_tokens':4})

    def test_invalid_view_is_not_applied_and_raw_provider_body_is_not_returned(self):
        requests=[]
        def transport(provider,url,key,payload):
            requests.append(provider)
            value=self.spec if len(requests)==1 else {'primary_view':'execute-untrusted-code','raw':'DO-NOT-EXPOSE'}
            return {'choices':[{'message':{'content':json.dumps(value)}}]}
        with patch.dict(os.environ,self.environment):
            result=enhance(self.project,True,transport=transport,route='baseten')
        self.assertEqual(result['outcome'],'partial')
        self.assertNotIn('DO-NOT-EXPOSE',json.dumps(result))
        self.assertIsNone(result['presentation'])

    def test_view_failure_after_successful_ranking_retains_the_actual_call_ledger(self):
        requests=[]
        def transport(provider,url,key,payload):
            requests.append(provider)
            if provider=='Meta':return {'choices':[{'message':{'content':json.dumps(self.spec)}}]}
            if provider=='Fireworks':return {'data':[{'index':0}]}
            return {'choices':[],'usage':{'total_tokens':7}}
        with patch.dict(os.environ,self.environment):
            result=enhance(self.project,True,transport=transport)
        self.assertEqual(requests,['Meta','Fireworks','Baseten'])
        self.assertEqual(result['outcome'],'partial')
        self.assertEqual(result['template_selection'],'fireworks_reranked')
        self.assertEqual(result['failed_stage'],'configure_view')
        self.assertEqual([call['operation'] for call in result['calls']],['interpret','rerank','configure_view'])
        self.assertEqual(result['calls'][-1]['usage'],{'total_tokens':7})

    def test_first_stage_failure_stays_an_error_without_later_calls(self):
        calls=[]
        def fail(*args):
            calls.append(args[0]);raise ProviderFailure('Unavailable')
        with patch.dict(os.environ,self.environment):
            with self.assertRaises(ProviderFailure):enhance(self.project,True,transport=fail,route='baseten')
        self.assertEqual(calls,['Baseten'])

    def test_open_weight_proposal_still_rejects_fabricated_source_states(self):
        self.requests=[];self.spec['states'].append('Invented state')
        def interpret(provider,url,key,payload):
            self.requests.append(provider)
            return {'choices':[{'message':{'content':json.dumps(self.spec)}}]}
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'test-only-event'},clear=True):
            with self.assertRaisesRegex(ProviderFailure,'unsupported states'):
                enhance(self.project,True,transport=interpret,route='baseten')
        self.assertEqual(len(self.requests),1)


if __name__=='__main__':unittest.main()
