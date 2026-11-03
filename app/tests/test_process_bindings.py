import base64
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock,patch

from exitforge.process_bindings import source_bindings,assemble_process
from exitforge.process_fixtures import process_case
from exitforge.processes import reconstruct_process,validate_process
from exitforge.providers import ProviderFailure


class SourceBindingTests(unittest.TestCase):
    def setUp(self):
        self.project,self.expected,_,_=process_case()
        self.env={'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'test-only-unused'}
        self.frames=[{'data_url':'data:image/png;base64,'+base64.b64encode(Path(f'examples/process-observations/delivery/frame-{n}.png').read_bytes()).decode()} for n in range(1,5)]

    def compact(self,project,spec):
        candidate=next(c for c in source_bindings(project) if c['parent_db']==spec['parent_db'] and c['child_db']==spec['child_db'])
        return {**{key:copy.deepcopy(value) for key,value in spec.items() if key not in ('parent_db','child_db','links','parent_states','child_states')},'binding_id':candidate['id']}

    def test_compact_proposal_never_needs_to_enumerate_rows_or_states(self):
        for domain in ('delivery','editorial'):
            with self.subTest(domain=domain):
                project,spec,_,_=process_case(domain);original=copy.deepcopy(project);proposal=self.compact(project,spec);packets=[]
                def fake(*args):
                    packets.append(args[-1]);return {'choices':[{'message':{'content':json.dumps(proposal)}}]}
                with patch.dict(os.environ,self.env):result=reconstruct_process(project,self.frames,True,fake)
                self.assertEqual(result['process']['links'],spec['links'])
                self.assertCountEqual(result['process']['parent_states'],spec['parent_states'])
                self.assertCountEqual(result['process']['child_states'],spec['child_states'])
                self.assertEqual(result['model_proposal'],proposal);self.assertNotIn('links',result['model_proposal'])
                self.assertFalse(result['process']['confirmed']);self.assertEqual(project,original)
                validate_process(project,result['process'])
                self.assertEqual(len(packets),1)
                text=packets[0]['messages'][1]['content'][0]['text']
                self.assertIn('source_bindings',text);self.assertIn(proposal['binding_id'],text)

    def test_stable_id_and_fingerprint_do_not_depend_on_source_order(self):
        first=source_bindings(self.project);proposal=self.compact(self.project,self.expected)
        result,proof=assemble_process(self.project,proposal,first)
        changed=copy.deepcopy(self.project);changed['databases'].reverse();changed['pages'].reverse()
        for db in changed['databases']:db['rows'].reverse()
        reordered=source_bindings(changed);other,other_proof=assemble_process(changed,proposal,reordered)
        self.assertEqual(first[0]['id'],reordered[0]['id'])
        self.assertEqual(proof['graph_sha256'],other_proof['graph_sha256'])
        self.assertCountEqual(result['links'],other['links'])

    def test_multiple_database_pairs_remain_distinct(self):
        other,spec,_,_=process_case('editorial')
        self.project['databases']+=other['databases'];self.project['pages']+=other['pages']
        candidates=source_bindings(self.project);self.assertEqual(len(candidates),2)
        process,_=assemble_process(self.project,self.compact(self.project,spec),candidates)
        self.assertEqual(process['links'],spec['links']);validate_process(self.project,process)

    def test_missing_ambiguous_external_and_unconfirmed_sources_stop_before_provider(self):
        child_id=self.expected['links'][0]['child'];other_parent=self.expected['links'][2]['parent']
        for mode in ('missing','ambiguous','external','unconfirmed'):
            with self.subTest(mode=mode):
                project=copy.deepcopy(self.project);child=next(p for p in project['pages'] if p['id']==child_id)
                if mode=='ambiguous':child['links'].append({**child['links'][0],'target':other_parent})
                elif mode=='external':child['links'][0]['external']=True
                else:child['links']=[]
                transport=Mock()
                with patch.dict(os.environ,self.env):
                    with self.assertRaisesRegex(ProviderFailure,'complete source-linked'):
                        reconstruct_process(project,self.frames,True,transport)
                transport.assert_not_called()
                self.assertEqual(source_bindings(project),[])

    def test_confirmed_relation_and_duplicate_same_target_are_valid_sources(self):
        child=next(p for p in self.project['pages'] if p['id']==self.expected['links'][0]['child'])
        child['relations'][0]['confirmed']=True;child['links']=[]
        candidate=source_bindings(self.project)[0];self.assertEqual(len(candidate['links']),4)
        child['links']=[{'target':self.expected['links'][0]['parent'],'external':False}]
        self.assertEqual(source_bindings(self.project)[0]['links'],candidate['links'])

    def test_legacy_omissions_are_completed_without_overwriting_original(self):
        for omitted in range(1,5):
            proposal=copy.deepcopy(self.expected);proposal['links']=proposal['links'][:-omitted]
            original=copy.deepcopy(proposal)
            process,proof=assemble_process(self.project,proposal,source_bindings(self.project))
            self.assertEqual(process['links'],self.expected['links'])
            self.assertEqual(proof['completed_omitted_links'],omitted);self.assertEqual(proposal,original)

    def test_contradictory_duplicate_or_hallucinated_model_links_are_not_silently_repaired(self):
        for mode in ('wrong_parent','duplicate','unknown_child','unknown_parent'):
            proposal=copy.deepcopy(self.expected)
            if mode=='wrong_parent':proposal['links'][0]['parent']=proposal['links'][2]['parent']
            elif mode=='duplicate':proposal['links'].append(copy.deepcopy(proposal['links'][0]))
            elif mode=='unknown_child':proposal['links'][0]['child']='invented'
            else:proposal['links'][0]['parent']='invented'
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'contradict|duplicate'):
                assemble_process(self.project,proposal,source_bindings(self.project))

    def test_unknown_binding_extra_fields_and_nonexistent_field_are_rejected(self):
        for mode in ('binding','extra','field'):
            proposal=self.compact(self.project,self.expected)
            if mode=='binding':proposal['binding_id']='invented'
            elif mode=='extra':proposal['links']=[]
            else:proposal['parent_field']='invented'
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                assemble_process(self.project,proposal,source_bindings(self.project))

    def test_semantic_or_legacy_state_hallucination_still_fails_strict_validator(self):
        for mode in ('action','legacy_state'):
            proposal=self.compact(self.project,self.expected) if mode=='action' else copy.deepcopy(self.expected)
            if mode=='action':proposal['actions'][0]['to']='Invented approval'
            else:proposal['child_states'].append('Invented approval')
            fake=lambda *args:{'choices':[{'message':{'content':json.dumps(proposal)}}]}
            with self.subTest(mode=mode),patch.dict(os.environ,self.env),self.assertRaises(ProviderFailure):
                reconstruct_process(self.project,self.frames,True,fake)
