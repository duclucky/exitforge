import base64
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from exitforge.compiler import validate_workspace,compile_application
from exitforge.process_fixtures import process_case
from exitforge.processes import validate_process,reconstruct_process
from exitforge.providers import ProviderFailure


class LinkedProcessTests(unittest.TestCase):
    def setUp(self):
        self.project,self.spec,_,_=process_case()
        self.frames=[{'data_url':'data:image/png;base64,'+base64.b64encode((Path('examples/process-observations/delivery')/f'frame-{i}.png').read_bytes()).decode()} for i in range(1,5)]

    def test_bounded_vision_call_retains_source_bindings_and_requires_review(self):
        calls=[];original=copy.deepcopy(self.project)
        def fake(provider,url,key,payload):
            calls.append(payload)
            return {'choices':[{'message':{'content':json.dumps(self.spec)}}],'usage':{'total_tokens':1}}
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'fake-local-test'}):
            result=reconstruct_process(self.project,self.frames,True,transport=fake)
        self.assertEqual(len(calls),1);self.assertEqual(calls[0]['model'],'meta-models/muse-spark-open-1026')
        self.assertEqual(sum(part['type']=='image_url' for part in calls[0]['messages'][1]['content']),4)
        self.assertEqual(self.project,original);self.assertFalse(result['process']['confirmed']);self.assertIsNone(result['process']['parent_revision'])
        self.assertEqual(result['process']['links'],self.spec['links'])

    def test_model_omissions_cannot_drop_explicit_source_relationships(self):
        for links in (self.spec['links'][:-1],[]):
            with self.subTest(model_links=len(links)):
                proposal=copy.deepcopy(self.spec);proposal['links']=links;calls=[]
                def fake(*args):
                    calls.append(1)
                    return {'choices':[{'message':{'content':json.dumps(proposal)}}]}
                with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'fake-local-test'}):
                    result=reconstruct_process(self.project,self.frames,True,transport=fake)
                self.assertEqual(result['process']['links'],self.spec['links'])
                self.assertEqual(result['model_proposal'],proposal)
                self.assertEqual(calls,[1])
                self.assertFalse(result['process']['confirmed'])
                validate_process(self.project,result['process'])

    def test_consent_image_bounds_and_invalid_ids_stop_without_retries(self):
        calls=[]
        def fake(*args):calls.append(1);return {'choices':[{'message':{'content':json.dumps(self.spec)}}]}
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'fake-local-test'}):
            for frames,consent in [(self.frames,False),(self.frames*2,True),([{'data_url':'data:text/html;base64,PHNjcmlwdD4='}],True)]:
                with self.assertRaises(ProviderFailure):reconstruct_process(self.project,frames,consent,transport=fake)
            self.assertEqual(calls,[])
            self.spec['links'][0]['parent']='invented-id'
            with self.assertRaises(ProviderFailure):reconstruct_process(self.project,self.frames,True,transport=fake)
            self.assertEqual(len(calls),1)

    def test_draft_task_is_reviewable_but_unsafe_confirmed_task_is_not_executable(self):
        self.spec.update(confirmed=False,parent_revision=None)
        self.spec['actions'][2]['task']='Confirm {Client} received {Name}.'
        validate_process(self.project,self.spec)
        self.spec.update(confirmed=True,parent_revision='Changes requested')
        with self.assertRaisesRegex(ValueError,'project'):validate_process(self.project,self.spec)

    def test_process_persists_after_source_statuses_change_and_rejects_terminal_revision(self):
        self.spec.update(confirmed=True,parent_revision='Changes requested');self.project['process']=self.spec
        for page in self.project['pages']:
            if self.spec['child_field'] in page['properties']:page['properties'][self.spec['child_field']]='Approved'
        validate_workspace(self.project);self.assertIn('ExitForgeProcessUI',compile_application(self.project))
        self.spec['parent_revision']='Delivered'
        with self.assertRaisesRegex(ValueError,'complete'):validate_workspace(self.project)

    def test_broken_review_history_and_unknown_operations_do_not_enter_a_package(self):
        self.spec.update(confirmed=False,parent_revision=None);self.project['process']=self.spec
        self.project['process_review']={'proposal':{},'calls':None,'observations':[]}
        with self.assertRaises(ValueError):validate_workspace(self.project)
        del self.project['process_review'];self.spec['actions'][0]['kind']='run_shell'
        with self.assertRaises(ValueError):validate_workspace(self.project)


if __name__=='__main__':unittest.main()
