#!/usr/bin/env python3
"""检查调研报告的机械项：引用、固定部分、图片、表格、凭证。写法由写作指南与审读员判断，脚本不查。

用法：
  python3 check_report.py report.md [--sources sources.json]

错误（E，退出码 1）：
  E1 正文引用的 [n] 不在来源表，或数字链接、来源列表与 sources.json 的 URL 不一致
  E2 正文出现【高】【中】【低】置信度标签
  E3 固定部分缺失：首个二级标题不是「一分钟看懂」；没有「还不知道的」；没有「口径与来源」；
     「口径与来源」不是最后一节；出现已取消的「留给你的问题」
  E4 表格有空格子
  E6 图片文件不存在
  E7 两个编号方括号紧挨着（如 [38][17]），会被 Markdown 渲染成链接；应合并写成 [38,17]
  E8 正文或来源里疑似凭证、Cookie、Bearer token、带 key / token 参数的 URL
  E9 「推荐阅读」条目的标题没有超链接（应为 - **[标题](URL)**（机构，日期）[n]：原因）
警告（W）：
  W1 正文含估算词（约 / 大约 / 估计 / 大概 / 据说）却没有来源编号
  W4 「来源」节列了正文没引用的编号
  W5 过渡废话（值得注意的是 / 综上所述 / 不难看出 / 由此可见）
  W8 截图下一行没有带来源编号的图注；数据图缺 charts/data/<同名>.json
  W9 图片和文字挤在同一段（图片下一行不是空行），部分编辑器会显示成空白
  W10 「推荐阅读」条目缺推荐原因（「：」之后的说明）或缺来源编号
  W13 来源编号不是从 1 开始连续：交付前跑 scripts/renumber_sources.py
  W17 来源列表里的标题可疑：只有站名、括号不闭合、带解析残留或内部占位符（如 [新1]）
  W18 正文出现内部工具名（Info2Action、lingowhale 等），读者不认识
"""
import json
import re
import sys
from pathlib import Path
from renumber_sources import page_key, source_urls, CITE_RE as LINK_CITE_RE

CITE_RE = re.compile(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]")
ADJ_RE = re.compile(r"\[\d{1,3}(?:\s*,\s*\d{1,3})*\]\[\d{1,3}")
TAG_RE = re.compile(r"【(高|中|低)】")
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
EST_WORDS = ("约", "大约", "估计", "大概", "据说")
FILLERS = ("值得注意的是", "综上所述", "不难看出", "由此可见")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
CRED_RE = re.compile(
    r"(?i)(?:sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|xox[abp]-[A-Za-z0-9-]{10,}"
    r"|Bearer\s+[A-Za-z0-9._-]{16,}|\bCookie\s*:\s*\S{8,}"
    r"|[?&](?:api_?key|access_?token|token|secret|password|cookie)=[^&\s)]{6,})"
)


def cite_nums(text: str) -> list[int]:
    out = []
    for g in CITE_RE.findall(text):
        out += [int(x) for x in g.split(",")]
    return out


def zh_len(s: str) -> int:
    s = CITE_RE.sub("", s)
    return len(re.findall(r"[一-鿿]", s)) + len(re.findall(r"[A-Za-z0-9]+", s))


def main() -> int:
    if sys.argv[1:2] in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rp = Path(sys.argv[1])
    text = rp.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: list[str] = []
    warns: list[str] = []

    h2 = [(i, l[3:].strip()) for i, l in enumerate(lines) if l.startswith("## ")]
    titles = [x for _, x in h2]

    # —— 固定部分 ——
    if not titles or not titles[0].startswith("一分钟看懂"):
        errors.append("E3 第一个二级标题应为「一分钟看懂」")
    if not any("还不知道" in x for x in titles):
        errors.append("E3 缺「还不知道的」")
    src_pos = [k for k, x in enumerate(titles) if x.startswith("口径与来源")]
    if not src_pos:
        errors.append("E3 缺「口径与来源」")
    elif src_pos[-1] != len(titles) - 1:
        errors.append("E3 「口径与来源」应为最后一节")
    if any(x.startswith("留给你的问题") for x in titles):
        errors.append("E3 「留给你的问题」已取消，删掉这一节")

    src_idx = h2[src_pos[-1]][0] if src_pos else len(lines)
    body = lines[:src_idx]
    body_text = "\n".join(body)

    # —— 来源 ——
    listed: set[int] = set()
    listed_urls = {}
    for l in lines[src_idx:]:
        m = re.match(r"^\s*(?:\[(\d{1,3})\]|(\d{1,3})[.、])\s*", l)
        if m:
            n = int(m.group(1) or m.group(2))
            listed.add(n)
            listed_urls[n] = source_urls(l[m.end():])
    known = listed
    source_items = {}
    if "--sources" in sys.argv:
        sp = Path(sys.argv[sys.argv.index("--sources") + 1])
        source_items = {int(s["n"]): s for s in json.loads(sp.read_text(encoding="utf-8"))}
        known = set(source_items)
    cited = set(cite_nums(body_text))
    if src_pos and not listed:
        errors.append("E1 「口径与来源」节没有列出任何编号")
    if listed and (cited - listed):
        errors.append(f"E1 正文引用了来源节没列的编号: {sorted(cited - listed)}")
    if cited - known:
        errors.append(f"E1 正文编号不在 sources.json: {sorted(cited - known)}")
    if listed - cited:
        warns.append(f"W4 来源节列了正文没引用的编号: {sorted(listed - cited)}")

    # 编号存在还不够：正文链接、来源列表和 JSON 必须指向同一页面。
    for n, urls in listed_urls.items():
        if n in source_items and (not urls or any(page_key(u) != page_key(source_items[n]["url"]) for u in urls)):
            errors.append(f"E1 来源 {n} 的 URL 与 sources.json 不一致或缺失")
    for m in LINK_CITE_RE.finditer(body_text):
        if not m.group(2):
            continue
        for n in map(int, m.group(1).split(",")):
            targets = [source_items[n]["url"]] if n in source_items else listed_urls.get(n, [])
            if not targets or any(page_key(m.group(2)) != page_key(u) for u in targets):
                errors.append(f"E1 正文引用 {n} 的 URL 与来源表不一致")

    # —— 行级 ——
    for i, l in enumerate(lines, 1):
        if CRED_RE.search(l):
            errors.append(f"E8 第 {i} 行疑似凭证或带密钥参数的 URL: {l.strip()[:40]}")
    for i, l in enumerate(body, 1):
        if ADJ_RE.search(l):
            errors.append(f"E7 第 {i} 行编号方括号相邻，会被渲染成链接: {ADJ_RE.search(l).group(0)}…")
        if TAG_RE.search(l):
            errors.append(f"E2 第 {i} 行有置信度标签: {l.strip()[:40]}")
        s = l.strip()
        if s.startswith("|") and not re.match(r"^\|\s*:?-", s):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if any(c == "" for c in cells[1:]):
                errors.append(f"E4 第 {i} 行表格有空格子")
        if not s or s.startswith(("#", ">", "|", "!")):
            continue
        for sent in re.split(r"(?<=[。！？])", s):
            if any(w in sent for w in EST_WORDS) and NUM_RE.search(sent) and not CITE_RE.search(sent):
                warns.append(f"W1 第 {i} 行估算数字无来源: {sent[:40]}")
        for f in FILLERS:
            if f in s:
                warns.append(f"W5 第 {i} 行过渡废话「{f}」")

    # —— 图片 ——
    n_img = 0
    for i, l in enumerate(body):
        for src in IMG_RE.findall(l):
            n_img += 1
            p = (rp.parent / src).resolve()
            if not p.exists():
                errors.append(f"E6 图片不存在: {src}")
                continue
            stem = Path(src).stem
            if i + 1 < len(body) and body[i + 1].strip():
                warns.append(f"W9 第 {i + 1} 行图片 {src} 和下一行文字在同一段，图注前空一行")
            if stem.startswith("shot-"):
                nxt = next((x for x in body[i + 1:i + 4] if x.strip()), "")
                if not CITE_RE.search(nxt):
                    warns.append(f"W8 截图 {src} 下一行缺带编号的图注")
            elif stem == "guide":
                continue
            elif not any((p.parent / x).exists() for x in (f"data/{stem}.json", f"{stem}.mmd", f"{stem}.json")):
                warns.append(f"W8 图 {src} 没有对应的 data/{stem}.json 或 {stem}.mmd")

    # —— 推荐阅读 ——
    rec = next((k for k, (_, t) in enumerate(h2) if t.startswith("推荐阅读")), None)
    if rec is not None:
        a = h2[rec][0]
        b = h2[rec + 1][0] if rec + 1 < len(h2) else len(lines)
        recs = [l.strip() for l in lines[a:b] if re.match(r"^\s*[-*]\s+", l)]
        for r in recs:
            if "：" not in r or len(r.split("：", 1)[1].strip()) < 8:
                warns.append(f"W10 推荐阅读缺推荐原因: {r[:40]}")
            if not CITE_RE.search(r):
                warns.append(f"W10 推荐阅读缺来源编号: {r[:40]}")
            if not re.search(r"\[[^\]]+\]\(https?://[^)\s]+\)", r):
                errors.append(f"E9 推荐阅读标题没有超链接: {r[:40]}")

    # —— 编号连续 ——
    if cited and sorted(cited) != list(range(1, len(cited) + 1)):
        warns.append(f"W13 来源编号不连续（引用 {len(cited)} 个，最大编号 {max(cited)}）：交付前跑 scripts/renumber_sources.py")

    # —— 来源标题 ——
    for l in lines[src_idx:]:
        m = re.match(r"^\s*(\d{1,3})[.、]\s+(.*)$", l)
        if not m:
            continue
        t = m.group(2).split(" — ")[0].strip()
        opens = sum(t.count(c) for c in "（(《「")
        closes = sum(t.count(c) for c in "）)》」")
        if (re.match(r"^[，,；;）)、:：]|^\d+[，,；;）)]", t) or "笔记" in t or len(t) < 6 or opens != closes
                or re.search(r"\[新\d\]|来源缩写", t)
                or re.fullmatch(r"App Store.{0,6}|维基百科|Wikipedia|iTunes Search API", t)
                ):
            warns.append(f"W17 来源 {m.group(1)} 标题可疑：{t[:30]}")

    # —— 内部工具名 ——
    for i, l in enumerate(body, 1):
        hit = re.search(r"Info2Action|lingowhale|own_feed_recall|research_notes", l)
        if hit and not l.lstrip().startswith("#"):
            warns.append(f"W18 第 {i} 行出现内部工具名「{hit.group(0)}」")
            break

    n_tab = sum(1 for k, l in enumerate(body) if l.strip().startswith("|") and (k == 0 or not body[k - 1].strip().startswith("|")))
    chars = zh_len(body_text)

    for e in errors:
        print(e)
    for w in warns:
        print(w)
    print(f"— 错误 {len(errors)}，警告 {len(warns)}，正文 {chars} 字，图 {n_img} 张，表 {n_tab} 张，引用编号 {len(cited)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
