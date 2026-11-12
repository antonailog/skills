"""逐个打开 sources.json（和 sites.json、videos.json）里的地址，分成「确定坏了 / 需要人工确认 / 正常」三类，写 _check.json。

- 确定坏了：HTTP 404、410、400；跳转后落到网站首页；页面标题是错误页（「Page not found」「页面不存在」）。
- 需要人工确认：401、403、429 这类（多半是网站拦脚本，不等于链接坏了）、5xx、连不上；跳到登录页、换了域名、
  跳到路径明显不同的页（原页面可能没了，被导到相近的页）。用网页工具或浏览器自己开一次，内容对得上正文就算正常。
- 正常：能打开，也没被导到别处。
请求用脚本自己的 UA，不伪装浏览器；被拦就记下来，不绕过人机验证。
装了 Playwright 时，状态码不对或连不上的，再用无头浏览器（它自带的 UA，不改）开一次：打开正常的归回「正常」，
  还是 404 或标题是错误页的归「确定坏了」，碰到验证页、还是 403 的照旧要人工确认（不点、不等它放行）。--no-browser 跳过这一步。
结果只给你和维护的人看（打不开的不挂到页面上），不上页面。走系统代理设置（HTTP_PROXY / HTTPS_PROXY 环境变量）。
默认只查 guide.md 里用到的来源、画廊网站和视频；加 --all 查三个表里的全部。
用法：python3 -I check_links.py <学习指南目录> [--all] [--no-browser]
"""
import asyncio
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UA = 'study-guide-link-check/1.0'
BROKEN, ASK, OK = '确定坏了', '需要人工确认', '正常'
# 人机验证页、登录墙上的字（小写）；collect_refs.py 里有同一份，两处一起改
BLOCKED = ['verify you are human', 'verifying you are human', 'confirm you are human', 'are you a robot', 'not a robot', 'security check',
           'checking your browser', 'verify that you are', 'unusual traffic', 'captcha', 'just a moment', 'access denied', 'enable javascript',
           'attention required', 'performing security verification', 'security service to protect against malicious bots',
           'performance and security by cloudflare', 'performance & security by cloudflare',
           'sign in to continue', 'log in to continue', '人机验证', '安全验证', '请完成验证', '访问被拒绝', '验证码', '登录后查看']
ERROR_TITLE = re.compile(r'\b404\b|not found|page (?:does not|doesn.t) exist|no longer (?:exists|available)'
                         r'|页面不存在|页面未找到|找不到(?:该|此|您要的)?页面|内容不存在|已被删除', re.I)
REDIRECTORS = {'doi.org', 'dx.doi.org', 'youtu.be', 't.co', 'bit.ly', 'b23.tv', 'aka.ms'}   # 本来就会跳到别的域名
LOGIN = re.compile(r'(^|/)(login|log-in|signin|sign-in|sign_in|auth|sso|passport)(/|$)', re.I)
LOCALE = re.compile(r'^[a-z]{2}([-_][a-z]{2,4})?$', re.I)   # en、zh-cn 这类语言段：/en/ 也算首页


def blocked(title: str | None, text: str = '') -> bool:
    t, x = (title or '').lower(), (text or '').lower()
    return any(k in t for k in BLOCKED) or (0 < len(x) < 3000 and any(k in x for k in BLOCKED))


def used(d: Path) -> set[str] | None:
    """guide.md 里用到的来源 id、画廊 key、视频名；没有 guide.md 返回 None（全查）"""
    g = d / 'guide.md'
    if '--all' in sys.argv or not g.exists():
        return None
    t = g.read_text(encoding='utf-8')
    ids = {x.strip() for grp in re.findall(r'\[\[([^\]]+)\]\]', t) for x in grp.split(',')}
    for block in re.findall(r'```gallery\n(.*?)```', t, re.S):   # 画廊行可以写成 `- key`，同 build_guide.py
        ids |= {re.sub(r'^[-*]\s+', '', x.strip()) for x in block.split('\n') if x.strip()}
    for line in re.findall(r'^\s*::video (.+)$', t, re.M):
        ids |= {x.strip() for x in line.split('|')}
    return ids


def urls(d: Path) -> dict[str, list[str]]:
    """地址 → 用到它的 id（来源 id、画廊 key、视频名）"""
    keep, got = used(d), {}
    for name, key in (('sources.json', 'id'), ('sites.json', 'key'), ('videos.json', 'name')):
        f = d / name
        if f.exists():
            for it in json.loads(f.read_text(encoding='utf-8')):
                if it.get('url') and (keep is None or it.get(key) in keep):
                    got.setdefault(it['url'], []).append(str(it.get(key)))
    return got


def clean(u: str) -> str:
    u = re.sub(r'\?X-Amz-.*$', '', u)   # 临时签名会过期，也会被当成密钥扫出来
    if '__cf_chl_' not in u:   # Cloudflare 验证页加在地址上的令牌
        return u
    p = urllib.parse.urlsplit(u)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not k.startswith('__cf_chl_')]
    return urllib.parse.urlunsplit(p._replace(query=urllib.parse.urlencode(q)))


def check(u: str) -> tuple[str, dict]:
    req = urllib.request.Request(u, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            head = r.read(200_000).decode('utf-8', 'ignore')
            m = re.search(r'<title[^>]*>(.*?)</title>', head, re.S | re.I)
            return u, {'code': r.status, 'final': clean(r.geturl()), 'title': re.sub(r'\s+', ' ', m.group(1)).strip() if m else None}
    except urllib.error.HTTPError as e:
        return u, {'code': e.code, 'final': clean(e.geturl() or u)}
    except Exception as e:   # 超时、连不上
        return u, {'code': None, 'error': type(e).__name__}


def segs(path: str) -> list[str]:
    p = re.sub(r'\.(html?|php|aspx?)$', '', urllib.parse.unquote(path).lower().rstrip('/')).replace('_', '-')
    s = [x for x in p.split('/') if x]
    return s[:-1] if s and s[-1] == 'index' else s


def site(host: str) -> str:
    parts = host.lower().removeprefix('www.').split('.')
    n = 3 if len(parts) > 2 and len(parts[-1]) == 2 and parts[-2] in ('com', 'co', 'org', 'net', 'gov', 'edu', 'ac') else 2
    return '.'.join(parts[-n:])


def moved(u: str, final: str | None) -> tuple[str, str] | None:
    """跳转后落到了哪：首页 → 确定坏了；登录页、别的域名、路径明显不同的页 → 需要人工确认"""
    a, b = urllib.parse.urlsplit(u), urllib.parse.urlsplit(final or u)
    if not a.hostname or not b.hostname or a.hostname.lower().removeprefix('www.') in REDIRECTORS:
        return None
    sa, sb = segs(a.path), segs(b.path)
    home = lambda s: all(LOCALE.match(x) for x in s)
    if (LOGIN.search(b.path) or re.match(r'(login|accounts?|auth|sso|passport|signin)\.', b.hostname)) and not LOGIN.search(a.path):
        return ASK, '跳到登录页'
    if not home(sa) and home(sb):
        return BROKEN, '跳到首页'
    if site(a.hostname) != site(b.hostname):
        return ASK, '换了域名'
    if sa and sb and not (sa[-1].startswith(sb[-1]) or sb[-1].startswith(sa[-1])):   # /articles/123 → /articles/123-标题 不算
        return ASK, '跳到路径不同的页'
    return None


def judge(u: str, r: dict, by: str = '') -> tuple[str, str]:
    """一次打开的结果 → (类别, 原因)；浏览器复查时 by 是「浏览器打开：」，加在原因前面"""
    code, title = r.get('code'), r.get('title')
    if code is None:
        return ASK, f'{by}连不上（{r.get("error")}）'
    if r.get('blocked') or (code >= 400 and blocked(title)):
        return ASK, f'{by}被拦（HTTP {code}{"，" + title if title else ""}）'
    if code in (400, 404, 410):
        return BROKEN, f'{by}HTTP {code}'
    if code >= 400:
        return ASK, f'{by}HTTP {code}' + ('（多半是网站拦脚本）' if code in (401, 403, 429) and not by else '')
    if title and ERROR_TITLE.search(title):
        return BROKEN, f'{by}标题是错误页'
    if blocked(title):
        return ASK, f'{by}人机验证页'
    m = moved(u, r.get('final'))
    return (m[0], by + m[1]) if m else (OK, '')


async def browse(us: list[str]) -> dict[str, dict]:
    """用无头浏览器再开一次（Playwright 自带的 UA）；看到验证页就停，不等它放行"""
    from playwright.async_api import async_playwright
    async def look(pg) -> tuple[str, str]:
        try:
            return await pg.title(), await pg.evaluate('document.body ? document.body.innerText : ""')
        except Exception:
            return '', ''
    async with async_playwright() as p:
        b = await p.chromium.launch()
        sem = asyncio.Semaphore(4)
        async def one(u: str) -> tuple[str, dict]:
            async with sem:
                pg = await b.new_page()
                try:
                    resp = await pg.goto(u, wait_until='domcontentloaded', timeout=30000)
                    title, text = await look(pg)
                    if not blocked(title, text):
                        try:
                            await pg.wait_for_load_state('load', timeout=10000)
                        except Exception:
                            pass
                        title, text = await look(pg)
                    return u, {'code': resp.status if resp else None, 'final': clean(pg.url), 'title': re.sub(r'\s+', ' ', title).strip() or None,
                               'blocked': blocked(title, text)}
                except Exception as e:
                    return u, {'code': None, 'error': type(e).__name__}
                finally:
                    await pg.close()
        res = dict(await asyncio.gather(*(one(u) for u in us)))
        await b.close()
    return res


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = Path(sys.argv[1]).expanduser().resolve()
    todo = urls(d)
    with ThreadPoolExecutor(8) as ex:
        res = dict(ex.map(check, todo))
    for u, r in res.items():
        r['verdict'], r['reason'] = judge(u, r)
    again = [u for u, r in res.items() if r.get('code') is None or r['code'] >= 400]   # 404 也复查：有的网站只对脚本回 404
    tried = False
    if again and '--no-browser' not in sys.argv:
        try:
            got = asyncio.run(browse(again))
            tried = True
        except Exception as e:   # 没装 Playwright 或浏览器
            got = {}
            print(f'浏览器复查没跑成（{type(e).__name__}），结果只按脚本请求分类；要复查先 pip install playwright && playwright install chromium')
        for u, br in got.items():
            res[u]['browser'] = br
            v, why = judge(u, br, '浏览器打开：')
            res[u]['verdict'], res[u]['reason'] = v, f'{res[u]["reason"]}；{why or "浏览器打开正常"}'
    (d / '_check.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')

    groups = {k: [u for u, r in res.items() if r['verdict'] == k] for k in (BROKEN, ASK, OK)}
    print(f'{len(res)} 个地址：{BROKEN} {len(groups[BROKEN])} · {ASK} {len(groups[ASK])} · {OK} {len(groups[OK])}'
          + (f'（其中 {len(again)} 个用浏览器复查过）' if tried else ''))
    def line(u: str) -> str:
        r = res[u]
        fin = r.get('browser', r).get('final')
        title = r.get('browser', r).get('title')
        return (f'  [{", ".join(todo[u])}] {r["reason"]}\n    {u}' + (f'\n    → {fin}' if fin and fin != u else '')
                + (f'（{title[:60]}）' if title and title not in r['reason'] else ''))
    hints = {BROKEN: '换链接或删掉引用', ASK: '用网页工具或浏览器自己开一次，内容对得上正文就算正常'}
    for k in (BROKEN, ASK):
        if groups[k]:
            print(f'\n{k}（{hints[k]}）：')
            print('\n'.join(line(u) for u in groups[k]))
    rescued = [u for u in groups[OK] if res[u].get('browser')]
    if rescued:
        print(f'\n{OK}里脚本被拦、浏览器打开正常的：')
        print('\n'.join(f'  [{", ".join(todo[u])}] {u}（{(res[u]["browser"].get("title") or "")[:60]}）' for u in rescued))


if __name__ == '__main__':
    main()
