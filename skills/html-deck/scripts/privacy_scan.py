#!/usr/bin/env python3
"""扫一个目录或 zip 里的全部文件（不分后缀，二进制的列出来），找不该外发的东西：本机路径和用户名、邮箱、手机号、密钥、IP、你指定的词。

页面上看不到不等于文件里没有：嵌入页、数据文件、备注都会被打包。外发和公开前对「解压后的全部文件」跑一遍。
用法：python3 privacy_scan.py <目录或.zip> [--words 词1,词2] [--words-file 文件] [--ignore 文件]
  --words / --words-file：额外要找的词（真名、公司名、项目代号……），文件里一行一个
  --ignore：确认没问题、可以放行的原文片段，一行一个
发现就退出码 1。图片、视频和其他二进制文件扫不到，最后会列出来请人过目。
"""
import argparse
import getpass
import re
import sys
import zipfile
from pathlib import Path

MEDIA = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.webm', '.mov', '.pdf'}
PATTERNS = [
    ('本机路径', re.compile(r'(?<![\w.-])/Users/(?!Shared\b)[A-Za-z0-9._-]+|(?<![\w.-])/home/[A-Za-z0-9._-]+|(?:/private)?/var/folders/[^\s"\'<>]+|(?<![\w./])~/[^\s"\'<>]+|[A-Za-z]:\\\\?Users\\\\?[^\\\s"\'<>]+')),
    ('邮箱', re.compile(r'(?<![\w.@-])[\w.+-]+@(?!example\.)[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}(?![\w-])')),
    ('手机号', re.compile(r'(?<![\d+])(?:\+?86[ -]?)?1[3-9]\d(?:[ -]?\d{4}){2}(?!\d)')),
    ('密钥', re.compile(r'sk-[A-Za-z0-9_-]{20,}|ghp_\w{20,}|gho_\w{20,}|github_pat_\w{20,}|AKIA[0-9A-Z]{16}|AIza[\w-]{30,}|xox[baprs]-[\w-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----')),
    ('疑似密钥', re.compile(r'(?i)\b(?:api[_-]?key|secret|access[_-]?token|password|passwd)\b\s*["\']?\s*[:=]\s*["\'][^"\'\s]{8,}')),
    ('IP', re.compile(r'(?<![\w.])(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\w.])')),
]
FONTS = {'.woff2', '.woff', '.ttf', '.otf'}
IP_OK = {'127.0.0.1', '0.0.0.0', '255.255.255.255', '255.255.255.0'}


def files_of(target: Path):
    if target.suffix.lower() == '.zip':
        with zipfile.ZipFile(target) as z:
            for n in z.namelist():
                if not n.endswith('/'):
                    yield n, (lambda n=n: z.read(n))
    else:
        for f in sorted(target.rglob('*')):
            if f.is_file():
                yield str(f.relative_to(target)), f.read_bytes


def scan(target: Path, words=(), ignore=()):
    hits, media = [], []
    user = getpass.getuser()
    pats = list(PATTERNS)
    if len(user) >= 3:
        pats.append(('用户名', re.compile(r'(?<![A-Za-z0-9])' + re.escape(user) + r'(?![A-Za-z0-9])')))
    for w in words:
        if w.strip():
            pats.append(('指定的词', re.compile(re.escape(w.strip()))))
    for name, read in files_of(target):
        for label, pat in pats:   # 文件名本身也可能带真名、手机号
            if label != 'IP':
                hits.extend((name, label, m.group(0), '（文件名）') for m in pat.finditer(name))
        ext = Path(name).suffix.lower()
        if ext in FONTS:   # 字体是脚本下载的开源字体子集，不用人看
            continue
        if ext in MEDIA:
            media.append(name)
            continue
        data = read()
        if b'\0' in data[:8192]:   # 二进制（字体、压缩包……），扫不了
            media.append(name)
            continue
        text = data.decode('utf-8', 'replace')
        for label, pat in pats:
            for m in pat.finditer(text):
                s = m.group(0)
                if label == 'IP' and (s in IP_OK or re.search(r'(?:v|ver|版本|version)\s*[:=]?\s*$|[A-Za-z]/$', text[max(0, m.start() - 10):m.start()], re.I)):
                    continue   # 版本号、Chrome/129.0.0.0 这类不是 IP
                if label == '邮箱' and re.search(r'\.(png|jpe?g|gif|webp|svg|css|js)$', s, re.I):
                    continue   # logo@2x.png 这类文件名
                ctx = text[max(0, m.start() - 30):m.end() + 30].replace('\n', ' ')
                if any(i and (i in ctx or i == s) for i in ignore):
                    continue
                hits.append((name, label, s, ctx))
    return hits, media


def report(hits, media):
    if hits:
        uniq = {}
        for name, label, s, ctx in hits:
            uniq.setdefault((name, label, s), ctx)
        print(f'发现 {len(uniq)} 处可能不该外发的内容：')
        for (name, label, s), ctx in uniq.items():
            print(f'  [{label}] {name}：{s}　…{ctx}…')
        print('处理办法：删掉或换掉；确认没问题的，把原文片段写进 --ignore 文件放行')
    else:
        print('隐私扫描：文本内容里没发现本机路径、用户名、邮箱、手机号、密钥、IP 和指定的词')
    if media:
        print(f'另有 {len(media)} 个图片、视频或二进制文件扫不到内容，请自己过目一遍：' + '、'.join(media[:12]) + ('…' if len(media) > 12 else ''))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('target')
    ap.add_argument('--words', default='')
    ap.add_argument('--words-file')
    ap.add_argument('--ignore')
    a = ap.parse_args()
    words = [w for w in a.words.split(',') if w]
    if a.words_file:
        words += Path(a.words_file).read_text('utf-8').splitlines()
    ignore = Path(a.ignore).read_text('utf-8').splitlines() if a.ignore else []
    hits, media = scan(Path(a.target).expanduser().resolve(), words, ignore)
    report(hits, media)
    sys.exit(1 if hits else 0)


if __name__ == '__main__':
    main()
