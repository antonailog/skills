#!/usr/bin/env python3
"""按讲稿里实际用到的字，从 Google Fonts 下载开源字体的子集，生成本地 fonts.css（离线包和网站版用）。

字体都是 SIL OFL 开源字体。每份稿只多几百 KB，换到别的电脑显示一样。
下载走系统代理（HTTPS_PROXY 环境变量）；下过的文件缓存在 ~/.cache/html-deck/fonts/。
单独跑：python3 fontpack.py <讲稿目录> <输出 deck 目录>
"""
import hashlib
import html as htmllib
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# 每套风格用到的字体：(Google Fonts 名, 字重)。和 assets/engine/themes/*.css 里的字体栈对应
FAMILIES = {
    'swiss': [('Inter', '400;700;800;900'), ('Noto Sans SC', '400;700;800;900')],
    'editorial': [('Noto Serif SC', '400;700'), ('Noto Sans SC', '400;700;800')],
    'keynote': [('Inter', '400;700;800;900'), ('Noto Sans SC', '400;700;800;900')],
    'brutal': [('Space Grotesk', '500;700'), ('Noto Sans SC', '400;700;800;900')],
}
MONO = ('JetBrains Mono', '400')
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36'
CACHE = Path.home() / '.cache' / 'html-deck' / 'fonts'
CHUNK = 300


def theme_of(html: str) -> str:
    m = re.search(r'themes/([\w-]+)\.css', html)
    return m.group(1) if m and m.group(1) in FAMILIES else 'swiss'


def chars_of(html: str) -> str:
    body = re.sub(r'(?is)<script.*?</script>|<style.*?</style>|<!--.*?-->', ' ', html)
    attrs = ' '.join(re.findall(r'data-(?:labels|series|unit)="([^"]*)"', body))
    text = htmllib.unescape(re.sub(r'<[^>]+>', ' ', body)) + attrs
    ascii_ = ''.join(chr(c) for c in range(0x20, 0x7f))
    extra = '０１２３４５６７８９%—–·…「」『』，。、；：？！（）《》“”‘’●○→←'
    return ''.join(sorted(set(text + ascii_ + extra) - set('\n\r\t')))


def fetch(url: str) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / hashlib.sha1(url.encode()).hexdigest()
    if f.exists():
        return f.read_bytes()
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    f.write_bytes(data)
    return data


def subset(html: str, deck_out: Path) -> tuple[str, int]:
    """下载子集到 deck_out/fonts/，返回 (fonts.css 内容, 字体总字节数)。失败抛异常。"""
    fams = list(FAMILIES[theme_of(html)])
    if re.search(r'<pre|<code', html):
        fams.append(MONO)
    chars = chars_of(html)
    out = deck_out / 'fonts'
    out.mkdir(parents=True, exist_ok=True)
    css, total = ['/* 只含这份讲稿用到的字（Google Fonts 子集，SIL OFL）。由 scripts/fontpack.py 生成 */'], 0
    for fam, weights in fams:
        latin = fam in ('Inter', 'Space Grotesk', 'JetBrains Mono')
        cs = ''.join(c for c in chars if ord(c) < 0x2E00) if latin else chars   # 含弯引号、破折号、箭头，跟写稿时在线字体的显示一致
        for ci in range(0, len(cs), CHUNK):
            part = cs[ci:ci + CHUNK]
            url = 'https://fonts.googleapis.com/css2?family=' + urllib.parse.quote(fam) + f':wght@{weights}&text=' + urllib.parse.quote(part) + '&display=swap'
            sheet = fetch(url).decode('utf-8')
            ranges = ','.join(f'U+{ord(c):X}' for c in part)
            for block in re.findall(r'@font-face\s*{[^}]*}', sheet):
                w = re.search(r'font-weight:\s*(\d+)', block).group(1)
                src = re.search(r'url\(([^)]+)\)', block).group(1)
                name = f'{fam.lower().replace(" ", "-")}-{w}-{ci // CHUNK}.woff2'
                data = fetch(src)
                (out / name).write_bytes(data)
                total += len(data)
                css.append(f"@font-face {{ font-family: '{fam}'; font-weight: {w}; font-style: normal; font-display: swap; src: url('fonts/{name}') format('woff2'); unicode-range: {ranges}; }}")
    return '\n'.join(css) + '\n', total


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    deck, out = Path(sys.argv[1]), Path(sys.argv[2])
    c, n = subset((deck / 'index.html').read_text('utf-8'), out)
    (out / 'fonts.css').write_text(c, 'utf-8')
    print(f'字体子集 {n / 1024:.0f} KB → {out / "fonts"}')
