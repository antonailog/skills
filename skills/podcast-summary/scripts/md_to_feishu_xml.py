#!/usr/bin/env python3
"""把笔记 Markdown 转成飞书文档 XML。约定：**粗** <u>下划线</u> ==高亮== *斜体* [链接](url) ![图](路径) 表格、有序／无序列表、问答两行段（**Q…** 下一行「答：」）。
SVG 图转成 <whiteboard type="svg" path="@文件">（创建时由 lark-cli 展开）；其他图片按 --img-map 换成网络地址。各级标题前若是正文，自动插入空段落。

用法：python3 md_to_feishu_xml.py 笔记.md 输出.xml [--img-map '{"images/封面.png":"https://..."}'] [--title-suffix '（新结构）']"""
import argparse, html, json, pathlib, re
import xml.etree.ElementTree as ET

def inline(t):
    t = t.replace('<u>', '\x01').replace('</u>', '\x02')
    t = html.escape(t, quote=False)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', t)
    t = re.sub(r'==(.+?)==', r'<span background-color="light-yellow">\1</span>', t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)', r'<em>\1</em>', t)
    return t.replace('\x01', '<u>').replace('\x02', '</u>')

def convert(lines, img_map):
    out, prev_heading, title = [], [True], None
    def emit(x, heading=False):
        if heading and not prev_heading[0]: out.append('<p></p>')
        out.append(x); prev_heading[0] = heading
    i, n = 0, len(lines)
    while i < n:
        L = lines[i]
        if not L.strip(): i += 1; continue
        if L.startswith('# '): title = L[2:].strip(); i += 1; continue
        m = re.match(r'^(#{2,4}) (.*)', L)
        if m: emit(f'<h{len(m.group(1)) - 1}>{inline(m.group(2).strip())}</h{len(m.group(1)) - 1}>', True); i += 1; continue
        if L.startswith('!['):
            alt, path = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', L).groups()
            if path.endswith('.svg'): emit(f'<whiteboard type="svg" path="@{path}"></whiteboard>')
            elif path in img_map: emit(f'<img href="{img_map[path]}" caption="{html.escape(alt, quote=True)}"/>')
            else: raise SystemExit(f'图片 {path} 不是 SVG，也不在 --img-map 里；本地图片要先给网络地址或建页后用 media-insert')
            i += 1; continue
        if L.startswith('|'):
            rows = []
            while i < n and lines[i].startswith('|'):
                if not re.match(r'^\|[\s\-|:]+\|$', lines[i]): rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')])
                i += 1
            th = ''.join(f'<th>{inline(c)}</th>' for c in rows[0]); tb = ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in rows[1:])
            emit(f'<table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>'); continue
        if re.match(r'^\d+\. ', L):
            items = []
            while i < n and re.match(r'^\d+\. ', lines[i]): items.append(f'<li seq="auto">{inline(re.sub(r"^\d+\. ", "", lines[i]).strip())}</li>'); i += 1
            emit('<ol>' + ''.join(items) + '</ol>'); continue
        if L.startswith('- '):
            items = []
            while i < n and lines[i].startswith('- '):
                txt = lines[i][2:].strip(); i += 1; sub = []
                while i < n and re.match(r'^  \d+\. ', lines[i]): sub.append(f'<li seq="auto">{inline(re.sub(r"^  \d+\. ", "", lines[i]).strip())}</li>'); i += 1
                items.append(f'<li>{inline(txt)}' + (f'<ol>{"".join(sub)}</ol>' if sub else '') + '</li>')
            emit('<ul>' + ''.join(items) + '</ul>'); continue
        para = [L.strip()]; i += 1
        while i < n and lines[i].strip() and not re.match(r'^(#|!\[|\||- |\d+\. )', lines[i]): para.append(lines[i].strip()); i += 1
        if len(para) == 2 and para[0].startswith('**Q') and para[1].startswith('答：'):
            emit(f'<p>{inline(para[0])}</p>'); emit(f'<p>{inline(para[1])}</p>'); continue
        emit(f'<p>{inline(" ".join(para))}</p>')
    return title, out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--img-map', default='{}'); ap.add_argument('--title-suffix', default='')
    a = ap.parse_args()
    title, out = convert(pathlib.Path(a.src).read_text(encoding='utf-8').split('\n'), json.loads(a.img_map))
    xml = f'<title>{html.escape(title + a.title_suffix)}</title>\n' + '\n'.join(out) + '\n'
    ET.fromstring('<root>' + xml.replace('<p></p>', '<p/>') + '</root>')
    pathlib.Path(a.out).write_text(xml, encoding='utf-8')
    c = lambda k: xml.count(k)
    print(json.dumps({'chars': len(xml), 'h1': c('<h1>'), 'h2': c('<h2>'), 'h3': c('<h3>'), 'whiteboard': c('<whiteboard'), 'img': c('<img'), 'table': c('<table'),
                      'spacer': c('<p></p>'), 'bold': c('<b>'), 'underline': c('<u>'), 'highlight': c('<span'), 'italic': c('<em>')}, ensure_ascii=False))

if __name__ == '__main__':
    main()
