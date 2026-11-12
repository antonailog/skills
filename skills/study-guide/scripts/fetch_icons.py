"""下载来源网站的小图标（favicon），给引用浮窗和文末来源列表用。

读 guide.md 里引用到的来源（sources.json）和 sites.json 的网址，按域名去重；每个域名先读首页里声明的图标
（<link rel="icon">、apple-touch-icon），没有就试 /favicon.ico；首页拒绝脚本请求的，再用 Playwright 打开一次读声明的图标，
还没有就用 DuckDuckGo 的公开图标服务（只发域名）。下载后转成 64×64 的 PNG（SVG 原样保存），
存 img/favicons/<域名>.png（去掉 www.）。构建时有图标的来源显示图标，没有的显示通用地球图标。
已经有的跳过（--force 重下）。不伪装浏览器、不绕过人机验证。要 Pillow，Playwright 可选。
用法：python3 -I fetch_icons.py <学习指南目录> [--force]
"""
import html
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UA = 'study-guide-collect/1.0'
REF = re.compile(r'\[\[\s*([\w.-]+(?:\s*,\s*[\w.-]+)*)\s*\]\]')


def host_of(url: str) -> str:
    return re.sub(r'^www\.', '', urllib.parse.urlsplit(url).hostname or '')


def get(url: str, limit: int = 600_000) -> tuple[bytes, str]:
    if urllib.parse.urlsplit(url).scheme not in ('http', 'https'):   # 页面里声明的 file: 之类地址不碰
        raise ValueError('不是 http(s) 地址')
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=15) as r:
        return r.read(limit), (r.headers.get('Content-Type') or '').lower()


def declared(page_url: str) -> list[str]:
    """首页里声明的图标，按合适程度排：32–64 的 png/svg 优先，其次 apple-touch-icon，再其次任意 icon"""
    try:
        raw, _ = get(page_url)
    except Exception:
        return []
    doc = raw.decode('utf-8', 'ignore')
    found = []
    def attr(tag: str, name: str) -> str:   # 属性值可能带引号，也可能不带
        m = re.search(rf'\b{name}\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', tag, re.I)
        return next((g for g in m.groups() if g is not None), '') if m else ''
    for tag in re.findall(r'<link\b[^>]*>', doc, re.I):
        rel, href = attr(tag, 'rel').lower(), attr(tag, 'href').rstrip('/')
        if not href or 'icon' not in rel or 'mask-icon' in rel:
            continue
        sizes = re.match(r'(\d+)x\d+', attr(tag, 'sizes'))
        size = int(sizes.group(1)) if sizes else 0
        svg = '.svg' in href.lower() or 'svg' in attr(tag, 'type').lower()
        rank = 0 if svg else 1 if 32 <= size <= 96 else 2 if 'apple' in rel else 3
        found.append((rank, -size, urllib.parse.urljoin(page_url, html.unescape(href))))
    return [u for *_, u in sorted(found)]


def save(data: bytes, ctype: str, out_png: Path) -> str | None:
    head = data[:300].lstrip().lower()
    if 'svg' in ctype or head.startswith(b'<svg') or (head.startswith(b'<?xml') and b'<svg' in data[:2000].lower()):
        # SVG 会和页面一起发布在自己的域名下：带脚本、事件属性、外部嵌入的不收
        if re.search(rb'<script|\bon[a-z]+\s*=|javascript:|<foreignobject|<iframe|<embed|<object', data, re.I):
            return None
        out_png.with_suffix('.svg').write_bytes(data)
        return 'svg'
    if head.startswith((b'<!doctype', b'<html')):
        return None   # 软 404：返回的是网页
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(data))
        if im.format == 'ICO' and im.info.get('sizes'):
            im.size = max(im.info['sizes'])   # ICO 里有几种尺寸，取最大的再缩
        im = im.convert('RGBA')
        if im.width < 12:
            return None
        im.thumbnail((64, 64))
        im.save(out_png, 'PNG')
        return 'png'
    except Exception:
        return None


def first_ok(host: str, urls: list[str], out_dir: Path) -> tuple[str, str]:
    for u in dict.fromkeys(urls):
        try:
            data, ctype = get(u, 400_000)
        except Exception:
            continue
        kind = save(data, ctype, out_dir / f'{host}.png')
        if kind:
            return host, kind
    return host, '没拿到'


def base_of(page: str) -> str:
    u = urllib.parse.urlsplit(page)
    return f'{u.scheme}://{u.netloc}/'


def fetch(host: str, page: str, out_dir: Path) -> tuple[str, str]:
    base = base_of(page)
    return first_ok(host, declared(base) + [urllib.parse.urljoin(base, '/favicon.ico')], out_dir)


def browser_icons(pages: dict[str, str]) -> dict[str, list[str]]:
    """首页拒绝脚本请求（403）的站：用 Playwright 打开一次（默认设置，不改 UA），读页面里声明的图标地址"""
    try:
        import asyncio
        from playwright.async_api import async_playwright
    except ImportError:
        return {}

    async def run() -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        async with async_playwright() as p:
            b = await p.chromium.launch()
            for host, page in pages.items():
                pg = await b.new_page()
                try:
                    await pg.goto(base_of(page), wait_until='domcontentloaded', timeout=20000)
                    hrefs = await pg.evaluate("[...document.querySelectorAll('link[rel*=icon]:not([rel*=mask])')].map(l => l.href)")
                    out[host] = [h for h in hrefs if h.startswith(('http://', 'https://'))]
                except Exception:
                    pass
                finally:
                    await pg.close()
            await b.close()
        return out
    try:
        return asyncio.run(run())
    except Exception as e:   # 装了 playwright 但没装浏览器、浏览器起不来：跳过这一步
        print(f'浏览器那一步跳过了：{type(e).__name__}')
        return {}


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    try:
        import PIL  # noqa: F401
    except ImportError:
        sys.exit('要先装 Pillow：pip install Pillow')
    d = Path(sys.argv[1]).expanduser().resolve()
    force = '--force' in sys.argv
    sources = {s['id']: s for s in json.loads((d / 'sources.json').read_text(encoding='utf-8'))} if (d / 'sources.json').exists() else {}
    guide = (d / 'guide.md').read_text(encoding='utf-8') if (d / 'guide.md').exists() else ''
    cited = {i.strip() for m in REF.findall(guide) for i in m.split(',')}
    urls = [sources[i]['url'] for i in cited if i in sources and sources[i].get('url')]
    if (d / 'sites.json').exists():
        urls += [s['url'] for s in json.loads((d / 'sites.json').read_text(encoding='utf-8')) if s.get('url')]
    hosts: dict[str, str] = {}
    for u in urls:
        if u.startswith('http'):
            hosts.setdefault(host_of(u), u)
    out_dir = d / 'img' / 'favicons'
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = {h: u for h, u in hosts.items() if h and (force or not any((out_dir / f'{h}.{e}').exists() for e in ('png', 'svg')))}
    with ThreadPoolExecutor(8) as ex:
        res = sorted(ex.map(lambda kv: fetch(kv[0], kv[1], out_dir), todo.items()))
    miss = {h for h, k in res if k == '没拿到'}
    if miss:   # 第二轮：真浏览器读声明的图标；第三轮：DuckDuckGo 的公开图标服务（只发域名）
        found = browser_icons({h: todo[h] for h in miss})
        for h in list(miss):
            if first_ok(h, found.get(h, []), out_dir)[1] != '没拿到' or first_ok(h, [f'https://icons.duckduckgo.com/ip3/{h}.ico'], out_dir)[1] != '没拿到':
                miss.discard(h)
    miss = sorted(miss)
    print(f'{len(hosts)} 个域名，这次下载 {len(res) - len(miss)} 个，已有 {len(hosts) - len(todo)} 个，没拿到 {len(miss)} 个')
    if miss:
        print('没拿到（页面上显示通用图标）：' + '、'.join(miss))


if __name__ == '__main__':
    main()
