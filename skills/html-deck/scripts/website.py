#!/usr/bin/env python3
"""生成能发到网上的网站版（静态目录）。现场讲稿不动，网站版另外生成：

- 删掉全部备注（class 里带 note 的元素）和 HTML 注释，网站版里按 N、P 没有反应（<html data-public>）
- --replace 旧=新：换掉不想公开的字（真名、公司名……），可写多次
- 标了 data-web="remove" 的元素整块删掉；标了 data-web-shot="嵌入/截图/x.png" 的元素换成这张截图
  （本机页面、私人数据只在现场版里用，网站版放截图）
- --top ".site-tb"：网站会在页面顶上加顶栏时，幻灯片缩到顶栏下面
- 字体子集、隐私扫描（发现就不出），部署到哪个网站由你自己的流程决定

用法：python3 website.py <讲稿目录> [-o <输出目录>] [--replace 旧=新 ...] [--title 标题] [--desc 摘要] [--top 选择器]
                        [--words 词1,词2] [--ignore 放行文件] [--no-fonts] [--force]
"""
import argparse
import html as htmllib
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deliver  # noqa: E402
import privacy_scan  # noqa: E402

MARK = '.html-deck-site'
SHOT_CSS = '<style>.web-shot{display:block;width:100%;height:auto;border:1px solid var(--hair)}.box>.web-shot,.pane>.web-shot{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:top;border:0}</style>'


def transform(html: str, a) -> str:
    html = deliver.replace_elements(html, lambda n: 'note' in n.cls(), lambda n, block: '', comments=True)
    for pair in a.replace:
        old, _, new = pair.partition('=')
        if old:
            html = html.replace(old, new)
    html = deliver.replace_elements(html, lambda n: n.attrs.get('data-web') == 'remove', lambda n, block: '')
    html = deliver.replace_elements(html, lambda n: bool(n.attrs.get('data-web-shot')),
                                    lambda n, block: f'<img class="web-shot" src="{htmllib.escape(n.attrs["data-web-shot"])}" alt="" loading="lazy">')
    attrs = ' data-public' + (f' data-top="{htmllib.escape(a.top)}"' if a.top else '')
    html = re.sub(r'<html\b([^>]*)>', lambda m: f'<html{m.group(1)}{attrs}>', html, count=1)
    if a.title:
        html = re.sub(r'<title>.*?</title>', f'<title>{htmllib.escape(a.title)}</title>', html, count=1, flags=re.S)
    if a.desc:
        html = html.replace('</title>', f'</title>\n<meta name="description" content="{htmllib.escape(a.desc)}">', 1)
    return html.replace('</head>', SHOT_CSS + '\n</head>', 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('deck')
    ap.add_argument('-o', '--out')
    ap.add_argument('--replace', action='append', default=[])
    ap.add_argument('--title')
    ap.add_argument('--desc')
    ap.add_argument('--top')
    ap.add_argument('--words', default='')
    ap.add_argument('--ignore')
    ap.add_argument('--no-fonts', action='store_true')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    deck = Path(a.deck).expanduser().resolve()
    out = Path(a.out).expanduser().resolve() if a.out else deck.parent / '交付' / '网站版'
    src = (deck / 'index.html').read_text('utf-8')
    loose = deliver.unsafe_loose(src)
    if loose:
        sys.exit('这几处没写结束标签，浏览器会把后面的文字也算进去，网站版删不干净，没生成。补上结束标签再跑：\n'
                 + '\n'.join(f'  第 {ln} 行 {tag}' for ln, tag in loose))
    html = transform(src, a)
    left = [w for w in (p.partition('=')[0] for p in a.replace) if w and w in html]
    if left:
        sys.exit('替换后还有：' + '、'.join(left))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / 'site'
        notes = deliver.stage(deck, html, root, fonts=not a.no_fonts)
        words = [w for w in a.words.split(',') if w] + [p.partition('=')[0] for p in a.replace if p.partition('=')[0]]
        ignore = Path(a.ignore).read_text('utf-8').splitlines() if a.ignore else []
        hits, media = privacy_scan.scan(root, words, ignore)
        privacy_scan.report(hits, media)
        left_notes = [n for n in deliver.tree((root / 'index.html').read_text('utf-8')).root.walk() if 'note' in n.cls()]
        if left_notes:
            sys.exit(f'网站版里还有 {len(left_notes)} 处备注没删掉，没生成。检查讲稿里备注的写法')
        if hits and not a.force:
            sys.exit('有可能不该公开的内容，没生成网站版。逐条处理：该删的删、该换的换（--replace）；确认没问题的原文片段写进 --ignore 文件放行')
        if out.exists() and any(out.iterdir()) and not (out / MARK).exists():
            sys.exit(f'{out} 已经有别的东西，不是这个脚本生成的，没动它。换一个空目录，或者你自己清空后再跑')
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(root, out)
        (out / MARK).write_text('html-deck website.py 生成的目录，重跑时会整个换掉\n', 'utf-8')
    for n in notes:
        print(n)
    print(f'网站版：{out}（{sum(1 for f in out.rglob("*") if f.is_file())} 个文件）。把整个目录发到你的网站；部署前在本地起个服务打开看一遍')


if __name__ == '__main__':
    main()
