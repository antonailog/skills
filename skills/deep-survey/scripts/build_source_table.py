#!/usr/bin/env python3
"""合并研究笔记中的来源：去重、编号、按域名初分 evidence family。

用法：
  python3 build_source_table.py <research_notes/课题目录> [--existing sources.json]

输出到同一目录：sources.json 与 sources.md。
--existing 保留旧编号（续查时不打乱正文引用），新来源接着编号。

另外标两件事（报告「口径与来源」据此在行尾注明）：
- origin = 自有信源：URL 出现在 05-自有信源池.json（Info2Action 召回）。
- weak = 原因：域名在固定信源库「踩坑名单」里属于导购、推广、聚合类；或引用它的每一行都标了「仅见搜索摘要」。
  信源库位置取环境变量 DEEP_SURVEY_SOURCE_LIBRARY，默认 ~/claudecode_workspace/知识/调研/_信源库/信源库.md，不存在就跳过。
"""
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

URL_RE = re.compile(r"https?://[^\s<>()\[\]\"'`）】」，、；：]+")
MD_LINK_RE = re.compile(r"\[([^\]]{1,200})\]\((https?://[^)\s]+)\)")
# 研究员常用格式：标题（URL ，日期）或 标题 (URL, date)，括号全角半角都认
PAREN_CITE_RE = re.compile(
    r"([^（(\[\]—；;、]{2,160}?)\s*[（(]\s*(https?://[^\s）),，]+)\s*(?:[，,]\s*([^）)]{0,40}))?\s*[）)]"
)
DATE_RE = re.compile(r"(20\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2})?日?)")
MULTI_LABEL_TLDS = {"com.cn", "net.cn", "org.cn", "gov.cn", "co.uk", "co.jp", "com.au", "com.hk", "com.tw", "co.kr"}
FIRST_PARTY_HINTS = ("github.com", "apps.apple.com", "play.google.com", "producthunt.com")
COMMUNITY_HINTS = ("reddit.com", "x.com", "twitter.com", "xiaohongshu.com", "weibo.com", "v2ex.com", "news.ycombinator.com", "zhihu.com")
REPORT_HINTS = ("iresearch", "analysys", "qianzhan", "questmobile", "statista", "gartner", "forrester", "mckinsey", "a16z", "sensortower", "similarweb", "ibisworld")


WEAK_MARKS = ("仅见搜索摘要", "仅搜索摘要", "未读原文")
LIBRARY = Path(os.environ.get("DEEP_SURVEY_SOURCE_LIBRARY",
                              Path.home() / "claudecode_workspace" / "知识" / "调研" / "_信源库" / "信源库.md"))


def weak_domains() -> dict[str, str]:
    """从信源库「踩坑名单」读导购、推广、聚合类域名。"""
    out: dict[str, str] = {}
    if not LIBRARY.exists():
        return out
    on = False
    for line in LIBRARY.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            on = "踩坑" in line
            continue
        if not on or not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or not any(k in cells[1] for k in ("导购", "推广", "聚合", "利益")):
            continue
        reason = "导购或聚合站" if ("导购" in cells[1] or "聚合" in cells[1]) else "带推广利益"
        for d in re.findall(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", cells[0].lower()):
            out[d.removeprefix("www.")] = reason
    return out


def normalize(url: str) -> str:
    url = url.rstrip(".,;:。，；：")
    parts = urlsplit(url)
    query = "&".join(q for q in parts.query.split("&") if q and not q.lower().startswith(("utm_", "ref=", "spm=", "from=")))
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip("/"), query, ""))


def family_of(host: str) -> str:
    labels = host.split(":")[0].split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_LABEL_TLDS:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def guess_type(host: str) -> str:
    if any(h in host for h in COMMUNITY_HINTS):
        return "社区原帖"
    if any(h in host for h in REPORT_HINTS):
        return "研报"
    if any(h in host for h in FIRST_PARTY_HINTS):
        return "一方"
    return "待定（一方/媒体）"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    notes_dir = Path(sys.argv[1])
    existing_path = None
    if "--existing" in sys.argv:
        existing_path = Path(sys.argv[sys.argv.index("--existing") + 1])
    if not notes_dir.is_dir():
        print(f"目录不存在: {notes_dir}")
        return 2

    sources: dict[str, dict] = {}
    if existing_path and existing_path.exists():
        for item in json.loads(existing_path.read_text(encoding="utf-8")):
            sources[item["url"]] = item

    next_n = max([s["n"] for s in sources.values()], default=0) + 1
    cite_lines: dict[str, int] = {}
    weak_lines: dict[str, int] = {}
    for md in sorted(notes_dir.glob("*.md")):
        # 0 开头的是确认单、计划、自有信源池索引：池子里的链接没被引用就不算来源
        if md.name in ("report.md", "sources.md") or md.name.startswith("0"):
            continue
        for line in md.read_text(encoding="utf-8", errors="replace").splitlines():
            titles = {normalize(u): t.strip() for t, u in MD_LINK_RE.findall(line)}
            dates: dict[str, str] = {}
            for t, u, d in PAREN_CITE_RE.findall(line):
                key = normalize(u)
                t = re.sub(r"^.*[—]\s*", "", t).strip(" -—:：")
                titles.setdefault(key, t)
                if d:
                    dm = DATE_RE.search(d)
                    dates[key] = dm.group(1) if dm else d.strip()
            date_m = DATE_RE.search(line)
            is_weak_line = any(w in line for w in WEAK_MARKS)
            for m in URL_RE.finditer(line):
                raw = m.group(0)
                url = normalize(raw)
                if md.name.startswith("1"):
                    cite_lines[url] = cite_lines.get(url, 0) + 1
                    weak_lines[url] = weak_lines.get(url, 0) + (1 if is_weak_line else 0)
                if url not in titles:
                    # 兜底：取 URL 前最后一个“—”之后、到 URL 为止的文字作标题
                    before = line[: m.start()]
                    seg = before.rsplit("—", 1)[-1] if "—" in before else before.rsplit("-", 1)[-1]
                    seg = re.sub(r"[（(]\s*$", "", seg)
                    seg = re.sub(r"[（(][^（()）]*[）)]", lambda mm: mm.group(0), seg)
                    seg = seg.strip(" 　:：,，;；、\t")
                    if 2 <= len(seg) <= 160 and not seg.startswith(("http", "- ")):
                        titles[url] = seg
                if url not in dates:
                    after = line[m.end(): m.end() + 60]
                    dm = DATE_RE.search(after.split("）")[0].split(")")[0])
                    if dm:
                        dates[url] = dm.group(1)
                if url in sources:
                    sources[url]["cited_in"].append(md.name)
                    if not sources[url]["title"] and titles.get(url):
                        sources[url]["title"] = titles[url]
                    if not sources[url]["date"] and dates.get(url):
                        sources[url]["date"] = dates[url]
                    continue
                host = urlsplit(url).netloc
                sources[url] = {
                    "n": next_n,
                    "title": titles.get(url, ""),
                    "url": url,
                    "date": dates.get(url) or (date_m.group(1) if date_m else ""),
                    "type": guess_type(host),
                    "family": family_of(host),
                    "cited_in": [md.name],
                }
                next_n += 1

    items = sorted(sources.values(), key=lambda s: s["n"])
    own = set()
    pool = notes_dir / "05-自有信源池.json"
    if pool.exists():
        own = {normalize(x.get("url", "")) for x in json.loads(pool.read_text(encoding="utf-8")) if x.get("url")}
    wd = weak_domains()
    for s in items:
        if s["url"] in own:
            s["origin"] = "自有信源"
        host = urlsplit(s["url"]).netloc
        reason = next((r for d, r in wd.items() if host == d or host.endswith("." + d)), None)
        if reason:
            s["weak"] = reason
        elif cite_lines.get(s["url"]) and weak_lines.get(s["url"]) == cite_lines.get(s["url"]):
            s["weak"] = "只读到搜索摘要"
        s["cited_in"] = sorted(set(s["cited_in"]))
        # 标题清理：去掉夹带的 URL 与残缺括号
        t = re.sub(r"[（(]?\s*https?://\S+", "", s["title"])
        t = t.strip(" 　（()）:：,，;；、")
        s["title"] = t
    (notes_dir / "sources.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["| 编号 | 标题 | URL | 日期 | 类型 | family | 标记 |", "|---|---|---|---|---|---|---|"]
    for s in items:
        mark = "；".join(x for x in (s.get("origin", ""), f"弱：{s['weak']}" if s.get("weak") else "") if x) or "—"
        lines.append(f"| {s['n']} | {s['title'] or '（待填）'} | {s['url']} | {s['date'] or '（待填）'} | {s['type']} | {s['family']} | {mark} |")
    (notes_dir / "sources.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    families = {}
    for s in items:
        families.setdefault(s["family"], []).append(s["n"])
    multi = {f: ns for f, ns in families.items() if len(ns) > 1}
    print(f"来源 {len(items)} 条，family {len(families)} 个，写入 {notes_dir / 'sources.json'} 与 sources.md")
    if multi:
        print("同 family 多来源（验证者按内容确认是否转引同源）：")
        for f, ns in multi.items():
            print(f"  {f}: {ns}")
    weak_n = [s["n"] for s in items if s.get("weak")]
    if weak_n:
        print(f"弱来源 {len(weak_n)} 条（导购 / 聚合 / 只读到摘要），报告里不能单独撑结论：{weak_n[:30]}")
    own_n = sum(1 for s in items if s.get("origin") == "自有信源")
    if own_n:
        print(f"自有信源 {own_n} 条")
    blank = [s["n"] for s in items if not s["title"] or not s["date"]]
    if blank:
        print(f"标题或日期待填的编号: {blank}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
