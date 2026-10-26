#!/usr/bin/env python3
"""交付前把报告的来源编号改成从 1 连续，并合并同一页面的多个编号。

用法：
  python3 renumber_sources.py <报告.md> --sources <sources.json> [--charts <charts 目录>] [--dry-run]

做什么：
  1. 按正文里第一次出现的顺序，给被引用的来源重新编号 1—N。
  2. 同一页面的多个旧编号合并成一个：App Store 页按「国家 + 应用编号」认（带不带应用名、
     带不带 ?see-all=reviews 都算同一页），36 氪桌面页与移动端页算同一页，其他网址去掉锚点后相同即同一页。
  3. 将正文和推荐阅读里的 [n]、[a,b] 及已有数字链接统一为可点击原文链接。
  4. 重写「口径与来源」的编号列表：沿用报告里原有的条目文字（报告员写的标题、日期、弱来源标记），
     只换编号；报告里没列的编号才用 sources.json 生成 `n. 标题 — URL（日期）`，弱来源（weak 字段）在行尾标出。
     列表之前的口径说明保留不动。
  5. 给了 --charts 时，同步改写 charts/data/*.json 的 source 字段，并提示重跑 make_chart.py（图的页脚编号要更新）。
  6. 同步 sources.json / sources.md，旧 CSV 数字恢复为 URL；保存编号对照与报告、来源原件，重跑不覆盖原件。

--dry-run 只打印会怎么改，不写文件。
"""
import csv
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from build_source_table import URL_RE, normalize, source_markdown

CITE_RE = re.compile(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\](?:\((https?://[^)\s]+)\))?")
LIST_RE = re.compile(r"^\s*(?:\[(\d{1,3})\]|(\d{1,3})[.、])\s+")


def page_key(url: str) -> str:
    u = urlsplit(normalize(url.strip()))
    host = u.netloc.lower()
    for p in ("www.", "m."):
        if host.startswith(p):
            host = host[len(p):]
    m = re.search(r"/([a-z]{2})/app/(?:[^/]+/)?(id\d+)", u.path)
    if host == "apps.apple.com" and m:
        return f"apps.apple.com/{m.group(1)}/{m.group(2)}"
    m = re.search(r"/p/(\d+)", u.path)
    if host == "36kr.com" and m:
        return f"36kr.com/p/{m.group(1)}"
    q = "&".join(x for x in u.query.split("&") if x and not x.startswith(("see-all", "utm_")))
    return f"{host}{u.path.rstrip('/')}" + (f"?{q}" if q else "")


def source_urls(text):
    return [m.group(0).split("（", 1)[0].rstrip(".,;:。，；：") for m in URL_RE.finditer(text)]


def sources_section(lines):
    """返回「口径与来源」节的起止行号（最后一个含「来源」、不是推荐阅读的二级标题）。"""
    idx = [i for i, l in enumerate(lines) if l.startswith("## ") and "来源" in l and "推荐" not in l]
    if not idx:
        return None, None
    a = idx[-1]
    b = next((i for i in range(a + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return a, b


def main() -> int:
    a = sys.argv[1:]
    if not a or "--sources" not in a:
        print(__doc__)
        return 2
    rp = Path(a[0])
    sp = Path(a[a.index("--sources") + 1])
    charts = Path(a[a.index("--charts") + 1]) if "--charts" in a else None
    dry = "--dry-run" in a
    original_report = rp.read_text(encoding="utf-8")
    original_sources = sp.read_text(encoding="utf-8")
    lines = original_report.splitlines()
    src = {int(s["n"]): s for s in json.loads(sp.read_text(encoding="utf-8"))}
    s0, s1 = sources_section(lines)
    if s0 is None:
        print("找不到「口径与来源」节")
        return 1
    body = lines[:s0]

    # 1 首次出现顺序
    order: list[int] = []
    for l in body:
        for m in CITE_RE.finditer(l):
            for x in m.group(1).split(","):
                n = int(x)
                if n not in order:
                    order.append(n)
    missing = [n for n in order if n not in src]
    if missing:
        print(f"正文引用了 sources.json 里没有的编号：{missing}，先修正")
        return 1

    # 已有链接若指向别的页面，应报错，不能在重排时掩盖错配。
    for line in body:
        for m in CITE_RE.finditer(line):
            if m.group(2) and any(page_key(m.group(2)) != page_key(src[int(n)]["url"])
                                  for n in m.group(1).split(",")):
                print(f"引用 URL 与来源编号不一致：{m.group(0)}")
                return 1

    # 2 合并同一页面
    key_new: dict[str, int] = {}
    old_new: dict[int, int] = {}
    new_src: dict[int, dict] = {}
    for n in order:
        k = page_key(src[n]["url"])
        if k not in key_new:
            key_new[k] = len(key_new) + 1
            new_src[key_new[k]] = dict(src[n], old=[n])
        else:
            new_src[key_new[k]]["old"].append(n)
            # 合并时优先保留不带查询串、标题更完整的那条
            cur = new_src[key_new[k]]
            if (not cur.get("title")) or ("?" in cur["url"] and "?" not in src[n]["url"]):
                cur.update({k2: v for k2, v in src[n].items() if k2 not in ("n", "old")})
        old_new[n] = key_new[k]

    def repl(m):
        nums = []
        for x in m.group(1).split(","):
            nn = old_new[int(x)]
            if nn not in nums:
                nums.append(nn)
        return ", ".join(f"[{n}]({new_src[n]['url']})" for n in nums)

    new_body = [CITE_RE.sub(repl, l) for l in body]

    # 4 来源列表
    sec = lines[s0:s1]
    keep = []
    for l in sec:
        if LIST_RE.match(l):
            break
        keep.append(l)
    while keep and not keep[-1].strip():
        keep.pop()
    # 报告员写的原条目（旧编号 → 编号之后的文字）。sources.json 的标题是脚本解析的，常残缺，只作兜底
    written: dict[int, str] = {}
    for l in sec:
        m = re.match(r"^\s*(?:\[(\d{1,3})\]|(\d{1,3})[.、])\s+(.*)$", l)
        if m:
            written[int(m.group(1) or m.group(2))] = m.group(3).rstrip()
    out_list = []
    reused = 0
    for nn in range(1, len(new_src) + 1):
        s = new_src[nn]
        old_text = next((written[o] for o in s["old"] if o in written), None)
        if old_text:
            urls = source_urls(old_text)
            if not urls or any(page_key(u) != page_key(s["url"]) for u in urls):
                print(f"来源条目 URL 与来源表不一致：旧编号 {s['old']}")
                return 1
            out_list.append(f"{nn}. {old_text}")
            reused += 1
            continue
        title = s.get("title") or "（无标题）"
        date = f"（{s['date']}）" if s.get("date") else ""
        weak = f"（弱来源：{s['weak']}）" if s.get("weak") else ""
        own = "（自有信源）" if s.get("origin") == "自有信源" else ""
        out_list.append(f"{nn}. {title} — {s['url']}{date}{own}{weak}")
    new_lines = new_body + keep + [""] + out_list + [""] + lines[s1:]

    merged = {nn: s["old"] for nn, s in new_src.items() if len(s["old"]) > 1}
    # 标题可疑：解析残留（以数字或标点开头、含「笔记」）、只有站名、太短。交付前人工改成文章名
    def bad_title(text):
        t = text.split(" — ")[0]
        opens = sum(t.count(c) for c in "（(《「")
        closes = sum(t.count(c) for c in "）)》」")
        return (re.match(r"^[，,；;）)、:：]|^\d+[，,；;）)]", t) or "笔记" in t or len(t) < 6 or opens != closes
                or re.search(r"\[新\d\]|来源缩写", t)
                or re.fullmatch(r"App Store.{0,6}|维基百科|iTunes Search API", t)
                or (not re.search(r"[《「\"“]", t) and len(t.split()) <= 2 and len(t) <= 14))
    suspicious = [i + 1 for i, line in enumerate(out_list) if bad_title(line.split(". ", 1)[1])]
    print(f"引用的来源 {len(order)} 个 → 合并同页后 {len(new_src)} 个，编号 1—{len(new_src)}；"
          f"沿用报告原条目 {reused} 条，按 sources.json 生成 {len(new_src) - reused} 条")
    if suspicious:
        print(f"标题可疑的新编号（只有站名或解析残留，交付前改成文章名）：{suspicious}")
    for nn, olds in merged.items():
        print(f"  合并 {olds} → {nn}：{new_src[nn]['url'][:70]}")

    # 5 先验证旧编号，再映射；未知旧编号不能与合法新编号碰巧相同。
    chart_changes = []
    if charts and (charts / "data").is_dir():
        for jp in sorted((charts / "data").glob("*.json")):
            spec = json.loads(jp.read_text(encoding="utf-8"))
            changed = False
            unknown = []

            def remap(value):
                nonlocal changed
                if isinstance(value, list):
                    values = [remap(v) for v in value]
                    return list(dict.fromkeys(values)) if all(isinstance(v, int) for v in values) else values
                if not isinstance(value, int) or value not in old_new:
                    unknown.append(value)
                    return value
                return old_new[value]

            def walk(value):
                nonlocal changed
                if isinstance(value, dict):
                    for key, item in value.items():
                        if key == "source":
                            mapped = remap(item)
                            if mapped != item:
                                value[key] = mapped
                                changed = True
                        else:
                            walk(item)
                elif isinstance(value, list):
                    for item in value:
                        walk(item)

            walk(spec)
            if unknown:
                print(f"{jp.name} 引用了正文没引用过的旧编号：{unknown}，未改写任何文件")
                return 1
            if changed:
                chart_changes.append((jp, spec))

    # 旧 CSV 的数字来源在旧表仍可用时恢复成稳定 URL；新 CSV 无需改写。
    csv_changes = []
    for cp in sorted((sp.parent / "40-dossier").glob("*.csv")):
        rows = list(csv.reader(io.StringIO(cp.read_text(encoding="utf-8-sig"))))
        if not rows or "来源" not in rows[0]:
            continue
        ci = rows[0].index("来源")
        changed = False
        for row in rows[1:]:
            if ci >= len(row):
                continue
            parts = [v.strip() for v in re.split(r"[;；]", row[ci]) if v.strip()]
            for i, value in enumerate(parts):
                if value.isdigit():
                    if int(value) not in src:
                        print(f"{cp.name} 旧来源编号不存在：{value}，未改写任何文件")
                        return 1
                    parts[i] = src[int(value)]["url"]
                    changed = True
            if changed:
                row[ci] = ";".join(parts)
        if changed:
            buf = io.StringIO()
            csv.writer(buf, lineterminator="\n").writerows(rows)
            csv_changes.append((cp, buf.getvalue()))

    if dry:
        print("（dry-run，未写文件）")
        return 0
    notes = sp.parent
    new_items = [{"n": n, **{k: v for k, v in item.items() if k not in ("n", "old")}}
                 for n, item in new_src.items()]
    report_text = "\n".join(new_lines) + "\n"
    source_text = json.dumps(new_items, ensure_ascii=False, indent=2) + "\n"
    md_text = source_markdown(new_items)
    md_path = notes / "sources.md"
    if (report_text == original_report and source_text == original_sources and not chart_changes
            and not csv_changes and md_path.exists() and md_path.read_text(encoding="utf-8") == md_text):
        print("编号、链接与来源表已一致，无需改写")
        return 0
    # 保留首次改写前的原件；重跑不覆盖恢复依据。
    for backup, original in [(notes / "report-编号前.md", original_report),
                             (notes / "sources-编号前.json", original_sources)]:
        if not backup.exists():
            backup.write_text(original, encoding="utf-8")
    rp.write_text(report_text, encoding="utf-8")
    sp.write_text(source_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    (notes / "sources-renumber.json").write_text(json.dumps(
        {"old_to_new": {str(k): v for k, v in old_new.items()}, "new": new_items},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for jp, spec in chart_changes:
        jp.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for cp, text in csv_changes:
        cp.write_text(text, encoding="utf-8")
    print(f"已同步 {rp.name}、{sp.name} 与 sources.md；原件及编号对照保存在 {notes}")
    if chart_changes:
        print(f"已改写 {len(chart_changes)} 个图表数据文件，重跑 make_chart.py --all 更新图上的来源编号")

    return 0


if __name__ == "__main__":
    sys.exit(main())
