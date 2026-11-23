"""离线包和网站版共用的部分：收集讲稿引用的文件、拷到一个干净目录、换上字体子集、找在线内容、改 HTML 元素。"""
import re
import shutil
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

import fontpack

REF_ATTRS = ('src', 'href', 'data-src', 'poster', 'data-web-shot')
CSS_URL = re.compile(r'url\(\s*([\'"]?)([^\'")]+)\1\s*\)')
ENGINE_FILES = ['deck.css', 'deck.js', 'qrcode.js']


def all_refs(html: str, links=True):
    """页面引用的全部地址：常见属性（单双引号都认）、srcset、style 属性和 <style> 里的 url()。
    links=False 时不算 <a>/<area> 的跳转链接（嵌入页里的导航链接不是它要用的文件）。"""
    refs = set()
    t = tree(html)
    for n in t.root.walk():
        refs.update(n.attrs[a] for a in REF_ATTRS if n.attrs.get(a) and (links or a != 'href' or n.tag not in ('a', 'area')))
        refs.update(x.strip().split(' ')[0] for x in n.attrs.get('srcset', '').split(',') if x.strip())
        refs.update(m.group(2) for m in CSS_URL.finditer(n.attrs.get('style', '')))
    for m in re.finditer(r'<style\b[^>]*>(.*?)</style>', html, re.S | re.I):
        refs.update(u.group(2) for u in CSS_URL.finditer(m.group(1)))
    return refs


def _local(refs, skip_engine):
    out = set()
    for r in refs:
        r = urllib.parse.unquote(re.split(r'[#?]', r.strip(), 1)[0])
        if r and not re.match(r'^([a-z][a-z0-9+.-]*:|//)', r, re.I) and not (skip_engine and r.startswith('deck/')):
            out.add(r)
    return sorted(out)


def local_refs(html: str, skip_engine=True, links=True):
    """本地文件引用（去掉 # 和 ? 后面的部分），不含网址；讲稿本身的引擎 deck/ 另外拷，不算在内。"""
    return _local(all_refs(html, links), skip_engine)


def _refs_in_file(f: Path):
    ext = f.suffix.lower()
    if ext in ('.html', '.htm'):
        return local_refs(f.read_text('utf-8', 'replace'), skip_engine=False, links=False)
    if ext == '.css':
        text = f.read_text('utf-8', 'replace')
        return _local([m.group(2) for m in CSS_URL.finditer(text)] + re.findall(r'@import\s+[\'"]([^\'"]+)', text), False)
    return []


def collect(deck: Path, html: str):
    """讲稿要用到的全部本地文件：页面直接引用的，加上嵌入网页和样式表再引用的（一层层往下找）。
    返回 (讲稿目录下的相对路径列表, 不存在的, 指到讲稿目录外面的)。脚本运行时才去加载的文件找不到。"""
    base = deck.resolve()
    files, missing, far = set(), [], []
    todo = [(base, r, '') for r in local_refs(html)]
    while todo:
        d, r, frm = todo.pop()
        label = f'{frm} 引用的 {r}' if frm else r
        p = (d / r).resolve()
        if r.startswith('/') or base not in p.parents:
            far.append(label)
            continue
        rel = p.relative_to(base).as_posix()
        if rel in files:
            continue
        if not p.exists():
            missing.append(label)
            continue
        if p.is_dir():   # 指向文件夹的链接：不整个带上，免得把没用到的页面和草稿一起带出去
            continue
        files.add(rel)
        todo += [(p.parent, s, rel) for s in _refs_in_file(p)]
    return sorted(files), sorted(set(missing)), sorted(set(far))


def stage(deck: Path, html: str, out: Path, fonts=True):
    """把 html 和它引用的文件、引擎、字体放进 out。返回提示列表。"""
    notes = []
    out.mkdir(parents=True, exist_ok=True)
    (out / 'index.html').write_text(html, 'utf-8')
    (out / 'deck' / 'themes').mkdir(parents=True, exist_ok=True)
    for f in ENGINE_FILES:
        shutil.copy2(deck / 'deck' / f, out / 'deck' / f)
    for t in (deck / 'deck' / 'themes').glob('*.css'):
        shutil.copy2(t, out / 'deck' / 'themes' / t.name)
    files, missing, far = collect(deck, html)
    if far:
        raise SystemExit('这些文件在讲稿目录外面，打包时带不上：' + '、'.join(far) + '。先拷进讲稿目录（比如 嵌入/），改成相对路径再打包')
    for r in files:   # 只带用到的：嵌入/ 里没被引用的页面和草稿不会跟着出去
        dst = out / r
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(deck / r, dst)
    if missing:
        notes.append('这些文件引用了但不存在，没带上：' + '、'.join(missing))
    if fonts:
        try:
            css, n = fontpack.subset(html, out / 'deck')
            (out / 'deck' / 'fonts.css').write_text(css, 'utf-8')
            notes.append(f'字体：只带了用到的字，共 {n / 1024:.0f} KB')
        except Exception as e:   # 没网、被墙：落到系统字体，换电脑可能换行不同
            (out / 'deck' / 'fonts.css').write_text('/* 字体没下载成功，用系统字体 */\n', 'utf-8')
            notes.append(f'字体没下载成功（{str(e)[:60]}），这次用系统字体；换到别的电脑时换行可能不同。联网后重跑可补上')
    else:
        shutil.copy2(deck / 'deck' / 'fonts.css', out / 'deck' / 'fonts.css')
    return notes


class Node:
    __slots__ = ('tag', 'attrs', 'start', 'end', 'children', 'parent')

    def __init__(self, tag, attrs, start, parent):
        self.tag, self.attrs, self.start, self.end, self.children, self.parent = tag, attrs, start, None, [], parent

    def cls(self):
        return (self.attrs.get('class') or '').split()

    def walk(self):
        for c in self.children:
            yield c
            yield from c.walk()


BLOCK = {'address', 'article', 'aside', 'blockquote', 'details', 'div', 'dl', 'fieldset', 'figcaption', 'figure', 'footer', 'form',
         'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'hr', 'main', 'menu', 'nav', 'ol', 'p', 'pre', 'section', 'table', 'ul'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}


class _Tree(HTMLParser):
    """用标准库的 HTML 解析器建一棵只记位置的树：引号里的 >、注释和 script 里的标签都不会搞乱配对。"""

    def __init__(self, html):
        super().__init__(convert_charrefs=False)
        self.html, self.root, self.comments = html, Node('#root', {}, 0, None), []
        self.cur = self.root
        self.lines = [0] + [m.end() for m in re.finditer('\n', html)]
        self.feed(html)
        self.close()
        while self.cur is not self.root:   # 没写结束标签的，到文件末尾为止
            self.cur.end = len(html)
            self.cur = self.cur.parent

    def _off(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def _start(self, tag, attrs, void):
        s = self._off()
        n = Node(tag, {k: v or '' for k, v in attrs}, s, self.cur)
        self.cur.children.append(n)
        if void:
            n.end = s + len(self.get_starttag_text())
        else:
            self.cur = n

    def handle_starttag(self, tag, attrs):
        # 跟浏览器一样：没关上的 <p> 遇到块级元素就算结束，没关上的 <li> 遇到下一个 <li> 就算结束
        n = self.cur
        if tag in BLOCK:   # 往上找还开着的 <p>（中间隔着 span 之类也算），连同里面没关的一起结束
            while n is not self.root and n.tag != 'p':
                n = n.parent
        elif tag == 'li' and n.tag != 'li':
            n = self.root
        if n is not self.root and n.tag in ('p', 'li'):
            s = self._off()
            while self.cur is not n.parent:
                self.cur.end = s
                self.cur = self.cur.parent
        self._start(tag, attrs, tag in VOID)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, True)

    def handle_endtag(self, tag):
        s = self._off()
        e = self.html.find('>', s) + 1
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is self.root:      # 多出来的结束标签，不管
            return
        while self.cur is not n:   # 中间没写结束标签的（<p>、<li>），在这里一起结束
            self.cur.end = s
            self.cur = self.cur.parent
        n.end = e
        self.cur = n.parent

    # 注释的真实起止由解析器的这几个方法返回（<!-->、<!x …>、<![if IE]> 这类写法长度各不一样）
    def _span(self, fn, i, *a, **k):
        s = self._off()
        j = fn(i, *a, **k)
        if j > i:
            self.comments.append((s, s + j - i))
        return j

    def parse_comment(self, i, *a, **k):
        return self._span(super().parse_comment, i, *a, **k)

    def parse_bogus_comment(self, i, *a, **k):
        return self._span(super().parse_bogus_comment, i, *a, **k)

    def parse_marked_section(self, i, *a, **k):
        return self._span(super().parse_marked_section, i, *a, **k)


def tree(html: str) -> _Tree:
    return _Tree(html)


def online_pages(html: str):
    """哪几页用了在线内容，断网时有没有备用截图。返回 [(页码, 有截图)]。"""
    res, page = set(), 0
    for n in tree(html).root.walk():
        if n.tag == 'section' and 'slide' in n.cls():
            anc = n.parent
            while anc and not (anc.tag == 'section' and 'slide' in anc.cls()):
                anc = anc.parent
            if anc is None:
                page += 1
            continue
        src = n.attrs.get('data-src') or n.attrs.get('src') or ''
        if page and re.match(r'^https?://', src):
            box = n.parent
            while box and 'box' not in box.cls():
                box = box.parent
            shot = bool(box) and any(c.tag == 'img' and 'shot' in c.cls() for c in box.walk())
            res.add((page, shot))
    return sorted(res)


def replace_elements(html: str, pred, fn, comments=False):
    """把 pred(节点) 为真的元素（整块，含子元素）换成 fn(节点, 整块原文)；comments=True 时顺带删掉 HTML 注释。"""
    t = tree(html)
    spans = [(n.start, n.end, n) for n in t.root.walk() if pred(n)]
    if comments:
        spans += [(s, e, None) for s, e in t.comments if '/stage' not in html[s:e]]
    out, i = [], 0
    for s, e, n in sorted(spans, key=lambda x: (x[0], -x[1])):
        if s < i:            # 套在已经换掉的块里面
            continue
        out.append(html[i:s])
        out.append('' if n is None else fn(n, html[s:e]))
        i = e
    out.append(html[i:])
    return ''.join(out)
