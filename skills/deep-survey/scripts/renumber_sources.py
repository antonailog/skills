#!/usr/bin/env python3
"""交付前把报告的来源编号改成从 1 连续，并合并同一页面的多个编号。

用法：
  python3 renumber_sources.py <报告.md> --sources <sources.json> [--charts <charts 目录>] [--dry-run]

做什么：
  1. 按正文里第一次出现的顺序，给被引用的来源重新编号 1—N。
  2. 同一页面的多个旧编号合并成一个：App Store 页按「国家 + 应用编号」认（带不带应用名、
     带不带 ?see-all=reviews 都算同一页），36 氪桌面页与移动端页算同一页，其他网址去掉锚点后相同即同一页。
  3. 改写正文和推荐阅读里的 [n]、[a,b]：合并后去重，保持原顺序。
  4. 重写「口径与来源」的编号列表：`n. 标题 — URL（日期）`；弱来源（sources.json 的 weak 字段）在行尾标出。
     列表之前的口径说明保留不动。
  5. 给了 --charts 时，同步改写 charts/data/*.json 的 source 字段，并提示重跑 make_chart.py（图的页脚编号要更新）。
  6. 新旧对照写到 sources.json 同目录的 sources-renumber.json；改写前的报告备份为同目录的 report-编号前.md。

--dry-run 只打印会怎么改，不写文件。
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

CITE_RE = re.compile(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]")
LIST_RE = re.compile(r"^\s*(?:\[(\d{1,3})\]|(\d{1,3})[.、])\s+")


def page_key(url: str) -> str:
    u = urlsplit(url.strip())
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
    lines = rp.read_text(encoding="utf-8").splitlines()
    src = {int(s["n"]): s for s in json.loads(sp.read_text(encoding="utf-8"))}
    s0, s1 = sources_section(lines)
    if s0 is None:
        print("找不到「口径与来源」节")
        return 1
    body = lines[:s0]

    # 1 首次出现顺序
    order: list[int] = []
    for l in body:
        for g in CITE_RE.findall(l):
            for x in g.split(","):
                n = int(x)
                if n not in order:
                    order.append(n)
    missing = [n for n in order if n not in src]
    if missing:
        print(f"正文引用了 sources.json 里没有的编号：{missing}，先修正")
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
                cur.update({k2: v for k2, v in src[n].items() if k2 != "n"})
                cur["old"] = cur["old"]
        old_new[n] = key_new[k]

    def repl(m):
        nums = []
        for x in m.group(1).split(","):
            nn = old_new[int(x)]
            if nn not in nums:
                nums.append(nn)
        return "[" + ",".join(str(x) for x in nums) + "]"

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
    out_list = []
    for nn in range(1, len(new_src) + 1):
        s = new_src[nn]
        title = s.get("title") or "（无标题）"
        date = f"（{s['date']}）" if s.get("date") else ""
        weak = f"（弱来源：{s['weak']}）" if s.get("weak") else ""
        own = "（自有信源）" if s.get("origin") == "自有信源" else ""
        out_list.append(f"{nn}. {title} — {s['url']}{date}{own}{weak}")
    new_lines = new_body + keep + [""] + out_list + [""] + lines[s1:]

    merged = {nn: s["old"] for nn, s in new_src.items() if len(s["old"]) > 1}
    print(f"引用的来源 {len(order)} 个 → 合并同页后 {len(new_src)} 个，编号 1—{len(new_src)}")
    for nn, olds in merged.items():
        print(f"  合并 {olds} → {nn}：{new_src[nn]['url'][:70]}")

    # 5 图表数据
    chart_changes = []
    if charts and (charts / "data").is_dir():
        for jp in sorted((charts / "data").glob("*.json")):
            spec = json.loads(jp.read_text(encoding="utf-8"))
            changed = False

            def walk(o):
                nonlocal changed
                if isinstance(o, dict):
                    for k, v in o.items():
                        if k == "source" and isinstance(v, list):
                            nv = []
                            for x in v:
                                if isinstance(x, list):
                                    nv.append(sorted({old_new.get(y, y) for y in x}))
                                else:
                                    nv.append(old_new.get(x, x))
                            if isinstance(nv[0] if nv else None, int):
                                nv = list(dict.fromkeys(nv))
                            if nv != v:
                                o[k] = nv
                                changed = True
                        else:
                            walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)

            walk(spec)
            unknown = []

            def collect(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        if k == "source":
                            for x in v:
                                for y in (x if isinstance(x, list) else [x]):
                                    if y not in old_new.values():
                                        unknown.append(y)
                        else:
                            collect(v)
                elif isinstance(o, list):
                    for v in o:
                        collect(v)
            if changed:
                chart_changes.append((jp, spec))
            collect(spec)
            if unknown:
                print(f"  注意：{jp.name} 引用了正文没引用过的编号 {sorted(set(unknown))}，图的来源要在正文里也出现")

    if dry:
        print("（dry-run，未写文件）")
        return 0
    notes = sp.parent
    (notes / "report-编号前.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    rp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    (notes / "sources-renumber.json").write_text(json.dumps(
        {"old_to_new": {str(k): v for k, v in old_new.items()},
         "new": [{"n": nn, **{k: v for k, v in s.items() if k not in ("n", "cited_in")}} for nn, s in new_src.items()]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    for jp, spec in chart_changes:
        jp.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已改写 {rp.name}；备份 {notes / 'report-编号前.md'}；对照表 {notes / 'sources-renumber.json'}")
    if chart_changes:
        print(f"已改写 {len(chart_changes)} 个图表数据文件，重跑 make_chart.py --all 更新图上的来源编号")
    return 0


if __name__ == "__main__":
    sys.exit(main())
