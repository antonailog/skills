"""给找链接的子 agent 备料：材料里每个内部引用标记（Deep Research 导出的 citeturn…）对应的来源条目和正文上下文。

只在材料带内部引用标记、链接又丢了的时候用（inventory.py 的「内部引用标记」列 > 0）。
输出 <学习指南目录>/links/_todo-<材料名>.json：[{id, n, entry, contexts, urls?}]，n 是该材料里第 n 个不同的引用（按第一次出现排）。
用法：python3 -I extract_cites.py <主题文件夹> <学习指南目录> [材料文件名 ...]（不给就做原件目录里全部 .md）
"""
import json
import re
import sys
from pathlib import Path

CITE = re.compile('?cite((?:turn[0-9a-z]+)+)')
SRC_HEAD = re.compile(r'^#{2,3} .*来源.*$|^\*\*来源列表。?\*\*.*$', re.M)


def ids(group: str) -> list[str]:
    return [x for x in group.split('') if x]


def clean(s: str) -> str:
    s = re.sub('[-]', '', CITE.sub('', s)).replace('**', '').replace('`', '')
    return re.sub(r'\s+', ' ', s).strip()


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    root, guide = Path(sys.argv[1]).expanduser().resolve(), Path(sys.argv[2]).expanduser().resolve()
    only = set(sys.argv[3:])
    files = [f for d in ('2-报告原件', '3-报告转写') if (root / d).exists() for f in sorted((root / d).glob('*.*')) if f.suffix in ('.md', '.txt')]
    out = guide / 'links'
    out.mkdir(parents=True, exist_ok=True)
    for f in files:
        if only and f.name not in only and f.stem not in only:
            continue
        body = f.read_text(encoding='utf-8', errors='replace')
        heads = list(SRC_HEAD.finditer(body))
        src_start = heads[-1].start() if heads else len(body)
        order: dict[str, int] = {}
        entry: dict[str, str] = {}
        ctx: dict[str, list[str]] = {}
        links: dict[str, list[str]] = {}
        pos = 0
        for line in body.split('\n'):
            at, pos = pos, pos + len(line) + 1
            for m in CITE.finditer(line):
                for i in ids(m.group(1)):
                    order.setdefault(i, len(order) + 1)
                    for u in re.findall(r'href="(https?://[^"]+)"|\]\((https?://[^)\s]+)\)', line):
                        u = u[0] or u[1]
                        if u not in links.setdefault(i, []):
                            links[i].append(u)
                    if at >= src_start and line.strip():
                        entry.setdefault(i, clean(line))
                    else:
                        parts = re.split(r'(?<=[。！？；.!?;])', clean(line[:m.start()]))
                        snippet = ''.join(parts[-3:]).strip()[-260:]
                        c = ctx.setdefault(i, [])
                        if snippet and snippet not in c and len(c) < 3:
                            c.append(snippet)
        if not order:
            continue
        todo = [{'id': i, 'n': n, 'entry': entry.get(i), 'contexts': ctx.get(i, []), **({'urls': links[i]} if i in links else {})} for i, n in order.items()]
        (out / f'_todo-{f.stem}.json').write_text(json.dumps(todo, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'{f.name}：{len(todo)} 个引用，有来源条目 {sum(1 for t in todo if t["entry"])}，自带链接 {sum(1 for t in todo if t.get("urls"))}')


if __name__ == '__main__':
    main()
