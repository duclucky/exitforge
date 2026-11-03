import unittest

from exitforge.compiler import compile_application, json_for_script, validate_workspace
from exitforge.importer import recover_archive
from exitforge.sample import sample_archive


class CompilerTests(unittest.TestCase):
    def test_local_record_origin_must_be_bounded_and_match_its_source(self):
        import copy
        project=recover_archive(sample_archive())
        project['pages'][0]['local_record']={'created_at':'yesterday'}
        with self.assertRaisesRegex(ValueError,'local record'):
            validate_workspace(project)
        project=recover_archive(sample_archive())
        local=copy.deepcopy(project['pages'][0]);local.update(id='local-created',source='ExitForge-created/local-created.md',local_record={'created_at':'2026-11-02T10:00:00.000Z'})
        project['pages'].append(local);validate_workspace(project)
        for origin in ({'created_at':'2026-11-02T10:00:00.000'}, {'created_at':'2026-02-31T10:00:00.000Z'}, {'created_at':'2026-11-02T10:00:00.000Z','extra':True},None):
            changed=copy.deepcopy(project);changed['pages'][-1]['local_record']=origin
            with self.assertRaisesRegex(ValueError,'local record'):validate_workspace(changed)

    def test_an_imported_process_cannot_smuggle_executable_actions(self):
        project=recover_archive(sample_archive())
        project['process']={'version':1,'actions':[{'kind':'eval','code':'execute arbitrary code'}]}
        with self.assertRaisesRegex(ValueError,'process'):
            validate_workspace(project)

    def test_script_data_cannot_break_out_of_container(self):
        value = json_for_script({'title': '</script><script>window.INJECTED=true</script>'})
        self.assertNotIn('</script>', value)
        self.assertIn('\\u003c', value)

    def test_rejects_arbitrary_executable_asset(self):
        project = recover_archive(sample_archive())
        project['assets']['attack'] = {'mime': 'text/html', 'name': 'evil.html', 'data': 'abc'}
        with self.assertRaises(ValueError):
            validate_workspace(project)

    def test_standalone_contains_its_data_runtime_and_no_external_dependencies(self):
        project = recover_archive(sample_archive(), 'sample.zip')
        result = compile_application(project)
        self.assertIn('workspace-data', result)
        self.assertIn("connect-src 'none'", result)
        self.assertNotIn('<script src=', result)
        self.assertNotIn('<link rel="stylesheet"', result)
        self.assertIn('Brand launch', result)
        self.assertEqual(len(project['databases'][0]['rows']), 30)

    def test_invalid_view_or_model_review_is_rejected_before_packaging(self):
        for change in (
            lambda p: p.update(presentation={'primary_view':'board','database_id':'missing'}),
            lambda p: p.update(ai_review={'specification':{'rationale':'Untrusted','unknowns':None},'calls':[]}),
            lambda p: p['provenance'].update(cloud_calls='invalid'),
        ):
            project = recover_archive(sample_archive())
            change(project)
            with self.assertRaises(ValueError):
                validate_workspace(project)

    def test_duplicate_database_task_and_workflow_identifiers_are_rejected(self):
        for kind in ('database','task','state'):
            project = recover_archive(sample_archive())
            if kind == 'database':
                project['databases'].append(dict(project['databases'][0]))
            elif kind == 'task':
                task = {'id':'a','page':project['pages'][0]['id'],'text':'Follow up','done':False}
                project['tasks'] = [task, dict(task)]
            else:
                project['workflow']['states'].append(project['workflow']['states'][0])
            with self.assertRaises(ValueError):
                validate_workspace(project)


if __name__ == '__main__':
    unittest.main()
