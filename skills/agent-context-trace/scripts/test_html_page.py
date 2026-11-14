"""Packaging regressions using only synthetic source text."""
import base64
import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

from html_page import render_html
from trace import parser


class HtmlPageTests(unittest.TestCase):
    def test_viewer_presentation_rules(self):
        result = subprocess.run(["node", "--test", str(Path(__file__).with_name("test_viewer.cjs"))],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_recorded_html_cannot_escape_the_inert_data_block(self):
        source = '</script><script>throw "injected"</script>&\u2028\u2029😀{{SCRIPT}}'
        data = {"sources": {"synthetic": source}}
        page = render_html(data)
        payload = re.search(r'<script type="application/json" id="trace-data">(.*?)</script>', page, re.S)[1]
        self.assertEqual(json.loads(payload), data)
        self.assertNotIn("<", payload)
        self.assertNotIn("&", payload)
        self.assertEqual(len(re.findall(r"<script\b", page)), 2)
        self.assertNotIn('src="http', page)
        self.assertNotIn('href="http', page)

    def test_csp_authorizes_only_the_packaged_viewer(self):
        page = render_html({})
        script = re.findall(r"<script>(.*?)</script>", page, re.S)[0]
        actual_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        self.assertIn("script-src 'sha256-" + actual_hash + "'", page)
        self.assertIn("connect-src 'none'", page)
        self.assertIn("img-src data:", page)
        csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', page)[1]
        directive = next(part.strip() for part in csp.split(';') if part.strip().startswith('script-src'))
        self.assertEqual(directive, "script-src 'sha256-" + actual_hash + "'")
        self.assertNotIn('unsafe-inline', directive)
        self.assertNotRegex(csp, r'https?:|vscode:|agent-context-trace:')

    def test_vendor_scripts_and_styles_are_inlined_in_order_and_hashed(self):
        page = render_html({})
        assets = Path(__file__).resolve().parent.parent / 'assets'
        script = re.findall(r'<script>(.*?)</script>', page, re.S)[0]
        style = re.search(r'<style>(.*?)</style>', page, re.S)[1]
        names = ['vendor/markdown-it.min.js', 'vendor/overlayscrollbars.browser.es6.min.js', 'viewer.js']
        self.assertEqual(script, '\n;\n'.join((assets / name).read_text() for name in names))
        self.assertEqual(style, '\n'.join((assets / name).read_text() for name in
                                        ['vendor/overlayscrollbars.min.css', 'viewer.css']))
        self.assertNotRegex(page, r'<script[^>]+src=|<link[^>]+href=')

    def test_build_accepts_the_same_scope_arguments_as_data(self):
        arguments = ["--node", "/tmp/demo.jsonl", "--range", "10-15", "--focus", "/tmp/rules", "--focus", "/tmp/notes.md",
                     "--since", "2026-01-02", "--until", "2026-01-03", "--projects-dir", "/tmp/projects", "-o", "/tmp/out", "--tree"]
        data_args = vars(parser().parse_args(["data"] + arguments))
        build_args = vars(parser().parse_args(["build"] + arguments))
        data_args.pop("command"); build_args.pop("command")
        self.assertEqual(data_args, build_args)


if __name__ == "__main__":
    unittest.main()
