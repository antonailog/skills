"""收料清点：扫整个主题文件夹，把能转的材料转成文字，打印一张材料表。

为什么扫整个文件夹：材料常常不在原件目录里（11-11 有 4 份报告放在主题文件夹根目录，首版只用了 3 份）。
转换：.md/.txt 直接读；.docx 用 textutil；.pdf 用 pdftotext；.html 去标签。转出的文字放 <主题>/3-报告转写/。
不转的：图片、视频、音频（列出来，请用户给字幕或转写稿）。

用法：python3 -I inventory.py <主题文件夹>（名字以「学习指南」结尾的目录是产出，自动跳过；0-说明.md、1-prompt.md 不算材料，但第 2 步要读）
"""
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

TEXT = {'.md', '.txt', '.markdown'}
SKIP_DIRS = {'node_modules', 'site', 'dist', '.git', 'app', '3-报告转写'}
MEDIA = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.mov', '.mp3', '.m4a', '.wav'}
URL = re.compile(r'https?://[^\s)\]>"\']+')


def convert(f: Path, out: Path) -> str | None:
    """返回文字；转不出来返回 None"""
    ext = f.suffix.lower()
    if ext in TEXT:
        return f.read_text(encoding='utf-8', errors='replace')
    out.parent.mkdir(parents=True, exist_ok=True)
    if ext == '.docx' and shutil.which('textutil'):
        subprocess.run(['textutil', '-convert', 'txt', str(f), '-output', str(out)], capture_output=True)
    elif ext == '.pdf' and shutil.which('pdftotext'):
        subprocess.run(['pdftotext', '-layout', str(f), str(out)], capture_output=True)
    elif ext in {'.html', '.htm'}:
        raw = f.read_text(encoding='utf-8', errors='replace')
        raw = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', raw, flags=re.S | re.I)
        out.write_text(html.unescape(re.sub(r'<[^>]+>', ' ', raw)), encoding='utf-8')
    else:
        return None
    return out.read_text(encoding='utf-8', errors='replace') if out.exists() else None


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = Path(sys.argv[1]).expanduser().resolve()
    conv = root / '3-报告转写'
    rows, media, failed = [], [], []
    for f in sorted(root.rglob('*')):
        rel = f.relative_to(root)
        if not f.is_file() or any(p in SKIP_DIRS or p.endswith('学习指南') or p.startswith('.') for p in rel.parts[:-1]):
            continue
        if rel.name.startswith(('0-说明', '1-prompt', '.')) or rel.parts[0].endswith('学习指南'):
            continue
        ext = f.suffix.lower()
        if ext in MEDIA:
            media.append(str(rel))
            continue
        t = convert(f, conv / (f.stem + '.txt'))
        if t is None or len(t.strip()) < 50:
            failed.append(str(rel))
            continue
        chars = len(re.sub(r'\s', '', t))
        rows.append((str(rel), ext.lstrip('.'), chars, len(set(URL.findall(t))), len(re.findall(r'turn\d+[a-z]+\d+', t))))
    print(f'主题文件夹：{root}\n')
    print('| # | 文件 | 类型 | 字数 | 链接 | 引用标记（次） |\n|---|---|---|---|---|---|')
    for i, (rel, ext, chars, urls, cites) in enumerate(rows, 1):
        print(f'| {i} | {rel} | {ext} | {chars} | {urls} | {cites} |')
    if failed:
        print('\n转不出文字或不到 50 字（空白、乱码、扫描版 PDF：请用户换格式或给 Markdown 版）：\n' + '\n'.join(f'- {x}' for x in failed))
    if media:
        print('\n图片 / 音视频（不转，视频音频请用户给字幕或转写稿）：\n' + '\n'.join(f'- {x}' for x in media))
    print('\n「引用标记」是正文里出现的次数（同一来源会出现多次）；去重后有几个来源看 extract_cites.py 的输出。\n「引用标记」> 0 而「链接」= 0：来源链接导出时丢了（Deep Research 常见），第 3 步要找回。')


if __name__ == '__main__':
    main()
