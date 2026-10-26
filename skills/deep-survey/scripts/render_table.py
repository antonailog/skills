#!/usr/bin/env python3
"""把竞品档案 CSV 渲染成 md 表格，供报告正文直接使用。

用法：
  python3 render_table.py <40-dossier/价格.csv> [--cols 列1,列2,...] [--rows 产品A,产品B] [--sources sources.json]

CSV 约定（常用字段见 references/researcher.md「对比表」）：
- 第一行是表头，必须有「来源」列，保留原文 URL，多个用分号；--sources 指定来源表后仅在输出中换成编号，兼容旧版数字来源；本机文件写「本机：路径:行号」
- 查不到的格写「未查到」，不留空
- 渲染时「来源」列变成 [171,2]（合并写，避免两个方括号相邻被当成 Markdown 链接）；「日期」列保留

校验：空格子、缺来源的行会报错并退出 1——表里的每个数字和正文一样要可追溯。
"""
import csv
import json
import sys
from pathlib import Path
from renumber_sources import page_key


def main() -> int:
    if sys.argv[1:2] in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 2
    p = Path(a[0])
    rows = list(csv.DictReader(p.open(encoding="utf-8-sig")))
    if not rows:
        print(f"空表：{p}")
        return 1
    header = list(rows[0].keys())
    if "来源" not in header:
        print("缺少「来源」列")
        return 1
    cols = a[a.index("--cols") + 1].split(",") if "--cols" in a else header
    keep = set(a[a.index("--rows") + 1].split(",")) if "--rows" in a else None
    source_path = Path(a[a.index("--sources") + 1]) if "--sources" in a else p.parent.parent / "sources.json"
    sources = json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else []
    by_url = {page_key(s["url"]): str(s["n"]) for s in sources}
    known = {str(s["n"]) for s in sources}
    errs = []
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for i, r in enumerate(rows, 2):
        if keep and r[header[0]] not in keep:
            continue
        cells = []
        for c in cols:
            v = (r.get(c) or "").strip()
            if not v:
                errs.append(f"第 {i} 行「{c}」为空")
            if c == "来源":
                parts = [x.strip() for x in v.replace("，", ";").replace("；", ";").split(";") if x.strip()]
                parts = [x[1:-1].strip() if x.startswith("[") and x.endswith("]") else x for x in parts]
                nums = []
                for x in parts:
                    if x.isdigit():
                        if sources and x not in known:
                            errs.append(f"第 {i} 行来源编号不在来源表：{x}")
                        nums.append(x)
                    elif x.startswith(("http://", "https://")):
                        n = by_url.get(page_key(x))
                        if n is None:
                            errs.append(f"第 {i} 行来源 URL 不在来源表：{x}")
                        else:
                            nums.append(n)
                local = [x for x in parts if x.startswith("本机")]
                if not parts or len(nums) + len(local) != len(parts):
                    errs.append(f"第 {i} 行来源未能映射到来源表或本机路径（先跑 build_source_table.py）：{v!r}")
                v = " ".join(([f"[{','.join(nums)}]"] if nums else []) + [f"`{x}`" for x in local])
            cells.append(v.replace("|", "｜"))
        out.append("| " + " | ".join(cells) + " |")
    if errs:
        for e in errs:
            print("错误：" + e)
        return 1
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
