import unittest

from exitforge.importer import recover_archive
from exitforge.sample import sample_archive


class HandoffScenarioTests(unittest.TestCase):
    def test_authorized_export_preserves_three_distinct_handoffs_without_inventing_rules(self):
        project=recover_archive(sample_archive('client-handoff'),'client-handoff-demo.zip')
        self.assertEqual(len(project['pages']),7)
        self.assertEqual(len(project['databases']),1)
        self.assertEqual(len(project['databases'][0]['rows']),3)
        self.assertEqual(len(project['assets']),3)
        brand=next(page for page in project['pages'] if page['title']=='Brand launch')
        self.assertIn('logo pack',brand['body'])
        self.assertEqual(brand['properties']['Client'],'Northstar Studio')
        self.assertEqual(brand['properties']['Status'],'In progress')
        self.assertEqual([item['done'] for item in brand['checklist']],[True,True,False])
        self.assertEqual(len(brand['attachments']),1)
        client=next(page for page in project['pages'] if page['title']=='Northstar Studio')
        self.assertTrue(any(link['target']==client['id'] for link in brand['links']))
        brief=next(page for page in project['pages'] if page['title']=='Continuity brief')
        self.assertIn('authorized export',brief['body'])
        self.assertIn('illustrative',brief['body'])
        self.assertFalse(project['workflow']['confirmed'])
        self.assertEqual(project['tasks'],[])

    def test_unknown_scenarios_are_not_silently_replaced(self):
        with self.assertRaises(ValueError):sample_archive('not-a-scenario')


if __name__=='__main__':unittest.main()
