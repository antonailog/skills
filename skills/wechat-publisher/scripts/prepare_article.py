#!/usr/bin/env python3
"""
prepare_article.py - 替换图片 URL 为 OSS URL，添加 width 属性和 frontmatter

用法:
    python3 prepare_article.py <md_file> <url_mapping_json> [output_path]

示例:
    python3 prepare_article.py ./article.md ./image_urls.json
    python3 prepare_article.py ./article.md ./image_urls.json ./article_发布版.md

输出:
    默认输出到 <原始文件名>_发布版.md
"""

import sys
import os
import re
import json
from urllib.parse import unquote


def extract_title(content):
    """从 Markdown 中提取标题（第一个 # 行）"""
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('# ') and not line.startswith('##'):
            return line[2:].strip()
    return '未命名文章'


def extract_first_image(content):
    """提取第一张图片的 URL 作为封面图"""
    match = re.search(r'!\[[^\]]*\]\(([^)]+)\)', content)
    return match.group(1) if match else ''


def replace_image_urls(content, url_mapping):
    """替换所有图片 URL 为 OSS URL"""
    for orig_url, oss_url in url_mapping.items():
        content = content.replace(orig_url, oss_url)
    return content


def is_portrait(path):
    """本地图片是竖图（高大于宽）时返回 True；读不出尺寸（或没装 Pillow）就当不是竖图。
    手机竖拍的照片像素是横着存的，方向记在 EXIF Orientation（5-8 要转 90 度），按转正后的宽高算"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
            if im.getexif().get(0x0112) in (5, 6, 7, 8):
                w, h = h, w
        return h > w
    except Exception:
        return False


def find_portrait_urls(content, md_dir, url_mapping):
    """找出正文里的竖图：返回它们的原地址，以及替换后的 OSS 地址"""
    found = set()
    for url in re.findall(r'!\[[^\]]*\]\(([^)\s]+)', content):
        if re.match(r'https?://', url):
            continue
        path = unquote(url)  # Markdown 里的路径可能是转义过的（空格写成 %20、中文写成 %E7…）
        local = path if os.path.isabs(path) else os.path.join(md_dir, path)
        if os.path.isfile(local) and is_portrait(local):
            found.add(url)
            if url in url_mapping:
                found.add(url_mapping[url])
    return found


def add_image_width(content, width=340, skip=()):
    """为图片添加 {width=N} 属性；skip 里的地址（竖图）不加，按正文宽度显示"""
    # 匹配 ![alt](url) 格式，确保后面没有已有的 {width=...}
    pattern = r'(!\[[^\]]*\]\(([^)\s]+)[^)]*\))(?!\s*\{width=)'

    def repl(m):
        if m.group(2) in skip:
            return m.group(1)
        return f'{m.group(1)}{{width={width}}}'

    return re.sub(pattern, repl, content)


def generate_frontmatter(title, cover):
    """生成 YAML frontmatter"""
    lines = [
        '---',
        f'title: "{title}"',
    ]
    if cover:
        lines.append(f'cover: "{cover}"')
    lines.append('---')
    lines.append('')
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 3:
        print('用法: python3 prepare_article.py <md_file> <url_mapping_json> [output_path]')
        sys.exit(1)

    md_path = sys.argv[1]
    mapping_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None

    if not os.path.isfile(md_path):
        print(f'错误: 文件不存在 {md_path}')
        sys.exit(1)

    if not os.path.isfile(mapping_path):
        print(f'错误: 映射文件不存在 {mapping_path}')
        sys.exit(1)

    # 读取原始 MD
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 读取 URL 映射
    with open(mapping_path, 'r', encoding='utf-8') as f:
        url_mapping = json.load(f)

    # 0. 替换地址之前，先按本地文件找出竖图
    portrait = find_portrait_urls(content, os.path.dirname(os.path.abspath(md_path)), url_mapping)

    # 1. 替换图片 URL
    print('🔗 替换图片 URL...')
    content = replace_image_urls(content, url_mapping)
    replaced_count = sum(1 for url in url_mapping.values() if url in content)
    print(f'  替换了 {len(url_mapping)} 个 URL')

    # 2. 添加 width 属性
    print('📐 添加图片 width 属性（竖图不加）...')
    content = add_image_width(content, skip=portrait)
    if portrait:
        print(f'  竖图 {len([u for u in portrait if not re.match(r"https?://", u)])} 张，不限宽度')

    # 3. 提取标题和封面
    title = extract_title(content)
    cover = extract_first_image(content)
    print(f'📝 标题: {title}')
    print(f'🖼️  封面: {cover[:60]}...' if cover else '🖼️  封面: 无')

    # 4. 如果原文已有 frontmatter，先去掉
    if content.startswith('---'):
        end_idx = content.index('---', 3)
        content = content[end_idx + 3:].lstrip('\n')

    # 5. 生成 frontmatter 并拼接
    frontmatter = generate_frontmatter(title, cover)
    final_content = frontmatter + content

    # 6. 输出
    if not output_path:
        base, ext = os.path.splitext(md_path)
        output_path = f'{base}_发布版{ext}'

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f'\n✅ 发布版已保存到: {output_path}')


if __name__ == '__main__':
    main()
