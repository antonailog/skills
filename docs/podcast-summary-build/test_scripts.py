"""Regression checks for source integrity and protection of existing user blocks."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

PACKAGE = Path(__file__).resolve().parents[2] / 'skills/podcast-summary'
spec = importlib.util.spec_from_file_location('audit', PACKAGE / 'scripts/audit_document.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditTests(unittest.TestCase):
    def root(self, body):
        return ET.fromstring('<doc>' + body + '</doc>')

    def test_healthy_unchanged_document(self):
        r = self.root('<title id="t">节目</title><h1 id="h">关键内容</h1><p id="p">内容</p><p id="gap"/><h2 id="pvt">个人思考</h2><p id="mine">我想留到下周</p>')
        self.assertTrue(audit.audit(r, r, [])['pass'])

    def test_authorized_subtree_replacement(self):
        a = self.root('<title id="t">节目</title><figure id="old"><source id="f" name="旧.svg"/></figure><p id="mine">我的话</p>')
        b = self.root('<title id="t">节目</title><figure id="new"><source id="n" name="新.svg"/></figure><p id="mine">我的话</p>')
        self.assertTrue(audit.audit(a, b, ['old'])['pass'])

    def test_private_record_mutation_fails(self):
        a = self.root('<p id="mine">我还没决定</p>')
        b = self.root('<p id="mine">我决定购买</p>')
        self.assertEqual(audit.audit(a, b, [])['unexpected_changed'], ['mine'])

    def test_reordering_protected_blocks_fails(self):
        a = self.root('<p id="a">前</p><p id="b">后</p>')
        b = self.root('<p id="b">后</p><p id="a">前</p>')
        self.assertFalse(audit.audit(a, b, [])['pass'])

    def test_heading_spacing_detects_missing_and_duplicate(self):
        for body in ['<p>正文</p><h2>要点</h2>', '<p>正文</p><p/><p/><h2>要点</h2>']:
            r = self.root(body)
            self.assertFalse(audit.audit(r, r, [])['pass'])

    def test_unknown_allowlist_and_duplicate_ids_rejected(self):
        r = self.root('<p id="a">正文</p>')
        with self.assertRaises(ValueError):
            audit.audit(r, r, ['typo'])
        with self.assertRaises(ValueError):
            audit.block_map(self.root('<p id="a"/><p id="a"/>'))

    def test_duplicate_images_use_src_and_require_review(self):
        r = self.root('<img id="a" src="image-source"/><img id="b" src="image-source"/>')
        result = audit.audit(r, r, [])
        self.assertEqual(result['duplicate_image_sources_review'], ['image-source'])
        self.assertEqual(result['resources_after'][0]['src'], 'image-source')
        self.assertTrue(result['pass'])  # Reuse may be intentional; it is a review flag, not automatic failure.


class ManifestTests(unittest.TestCase):
    def run_cli(self, root, *args):
        return subprocess.run(['python3', str(PACKAGE / 'scripts/source_manifest.py'), *args,
                               '--root', str(root), '--manifest', 'manifest.json'],
                              capture_output=True, text=True)

    def test_create_verify_tamper_missing_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'sources').mkdir()
            file = root / 'sources/transcript.txt'
            file.write_text('完整原文')
            self.assertEqual(self.run_cli(root, 'create', 'sources').returncode, 0)
            self.assertEqual(self.run_cli(root, 'verify').returncode, 0)
            self.assertEqual(self.run_cli(root, 'create', 'sources').returncode, 2)
            file.write_text('被误改')
            self.assertEqual(self.run_cli(root, 'verify').returncode, 1)
            file.unlink()
            result = self.run_cli(root, 'verify')
            self.assertEqual(json.loads(result.stdout)['missing'], ['sources/transcript.txt'])

    def test_escape_root_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(self.run_cli(td, 'create', '../').returncode, 2)

    def test_symlinks_must_resolve_inside_selected_root(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            root = Path(td)
            (root/'sources').mkdir()
            (root/'results').mkdir()
            (root/'results/file.txt').write_text('原文')
            (root/'sources/link.txt').symlink_to(root/'results/file.txt')
            self.assertEqual(self.run_cli(root, 'create', 'sources').returncode, 0)
            self.assertEqual(self.run_cli(root, 'verify').returncode, 0)
            (root/'sources/link.txt').unlink()
            (Path(outside)/'file.txt').write_text('不在明确范围内')
            (root/'sources/link.txt').symlink_to(Path(outside)/'file.txt')
            self.assertEqual(self.run_cli(root, 'verify').returncode, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
