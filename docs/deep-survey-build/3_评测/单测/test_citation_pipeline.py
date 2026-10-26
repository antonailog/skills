"""来源交付回归：防止编号存在但指向错误，以及重跑时损坏原始资料。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(os.environ.get("DEEP_SURVEY_SKILL", Path(__file__).resolve().parents[4] / "skills/deep-survey"))


class CitationPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.sources = self.d / "sources.json"
        self.sources.write_text(json.dumps([
            {"n": 7, "title": "完整的来源甲标题", "url": "https://a.example/page", "date": "2026-10-14"},
            {"n": 3, "title": "完整的来源乙标题", "url": "https://b.example/page", "date": "2026-10-14"},
        ]), encoding="utf-8")
        self.report = self.d / "report.md"
        self.report.write_text(
            "# 参会判断\n\n## 一分钟看懂\n\n事实 [7,3]。\n\n"
            "## 还不知道的\n\n排期未知。\n\n## 口径与来源\n\n保留口径。\n\n"
            "7. 完整的来源甲标题 — https://a.example/page（2026-10-14）\n"
            "3. 完整的来源乙标题 — https://b.example/page（2026-10-14）\n", encoding="utf-8")

    def run_script(self, script, *args):
        return subprocess.run([sys.executable, str(SKILL / "scripts" / script), *map(str, args)],
                              capture_output=True, text=True)

    def renumber(self, *args):
        return self.run_script("renumber_sources.py", self.report, "--sources", self.sources, *args)

    def files(self):
        return {str(p.relative_to(self.d)): p.read_bytes() for p in self.d.rglob("*") if p.is_file()}

    def test_delivery_syncs_links_tables_legacy_csv_and_is_idempotent(self):
        dossier = self.d / "40-dossier"
        dossier.mkdir()
        csv = dossier / "compare.csv"
        csv.write_text("产品,来源,日期\n甲,7;3,2026-10-14\n", encoding="utf-8")
        original_report, original_sources = self.report.read_bytes(), self.sources.read_bytes()
        r = self.renumber()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[1](https://a.example/page), [2](https://b.example/page)", self.report.read_text())
        self.assertEqual([(x["n"], x["url"]) for x in json.loads(self.sources.read_text())],
                         [(1, "https://a.example/page"), (2, "https://b.example/page")])
        self.assertIn("https://a.example/page;https://b.example/page", csv.read_text())
        self.assertTrue((self.d / "sources.md").is_file())
        self.assertEqual((self.d / "report-编号前.md").read_bytes(), original_report)
        self.assertEqual((self.d / "sources-编号前.json").read_bytes(), original_sources)
        delivered = self.files()
        r = self.renumber()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.files(), delivered)
        r = self.run_script("check_report.py", self.report, "--sources", self.sources)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_dry_run_writes_nothing(self):
        before = self.files()
        self.assertEqual(self.renumber("--dry-run").returncode, 0)
        self.assertEqual(self.files(), before)

    def test_unknown_chart_source_cannot_hide_behind_new_number(self):
        data = self.d / "charts/data"
        data.mkdir(parents=True)
        # 旧编号 1 未出现在正文，恰好会成为重排后的新编号 1。
        (data / "chart.json").write_text(json.dumps({"items": [{"source": [1]}]}))
        before = self.files()
        r = self.renumber("--charts", data.parent)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.files(), before)

    def test_chart_sources_remap_and_repeated_run_is_stable(self):
        data = self.d / "charts/data"
        data.mkdir(parents=True)
        chart = data / "chart.json"
        chart.write_text(json.dumps({"items": [{"source": [7, 3]}], "series": {"source": [[3], [7, 3]]}}))
        self.assertEqual(self.renumber("--charts", data.parent).returncode, 0)
        s = json.loads(chart.read_text())
        self.assertEqual(s["items"][0]["source"], [1, 2])
        self.assertEqual(s["series"]["source"], [[2], [1, 2]])
        before = self.files()
        self.assertEqual(self.renumber("--charts", data.parent).returncode, 0)
        self.assertEqual(self.files(), before)

    def test_checker_detects_same_number_wrong_source(self):
        self.report.write_text(self.report.read_text().replace("https://a.example/page", "https://wrong.example/page"))
        r = self.run_script("check_report.py", self.report, "--sources", self.sources)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("URL", r.stdout)

    def test_tracking_variants_are_not_false_mismatches(self):
        self.report.write_text(self.report.read_text().replace(
            "https://a.example/page", "https://www.a.example/page?ref=newsletter&utm_source=test#details"))
        r = self.renumber()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.run_script("check_report.py", self.report, "--sources", self.sources)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_wrong_clickable_link_is_rejected_before_mutation(self):
        self.report.write_text(self.report.read_text().replace("[7,3]", "[7](https://wrong.example/page), [3]"))
        before = self.files()
        self.assertNotEqual(self.renumber().returncode, 0)
        self.assertEqual(self.files(), before)
        self.assertNotEqual(self.run_script("check_report.py", self.report, "--sources", self.sources).returncode, 0)

    def test_merge_same_page_has_single_consistent_target(self):
        items = json.loads(self.sources.read_text())
        items[1]["url"] = "https://a.example/page#details"
        self.sources.write_text(json.dumps(items))
        self.report.write_text(self.report.read_text().replace("https://b.example/page", "https://a.example/page#details"))
        self.assertEqual(self.renumber().returncode, 0)
        self.assertEqual(len(json.loads(self.sources.read_text())), 1)
        self.assertEqual(self.report.read_text().count("[1](https://a.example/page)"), 1)
        self.assertEqual(self.run_script("check_report.py", self.report, "--sources", self.sources).returncode, 0)

    def test_rebuild_preserves_existing_numbers_and_csv_urls(self):
        (self.d / "10-facts.md").write_text("- 新材料 — 完整来源丙（https://c.example/page，2026-10-14）\n")
        dossier = self.d / "40-dossier"
        dossier.mkdir()
        csv = dossier / "compare.csv"
        csv.write_text("产品,来源,日期\n甲,https://a.example/page,2026-10-14\n")
        original_csv = csv.read_bytes()
        r = self.run_script("build_source_table.py", self.d)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ids = {x["url"]: x["n"] for x in json.loads(self.sources.read_text())}
        self.assertEqual(ids["https://a.example/page"], 7)
        self.assertEqual(ids["https://b.example/page"], 3)
        self.assertGreater(ids["https://c.example/page"], 7)
        self.assertEqual(csv.read_bytes(), original_csv)
        r = self.run_script("render_table.py", csv, "--sources", self.sources)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[7]", r.stdout)


if __name__ == "__main__":
    unittest.main()
