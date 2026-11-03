#!/usr/bin/env python3
"""按 活动.json 出微信群推送海报：填模板 → 下载/裁好宣传图 → 760 宽按 3 倍截成 海报.png → 自检。

用法：python3 make_poster.py <活动.json> [输出目录，默认和 活动.json 同目录]

活动.json：
{
  "week": ["2026-11-02", "2026-11-08"],          刊头的日期范围
  "title": "本周活动推荐",
  "cities": ["北京", "上海"],                     可选：分区顺序；不给就北京在前，其余按场数
  "events": [{
    "id": "aie-sh-1105", "city": "上海",
    "date": "11/5–6", "when": "周四–五 09:30 起", "due": "",      due 非空时日期后面出红色标签（如「申报截止」）
    "name": "AI Engineer Shanghai 2026",                          名字里写 \n 手动换行
    "venue": "闵行 · 虹桥祥源希尔顿酒店", "venue_hl": "",          venue_hl：地址里要突出的那几个字（合作场地）
    "org": "AI Engineer，Arogo Intelligence 联合主办",
    "intro": "AI Engineer 大会首次来华……",                        票面三行以内
    "price": "¥1999",                                             空着就印「费用未写」
    "cover": "covers/18e8d65f7551.jpg",                           网站相对路径 / 网址 / 本地文件；空着用分类默认图
    "category": "大会峰会"                                        只在没有宣传图时用来挑默认图的颜色
  }]
}

产出：海报.html、海报.png、素材/、预览-1.png、预览-2.png（上下两半，缩小了方便看）。
自检会报：二维码扫不出网址、某行最后只剩一两个字（孤字）、介绍超过三行、价格太长、宣传图没下下来。
"""
import datetime as dt
import html
import json
import shutil
import sys
import urllib.request
from collections import Counter
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

BASE = "https://antonailog.com/more/ai-events/"
SKILL = Path(__file__).resolve().parents[1]
W = 760
# 城市色：沿用网站的 Notion 色板，北京橙、上海蓝、深圳绿；没列的城市用黄
CITY = {"北京": "#D9730D", "上海": "#2F7FB0", "深圳": "#448361", "杭州": "#9065B0", "广州": "#C14C8A", "线上": "#9F6B53"}
CITY_BG = {"#D9730D": "#FBEBDA", "#2F7FB0": "#E3F0F7", "#448361": "#E6F0E8", "#9065B0": "#F6F3F9", "#C14C8A": "#FAF1F5", "#9F6B53": "#F4EEEE", "#CB912F": "#FBF3DB"}
CAT_PH = {"大会峰会": "purple", "黑客松比赛": "orange", "路演对接": "brown", "共创工作坊": "green", "征集榜单": "yellow",
          "直播课程": "pink", "分享会沙龙": "blue", "其他": "gray"}
PIN = '<svg><use href="#pin"/></svg>'
ORG = '<svg><use href="#org"/></svg>'


def esc(s):
    return html.escape(s or "", quote=False)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ai-events-push"})
    return urllib.request.urlopen(req, timeout=60).read()


def city_vars(city):
    c = CITY.get(city, "#CB912F")
    r, g, b = (int(c[k:k + 2], 16) for k in (1, 3, 5))
    return f"--c:{c};--c-bg:{CITY_BG[c]};--c-line:rgba({r},{g},{b},.25)"


def fetch_cover(e, assets, warns):
    """宣传图放进 素材/：网站路径、网址下载，本地文件复制；太长的竖海报截顶上一块方图（整张缩进 16:9 只剩一条）"""
    src = (e.get("cover") or "").strip()
    name = e["id"] + ".jpg"
    dst = assets / name
    try:
        if not src:
            raise FileNotFoundError("没给宣传图")
        if src.startswith(("covers/", "img/")):
            dst.write_bytes(get(BASE + src))
        elif src.startswith("http"):
            dst.write_bytes(get(src))
        else:
            p = Path(src).expanduser()
            shutil.copy(p if p.is_absolute() else SPEC_DIR / p, dst)
        im = Image.open(dst).convert("RGB")
    except Exception as ex:
        color = CAT_PH.get(e.get("category", ""), "gray")
        ph = assets / f"ph-{color}.jpg"
        if not ph.exists():
            try:
                ph.write_bytes(get(f"{BASE}img/ph-{color}.jpg"))
            except Exception:   # 网站也连不上：本地画一张浅灰图顶上，不留作缓存，联网后重跑会换回分类默认图
                ph = assets / "ph-offline.jpg"
                Image.new("RGB", (640, 360), (236, 236, 236)).save(ph, "JPEG", quality=88)
                warns.append(f"{e['name'][:20]}：宣传图和分类默认图都没下下来，用了纯色图，联网后重跑")
                return ph.name, True
        if src:
            warns.append(f"{e['name'][:20]}：宣传图没拿到（{ex}），用了分类默认图")
        return ph.name, True
    if im.height > im.width * 1.5:
        im = im.crop((0, 0, im.width, im.width))
    im.save(dst, "JPEG", quality=88)
    return name, False


def ticket(e, assets, warns):
    img, ph = fetch_cover(e, assets, warns)
    stub = (f'<img class="cover-ph" src="素材/{img}">' if ph else
            f'<img class="cover-bg" src="素材/{img}"><img class="cover-fg" src="素材/{img}">')
    due = f'<span class="due">{esc(e["due"])}</span>' if e.get("due") else ""
    name = "<br>".join(esc(x) for x in e["name"].split("\n"))
    venue = esc(e.get("venue", ""))
    hl = e.get("venue_hl")
    if hl and esc(hl) in venue:
        venue = venue.replace(esc(hl), f'<b class="venue-hl">{esc(hl)}</b>', 1)
    price = (e.get("price") or "").strip()
    if len(price) > 6:
        warns.append(f"{e['name'][:20]}：价格「{price}」太长，副券竖排放不下，压到 6 个字以内")
    tail = f'<b class="price">{esc(price)}</b>' if price else '<b class="price dim">费用未写</b>'
    if not (e.get("intro") or "").strip():
        warns.append(f"{e['name'][:20]}：介绍是空的")
    org = f'<p class="meta">{ORG}<span>{esc(e["org"])}</span></p>' if e.get("org") else ""
    return f'''<article class="ticket" data-id="{esc(e["id"])}"><div class="tk">
      <div class="seg stub">{stub}</div>
      <div class="seg body">
        <p class="r1"><b>{esc(e["date"])}</b>{esc(e.get("when", ""))}{due}</p>
        <p class="name">{name}</p>
        <p class="meta">{PIN}<span>{venue}</span></p>
        {org}
        <p class="why">{esc(e.get("intro", ""))}</p>
      </div>
      <div class="seg tail">{tail}</div>
    </div></article>'''


def city_order(spec):
    n = Counter(e["city"] for e in spec["events"])
    if spec.get("cities"):
        return [c for c in spec["cities"] if c in n] + [c for c in n if c not in spec["cities"]]
    return sorted(n, key=lambda c: (c != "北京", c == "线上", -n[c], c))


def build(spec, out):
    assets = out / "素材"
    assets.mkdir(parents=True, exist_ok=True)
    for f in ("qrcode.min.js", "fonts/geist-latin-wght-normal.woff2"):
        shutil.copy(SKILL / "assets" / f, assets / Path(f).name)
    warns = []
    order = city_order(spec)
    n = Counter(e["city"] for e in spec["events"])
    sections = []
    for c in order:
        ts = "\n    ".join(ticket(e, assets, warns) for e in spec["events"] if e["city"] == c)
        sections.append(f'''<section class="city" style="{city_vars(c)}">
  <div class="city-h"><span class="city-name">{esc(c)}</span><span class="city-n">{n[c]} 场</span></div>
  <div class="tickets">
    {ts}
  </div>
</section>''')
    a, b = spec["week"]
    week = f"{a[5:7]}.{a[8:10]} — {b[5:7]}.{b[8:10]}"
    counts = "".join(f'<span style="{city_vars(c)}"><i>{esc(c)}</i> {n[c]} 场</span>' for c in order)
    tiles = "".join(f'<span class="tile">{d}</span>' for d in str(len(spec["events"])))
    title = esc(spec.get("title") or "本周活动推荐")
    hero = f'''<header class="hero">
  <div class="brand"><b>国内AI活动追踪</b><span>by 阿東</span></div>
  <div class="hero-row">
    <h1 class="title">{title}</h1>
    <div class="stat">{tiles}<small>场</small></div>
  </div>
  <p class="sub"><b>{week}</b>{counts}</p>
</header>'''
    tpl = (SKILL / "assets" / "poster.html").read_text(encoding="utf-8")
    page = tpl.replace("{{TITLE}}", title).replace("{{HERO}}", hero).replace("{{SECTIONS}}", "\n\n".join(sections))
    (out / "海报.html").write_text(page, encoding="utf-8")
    return warns


CHECK_JS = """() => {
  const out = [];
  for (const el of document.querySelectorAll('.name, .why')) {
    const r = document.createRange(); r.selectNodeContents(el);
    const rects = [...r.getClientRects()].filter((x) => x.width > 1);
    if (!rects.length) continue;
    const lines = [...new Set(rects.map((x) => Math.round(x.bottom)))].sort((a, b) => a - b);
    const last = rects.filter((x) => Math.abs(x.bottom - lines[lines.length - 1]) < 3);
    const lastW = Math.max(...last.map((x) => x.right)) - Math.min(...last.map((x) => x.left));
    const fs = parseFloat(getComputedStyle(el).fontSize);
    out.push({ id: el.closest('.ticket').dataset.id, kind: el.className, lines: lines.length, lastChars: Math.round(lastW / fs) });
  }
  return out;
}"""


def shoot(out, warns):
    png = out / "海报.png"
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": W, "height": 900}, device_scale_factor=3)
        page.goto((out / "海报.html").as_uri(), wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(400)
        for x in page.evaluate(CHECK_JS):
            nm = page.evaluate(f"() => document.querySelector('[data-id=\"{x['id']}\"] .name').textContent.slice(0, 20)")
            if x["lines"] > 1 and x["lastChars"] <= 2:
                warns.append(f"{nm}：{'名称' if x['kind'] == 'name' else '介绍'}最后一行只剩 {x['lastChars']} 个字，压短或改写一下")
            if x["kind"] == "why" and x["lines"] > 3:
                warns.append(f"{nm}：介绍有 {x['lines']} 行，压到三行以内")
        page.locator("#qr").screenshot(path=str(out / "_qr.png"))
        page.screenshot(path=str(png), full_page=True)
        b.close()
    try:
        import cv2
        q = Image.open(out / "_qr.png").convert("RGB")
        pad = Image.new("RGB", (q.width + 80, q.height + 80), "white")   # 二维码本身不留白边，扫码要四周留白
        pad.paste(q, (40, 40)); pad.save(out / "_qr.png")
        got = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(out / "_qr.png")))[0]
        if got != BASE:
            warns.append(f"二维码扫出来是「{got}」，不是 {BASE}")
    except ImportError:
        warns.append("没装 opencv，二维码没验，自己用手机扫一下")
    (out / "_qr.png").unlink(missing_ok=True)
    im = Image.open(png)
    w, h = im.size
    for k, box in enumerate(((0, 0, w, h // 2 + 60), (0, h // 2 - 60, w, h)), 1):
        part = im.crop(box)
        part.resize((part.width // 2, part.height // 2)).save(out / f"预览-{k}.png")
    return png, (w, h)


def check_spec(spec):
    """缺了必填字段就停，别出一张缺东西的图"""
    errs = []
    try:
        a, b = (dt.date.fromisoformat(x) for x in spec["week"])
        assert len(spec["week"]) == 2 and a <= b
    except Exception:
        errs.append("week 要写成 [\"周一\", \"周日\"] 两个日期，比如 [\"2026-11-09\", \"2026-11-15\"]")
    if not spec.get("events"):
        errs.append("events 是空的，至少要有一场")
    for k, e in enumerate(spec.get("events") or [], 1):
        miss = [f for f in ("id", "city", "date", "name") if not str(e.get(f) or "").strip()]
        if miss:
            errs.append(f"第 {k} 场（{str(e.get('name') or e.get('id') or '?')[:20]}）缺 {'、'.join(miss)}")
    if errs:
        sys.exit("活动.json 有问题：\n  - " + "\n  - ".join(errs))


def main():
    global SPEC_DIR
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    spec_path = Path(sys.argv[1]).resolve()
    SPEC_DIR = spec_path.parent
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else SPEC_DIR
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    check_spec(spec)
    warns = build(spec, out)
    png, (w, h) = shoot(out, warns)
    print(f"海报：{png}（{w}×{h}）")
    print(f"预览：{out / '预览-1.png'}、{out / '预览-2.png'}")
    print("自检：" + ("没有问题" if not warns else f"{len(warns)} 处要看"))
    for x in warns:
        print("  - " + x)


SPEC_DIR = Path.cwd()
if __name__ == "__main__":
    main()
