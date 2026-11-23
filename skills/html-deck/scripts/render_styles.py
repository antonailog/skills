#!/usr/bin/env python3
"""用讲稿里的真实内容把几套风格都渲染一遍，生成风格讨论页让用户挑。

用法：python3 render_styles.py <讲稿目录> --pages 1,3,6 [--themes swiss,editorial,keynote,brutal] [-o <输出目录>]
默认输出到讲稿旁边的 改稿/风格/：每套风格每页一张截图，加一个 风格讨论.html。需要 Playwright。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import discussion  # noqa: E402

THEMES = {
    'swiss': ('瑞士网格', '白底黑字、粗线标题、红色只给重点；信息密度高、克制', '观点型演讲、行业分享'),
    'editorial': ('编辑书卷', '纸色底、衬线标题、细线和斜体引用；安静、有书卷气', '课程、思想分享、读书会'),
    'keynote': ('暗场发布会', '深色底、蓝青渐变强调、发光背景；有现场感', '产品演示、发布会、技术分享'),
    'brutal': ('新野兽派', '米黄底、粗黑框加硬阴影、亮色块；活泼、有记忆点', '社区分享、轻松的课、面向年轻听众'),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('deck')
    ap.add_argument('--pages', required=True, help='用哪几页渲染，如 1,3,6（建议封面加 2—3 页有代表性的内容页）')
    ap.add_argument('--themes', default=','.join(THEMES))
    ap.add_argument('--recommend', default='', help='推荐哪几套，逗号分隔')
    ap.add_argument('-o', '--out')
    a = ap.parse_args()
    deck = Path(a.deck).expanduser().resolve()
    out = Path(a.out).expanduser().resolve() if a.out else deck.parent / '改稿' / '风格'
    out.mkdir(parents=True, exist_ok=True)
    pages = [int(x) for x in a.pages.split(',')]
    themes = [t for t in a.themes.split(',') if t in THEMES]
    rec = set(a.recommend.split(','))
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit('没装 Playwright：pip install playwright && playwright install chromium。没法渲染时，把 references/themes.md 里的风格说明给用户挑')
    url = (deck / 'index.html').as_uri()
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={'width': 1280, 'height': 720})
        for t in themes:
            pg.goto(f'{url}?theme={t}')
            pg.wait_for_timeout(1500)
            total = pg.evaluate('deck.slides.length')
            bad = [n for n in pages if not 1 <= n <= total]
            if bad:
                sys.exit(f'讲稿只有 {total} 页，没有第 {"、".join(map(str, bad))} 页')
            for n in pages:
                pg.evaluate(f'deck.show({n - 1}, true, true)')
                pg.wait_for_timeout(1300)
                pg.screenshot(path=str(out / f'{t}-{n:02d}.png'))
        br.close()
    spec = {
        'title': '风格：用你的内容渲染了 {} 套，选一套'.format(len(themes)),
        'lead': '每套风格用讲稿里同样的几页真实内容渲染：第 ' + '、'.join(map(str, pages)) + ' 页。功能完全一样，只换外观；以后想换也只是换一个文件。',
        'questions': [{
            'title': '用哪套风格', 'wide': True,
            'options': [{'label': THEMES[t][0], 'desc': f'{THEMES[t][1]}。适合：{THEMES[t][2]}', 'rec': t in rec,
                         'images': [f'{t}-{n:02d}.png' for n in pages]} for t in themes],
        }],
    }
    (out / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1), 'utf-8')
    html = discussion.build(spec, out)
    (out / '风格讨论.html').write_text(html, 'utf-8')
    print(f'风格讨论页：{out / "风格讨论.html"}')


if __name__ == '__main__':
    main()
