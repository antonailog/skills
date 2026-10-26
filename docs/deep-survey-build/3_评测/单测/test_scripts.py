"""deep-survey 脚本单测。运行：python3 -m unittest discover -s <本目录> -v

覆盖 v5 实跑踩过的坑：来源解析（全角括号、一行多个链接、嵌套括号）、池子索引不进来源表、
同页合并、反例与线索表检查、出图编码规则。只用标准库。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# 本文件在 <仓库>/docs/deep-survey-build/3_评测/单测/ 下，skill 在 <仓库>/skills/deep-survey
SKILL = Path(os.environ.get("DEEP_SURVEY_SKILL", Path(__file__).resolve().parents[4] / "skills" / "deep-survey"))
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)


class BuildSourceTable(unittest.TestCase):
    def build(self, note_text, extra=None):
        d = Path(tempfile.mkdtemp())
        (d / "10-测试.md").write_text(note_text, encoding="utf-8")
        for name, text in (extra or {}).items():
            (d / name).write_text(text, encoding="utf-8")
        r = run(SCRIPTS / "build_source_table.py", d)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return {s["url"]: s for s in json.loads((d / "sources.json").read_text(encoding="utf-8"))}

    def test_fullwidth_parens_title_and_date(self):
        src = self.build("## Cited Findings\n- {N1} 某事实 — 标题甲（https://a.com/x ，2026-01-02）\n")
        s = src["https://a.com/x"]
        self.assertEqual(s["title"], "标题甲")
        self.assertEqual(s["date"], "2026-01-02")

    def test_fullwidth_comma_right_after_url(self):
        src = self.build("## Cited Findings\n- {N1} 某事实 — 标题乙（https://b.com/y，2025-03-04）\n")
        self.assertIn("https://b.com/y", src)

    def test_two_urls_in_one_line(self):
        src = self.build("## Cited Findings\n- {N2} 两源 — 标题丙（https://c.com/1 ，2026-02-01）；"
                         "标题丁（https://d.com/2 ，2026-02-02）\n")
        self.assertEqual(src["https://c.com/1"]["title"], "标题丙")
        self.assertEqual(src["https://d.com/2"]["title"], "标题丁")
        self.assertEqual(src["https://d.com/2"]["date"], "2026-02-02")

    def test_nested_parens_in_title(self):
        src = self.build("## Cited Findings\n- {N3} 某事实 — 年度报告（2025 版）（https://e.com/3 ，2025-05-06）\n")
        self.assertEqual(src["https://e.com/3"]["title"], "年度报告（2025 版）")

    def test_tracking_params_and_www_removed(self):
        src = self.build("## Cited Findings\n- {N1} x — 标题（https://www.f.com/p?id=1&utm_source=x ，2026-01-01）\n")
        self.assertIn("https://f.com/p?id=1", src)

    def test_pool_index_not_counted(self):
        src = self.build("## Cited Findings\n- {N1} x — 标题（https://g.com/1 ，2026-01-01）\n",
                         {"05-自有信源池.md": "1. **没被引用的池子条目**\n   https://pool.com/a\n"})
        self.assertNotIn("https://pool.com/a", src)


class Renumber(unittest.TestCase):
    def test_app_store_variants_are_one_page(self):
        from renumber_sources import page_key
        a = page_key("https://apps.apple.com/cn/app/%E7%8C%AB/id6475000292")
        b = page_key("https://apps.apple.com/cn/app/id6475000292?see-all=reviews")
        self.assertEqual(a, b)
        self.assertNotEqual(a, page_key("https://apps.apple.com/us/app/id6475000292"))

    def test_36kr_desktop_and_mobile_are_one_page(self):
        from renumber_sources import page_key
        self.assertEqual(page_key("https://36kr.com/p/123"), page_key("https://m.36kr.com/p/123"))

    def test_keeps_writer_entries(self):
        d = Path(tempfile.mkdtemp())
        (d / "sources.json").write_text(json.dumps([
            {"n": 7, "title": "残缺）标题", "url": "https://h.com/a", "date": ""},
            {"n": 3, "title": "", "url": "https://h.com/b", "date": ""}], ensure_ascii=False), encoding="utf-8")
        rp = d / "report.md"
        rp.write_text("## 一分钟看懂\n\n正文 [7]，再 [3]。\n\n## 口径与来源\n\n口径说明。\n\n"
                      "3. 报告员写的乙 — https://h.com/b（2026-01-01）\n"
                      "7. 报告员写的甲（弱来源：导购站） — https://h.com/a（2026-01-02）\n", encoding="utf-8")
        r = run(SCRIPTS / "renumber_sources.py", rp, "--sources", d / "sources.json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = rp.read_text(encoding="utf-8")
        self.assertIn("正文 [1](https://h.com/a)，再 [2](https://h.com/b)", out)
        self.assertIn("1. 报告员写的甲（弱来源：导购站） — https://h.com/a", out)
        self.assertIn("口径说明。", out)


REPORT = """# 标题

## 一分钟看懂

**是什么**：x。

| 项 | 内容 |
|---|---|
| {row1} | 一段文本和几道题 |
| 输出 | 选项和概率 |
| 效果 | 英文分类同类前列 |
| 价格 | 输入每百万 token 0.042 美元 |
| 结论 | {conclusion} |

![导引](g.svg)

读法导航。

## 一、是什么：x

事实 [1]。

## 二、{chap2}：y

### 第二梯队

{tier_intro}

| 玩家 | 线索 |
|---|---|
| A | 1 |

{body_extra}

## 三、集成判断：z

| 选项 | 适合谁 | 代价 | 先验证什么 | 通过 / 放弃线 | 周期 | 预算 |
|---|---|---|---|---|---|---|
| a | b | c | d | e | f | g |

## 四、还不知道的
{extra_section}
## 推荐阅读

- {rec}（机构，2026）[1]：推荐原因写够八个字以上。

## 口径与来源

1. {title} — https://x.com/a（2026-01-01）
"""

class CheckReport(unittest.TestCase):
    """v8：脚本只查机械项（引用、固定部分、图片、表格、凭证），不查章节大纲、事实表形状与写法。"""

    def check(self, **kw):
        d = Path(tempfile.mkdtemp())
        (d / "g.svg").write_text("<svg/>", encoding="utf-8")
        fields = {"tier_intro": "规模线索未逐条核查。", "body_extra": "", "title": "某机构《某报告》",
                  "row1": "输入", "chap2": "格局", "extra_section": "",
                  "rec": "**[甲](https://x.com/a)**", "conclusion": "先小试"}
        fields.update(kw)
        (d / "r.md").write_text(REPORT.format(**fields), encoding="utf-8")
        return run(SCRIPTS / "check_report.py", d / "r.md").stdout

    def test_clean_report_has_no_errors_or_new_warnings(self):
        out = self.check()
        self.assertIn("— 错误 0", out, out)
        for code in ("W17", "W18"):
            self.assertNotIn(code, out)

    def test_site_only_source_title(self):
        self.assertIn("W17", self.check(title="App Store 美区"))
        self.assertIn("W17", self.check(title="15，笔记内证）；某站"))

    def test_internal_tool_name(self):
        self.assertIn("W18", self.check(body_extra="数据来自 Info2Action 召回。"))

    def test_plan_outline_and_fact_rows_not_checked(self):
        out = self.check(chap2="输入输出", row1="规模")
        self.assertNotIn("E3", out, out)
        self.assertNotIn("E5", out, out)

    def test_leave_questions_section_removed(self):
        self.assertIn("E3 「留给你的问题」已取消", self.check(extra_section="\n## 留给你的问题\n\n1. 一\n"))

    def test_reading_title_needs_link(self):
        self.assertIn("E9", self.check(rec="**甲**"))
        self.assertNotIn("E9", self.check())

    def test_source_word_in_chapter_title_is_fine(self):
        out = self.check(chap2="格局：收入来源集中在 API")
        self.assertNotIn("E3", out, out)

    def test_credential_is_error(self):
        self.assertIn("E8", self.check(body_extra="调用示例：Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456"))
        self.assertIn("E8", self.check(body_extra="链接 https://api.example.com/v1?api_key=abc123def456"))
        self.assertNotIn("E8", self.check(body_extra="官方文档说要在请求头里带 Bearer token，示例已略去。"))


class DossierSources(unittest.TestCase):
    def test_csv_keeps_urls_and_renders_current_numbers(self):
        d = Path(tempfile.mkdtemp())
        (d / "10-1-格局.md").write_text("- 甲 — 某文（https://a.com/x，2026-01-01）\n", encoding="utf-8")
        (d / "40-dossier").mkdir()
        (d / "40-dossier" / "价格.csv").write_text(
            "产品,价格,来源,日期\n甲,1 美元,https://a.com/x;https://b.com/y,2026-01\n乙,2 美元,本机：src/a.py:3,2026-01\n",
            encoding="utf-8")
        r = run(SCRIPTS / "build_source_table.py", d)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        csv_text = (d / "40-dossier" / "价格.csv").read_text(encoding="utf-8")
        self.assertIn("https://a.com/x;https://b.com/y", csv_text)
        self.assertIn("本机：src/a.py:3", csv_text)
        r = run(SCRIPTS / "render_table.py", d / "40-dossier" / "价格.csv")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("[1,2]", r.stdout)
        self.assertIn("`本机：src/a.py:3`", r.stdout)

class ChartRules(unittest.TestCase):
    def render(self, spec):
        d = Path(tempfile.mkdtemp())
        (d / "s.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        return run(SCRIPTS / "make_chart.py", d / "s.json", "--out", d / "s.png", "--theme", "clean-默认")

    def test_mixed_periods_rejected(self):
        r = self.render({"type": "bar", "title": "t", "items": [
            {"label": "A", "value": 1, "source": [1], "period": "2025 全年"},
            {"label": "B", "value": 2, "source": [2], "period": "2025H1"}]})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("期间", r.stdout + r.stderr)

    def test_ratio_needs_denominator(self):
        r = self.render({"type": "bar", "title": "t", "unit": "%", "items": [
            {"label": "A", "value": 10, "source": [1]}]})
        self.assertIn("分母", r.stdout + r.stderr)

    def test_timeline_kinds_limit(self):
        ev = [{"date": f"202{i}", "label": f"事件{i}", "kind": f"类{i}", "source": [1]} for i in range(5)]
        r = self.render({"type": "timeline", "title": "t", "events": ev})
        self.assertIn("最多 4 种", r.stdout + r.stderr)

    def test_timeline_renders(self):
        ev = [{"date": "2023-02", "label": "意大利叫停 Replika", "kind": "监管", "source": [1]},
              {"date": "2024-08", "label": "Google 带走创始人", "kind": "资本", "source": [2]}]
        self.assertEqual(self.render({"type": "timeline", "title": "t", "events": ev}).returncode, 0)


if __name__ == "__main__":
    unittest.main()
