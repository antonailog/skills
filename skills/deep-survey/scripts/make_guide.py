#!/usr/bin/env python3
"""生成报告开头「一分钟看懂」里的导引图（SVG）：一眼看清报告有哪些模块、每个模块的关键内容。

用法：
  python3 make_guide.py <guide.json> --theme <主题名> [--out <guide.svg>]

guide.json：
  {
    "title": "AI 陪伴赛道 · 全文导引",          # 可选，图顶部的小标题
    "sections": [
      {"no": "一", "title": "它是什么", "point": "卖的是关系，不是答案",
       "keywords": ["五个零件", "三种形态", "十年时间线"]},
      ...
    ]
  }
- 每个模块：编号 + 短标题（≤8 字）+ 一句核心判断（可选，≤16 字）+ 3—5 个关键词（每个 ≤10 字）。
- 模块数 6—10 个，每行 4 个；颜色与字体取自 assets/chart-themes.json，与同一份报告的图表用同一套主题。
- 输出 SVG（文字保持可选中、放大不糊）；文字用系统字体渲染，macOS 下的 Typora、VS Code、Obsidian 都能正常显示。
"""
import json
import sys
from html import escape
from pathlib import Path

THEMES_PATH = Path(__file__).resolve().parent.parent / "assets" / "chart-themes.json"
CSS_FALLBACK = {"sans": "'PingFang SC','Hiragino Sans GB',sans-serif", "serif": "'Songti SC',serif",
                "mono": "Menlo,monospace"}


def font_stack(fonts, kind):
    return ",".join(f"'{f}'" for f in fonts) + "," + CSS_FALLBACK[kind]


def text_w(s, size):
    """粗估文字宽度（像素）：中文 1 字宽，英文数字约 0.58 字宽。"""
    w = 0.0
    for ch in s:
        w += 1.0 if ord(ch) > 0x2E80 else 0.58
    return w * size


def wrap(s, size, max_w):
    lines, cur = [], ""
    for ch in s:
        if text_w(cur + ch, size) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def main():
    a = sys.argv[1:]
    if not a or "--theme" not in a:
        print(__doc__)
        return 2
    spec = json.loads(Path(a[0]).read_text(encoding="utf-8"))
    data = json.loads(THEMES_PATH.read_text(encoding="utf-8"))
    name = a[a.index("--theme") + 1]
    if name not in data["themes"]:
        print(f"未知主题「{name}」，可选：{'、'.join(data['themes'])}")
        return 1
    t = data["themes"][name]
    fam = data["families"][t["family"]]
    out = Path(a[a.index("--out") + 1]) if "--out" in a else Path(a[0]).with_suffix(".svg")

    secs = spec["sections"]
    if not 4 <= len(secs) <= 12:
        print("模块数应为 4—12 个")
        return 1
    serif = t["family"] == "magazine"
    f_title = font_stack(fam["font_title"], "serif" if serif else "sans")
    f_body = font_stack(fam["font_body"], "sans")
    f_num = font_stack(fam.get("font_kpi", fam["font_num"]), "serif" if serif else "sans")
    accent = t["hi"]
    # 高亮色太浅（柠檬黄、柠檬绿）时，线条与编号用墨色
    def lum(h):
        h = h.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    la, lb = sorted((lum(accent), lum(t["paper"])), reverse=True)
    mark = accent if (la + 0.05) / (lb + 0.05) >= 3 else t["ink"]

    W, pad, gap, cols = 1200, 36, 18, 4
    card_w = (W - 2 * pad - (cols - 1) * gap) / cols
    inner = card_w - 32
    # 先排版每张卡，求每行高度
    cards = []
    for s in secs:
        title_lines = wrap(s["title"], 19, inner)
        point_lines = wrap(s.get("point", ""), 13.5, inner) if s.get("point") else []
        kw = s.get("keywords", [])[:5]
        h = 20 + 34 + len(title_lines) * 26 + (len(point_lines) * 20 + 8 if point_lines else 0) + 10 + len(kw) * 25 + 16
        cards.append((s, title_lines, point_lines, kw, h))
    rows = [cards[i:i + cols] for i in range(0, len(cards), cols)]
    row_h = [max(c[4] for c in r) for r in rows]
    head = 64 if spec.get("title") else 24
    H = head + sum(row_h) + gap * (len(rows) - 1) + pad

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{int(H)}" viewBox="0 0 {W} {int(H)}">',
         f'<rect width="{W}" height="{int(H)}" fill="{t["paper"]}"/>']
    if spec.get("title"):
        if fam.get("top_rule"):
            o.append(f'<rect x="{pad}" y="14" width="{W - 2 * pad}" height="4" fill="{t["ink"]}"/>')
        o.append(f'<text x="{pad}" y="48" font-family="{escape(f_title)}" font-size="20" '
                 f'font-weight="{"300" if fam["title_weight"] == "light" else "700"}" fill="{t["ink"]}">'
                 f'{escape(spec["title"])}</text>')
    y = head
    for r, rh in zip(rows, row_h):
        for ci, (s, tl, pl, kw, _) in enumerate(r):
            x = pad + ci * (card_w + gap)
            if fam["kpi_style"] == "card":
                o.append(f'<rect x="{x:.1f}" y="{y}" width="{card_w:.1f}" height="{rh}" rx="10" fill="{t["card"]}"/>')
            else:
                o.append(f'<rect x="{x:.1f}" y="{y}" width="{card_w:.1f}" height="{rh}" fill="{t["card"]}" fill-opacity="0.55"/>')
            o.append(f'<rect x="{x:.1f}" y="{y}" width="{card_w:.1f}" height="3" fill="{mark}"/>')
            cx, cy = x + 16, y + 20
            o.append(f'<text x="{cx:.1f}" y="{cy + 26}" font-family="{escape(f_num)}" font-size="30" '
                     f'fill="{mark}" font-weight="{"300" if t["family"] == "swiss" else "400"}">{escape(s["no"])}</text>')
            cy += 34
            for line in tl:
                cy += 26
                o.append(f'<text x="{cx:.1f}" y="{cy}" font-family="{escape(f_title)}" font-size="19" '
                         f'font-weight="700" fill="{t["ink"]}">{escape(line)}</text>')
            if pl:
                cy += 6
                for line in pl:
                    cy += 20
                    o.append(f'<text x="{cx:.1f}" y="{cy}" font-family="{escape(f_body)}" font-size="13.5" '
                             f'fill="{t["ink2"]}">{escape(line)}</text>')
                cy += 2
            cy += 10
            o.append(f'<line x1="{cx:.1f}" y1="{cy}" x2="{x + card_w - 16:.1f}" y2="{cy}" stroke="{t["grid"]}" stroke-width="1"/>')
            for k in kw:
                cy += 25
                o.append(f'<rect x="{cx:.1f}" y="{cy - 9}" width="6" height="6" fill="{mark}"/>')
                o.append(f'<text x="{cx + 14:.1f}" y="{cy}" font-family="{escape(f_body)}" font-size="14.5" '
                         f'fill="{t["ink"]}">{escape(k)}</text>')
        y += rh + gap
    o.append("</svg>")
    out.write_text("\n".join(o), encoding="utf-8")
    print(f"ok  {out}（{len(secs)} 个模块，主题 {name}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
