"""页面自检：打开构建好的学习指南，在 360 / 390 / 768 / 1440 四个宽度上查。

查什么：控制台报错、4xx/5xx、坏图、横向溢出、表格里挤成一字一行的列、正文宽度和是否在页面正中（1440）、残留的「给核对者看的说明」、各组件数量。
--shots <目录>：每个宽度截首屏；1440 宽时再截组件：
  单独成段的图逐张截（截图、信息图都是这种，文件名带图片名），第一张再点开截放大后的样子；
  表格、表格卡片、画廊、中轴两栏、流程图、自定义演示、视频卡（mp4、YouTube 封面按钮、点了去原站的封面卡）各截第一个。
--guide <学习指南目录>：先核对页面标题（h1）和 guide.md 第一行一致，不一致直接报错退出。
  本机端口可能被别的预览占着，检查到的是另一篇时，结果照样会显示「通过」。
用法：python3 -I page_check.py <页面地址，如 http://127.0.0.1:<端口>/> [--guide 学习指南目录] [--shots 目录]
"""
import asyncio
import re
import sys
from pathlib import Path

# 写给核对者看、读者用不上的说明文字，不该出现在页面上；正文真的需要这些词时，人工看一眼排除
BANNED = ['不在原文里', '补充 ·', '核对状态', '截图日期', '截不到画面', '已核对', '未核对', 'AI 补充', '导出时丢了', '可能过时']
# 视频：mp4 是 <video>；YouTube 没点之前是一个封面按钮（点了才换成 iframe）；不能嵌的是点了去原站的封面卡
VIDEO = 'video, iframe, button[aria-label^="播放："], a[aria-label^="打开："]'
COUNT = {'引用': '[data-cite]', '表格卡片': 'article.tc', '图片': '.tc-fig img, figure.fig-box img', '画廊': '.gal', '中英切换': '.bi',
         '中轴阶段': '.stg-band', '流程图': '.fig-box svg', '视频': VIDEO}
# --shots 在 1440 宽时各截第一个：(文件名, 选择器)
PARTS = [('table', '.fit-wrap:not(:has(.tbl[hidden]))'), ('card', 'article.tc'), ('gallery', '.gal'), ('stages', '.stg'), ('flow', 'div.fig-box'), ('demo', 'figure.fig-box'),
         ('video-mp4', 'figure:has(video)'), ('video-youtube', 'figure:has(button[aria-label^="播放："])'), ('video-cover', 'figure:has(a[aria-label^="打开："])')]
LOADED = '''e=>Promise.race([Promise.all([...e.querySelectorAll('img')].map(i=>i.complete||new Promise(r=>{i.onload=i.onerror=r}))),new Promise(r=>setTimeout(r,4000))])'''


async def snap(el, path: str) -> None:
    await el.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})")
    await el.evaluate(LOADED)
    await el.page.wait_for_timeout(400)
    await el.screenshot(path=path)


async def shoot_parts(pg, pre: str) -> int:
    """截组件；返回问题数（点了图没放大）"""
    await pg.add_style_tag(content='.topbar{position:static!important}')   # 比屏幕高的元素截图时别把吸顶顶栏截进去
    figs = pg.locator('.tc-fig')
    n, names = await figs.count(), set()
    for i in range(min(n, 12)):
        src = await figs.nth(i).locator('img').first.get_attribute('src') or ''
        stem = re.sub(r'[^\w-]+', '-', src.rsplit('/', 1)[-1].rsplit('.', 1)[0])[:40] or str(i + 1)
        stem = f'{stem}-{i + 1}' if stem in names else stem
        names.add(stem)
        await snap(figs.nth(i), f'{pre}-img-{stem}.png')
    if n > 12:
        print(f'  单独成段的图有 {n} 张，只截了前 12 张')
    bad = 0
    if n:
        await figs.first.locator('button').click()
        lb = pg.locator('.lb')
        try:
            await lb.wait_for(timeout=3000)
            await lb.evaluate(LOADED)
            await pg.screenshot(path=f'{pre}-img-zoom.png')
            await pg.keyboard.press('Escape')
        except Exception:
            print('  点了第一张图没有放大（.lb 没出来）')
            bad = 1
    for name, sel in PARTS:
        el = pg.locator(sel).first
        if await el.count():
            await snap(el, f'{pre}-{name}.png')
    return bad


async def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    from playwright.async_api import async_playwright
    url = sys.argv[1]
    i = sys.argv.index('--shots') if '--shots' in sys.argv else -1
    if i >= 0 and i + 1 >= len(sys.argv):
        sys.exit('--shots 后面要给截图目录')
    shots = sys.argv[i + 1] if i >= 0 else None
    j = sys.argv.index('--guide') if '--guide' in sys.argv else -1
    if j >= 0 and j + 1 >= len(sys.argv):
        sys.exit('--guide 后面要给学习指南目录')
    expect = None
    if j >= 0:
        gp = Path(sys.argv[j + 1]).expanduser() / 'guide.md'
        first = next((t for t in gp.read_text(encoding='utf-8').split('\n') if t.strip()), '')
        expect = re.sub(r'\s+', ' ', first.removeprefix('# ')).strip()
    problems = 0
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for w in (1440, 768, 390, 360):
            pg = await b.new_page(viewport={'width': w, 'height': 900})
            errs, bad = [], []
            pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
            pg.on('response', lambda r: bad.append(f'{r.status} {r.url}') if r.status >= 400 else None)
            await pg.goto(url, wait_until='networkidle')
            await pg.wait_for_timeout(800)
            if expect is not None and w == 1440:
                h1 = re.sub(r'\s+', ' ', await pg.evaluate('document.querySelector("h1")?.innerText || ""')).strip()
                if h1 != expect:
                    sys.exit(f'打开的不是这一篇：页面标题「{h1}」，guide.md 是「{expect}」。端口可能被别的预览占着，换一个空闲端口重起')
            if shots:
                await pg.screenshot(path=f'{shots}/{w}-top.png')   # 先截首屏：滚过以后左侧目录会停在别处
            await pg.evaluate('async()=>{for(let y=0;y<document.body.scrollHeight;y+=800){scrollTo({top:y,behavior:"instant"});await new Promise(r=>setTimeout(r,40))}scrollTo({top:0,behavior:"instant"})}')
            await pg.wait_for_timeout(1500)
            r = await pg.evaluate('''(banned)=>{const m=document.querySelector('main')?.getBoundingClientRect();const t=document.body.innerText;
              return {over:document.documentElement.scrollWidth-innerWidth, broken:[...document.images].filter(i=>i.complete&&!i.naturalWidth).map(i=>i.src),
                width:m?Math.round(m.width):null, off:m?Math.round((m.left+m.right)/2-innerWidth/2):null, banned:banned.filter(x=>t.includes(x)),
                squeezed:[...document.querySelectorAll('table td, table th')].filter(c=>c.offsetParent!==null&&c.textContent.trim().length>4&&c.getBoundingClientRect().width<52).map(c=>c.textContent.trim().slice(0,12))}}''', BANNED)
            line = f'{w}px：报错 {len(errs)} · 4xx {len(bad)} · 坏图 {len(r["broken"])} · 横向溢出 {r["over"]}px · 挤成一字一行的格子 {len(r["squeezed"])}'
            if w == 1440:
                line += f' · 正文宽 {r["width"]} · 偏离中心 {r["off"]}px'
                # 只数看得见的：句子多的表在页面上有宽屏、手机两份，藏起来的那份不算
                counts = await pg.evaluate('m=>Object.fromEntries(Object.entries(m).map(([k,s])=>[k,[...document.querySelectorAll(s)].filter(e=>e.getClientRects().length>0).length]))', COUNT)
                line += '\n  组件：' + '、'.join(f'{k} {v}' for k, v in counts.items())
                if r['banned']:
                    line += f'\n  残留说明文字：{r["banned"]}（逐个看是不是正文本来就要的）'
            problems += len(errs) + len(bad) + len(r['broken']) + (r['over'] > 0) + len(r['squeezed'])
            if r['squeezed']:
                line += f'\n  挤成一字一行：{r["squeezed"][:5]}（这张表改成卡片、拆成列表，或减少列数）'
            print(line)
            for x in (errs[:3] + bad[:3] + r['broken'][:3]):
                print('   ', x)
            if shots and w == 1440:
                problems += await shoot_parts(pg, f'{shots}/{w}')
            await pg.close()
        await b.close()
    print('通过' if not problems else f'有 {problems} 处要修')


if __name__ == '__main__':
    asyncio.run(main())
