"""把学习指南目录（guide.md、sources.json，可选 sites.json、videos.json、img/、site.config.json）转成页面数据 src/gen/。

学习指南目录：第一个参数或环境变量 GUIDE_DIR（相对本 app 目录）；都不给就是 app 的上一层（..）。
构建：npm run build:blog → <主题>/site/（多文件、相对路径，img/ 一起拷）；npm run build → <主题>/index.html（单文件，双击看）。
试示例：npm run example（= 对 example/ 跑上面两个）；只跑本脚本：python3 -I scripts/build_guide.py example
站点信息（站名、导航、返回链接、页脚）读 app 的 site.config.json，本机 ~/.config/study-guide/ 和学习指南目录里放同名文件可依次逐项覆盖。
博客样式用 src/blog/ 的快照；环境变量 BLOG_CSS_DIR 或 site.config.json 的 blogCssDir 指向放 tokens.css、post.css 的目录时用那里的。
写法约定见 skill 的 references/components.md；写错了（未知引用、画廊、视频、演示名，代码块没闭合）报出行号并退出。
"""
import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
GEN = APP / 'src' / 'gen'
FENCE = re.compile(r'^\s*(`{3,}|~{3,})(.*)$')
REF = re.compile(r'\[\[\s*([\w.-]+(?:\s*,\s*[\w.-]+)*)\s*\]\]')
HL = re.compile(r'==(?=\S)(.+?)(?<=\S)==')
UL = re.compile(r'\+\+(?=\S)(.+?)(?<=\S)\+\+')
LABEL = re.compile(r'^(?:\*\*)?(你|AI|[^\s：*`#>|!\[\-\d][^\s：*`]{0,4})(?:\*\*)?：\s*')

errors: list[str] = []
warns: list[str] = []


def err(no: int | None, msg: str) -> None:
    errors.append(f'guide.md 第 {no} 行：{msg}' if no else msg)


def load_json(p: Path, default):
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        sys.exit(f'{p.name} 不是合法 JSON：第 {e.lineno} 行 {e.msg}')


def topic_dir() -> Path:
    g = (sys.argv[1] if len(sys.argv) > 1 else '') or os.environ.get('GUIDE_DIR') or '..'
    p = Path(g).expanduser()
    return (p if p.is_absolute() else APP / p).resolve()


def load_config(topic: Path) -> dict:
    """app 的 site.config.json 打底，本机 ~/.config/study-guide/ 和学习指南目录里的同名文件依次逐项覆盖；_ 开头的键是说明；相对路径相对它所在的文件夹"""
    cfg: dict = {}
    for f in (APP / 'site.config.json', Path.home() / '.config' / 'study-guide' / 'site.config.json', topic / 'site.config.json'):
        for k, v in load_json(f, {}).items():
            if k.startswith('_'):
                continue
            if k == 'blogCssDir' and v and not Path(v).expanduser().is_absolute():
                v = str((f.parent / v).resolve())
            cfg[k] = v
    return cfg


def copy_blog_css(cfg: dict) -> None:
    d = os.environ.get('BLOG_CSS_DIR') or cfg.get('blogCssDir') or ''
    src = Path(d).expanduser().resolve() if d else APP / 'src' / 'blog'
    (GEN / 'blog').mkdir(parents=True, exist_ok=True)
    for name in ('tokens.css', 'post.css'):
        f = src / name if (src / name).exists() else next(iter(sorted(src.glob(f'*/{name}'))), None)
        if not f:
            sys.exit(f'博客样式目录 {src} 里（含下一层）找不到 {name}')
        shutil.copy2(f, GEN / 'blog' / name)


def figure_names() -> set[str]:
    """src/figures/index.tsx 里 FIGURES 登记的名字"""
    t = (APP / 'src' / 'figures' / 'index.tsx').read_text()
    body = t[t.find('{', t.find('FIGURES')) + 1:]
    return set(re.findall(r'^\s*[\'"]?([\w-]+)[\'"]?\s*:', body, re.M))



ORDINAL = re.compile(r'^(\d{1,3}|[①-⑳]|[一二三四五六七八九十]{1,3}|[A-Za-z]\d{0,2})[.、)]?$')   # 同 TableCards.tsx 的 ORDINAL


def wants_cards(head: list[str], rows: list[list[str]]) -> bool:
    """同 src/components/TableCards.tsx 的 wantCards：5 列以上、至少 2 列的格子平均超过 16 字"""
    if len(head) < 5:
        return False
    return sum(1 for k in range(len(head)) if sum(len(plain(r[k])) for r in rows if k < len(r)) / max(len(rows), 1) > 16) >= 2


def check_mermaid(lines: list[tuple[int, str]]) -> None:
    """mermaid 里分组框（subgraph）设成不可见、又用箭头连分组框时，箭头两头落在看不见的框边上，画出来是断的"""
    arrow = re.compile(r'\s*(?:<?[-=.]{2,}[->ox]?|<?[-=.]+[->ox])\s*')   # -->、==>、-.->、---、<-->、--o 等
    i = 0
    while i < len(lines):
        no, t = lines[i]
        if re.match(r'^\s*`{3,}\s*mermaid\s*$', t):
            j = i + 1
            while j < len(lines) and not re.match(r'^\s*`{3,}\s*$', lines[j][1]):
                j += 1
            body = lines[i + 1:j]
            text = '\n'.join(x for _, x in body)
            groups = set(re.findall(r'^\s*subgraph\s+([A-Za-z_][\w]*)', text, re.M))
            hidden = {g for g in groups if re.search(rf'^\s*style\s+{re.escape(g)}\b[^\n]*stroke:\s*(?:none|transparent)', text, re.M)}
            for ln, x in body:
                x = re.sub(r'\|[^|]*\|', ' ', x.strip())   # 边上的文字 -->|是| 先去掉
                if not hidden or not arrow.search(x) or x.startswith(('subgraph', 'style', 'classDef', 'class ', 'direction', '%%')):
                    continue
                ends = {e for part in arrow.split(x) for e in re.findall(r'(?:^|&)\s*([A-Za-z_]\w*)', part.strip())}
                if sum(e in groups for e in ends) >= 2 and ends & hidden:
                    warns.append(f'第 {ln} 行：mermaid 里箭头连的是看不见的分组框（{"、".join(sorted(ends & hidden))}），画出来箭头两头悬空；让分组框显示出来并写上组名，或者改成连框里的节点')
            i = j
        i += 1


def check_tables(lines: list[tuple[int, str]]) -> None:
    """会变成卡片的宽表：表头是卡片里的标签，标签栏固定 6 字宽，超过 5 字会挤到内容上"""
    i = 0
    while i < len(lines):
        no, t = lines[i]
        if t.lstrip().startswith('|') and i + 1 < len(lines) and re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1][1]):
            cells = lambda x: [c.strip() for c in x.strip().strip('|').split('|')]
            head, rows, j = cells(t), [], i + 2
            while j < len(lines) and lines[j][1].lstrip().startswith('|'):
                rows.append(cells(lines[j][1]))
                j += 1
            if wants_cards(head, rows):
                # 同 TableCards.tsx：第一列有重复值（分组）或全是序号时，标题用到第二列，标签从第三列起
                first = [plain(r[0]) for r in rows if r]
                skip = 2 if len(set(first)) < len(first) or all(ORDINAL.match(x) for x in first) else 1
                for h in head[skip:]:
                    if len(plain(h)) > 5:
                        warns.append(f'第 {no} 行：这张表会变成卡片，表头「{plain(h)}」超过 5 字，卡片里标签会挤到内容上；改成 2–5 字的术语')
            i = j
        else:
            i += 1


class Builder:
    def __init__(self, sources: dict, sites: dict, videos: dict, figs: set[str], topic: Path):
        self.sources, self.sites, self.videos, self.figs, self.topic = sources, sites, videos, figs, topic
        self.order: dict[str, int] = {}
        self.canon: dict[str, str] = {}
        self.blocks: list[dict] = []
        self.used_sites: set[str] = set()
        self.used_videos: set[str] = set()

    # ---- 行内：引用、荧光笔、下划线（行内代码里的不动） ----
    def inline(self, s: str, no: int) -> str:
        def mark(kind: str):
            def f(m: re.Match) -> str:
                inner = m.group(1)
                refs = ''.join(f'[[{r}]]' for r in REF.findall(inner))   # 引用挪到高亮外面，免得链接套链接
                return f'[{REF.sub("", inner)}]({kind}:){refs}'
            return f

        def cite(m: re.Match) -> str:
            out = []
            for i in re.split(r'\s*,\s*', m.group(1)):
                if i not in self.sources:
                    err(no, f'引用 [[{i}]] 在 sources.json 里没有')
                    continue
                st = self.sources[i].get('_status')
                if st and st != '核对过':
                    warns.append(f'第 {no} 行：[[{i}]] 的核对状态是「{st}」，先对着原网页核一遍再引')
                key = self.sources[i].get('url') or i   # 同一网址被拆成几个 id 时共用一个编号，来源列表不重复
                self.canon.setdefault(key, i)
                n = self.order.setdefault(key, len(self.order) + 1)
                out.append(f'[{n}](cite:{self.canon[key]})')
            return ''.join(out)

        parts = re.split(r'(`+[^`]*`+)', s)
        for k in range(0, len(parts), 2):
            t = HL.sub(mark('hl'), parts[k])
            t = UL.sub(mark('ul'), t)
            parts[k] = REF.sub(cite, t)
        return ''.join(parts)

    def block(self, b: dict) -> list[str]:
        self.blocks.append(b)
        return ['', f'[blk](blk:{len(self.blocks) - 1})', '']

    # ---- 逐行：代码块、::fig、::video ----
    def process(self, lines: list[tuple[int, str]], in_stages: bool = False) -> list[str]:
        out: list[str] = []
        i = 0
        while i < len(lines):
            no, line = lines[i]
            m = FENCE.match(line)
            if m:
                mark, lang = m.group(1), m.group(2).strip().split(' ')[0]
                j = close_of(lines, i, mark, nested=lang == 'stages')
                if j is None:
                    err(no, f'代码块 {mark}{lang} 没有闭合')
                    return out
                inner = lines[i + 1:j]
                if lang == 'gallery':
                    keys = [re.sub(r'^[-*]\s+', '', t.strip()) for _, t in inner if t.strip()]
                    for (n2, t) in inner:
                        k = re.sub(r'^[-*]\s+', '', t.strip())
                        if k and k not in self.sites:
                            err(n2, f'画廊里的 {k} 在 sites.json 里没有')
                    self.used_sites.update(k for k in keys if k in self.sites)
                    out += self.block({'type': 'gallery', 'keys': [k for k in keys if k in self.sites]})
                elif lang == 'stages':
                    if in_stages:
                        err(no, 'stages 里不能再套 stages')
                    else:
                        out += self.block(self.stages(inner))
                else:
                    out += [t for _, t in lines[i:j + 1]]
                i = j + 1
                continue
            s = line.strip()
            if s.startswith('::fig'):
                name = s[5:].strip()
                if name not in self.figs:
                    err(no, f'::fig {name} 没在 src/figures/index.tsx 登记')
                out += ['', f'[fig](fig:{name})', '']
            elif s.startswith('::video'):
                names = [x.strip() for x in s[7:].split('|') if x.strip()]
                for n in names:
                    if n not in self.videos:
                        err(no, f'视频「{n}」在 videos.json 里没有（按 name 对）')
                self.used_videos.update(n for n in names if n in self.videos)
                out += self.block({'type': 'video', 'names': [n for n in names if n in self.videos]})
            else:
                out.append(self.inline(line, no))
                if re.match(r'^!\[[^\]]*\]\(([^)\s]+)', s):
                    self.check_img(re.match(r'^!\[[^\]]*\]\(([^)\s]+)', s).group(1), no)
            i += 1
        return out

    def check_img(self, src: str, no: int) -> None:
        if not re.match(r'^(https?:|data:|/)', src) and not (self.topic / src).exists():
            warns.append(f'第 {no} 行：图片 {src} 不存在（页面上会自动不显示）')

    # ---- ```stages：## 阶段名；行首「目标：」「你：」「AI：」「其他标签：」开一段，到下一个标签为止（可以多段、带列表和代码块）；
    #      目标后面隔空行的无标签段落、其他标签的内容都放竖线下面 ----
    def stages(self, inner: list[tuple[int, str]]) -> dict:
        intro: list[tuple[int, str]] = []
        stages: list[dict] = []
        kind, gap = 'foot', False
        i = 0
        while i < len(inner):
            no, t = inner[i]
            seg = stages[-1][kind] if stages else intro
            m = FENCE.match(t)
            if m:
                j = close_of(inner, i, m.group(1), nested=False)
                j = len(inner) - 1 if j is None else j
                seg += inner[i:j + 1]
                i, gap = j + 1, False
                continue
            i += 1
            h = re.match(r'^##\s+(.+)$', t)
            if h:
                stages.append({'name': self.inline(h.group(1).strip(), no), 'goal': [], 'me': [], 'ai': [], 'foot': []})
                kind, gap = 'foot', False
                continue
            if not t.strip():
                seg.append((no, ''))
                gap = True
                continue
            lab = LABEL.match(t) if stages else None
            if lab:
                name = lab.group(1)
                kind = {'目标': 'goal', '你': 'me', 'AI': 'ai'}.get(name, 'foot')
                seg = stages[-1][kind]
                if seg and seg[-1][1].strip():
                    seg.append((no, ''))
                seg.append((no, f'**{name}**：' + t[lab.end():]))
            else:
                if gap and kind == 'goal':
                    kind = 'foot'
                    seg = stages[-1][kind]
                seg.append((no, t))
            gap = False
        if not stages:
            err(inner[0][0] if inner else None, 'stages 里没有「## 阶段名」')
        md = lambda ls: '\n'.join(self.process(ls, in_stages=True)).strip()   # noqa: E731
        return {'type': 'stages', 'intro': md(intro),
                'stages': [{'name': s['name'], **{k: md(s[k]) for k in ('goal', 'me', 'ai', 'foot')}} for s in stages]}


CHAPTER = re.compile(r'^([零一二三四五六七八九十]+)、(.+)$')


def zh_int(z: str) -> int:
    d = '零一二三四五六七八九'
    if '十' not in z:
        return d.index(z)
    a, _, c = z.partition('十')
    return (d.index(a) if a else 1) * 10 + (d.index(c) if c else 0)


def int_zh(n: int) -> str:
    d = '零一二三四五六七八九'
    if n < 10:
        return d[n]
    return ('' if n // 10 == 1 else d[n // 10]) + '十' + (d[n % 10] if n % 10 else '')


def number_chapters(md: str, has_refs: bool) -> tuple[str, str | None]:
    """目录编号统一：
    - 第一个编号章之前的那一章（一分钟看懂这类概览）编成「零、」→ 目录 00
    - 最后一个编号章之后没编号的章（检查清单、还不确定的……）收进一个「其他」章，编号接着排，它们降一级成小节；来源列表挂在「其他」下面
    - 后面没有这类章、但有来源时，来源单独占一个编号
    返回改写后的 md 和来源列表的位置：'other'（挂在其他下）/ 'own'（自成一章）/ None"""
    lines = md.split('\n')
    fence = None
    h2: list[int] = []
    for k, line in enumerate(lines):
        m = FENCE.match(line)
        if m:
            if fence is None:
                fence = m.group(1)
            elif not m.group(2).strip() and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if fence is None and line.startswith('## '):
            h2.append(k)
    numbered = [k for k in h2 if CHAPTER.match(plain(lines[k][3:]))]
    if not numbered:
        return md, None
    first, last = numbered[0], numbered[-1]
    lead = [k for k in h2 if k < first]
    if len(lead) == 1:
        lines[lead[0]] = '## 零、' + lines[lead[0]][3:]
    nxt = zh_int(CHAPTER.match(plain(lines[last][3:])).group(1)) + 1
    tail = [k for k in h2 if k > last]
    if not tail:
        return '\n'.join(lines), ('own' if has_refs else None)
    fence = None
    for k in range(tail[0], len(lines)):   # 收进「其他」：章降成小节，小节降成小标题
        m = FENCE.match(lines[k])
        if m:
            if fence is None:
                fence = m.group(1)
            elif not m.group(2).strip() and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if fence is None and re.match(r'^#{2,3} ', lines[k]):
            lines[k] = '#' + lines[k]
    lines[tail[0]:tail[0]] = [f'## {int_zh(nxt)}、其他', '']
    return '\n'.join(lines), ('other' if has_refs else None)


def refs_of(at: str | None, heads: list[dict]) -> dict | None:
    """来源列表在目录里的位置：挂在「其他」章下（parent = 那一章的 id），或自成一章（n = 编号）"""
    if at == 'other':
        return {'parent': [h for h in heads if h['level'] == 2][-1]['id']}
    if at == 'own':
        last = [h for h in heads if h['level'] == 2 and h.get('n')][-1]
        return {'n': f"{int(last['n']) + 1:02d}"}
    return None


def icon_of(topic: Path, url: str | None) -> str | None:
    """来源网站的小图标：scripts/fetch_icons.py 下载到 img/favicons/<域名>.png（或 .svg）；没有就让页面显示通用图标"""
    if not url:
        return None
    host = re.sub(r'^www\.', '', (re.match(r'^[a-z]+://([^/:?#]+)', url, re.I) or [None, ''])[1].lower())
    for ext in ('png', 'svg'):
        if host and (topic / 'img' / 'favicons' / f'{host}.{ext}').exists():
            return f'img/favicons/{host}.{ext}'
    return None


def close_of(lines: list[tuple[int, str]], i: int, mark: str, nested: bool) -> int | None:
    """代码块的闭合行；nested=True 时里面带语言名的代码块（```prompt）先配对，不算闭合"""
    stack: list[str] = []
    for j in range(i + 1, len(lines)):
        m = FENCE.match(lines[j][1])
        if not m:
            continue
        c, info = m.group(1), m.group(2).strip()
        if stack:
            if not info and c[0] == stack[-1][0] and len(c) >= len(stack[-1]):
                stack.pop()
            continue
        if not info and c[0] == mark[0] and len(c) >= len(mark):
            return j
        if info and nested:
            stack.append(c)
    return None


def plain(md: str) -> str:
    t = re.sub(r'\[\[[^\]]*\]\]', '', md)   # 原文里的引用 [[id]]（表格检查读的是原文行）
    t = re.sub(r'==|\+\+', '', t)   # 高亮、下划线标记
    t = re.sub(r'\[(\d+)\]\(cite:[^)]+\)', '', t)
    t = re.sub(r'\[([^\]]*)\]\((?:hl|ul):\)', r'\1', t)
    t = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', t)
    return re.sub(r'[`*_#>]', '', t).strip()


def main() -> None:
    topic = topic_dir()
    gp = topic / 'guide.md'
    if not gp.exists():
        sys.exit(f'学习指南目录里没有 guide.md：{topic.name}/（用参数或 GUIDE_DIR 指定学习指南目录）')
    cfg = load_config(topic)
    copy_blog_css(cfg)

    src_list = load_json(topic / 'sources.json', [])
    sources: dict = {}
    for k, s in enumerate(src_list):
        if not s.get('id'):
            sys.exit(f'sources.json 第 {k + 1} 条没有 id')
        if s['id'] in sources:
            sys.exit(f'sources.json 里 id {s["id"]} 重复')
        sources[s['id']] = s
    sites = {s['key']: s for s in load_json(topic / 'sites.json', [])}
    videos = {v['name']: v for v in load_json(topic / 'videos.json', [])}
    b = Builder(sources, sites, videos, figure_names(), topic)

    raw = gp.read_text()
    raw = re.sub(r'<!--.*?-->', lambda m: '\n' * m.group(0).count('\n'), raw, flags=re.S)   # 去注释、保留行号
    lines = list(enumerate(raw.split('\n'), start=1))
    k = next((i for i, (_, t) in enumerate(lines) if t.strip()), None)
    if k is None or not lines[k][1].startswith('# '):
        sys.exit('guide.md 第一行要是「# 标题」')
    title = lines[k][1][2:].strip()
    rest = lines[k + 1:]
    h2 = next((i for i, (_, t) in enumerate(rest) if t.startswith('## ')), len(rest))
    lede = '\n'.join(b.process(rest[:h2])).strip()   # 标题和第一章之间的段落 = 导语
    md = '\n'.join(b.process(rest[h2:]))

    md, refs_at = number_chapters(md, bool(b.order))
    heads = []
    fence = None
    c2 = c3 = 0
    for n, line in enumerate(md.split('\n'), start=1):
        m = FENCE.match(line)
        if m:
            if fence is None:
                fence = m.group(1)
            elif not m.group(2).strip() and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        hm = re.match(r'^(#{2,3}) (.+)$', line)
        if hm and fence is None:
            if len(hm.group(1)) == 2:
                c2, c3 = c2 + 1, 0
                hid = f'c{c2}'
            else:
                c3 += 1
                hid = f'c{c2}-{c3}'
            text = plain(hm.group(2))
            h = {'line': n, 'level': len(hm.group(1)), 'text': text, 'id': hid}
            if h['level'] == 2:
                cm = CHAPTER.match(text)
                h['n'], h['title'] = (f'{zh_int(cm.group(1)):02d}', cm.group(2)) if cm else (None, text)
            heads.append(h)

    check_tables(lines)   # 用原文行号（guide.md 里的行）提醒
    check_mermaid(lines)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        sys.exit(f'{len(errors)} 处写法错误，没有生成页面数据')

    every = md + lede + json.dumps(b.blocks, ensure_ascii=False)
    chars = len(re.findall(r'[一-鿿]', plain(every))) + len(re.findall(r'[A-Za-z]+', plain(every)))
    used_src = [(b.canon[k], n) for k, n in sorted(b.order.items(), key=lambda x: x[1])]
    page = {
        'title': title,
        'lede': lede,
        'date': cfg.get('date') or datetime.date.today().isoformat(),
        'minutes': max(1, round(chars / 450)),
        'back': cfg.get('back'),
        'md': md,
        'heads': heads,
        'refs': refs_of(refs_at, heads),
        'sources': [{'n': n, 'id': i, **{f: sources[i].get(f) for f in ('title', 'url', 'site', 'date')}, 'icon': icon_of(topic, sources[i].get('url'))} for i, n in used_src],
        'sites': {key: sites[key] for key in sorted(b.used_sites)},
        'videos': {name: videos[name] for name in sorted(b.used_videos)},
        'blocks': b.blocks,
    }
    desc = cfg.get('description') or plain(lede).replace('\n', '')[:120]
    shell = {f: cfg.get(f) for f in ('lang', 'siteName', 'siteHref', 'nav', 'github', 'footer', 'favicon', 'stylesheets', 'themeKey')}
    shell.update({'title': title.split('：')[0] + (cfg.get('titleSuffix') or ''), 'ogTitle': title, 'description': desc})
    GEN.mkdir(parents=True, exist_ok=True)
    (GEN / 'guide.json').write_text(json.dumps(page, ensure_ascii=False))
    (GEN / 'shell.json').write_text(json.dumps(shell, ensure_ascii=False, indent=1))
    for w in warns:
        print('提醒：' + w)
    unused = len(sources) - len(used_src)
    print(f'{title}：约 {chars} 字，章 {c2}，标题 {len(heads)}，引用 {len(used_src)} 个来源'
          + (f'（sources.json 里另有 {unused} 条没引）' if unused else '')
          + f'，画廊 {sum(1 for x in b.blocks if x["type"] == "gallery")}，分工图 {sum(1 for x in b.blocks if x["type"] == "stages")}，视频组 {sum(1 for x in b.blocks if x["type"] == "video")}')


if __name__ == '__main__':
    main()
