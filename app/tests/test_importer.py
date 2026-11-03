import io
import unittest
import zipfile

from exitforge.importer import ImportFailure, recover_archive


def archive(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, contents in files.items():
            bundle.writestr(name, contents)
    return output.getvalue()


class RecoveryTests(unittest.TestCase):
    def test_recovers_changed_records_links_checklists_and_local_attachment(self):
        a, b = "a" * 32, "b" * 32
        result = recover_archive(archive({
            f"Projects {a}.csv": 'Name,Status,Client\nLaunch,Review,Acme\n',
            f"Projects {a}/Launch {b}.md": '# Launch\n\n[Acme](../Acme%20' + 'c' * 32 + '.md)\n\n- [x] Draft\n- [ ] Deliver\n\n[Brief](brief.txt)',
            f"Acme {'c' * 32}.md": '# Acme\n\nA real linked client page.',
            f"Projects {a}/brief.txt": 'Scope and delivery notes.',
        }), 'changed.zip')
        launch = next(x for x in result['pages'] if x['title'] == 'Launch')
        self.assertEqual(launch['properties']['Status'], 'Review')
        self.assertEqual([x['done'] for x in launch['checklist']], [True, False])
        self.assertEqual(launch['links'][0]['target'], 'c' * 32)
        self.assertEqual(len(launch['attachments']), 1)
        self.assertEqual(len(result['databases'][0]['rows']), 1)
        self.assertFalse(result['workflow']['confirmed'])
        self.assertEqual(result['provenance']['mode'], 'local-parser')

    def test_keeps_ambiguous_relations_unresolved(self):
        result = recover_archive(archive({
            'Projects.csv': 'Name,Client\nJob,Acme\n',
            'one/Acme.md': '# Acme\nOne',
            'two/Acme.md': '# Acme\nTwo',
        }))
        job = next(x for x in result['pages'] if x['title'] == 'Job')
        self.assertEqual(job['relations'], [])
        self.assertTrue(any('ambiguous' in x.lower() for x in result['warnings']))

    def test_rejects_traversal_and_non_zip(self):
        with self.assertRaises(ImportFailure):
            recover_archive(archive({'../escape.md': '# Bad'}))
        with self.assertRaises(ImportFailure):
            recover_archive(b'not a zip')

    def test_does_not_embed_executable_attachments_or_follow_external_links(self):
        result = recover_archive(archive({
            'Page.md': '# Page\n\n[External](https://example.test/no-fetch)\n[Evil](bad.html)',
            'bad.html': '<script>alert(1)</script>',
        }))
        self.assertFalse(result['assets'])
        self.assertTrue(any('unsupported' in x.lower() for x in result['warnings']))
        self.assertEqual(result['pages'][0]['links'][0]['external'], True)

    def test_duplicate_source_identifiers_do_not_silently_merge(self):
        key = 'f' * 32
        with self.assertRaises(ImportFailure):
            recover_archive(archive({f'One {key}.md':'# One', f'Two {key}.md':'# Two'}))

    def test_rejects_unbounded_expansion(self):
        with self.assertRaises(ImportFailure):
            recover_archive(archive({'Huge.md':'A' * 3_000_000}))


if __name__ == '__main__':
    unittest.main()
