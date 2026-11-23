#!/usr/bin/env python3
"""把一份讨论规格（JSON）生成一个能点选的讨论页：页顶列要定几件事和推荐，选项并排（可放真实渲染图），
点选加备注，「复制我的决定」后按钮显示「已复制」。图片内嵌进页面，一个文件就能发给人看。

用法：python3 discussion.py <spec.json> -o <讨论页.html>

spec.json：
{
  "title": "第二轮：要你定的 3 件事",
  "lead": "一段说明（可含 HTML）",
  "questions": [
    {"page": "第 5 页", "title": "图表用哪种", "context": "用户批注原文（可空）", "desc": "说明（可含 HTML）",
     "multi": false, "wide": false, "fill": "可选：让用户直接改的一段文字",
     "options": [{"label": "柱状图", "desc": "为什么", "rec": true, "images": ["截图路径.png"], "html": "可选"}]}
  ]
}
图片路径相对 spec.json 所在目录。
"""
import argparse
import base64
import io
import json
import mimetypes
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent


def inline(path: Path) -> str:
    try:
        from PIL import Image
        im = Image.open(path).convert('RGB')
        if im.width > 1600:
            im = im.resize((1600, round(im.height * 1600 / im.width)))
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=84)
        return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        mt = mimetypes.guess_type(str(path))[0] or 'image/png'
        return f'data:{mt};base64,' + base64.b64encode(path.read_bytes()).decode()


def build(spec: dict, base: Path) -> str:
    for q in spec.get('questions', []):
        for o in q.get('options') or []:
            o['images'] = [inline((base / s).resolve()) for s in o.get('images', [])]
    tpl = (SKILL / 'assets' / 'discussion.html').read_text('utf-8')
    data = json.dumps(spec, ensure_ascii=False).replace('</', '<\\/')
    return tpl.replace('/*SPEC*/null', data, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('spec')
    ap.add_argument('-o', '--out', required=True)
    a = ap.parse_args()
    sp = Path(a.spec).expanduser().resolve()
    html = build(json.loads(sp.read_text('utf-8')), sp.parent)
    out = Path(a.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, 'utf-8')
    print(f'讨论页：{out.resolve()}（{len(html) // 1024} KB）')


if __name__ == '__main__':
    main()
