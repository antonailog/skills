#!/usr/bin/env python3
"""把文章里单独一行的占位换成真的图和视频，生成能在编辑器里预览的成稿。

- [图N]：换成 图/ 目录下以「图N-」开头的图片。
- [视频N]：换成 图/ 目录下以「视频N-」开头的视频，封面用「视频N-封面」那张图（有的话）。
- [公众号二维码]：换成第四个参数给的二维码图片，一般是写作档案里的 素材/公众号二维码.jpg。

用法：python3 embed_images.py <文章.md> <图目录> <输出.md> [二维码图片] [--no-title]

--no-title：不给第一行加「# 」。即刻、X 这类没有标题行的短帖用它。
"""
import os
import re
import sys
from pathlib import Path

VIDEO = {".mp4", ".mov", ".webm", ".m4v"}


def main():
    args = [a for a in sys.argv[1:] if a != "--no-title"]
    no_title = "--no-title" in sys.argv[1:]
    src, img_dir, dst = Path(args[0]), Path(args[1]), Path(args[2])
    QR = Path(args[3]).resolve() if len(args) > 3 else None
    files = sorted(img_dir.iterdir()) if img_dir.exists() else []
    rel = lambda p: Path(os.path.relpath(p, dst.parent)).as_posix()
    text = src.read_text().strip()
    missing = []

    def find(prefix, want_video=None, poster=False):
        for p in files:
            if not p.name.startswith(prefix + "-"):
                continue
            is_video = p.suffix.lower() in VIDEO
            if poster and "封面" in p.stem and not is_video:
                return p
            if not poster and (want_video is None or is_video == want_video):
                return p
        return None

    def image(m):
        p = find("图" + m.group(1))
        if not p:
            missing.append("图" + m.group(1))
            return m.group(0)
        return f"![图{m.group(1)}]({rel(p)})"

    def video(m):
        key = "视频" + m.group(1)
        p = find(key, want_video=True)
        if not p:
            missing.append(key)
            return m.group(0)
        cover = find(key, poster=True)
        poster = f' poster="{rel(cover)}"' if cover else ""
        return f'<video src="{rel(p)}"{poster} controls width="100%"></video>'

    def qr(_):
        if QR is None or not QR.exists():
            missing.append("公众号二维码")
            return "[公众号二维码]"
        return f"![公众号二维码]({rel(QR)})"

    text = re.sub(r"^\[图(\d+)\]$", image, text, flags=re.M)
    text = re.sub(r"^\[视频(\d+)\]$", video, text, flags=re.M)
    text = re.sub(r"^\[公众号二维码\]$", qr, text, flags=re.M)
    lines = text.split("\n")
    if lines and not no_title and not lines[0].startswith("#"):
        lines[0] = "# " + lines[0]
    dst.write_text("\n".join(lines) + "\n")
    if missing:
        print("没找到的：", "、".join(missing))


if __name__ == "__main__":
    main()
