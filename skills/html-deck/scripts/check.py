#!/usr/bin/env python3
"""检查一份讲稿能不能上台：每页有没有溢出或被截断、引用的文件在不在、有没有脚本报错、断网能不能放。

用法：python3 check.py <讲稿目录> [--shots <目录>]   （--shots 会把每页最后一步截图存下来）
有问题退出码 1。需要 Playwright（pip install playwright && playwright install chromium）。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deliver  # noqa: E402

OVERFLOW_JS = r"""(i) => {
  const s = deck.slides[i], R = s.getBoundingClientRect(), k = R.width / 1280, out = [];
  const skip = (e) => e.closest('.note, svg, iframe, .scroll, .gal, .duo, pre.code, .box, #ov');
  const name = (e) => { const t = (e.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 24); return e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : '') + (t ? ' 「' + t + '」' : ''); };
  if (s.scrollHeight > s.clientHeight + 2) out.push('整页内容比一页高 ' + Math.round((s.scrollHeight - s.clientHeight)) + 'px');
  s.querySelectorAll('*').forEach((e) => {
    if (skip(e) || !e.getClientRects().length) return;
    const r = e.getBoundingClientRect();
    if (r.right > R.right + 2 * k || r.bottom > R.bottom + 2 * k || r.left < R.left - 2 * k) out.push('超出页面：' + name(e));
    const cs = getComputedStyle(e);
    if ((cs.overflow === 'hidden' || cs.overflowY === 'hidden') && e.scrollHeight > e.clientHeight + 4 && e !== s && !e.classList.contains('slide')) out.push('被截断：' + name(e));
  });
  return [...new Set(out)].slice(0, 6);
}"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('deck')
    ap.add_argument('--shots')
    a = ap.parse_args()
    deck = Path(a.deck).expanduser().resolve()
    index = deck / 'index.html'
    if not index.exists():
        sys.exit(f'{index} 不存在')
    html = index.read_text('utf-8')
    problems, notes = [], []

    # 页面直接引用的，加上嵌入网页、样式表再引用的（打包时就照这份清单带文件）
    _, missing, far = deliver.collect(deck, html)
    problems += [f'在讲稿目录外面，打包时带不上：{r}（拷进讲稿目录，改成相对路径）' for r in far]
    problems += [f'文件不存在：{r}' for r in missing]
    problems += [f'第 {ln} 行 {tag} 没写结束标签：浏览器会把后面的文字也算进去，网站版删不干净' for ln, tag in deliver.unsafe_loose(html)]
    problems += [f'引用的是文件夹：{r}（本地打开时只显示文件列表，写成 {r.rstrip("/")}/index.html）'
                 for r in deliver.local_refs(html, links=False) if (deck / r).is_dir()]
    if '</div><!-- /stage -->' not in html:
        problems.append('缺少 </div><!-- /stage --> 结束标记（编辑模式和交付脚本靠它）')

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('\n'.join(problems) or '文件检查通过')
        sys.exit('没装 Playwright，这次只查了文件，没查溢出和断网：pip install playwright && playwright install chromium')

    url = index.as_uri()
    with sync_playwright() as p:
        br = p.chromium.launch()
        for offline in (False, True):
            ctx = br.new_context(viewport={'width': 1280, 'height': 720}, offline=offline)
            pg = ctx.new_page()
            errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
            pg.on('console', lambda m: errs.append(m.text[:160]) if m.type == 'error' and 'net::' not in m.text and 'Failed to load resource' not in m.text else None)
            pg.goto(url)
            pg.wait_for_timeout(1200)
            n = pg.evaluate('window.deck ? deck.slides.length : 0')
            if not n:
                problems.append('引擎没跑起来（window.deck 不存在），检查 deck/deck.js 是否引入')
                break
            if not offline:
                for i in range(n):
                    tabs = pg.evaluate(f'deck.slides[{i}]._tabs.length') or 1
                    for t in range(tabs):
                        pg.evaluate(f'(() => {{ deck.show({i}, true, true); const s = deck.slides[{i}]; if (s._tabs.length) deck.setTab(s, {t}); }})()')
                        pg.wait_for_timeout(250)
                        for o in pg.evaluate(OVERFLOW_JS, i):
                            problems.append(f'第 {i + 1} 页' + (f'（页签 {t + 1}）' if tabs > 1 else '') + f'：{o}')
                    if a.shots:
                        Path(a.shots).mkdir(parents=True, exist_ok=True)
                        pg.wait_for_timeout(900)
                        pg.screenshot(path=str(Path(a.shots) / f'{i + 1:02d}.png'))
                online = pg.evaluate('''deck.slides.map((s, i) => [...s.querySelectorAll('iframe[data-src], img[src], video[src]')]
                  .filter((e) => /^https?:/.test(e.dataset.src || e.getAttribute('src') || '')).map((e) => [i + 1, !!(e.closest('.box') && e.closest('.box').querySelector('.shot'))])).flat()''')
                for pgno, has_shot in online:
                    (notes if has_shot else problems).append(f'第 {pgno} 页用了在线内容，' + ('断网时自动换成备用截图' if has_shot else '没有备用截图，断网时这块是空白（在 .box 里加 <img class="shot" src="嵌入/截图/…">）'))
            for e in sorted(set(errs)):
                problems.append(('断网时' if offline else '') + f'脚本报错：{e}')
            ctx.close()
        br.close()

    for x in notes:
        print('提示：' + x)
    if problems:
        print(f'发现 {len(problems)} 个问题：')
        print('\n'.join('  - ' + x for x in problems))
        sys.exit(1)
    print(f'检查通过：{n} 页，没有溢出，文件都在，联网和断网都没有报错')


if __name__ == '__main__':
    main()
