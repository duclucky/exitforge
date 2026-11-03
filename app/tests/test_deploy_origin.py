"""A fixed domain must survive stale Quick Tunnel logs and process restarts."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('watch_origin', Path(__file__).resolve().parents[1] / 'deploy/watch_origin.py')
watch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(watch)


class DeploymentOriginTests(unittest.TestCase):
    def test_fixed_origin_wins_over_temporary_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            fixed = Path(directory) / 'fixed-origin.txt'
            fixed.write_text('https://exitforge.site\n')
            self.assertEqual(watch.choose_origin(fixed, 'https://old.trycloudflare.com'), 'https://exitforge.site')

    def test_invalid_fixed_origin_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fixed = Path(directory) / 'fixed-origin.txt'
            for value in ('', 'http://exitforge.site', 'https://exitforge.site/path', 'https://user@exitforge.site', 'https://exitforge.site:444'):
                fixed.write_text(value)
                with self.assertRaises(ValueError):
                    watch.choose_origin(fixed, 'https://old.trycloudflare.com')

    def test_preview_mode_uses_latest_tunnel_url(self):
        with tempfile.TemporaryDirectory() as directory:
            fixed = Path(directory) / 'fixed-origin.txt'
            self.assertEqual(watch.choose_origin(fixed, 'https://old.trycloudflare.com https://new.trycloudflare.com'), 'https://new.trycloudflare.com')
            self.assertEqual(watch.choose_origin(fixed, 'no tunnel'), '')
