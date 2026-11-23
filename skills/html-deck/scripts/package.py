#!/usr/bin/env python3
"""打离线播放包：讲稿、用到的文件、引擎、字体子集，加一份「怎么播放」，打成 zip 拷到别的电脑直接放。

用法：python3 package.py <讲稿目录> [-o <zip 路径>] [--name 文件夹名] [--words 词1,词2] [--ignore 放行文件] [--no-fonts] [--force]
- 默认输出到讲稿旁边的 交付/<名>.zip
- 打包前对要装进包的全部文件跑隐私扫描（scripts/privacy_scan.py），发现就停下不出包；逐条处理，确认没问题的原文片段写进 --ignore 文件放行（--force 只在你清楚后果时用）
- 包里不带编辑模式；备注会带上（现场按 N 或 P 看）
"""
import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deliver  # noqa: E402
import privacy_scan  # noqa: E402

HOWTO = '''怎么播放

1. 把压缩包整个解压。index.html 和旁边的 deck、嵌入 文件夹要放在一起，不要只拖出 index.html。
2. 用 Chrome 或 Edge 打开 index.html（双击，或拖进浏览器窗口）。
3. 按 F 全屏（翻页笔的「开始放映」键也行）。→ 或 PageDown 下一步，← 或 PageUp 上一步。
4. 其他按键：O 看所有页的缩略图、点哪页跳哪页；B 或句号黑屏，再按一下恢复；N 看备注。
5. 双屏演讲：按 P 打开演讲者视图（当前页、下一页、备注、计时），把幻灯片窗口拖到投影上全屏，两个窗口翻页同步。
{online}'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('deck')
    ap.add_argument('-o', '--out')
    ap.add_argument('--name')
    ap.add_argument('--words', default='')
    ap.add_argument('--ignore')
    ap.add_argument('--no-fonts', action='store_true')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    deck = Path(a.deck).expanduser().resolve()
    html = (deck / 'index.html').read_text('utf-8')
    title = re.sub(r'\s+', ' ', (re.search(r'<title>(.*?)</title>', html, re.S) or [None, '讲稿'])[1]).strip()
    name = re.sub(r'[\\/:*?"<>|·\x00-\x1f]+', '-', a.name or title).strip(' -.')[:60].strip(' -.') or '讲稿'   # 去掉 .. 和过长的名字
    out = Path(a.out).expanduser().resolve() if a.out else deck.parent / '交付' / f'{name}.zip'
    pages = deliver.online_pages(html)
    online = ''
    if pages:
        ok = [str(p) for p, s in pages if s]
        bad = [str(p) for p, s in pages if not s]
        online = '\n联网时' + '、'.join(sorted(set(ok + bad), key=int)) + ' 页显示在线内容。'
        if ok:
            online += f'没网时第 {"、".join(ok)} 页自动换成截图。'
        if bad:
            online += f'第 {"、".join(bad)} 页没有备用截图，没网时那块是空白。'
        online += '其他页都不需要联网。\n'
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / name
        notes = deliver.stage(deck, html, root, fonts=not a.no_fonts)
        (root / '怎么播放.txt').write_text(HOWTO.format(online=online), 'utf-8')
        words = [w for w in a.words.split(',') if w]
        ignore = Path(a.ignore).read_text('utf-8').splitlines() if a.ignore else []
        hits, media = privacy_scan.scan(root, words, ignore)
        privacy_scan.report(hits, media)
        if hits and not a.force:
            sys.exit('有可能不该外发的内容，没出包。逐条处理：该删的删、该换的换；确认没问题的原文片段写进 --ignore 文件放行')
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted(root.rglob('*')):
                if f.is_file():
                    z.write(f, f'{name}/{f.relative_to(root)}')
        count = sum(1 for f in root.rglob('*') if f.is_file())
    for n in notes:
        print(n)
    print(f'离线包：{out}（{count} 个文件，{out.stat().st_size / 1e6:.1f} MB）')
    print('拷到别的电脑前，最好在那台电脑上打开翻一遍（字体、视频、翻页笔、投影比例）')


if __name__ == '__main__':
    main()
