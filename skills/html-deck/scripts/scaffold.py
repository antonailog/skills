#!/usr/bin/env python3
"""建一份新演示稿的项目目录，或给已有讲稿换上新版引擎。

用法：
  python3 scaffold.py <项目目录> --title "标题" [--theme swiss] [--author 名字] [--event 场合]
  python3 scaffold.py <项目目录> --engine-only      # 只把 skill 里的引擎重新拷进 讲稿/deck/（升级引擎用，不碰内容）

建出来：
  <项目>/讲稿/index.html    内容（从模板起步）
  <项目>/讲稿/deck/         引擎和 4 套风格（每份稿各拷一份，以后升级引擎不会改坏旧稿）
  <项目>/讲稿/嵌入/          截图、视频、嵌入页
  <项目>/改稿/              编辑模式的批注、讨论页
  <项目>/交付/              离线包、网站版
"""
import argparse
import html as htmllib
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ENGINE = SKILL / 'assets' / 'engine'
THEMES = ['swiss', 'editorial', 'keynote', 'brutal']


def copy_engine(deck: Path):
    d = deck / 'deck'
    (d / 'themes').mkdir(parents=True, exist_ok=True)
    for f in ['deck.css', 'deck.js', 'qrcode.js', 'fonts.css']:
        shutil.copy2(ENGINE / f, d / f)
    for t in THEMES:
        shutil.copy2(ENGINE / 'themes' / f'{t}.css', d / 'themes' / f'{t}.css')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('project')
    ap.add_argument('--title', default='演示稿标题')
    ap.add_argument('--theme', default='swiss', choices=THEMES)
    ap.add_argument('--author', default='讲者')
    ap.add_argument('--event', default='')
    ap.add_argument('--engine-only', action='store_true')
    ap.add_argument('--force', action='store_true', help='讲稿/index.html 已存在时也覆盖')
    a = ap.parse_args()
    root = Path(a.project).expanduser().resolve()
    deck = root / '讲稿'
    if a.engine_only:
        if not (deck / 'index.html').exists():
            sys.exit(f'{deck}/index.html 不存在，不是 html-deck 的项目')
        copy_engine(deck)
        print(f'已把引擎更新到 {deck / "deck"}（内容没动）')
        return
    if (deck / 'index.html').exists() and not a.force:
        sys.exit(f'{deck}/index.html 已存在。要升级引擎用 --engine-only；确定要覆盖内容加 --force')
    for sub in [deck / '嵌入' / '截图', deck / '嵌入' / '视频', root / '改稿', root / '交付']:
        sub.mkdir(parents=True, exist_ok=True)
    copy_engine(deck)
    html = (SKILL / 'assets' / 'template.html').read_text('utf-8')
    for k, v in {'TITLE': a.title, 'THEME': a.theme, 'AUTHOR': a.author, 'EVENT': a.event}.items():
        html = html.replace('{{' + k + '}}', htmllib.escape(v))
    (deck / 'index.html').write_text(html, 'utf-8')
    print(f'项目已建好：{root}')
    print(f'  讲稿：{deck / "index.html"}（风格 {a.theme}）')
    print(f'  编辑模式：python3 {SKILL / "scripts" / "serve.py"} {deck}')


if __name__ == '__main__':
    main()
