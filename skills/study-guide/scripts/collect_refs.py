"""收集外部对象的可展示信息：sites.json 里的网站、作品、产品，videos.json 里的视频。

对每个网站：读页面的标题、简介、封面图（og:image）、能不能嵌视频；截一屏存 img/sites/<img>.jpg。
  页面一打开（domcontentloaded）先看状态码、标题和正文：返回 4xx/5xx、是人机验证页（Cloudflare 的「Just a moment…」
  「Performing security verification」这类）或登录墙，就直接判被拦，不往下等；加载完是空白页也算被拦。
  被拦时改用封面图，两样都没有就只留链接（页面上显示成一行链接）。截图为什么没用上、封面图为什么没拿到（HTTP 403 等），写在输出表的备注里。
截哪一屏由 sites.json 那条的可选字段 shot 控制：{"wait": 毫秒, "scroll": "CSS 选择器" 或 像素, "element": "…", "hide_overlays": true}。
  wait：页面加载完再等多久（默认 1500；有加载动画的页面给 4000–8000，截到的才不是动画）；
  scroll：截图前把这个元素滚到屏幕顶上，或者往下滚这么多像素；
  element：只截页面里的这一个元素，写 CSS 选择器，或者「img:」加图片地址里的一段（"img:heatmap"），
    要看的图在页面中部（热力图、网格示意、作品大图）时用；会先滚过去、等懒加载的图加载完再截；
  hide_overlays：截图前隐藏浮在页面上、带 cookie / privacy / consent / 隐私 字样的弹窗和横条（默认开；不点「同意」）。
    误藏了要看的吸顶内容时写 false。
  字体、作品、模板这类对象，读者要看的是它本身的样子：登记的 url 选样张页、展示页、作品详情页，比首页或代码仓库的文件列表有用；
  样张在页面下方，就用 scroll 滚过去。
对每个视频：YouTube 地址补上 youtube 字段（能嵌）；没有封面的用页面封面图补 poster。
抓到的标题、简介写进 links/_refs_info.json，**只给写作时参考**（多是对方自己的宣传语），页面上的 desc、meta 由你按正文写。
不伪装浏览器、不绕过人机验证。要 Playwright（pip install playwright && playwright install chromium）和 Pillow。
用法：python3 -I collect_refs.py <学习指南目录> [--force 重截已有的]
  已有截图的默认不重截；改了某一条的 shot，删掉那张截图再跑（--force 会把全部重截一遍）。
"""
import asyncio
import html
import io
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = 'study-guide-collect/1.0'
# 人机验证页、登录墙上的字（小写）；check_links.py 里有同一份，两处一起改
BLOCKED = ['verify you are human', 'verifying you are human', 'confirm you are human', 'are you a robot', 'not a robot', 'security check',
           'checking your browser', 'verify that you are', 'unusual traffic', 'captcha', 'just a moment', 'access denied', 'enable javascript',
           'attention required', 'performing security verification', 'security service to protect against malicious bots',
           'performance and security by cloudflare', 'performance & security by cloudflare',
           'sign in to continue', 'log in to continue', '人机验证', '安全验证', '请完成验证', '访问被拒绝', '验证码', '登录后查看']


def blocked_reason(title: str, text: str) -> str | None:
    """标题命中，或者正文不长（验证页、登录墙都很短）而且命中 → 被拦；长文章里顺带提到 captcha 的不算"""
    t, x = (title or '').lower(), (text or '').lower()
    if any(k in t for k in BLOCKED) or (len(x) < 3000 and any(k in x for k in BLOCKED)):
        return '人机验证页或登录墙'
    return None


def meta_of(url: str) -> dict:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=20) as r:
            raw = r.read(400_000).decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e:
        return {'error': f'HTTP {e.code}'}
    except Exception as e:
        return {'error': type(e).__name__}
    def og(prop: str) -> str | None:
        m = re.search(rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']+)', raw, re.I) \
            or re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{prop}["\']', raw, re.I)
        return html.unescape(m.group(1)).strip() if m else None
    t = re.search(r'<title[^>]*>(.*?)</title>', raw, re.S | re.I)
    img = og('og:image') or og('twitter:image')
    return {'title': og('og:title') or (re.sub(r'\s+', ' ', html.unescape(t.group(1))).strip() if t else None),
            'description': og('og:description') or og('description'),
            'image': (u if web(u := urllib.parse.urljoin(url, img)) else None) if img else None,
            'video': og('og:video') or og('og:video:url') or og('twitter:player')}


def youtube_id(url: str) -> str | None:
    m = re.search(r'(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([\w-]{11})', url or '')
    return m.group(1) if m else None


IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp')


def img_path(name: str) -> str:
    """sites.json 的 img 或 key → 文件名：本身是图片扩展名就用它，否则补 .jpg（key 常带点，比如 figma.com）。Gallery.tsx 的 shotOf 同一规则"""
    return name if Path(name).suffix.lower() in IMG_EXT else f'{name}.jpg'


def web(url: str | None) -> bool:
    """只下载 http / https 的地址（页面里写的 file: 之类不碰）"""
    return bool(url) and urllib.parse.urlsplit(url).scheme in ('http', 'https')


def save_img(im, out: Path) -> None:
    """先写临时文件再替换：中途失败不会留下半张图，也不会删掉原来那张"""
    tmp = out.with_name(f'{out.stem}.tmp{out.suffix}')
    im.save(tmp, quality=80)
    tmp.replace(out)


def download(url: str, out: Path) -> str | None:
    """下载图片转成 JPG：成功返回 None，失败返回原因（HTTP 403、超时、不是位图……）"""
    from PIL import Image
    if not web(url):
        return '不是 http(s) 地址'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=30) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        return f'HTTP {e.code}'
    except Exception as e:   # 超时、连不上
        return type(e).__name__
    try:
        im = Image.open(io.BytesIO(data)).convert('RGB')
        im.thumbnail((1200, 1200))
        save_img(im, out)
    except Exception:
        return '不是位图（可能是 SVG）'
    return None


# 浮在页面上（fixed / sticky）、带这些字样的元素当成 Cookie、隐私弹窗隐藏掉；只隐藏，不点「同意」
HIDE_OVERLAYS = '''() => { for (const el of document.querySelectorAll('body *')) { const s = getComputedStyle(el);
  if ((s.position === 'fixed' || s.position === 'sticky') && /cookie|privacy|consent|gdpr|隐私/i.test(el.innerText || '')) el.style.display = 'none' } }'''
# 元素里的图都加载完（或最多等 5 秒）
LOADED = '''e => Promise.race([Promise.all([...(e.tagName === 'IMG' ? [e] : e.querySelectorAll('img'))].map(i => i.complete || new Promise(r => { i.onload = i.onerror = r }))),
  new Promise(r => setTimeout(r, 5000))])'''


async def look(pg) -> tuple[str, str]:
    try:
        return await pg.title(), await pg.evaluate('document.body ? document.body.innerText : ""')
    except Exception:   # 页面还在跳转
        return '', ''


async def shoot(b, url: str, out: Path, opt: dict) -> str | None:
    """截一屏：成功返回 None，没用上返回原因"""
    from PIL import Image
    pg = await b.new_page(viewport={'width': 1440, 'height': 900}, device_scale_factor=2)   # 2 倍：截元素时小图也清楚；整屏照样缩到 1200 宽
    try:
        r = await pg.goto(url, wait_until='domcontentloaded', timeout=30000)
        if r and r.status >= 400:
            return f'页面返回 HTTP {r.status}' + (f'（{why}）' if (why := blocked_reason(*await look(pg))) else '')
        if why := blocked_reason(*await look(pg)):   # 验证页一打开就认得出，不等它
            return why
        for state, ms in (('load', 15000), ('networkidle', 8000)):   # 一直有后台请求的页面等不到 networkidle，到点就往下走
            try:
                await pg.wait_for_load_state(state, timeout=ms)
            except Exception:
                pass
        await pg.wait_for_timeout(int(opt.get('wait', 1500)))
        sc = opt.get('scroll')
        if isinstance(sc, (int, float)) and not isinstance(sc, bool):
            await pg.evaluate('y => scrollTo(0, y)', sc)
        elif sc:
            el = pg.locator(sc).first
            if not await el.count():
                return f'shot.scroll 的 {sc} 在页面上没找到'
            await el.evaluate("e => e.scrollIntoView({block: 'start'})")
        if sc:
            await pg.wait_for_timeout(800)   # 滚过去以后懒加载的图
        title, text = await look(pg)
        if why := blocked_reason(title, text):
            return why
        if len(text.strip()) < 40:
            return '空白页'
        hide = opt.get('hide_overlays', True)
        if hide:
            await pg.evaluate(HIDE_OVERLAYS)
        png = out.with_name(f'{out.stem}.shot.png')
        if el_sel := opt.get('element'):
            if el_sel.startswith('img:'):
                el_sel = f'img[src*="{el_sel[4:]}"]'
            el = pg.locator(el_sel).first
            if not await el.count():
                return f'shot.element 的 {opt["element"]} 在页面上没找到'
            await el.scroll_into_view_if_needed()
            await pg.wait_for_timeout(1500)
            await el.evaluate(LOADED)   # 懒加载的图滚到了才开始下载
            if hide:
                await pg.evaluate(HIDE_OVERLAYS)   # 有的弹窗滚动以后才出来
            await el.screenshot(path=str(png))
        else:
            await pg.screenshot(path=str(png))
        try:
            im = Image.open(png).convert('RGB')
            im.thumbnail((1200, 1200))
            save_img(im, out)
        finally:
            png.unlink(missing_ok=True)
        return None
    except Exception as e:
        return type(e).__name__
    finally:
        await pg.close()


async def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    from playwright.async_api import async_playwright
    d = Path(sys.argv[1]).expanduser().resolve()
    force = '--force' in sys.argv
    info_f = d / 'links' / '_refs_info.json'
    info_f.parent.mkdir(parents=True, exist_ok=True)
    info = json.loads(info_f.read_text(encoding='utf-8')) if info_f.exists() else {}
    rows = []

    sites_f = d / 'sites.json'
    sites = json.loads(sites_f.read_text(encoding='utf-8')) if sites_f.exists() else []
    (d / 'img' / 'sites').mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for s in sites:
            m = meta_of(s['url'])
            info[s['key']] = m
            name = s.get('img') or s['key']
            out = d / 'img' / 'sites' / img_path(name)
            if s.get('img') and '/' in s['img']:
                out = d / s['img']
            notes = []
            got = '已有，没重截' if out.exists() and not force else None
            if not got:
                why = await shoot(b, s['url'], out, s.get('shot') or {})
                if not why:
                    got = '截图'
                else:
                    notes.append(f'截图没用上：{why}')
                    if m.get('image'):
                        cover = f'下载失败（{err}）' if (err := download(m['image'], out)) else None
                    else:
                        cover = f'读不到页面（{m["error"]}）' if m.get('error') else '页面没有 og:image'
                    if cover:
                        notes.append(f'封面图：{cover}')
                    else:
                        got = '封面图'
            if got:
                s.setdefault('img', name)
            elif out.exists():   # --force 重截失败：保留原来那张
                got = '重截失败，保留原图'
            else:
                s.pop('img', None)
            yt = youtube_id(s['url']) or youtube_id(m.get('video') or '')
            if yt:
                notes.append(f'YouTube {yt}，可以挪进 videos.json')
            rows.append((s['name'], got or '无，只留链接', '；'.join(notes)))
        await b.close()
    if sites:
        sites_f.write_text(json.dumps(sites, ensure_ascii=False, indent=1), encoding='utf-8')

    videos_f = d / 'videos.json'
    videos = json.loads(videos_f.read_text(encoding='utf-8')) if videos_f.exists() else []
    (d / 'img' / 'videos').mkdir(parents=True, exist_ok=True)
    for v in videos:
        note = ''
        yt = v.get('youtube') or youtube_id(v.get('url', ''))
        if yt:
            v['youtube'] = yt
            v.setdefault('poster', f'https://i.ytimg.com/vi/{yt}/hqdefault.jpg')
        if not v.get('poster') and v.get('url'):
            m = meta_of(v['url'])
            info['video:' + v['name']] = m
            slug = re.sub(r'[^\w-]+', '-', v['name'])[:40]
            out = d / 'img' / 'videos' / f'{slug}.jpg'
            if not m.get('image'):
                note = f'封面图：读不到页面（{m["error"]}）' if m.get('error') else '封面图：页面没有 og:image'
            elif why := download(m['image'], out):
                note = f'封面图：下载失败（{why}）'
            else:
                v['poster'] = f'img/videos/{slug}.jpg'
        embed = '能嵌' if v.get('youtube') or v.get('mp4') else ('封面卡' if v.get('poster') else '没有封面：别用 ::video，写成链接')
        rows.append((v['name'], embed, note))
    if videos:
        videos_f.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding='utf-8')

    info_f.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding='utf-8')
    print('| 对象 | 拿到了什么 | 备注 |\n|---|---|---|')
    for r in rows:
        print(f'| {r[0]} | {r[1]} | {r[2]} |')
    print('\n截图和封面图都要打开看一眼：还有没藏掉的弹窗、加载动画、空白首屏、和正文说的不是一个东西，都删掉重找（换 url，或者在 shot 里加 wait、scroll、element）。'
          '\n封面图 HTTP 403 多半是图床拦脚本下载：换一个能展示它的页面（官方展示页、新闻稿配图），或者只留链接。')


if __name__ == '__main__':
    asyncio.run(main())
