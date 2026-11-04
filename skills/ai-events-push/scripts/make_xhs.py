#!/usr/bin/env python3
"""按 小红书.json 出一组活动推荐图：封面 + 按日期分页，768×1024 按 2 倍截图 → 自检。

用法：python3 -I make_xhs.py <小红书.json> [输出目录，默认和 JSON 同目录]

小红书.json：
{
  "range": ["2026-11-04", "2026-11-10"],       封面大字的日期范围
  "title": "AI 活动推荐", "sign": "by 阿東",
  "per_page": 4,                              可省略：一页最多几张，超过就平均分（6 → 3+3）
  "cities": ["北京", "上海", "线上"],           可省略：北京在前，其余按场数，线上最后
  "cover_ids": ["aie-sh-1105"],                封面叠放 1–5 张，引用 events 里的 id
  "events": [{
    "id": "aie-sh-1105", "day": "2026-11-05", "form": "线下", "city": "上海",
    "date": "11/5–6", "time": "09:30 起", "due": "",   day 决定排在哪天，date 是票上的跨天日期
    "name": "AI Engineer Shanghai 2026",              名称里写 \\n 手动换行
    "venue": "闵行 · 虹桥祥源希尔顿酒店", "org": "AI Engineer × Arogo Intelligence",
    "intro": "AI Engineer 大会首次来华……", "price": "¥1999",
    "cover": "原图/aie-sh-1105.jpg",                   相对 JSON 的本地文件 / 网站 covers/ 路径 / 网址
    "category": "大会峰会"                             可省略：没拿到宣传图时挑分类默认图
  }]
}

产出：01-封面.png、02-11月4日-1.png …、小红书.html、素材/、总览.png。
图上不放网址和二维码。自检会报 id：票面溢出、孤字、介绍超三行或空着、价格超 6 字、默认图、
宣传图里的二维码、尺寸不对、封面引用不对、总图数超 18。没有问题退出 0，有问题照样出图、退出 1。
"""
import datetime as dt
import html
import importlib.util
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

from PIL import Image
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout, sync_playwright

SKILL = Path(__file__).resolve().parents[1]
W, H, SCALE = 768, 1024, 2
# -I 不把脚本目录放进 sys.path，按文件加载同目录的老脚本，复用下载、裁图、默认图和城市排序。
sys.dont_write_bytecode = True
_module = importlib.util.spec_from_file_location("make_poster", SKILL / "scripts" / "make_poster.py")
poster = importlib.util.module_from_spec(_module)
_module.loader.exec_module(poster)
esc = poster.esc
CITY = dict(poster.CITY, 线上="#7B5BC4")   # 小红书样图里线上用紫色
URL = re.compile(r"(?:https?://|www\.)[^\s<>\"'，。；！？）]+|"
                 r"(?<![\w@])(?:[a-z0-9-]+\.)+(?:com|cn|net|org|io|ai|app|dev|co|me|xyz|top|site)"
                 r"\b(?:/[^\s<>\"'，。；！？）]*)?", re.I)


def check_spec(spec):
    """不能排的字段先报清楚；封面引用、票面和素材问题留到自检，图照样出。"""
    errs = []
    if not isinstance(spec, dict):
        raise ValueError("JSON 最外层要是对象")
    try:
        dates = spec["range"]
        assert isinstance(dates, list) and len(dates) == 2
        a, b = (dt.date.fromisoformat(x) for x in dates)
        assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", x) for x in dates) and a <= b
    except (KeyError, TypeError, ValueError, AssertionError):
        errs.append('range 要写成两个先后有序的日期，比如 ["2026-11-04", "2026-11-10"]')
    for key in ("title", "sign"):
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            errs.append(f"{key} 要写非空文字")
    cap = spec.get("per_page", 4)
    if type(cap) is not int or cap < 1:
        errs.append("per_page 要是大于 0 的整数")
    if not isinstance(spec.get("cover_ids"), list) or any(not isinstance(x, str) for x in spec.get("cover_ids", [])):
        errs.append("cover_ids 要是 id 列表")
    if "cities" in spec and (not isinstance(spec["cities"], list) or any(not isinstance(c, str) for c in spec["cities"])):
        errs.append("cities 要是城市名称列表")
    events = spec.get("events")
    if not isinstance(events, list) or not events:
        errs.append("events 是空的，至少要有一场")
        events = []
    seen = set()
    for k, e in enumerate(events, 1):
        if not isinstance(e, dict):
            errs.append(f"第 {k} 场要是对象")
            continue
        label = str(e.get("id") or f"第 {k} 场")
        for key in ("id", "day", "form", "city", "date", "name"):
            if not isinstance(e.get(key), str) or not e[key].strip():
                errs.append(f"[{label}] 缺 {key}，要写非空文字")
        for key in ("time", "due", "venue", "org", "intro", "price", "cover", "category"):
            if e.get(key) is not None and not isinstance(e[key], str):
                errs.append(f"[{label}] {key} 要写文字")
        eid = e.get("id")
        if isinstance(eid, str):
            if not re.fullmatch(r"[\w.-]+", eid) or eid in (".", ".."):
                errs.append(f"[{label}] id 只能用文字、数字、下划线、点和短横线")
            if eid in seen:
                errs.append(f"[{label}] id 重复了")
            seen.add(eid)
        try:
            dt.date.fromisoformat(e["day"])
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["day"])
        except (KeyError, TypeError, ValueError, AssertionError):
            errs.append(f"[{label}] day 要写成 YYYY-MM-DD")
        if e.get("form") not in ("线上", "线下"):
            errs.append(f"[{label}] form 只能写线上或线下")
    if errs:
        raise ValueError("\n  - " + "\n  - ".join(errs))


def clean_text(value, label, warns):
    """输入里误带的网址不印在图上，报出来让作者补一句合适的文字。"""
    value = value or ""
    clean, n = URL.subn("", value)
    if n:
        warns.append(f"{label}：含网址，已从图上去掉，请改写这一处")
    return clean.strip()


def prepare(spec, spec_dir, assets, warns):
    spec = dict(spec)
    for key in ("title", "sign"):
        spec[key] = clean_text(spec[key], f"[封面] {key}", warns)
    spec["events"] = [dict(e) for e in spec["events"]]
    for e in spec["events"]:
        for key in ("city", "date", "time", "due", "name", "venue", "org", "intro", "price"):
            e[key] = clean_text(e.get(key), f"[{e['id']}] {key}", warns)
        if not e["intro"]:
            warns.append(f"[{e['id']}] 介绍是空的")
        if len(e["price"]) > 6:
            warns.append(f"[{e['id']}] 价格「{e['price']}」超过 6 个字，副券竖排放不下")
        source = dict(e)
        src = (e.get("cover") or "").strip()
        if src and not src.startswith(("covers/", "img/", "http://", "https://")):
            source["cover"] = str((spec_dir / Path(src).expanduser()).resolve())
        notes = []
        filename, fallback = poster.fetch_cover(source, assets, notes)
        e["_image"] = filename
        if fallback:
            warns.append(f"[{e['id']}] 宣传图没拿到，用了默认图" + (f"（{'；'.join(notes)}）" if notes else "（没给宣传图）"))
    if "cities" in spec:
        spec["cities"] = [clean_text(c, "[封面] cities", warns) for c in spec["cities"]]
    else:
        spec["cities"] = poster.city_order({"events": [dict(e, city="线上" if e["form"] == "线上" else e["city"]) for e in spec["events"]]})
    return spec


def check_qr(events, assets, warns):
    """扫处理后的图：长海报底部被裁掉的二维码不算，票根里还留着的要报。"""
    try:
        import cv2
    except ImportError:
        warns.extend(f"[{e['id']}] 二维码没扫（没装 opencv）" for e in events)
        return
    detector = cv2.QRCodeDetector()
    for e in events:
        im = cv2.imread(str(assets / e["_image"]))
        if im is None:
            warns.append(f"[{e['id']}] 宣传图读不出来，二维码没扫")
            continue
        try:
            found, _ = detector.detectMulti(im)
            if not found:
                found, _ = detector.detect(im)
            if found:
                warns.append(f"[{e['id']}] 处理后的票根宣传图里扫到二维码，请换一张或裁掉")
        except cv2.error as ex:
            warns.append(f"[{e['id']}] 二维码没扫（opencv 检测失败：{str(ex).splitlines()[0]}）")


def color(e):
    return CITY.get("线上" if e["form"] == "线上" else e["city"], "#CB912F")


def ticket(e, show_date=False):
    """封面和活动页用同一张票；活动页只有跨天的才在时间前写日期。"""
    src = "素材/" + quote(e["_image"])
    tag = ('<span class="tag on">线上</span>' if e["form"] == "线上" else
           f'<span class="tag">线下<i></i>{esc(e["city"])}</span>')
    due = f'<span class="due">{esc(e["due"])}</span>' if e["due"] else ""
    name = "<br>".join(esc(x) for x in e["name"].split("\n"))
    cross_day = bool(re.search(r"[–—~～至]|\d\s*-\s*\d", e["date"]))
    when = f'{e["date"]} {e["time"]}' if show_date or cross_day else e["time"]
    tail = f'<b class="price">{esc(e["price"])}</b>' if e["price"] else '<b class="price dim">费用未写</b>'
    return f'''<article class="ticket" style="--c:{color(e)}" data-id="{html.escape(e['id'], quote=True)}"><div class="tk">
  <div class="seg stub"><img class="bg" src="{src}"><img class="fg" src="{src}"></div>
  <div class="seg body">
    <p class="r1">{tag}<b>{esc(when)}</b>{due}</p>
    <p class="name">{name}</p>
    <p class="meta">{poster.PIN}<span>{esc(e["venue"])}</span></p>
    <p class="meta">{poster.ORG}<span>{esc(e["org"])}</span></p>
    <p class="why">{esc(e["intro"])}</p>
  </div>
  <div class="seg tail">{tail}</div>
</div></article>'''


def paginate(events, cap):
    """一天单独占页，余数放前几页；每页相差最多一张，同一天保持 JSON 顺序。"""
    days = defaultdict(list)
    for e in events:
        days[e["day"]].append(e)
    pages = []
    for day, evs in sorted(days.items()):
        n = -(-len(evs) // cap)
        size, extra = divmod(len(evs), n)
        start = 0
        for k in range(n):
            stop = start + size + (k < extra)
            pages.append((day, k + 1, n, evs[start:stop]))
            start = stop
    return pages


def cover(spec, warns):
    ids = spec["cover_ids"]
    if not 1 <= len(ids) <= 5:
        warns.append(f"[封面：{', '.join(ids) or '无 id'}] cover_ids 有 {len(ids)} 张票，要在 1–5 张之间")
    byid = {e["id"]: e for e in spec["events"]}
    for eid in ids:
        if eid not in byid:
            warns.append(f"[{eid}] cover_ids 引用的 id 不在 events 里，封面跳过这张")
    items = [byid[eid] for eid in ids if eid in byid][:5]
    rot, left = [-5, 3, -2.5, 4, -1.5], [-6, 18, -2, 22, 4]
    # 五张时就是样图的 128px；少于五张把首尾位置保留，均匀散开；单张居中。
    tops = [k * 512 / (len(items) - 1) for k in range(len(items))] if len(items) > 1 else [256]
    ts = "".join(f'<div class="fi" style="--rot:{rot[k]}deg;left:{left[k]}px;top:{tops[k]:g}px;z-index:{k + 1}">{ticket(e, True)}</div>'
                 for k, e in enumerate(items))
    cities = "".join(f'<span style="--c:{CITY.get(c, "#CB912F")}"><i></i>{esc(c)}</span>' for c in spec["cities"])
    a, b = (dt.date.fromisoformat(x).strftime("%m.%d") for x in spec["range"])
    return f'''<p class="csign">{esc(spec["sign"])}</p>
  <h1><span class="t1">{a}<em>—</em>{b}</span><span class="t2">{esc(spec["title"])}</span></h1>
  <p class="cities">{cities}</p>
  <div class="fan">{ts}</div>'''


def build(spec, out, warns):
    pages = [("封面", "cover", cover(spec, warns))]
    for day, k, n, events in paginate(spec["events"], spec.get("per_page", 4)):
        d = dt.date.fromisoformat(day)
        label = f"{d.month}月{d.day}日" + (f"-{k}" if n > 1 else "")
        ts = "\n".join(ticket(e) for e in events)
        body = f'''<section class="sec"><h2 class="sh"><span class="md">{d.month}/{d.day}</span><span class="wd">周{'一二三四五六日'[d.weekday()]}</span><i></i><span class="sign">{esc(spec['sign'])}</span></h2>
  <div class="tickets">{ts}</div></section>'''
        pages.append((label, "flow", body))
    if len(pages) > 18:
        warns.append(f"[整组] 总图数 {len(pages)} 张，超过小红书上限 18 张")
    filenames = [f"{k:02d}-{label}.png" for k, (label, _, _) in enumerate(pages, 1)]
    sections = [f'<section class="page {kind}" data-key="{label}">{body}</section>' for label, kind, body in pages]
    tpl = (SKILL / "assets" / "xhs.html").read_text(encoding="utf-8")
    values = {"TITLE": esc(spec["title"]), "PAGES": "\n\n".join(sections)}
    doc = re.sub(r"\{\{(TITLE|PAGES)\}\}", lambda m: values[m[1]], tpl)
    (out / "小红书.html").write_text(doc, encoding="utf-8")
    return filenames


CHECK_JS = """() => {
  const out = [];
  // 旋转会把同一行的 rect 弄成不同高度；量字时暂时还原，截图前恢复。
  const fans = [...document.querySelectorAll('.fi')].map(el => [el, el.style.transform]);
  for (const [el] of fans) el.style.transform = 'none';
  const label = el => `[${el.closest('[data-id]').dataset.id}]（${el.closest('.page').dataset.key}）`;
  try {
    for (const el of document.querySelectorAll('.name, .why')) {
      const r = document.createRange(); r.selectNodeContents(el);
      const rects = [...r.getClientRects()].filter(x => x.width > 1);
      if (!rects.length) continue;
      const lines = [...new Set(rects.map(x => Math.round(x.bottom)))].sort((a, b) => a - b);
      const last = rects.filter(x => Math.abs(x.bottom - lines[lines.length - 1]) < 3);
      const lastW = Math.max(...last.map(x => x.right)) - Math.min(...last.map(x => x.left));
      const chars = Math.round(lastW / parseFloat(getComputedStyle(el).fontSize));
      if (lines.length > 1 && chars <= 2)
        out.push(`${label(el)}${el.className === 'name' ? '名称' : '介绍'}最后一行只剩约 ${chars} 个字（孤字）`);
      if (el.className === 'why' && lines.length > 3)
        out.push(`${label(el)}介绍有 ${lines.length} 行，超过三行`);
    }
    for (const el of document.querySelectorAll('.ticket .body')) {
      if (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1)
        out.push(`${label(el)}票面正文放不下：高多 ${Math.max(0, el.scrollHeight - el.clientHeight)}px，宽多 ${Math.max(0, el.scrollWidth - el.clientWidth)}px`);
    }
    for (const el of document.querySelectorAll('.flow .ticket')) {
      const page = el.closest('.page');
      if (el.getBoundingClientRect().bottom > page.getBoundingClientRect().bottom - 26)
        out.push(`${label(el)}门票超出页面，请调小 per_page`);
    }
  } finally {
    for (const [el, transform] of fans) el.style.transform = transform;
  }
  return out;
}"""


def shoot(out, filenames, warns):
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = b.new_page(viewport={"width": 800, "height": 1100}, device_scale_factor=SCALE)
            try:
                page.goto((out / "小红书.html").as_uri(), wait_until="networkidle", timeout=20000)
            except PlaywrightTimeout:
                page.evaluate("window.stop()")   # CDN 不通就用系统字体，不为等字体卡住出图
            ready = page.evaluate("""() => Promise.race([
              document.fonts.ready.then(() => true), new Promise(resolve => setTimeout(() => resolve(false), 10000))])""")
            if not ready:
                page.evaluate("window.stop()")
            fonts = page.evaluate("() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replaceAll('\"', ''))")
            if not all(f in fonts for f in ("Noto Sans SC", "ZCOOL QingKe HuangYou")):
                print("字体：jsdelivr 未加载完整，已退回系统字体，版式可能略有不同")
            page.evaluate("() => Promise.all([...document.images].map(im => im.decode().catch(() => {})))")
            warns.extend(page.evaluate(CHECK_JS))
            for k, filename in enumerate(filenames):
                page.locator(".page").nth(k).screenshot(path=str(out / filename))
        finally:
            b.close()
    for filename in filenames:
        with Image.open(out / filename) as im:
            if im.size != (W * SCALE, H * SCALE):
                warns.append(f"[{filename}] PNG 是 {im.width}×{im.height}，要是 1536×2048")
    # 所有页面按编号缩小拼在一张里，留白和分页一眼就能看全。
    cols = min(3, len(filenames))
    rows = -(-len(filenames) // cols)
    sheet = Image.new("RGB", (cols * 384 + (cols + 1) * 16, rows * 512 + (rows + 1) * 16), "#e9e9e9")
    for k, filename in enumerate(filenames):
        with Image.open(out / filename) as im:
            thumb = im.convert("RGB").resize((384, 512), Image.Resampling.LANCZOS)
            sheet.paste(thumb, (16 + k % cols * 400, 16 + k // cols * 528))
    sheet.save(out / "总览.png")


def main():
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    if not 2 <= len(sys.argv) <= 3:
        print(__doc__)
        return 1
    spec_path = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else spec_path.parent
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        check_spec(spec)
    except (OSError, ValueError) as ex:
        print(f"小红书 JSON 有问题：{ex}")
        return 1
    assets = out / "素材"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy(SKILL / "assets" / "fonts" / "geist-latin-wght-normal.woff2", assets)
    warns = []
    spec = prepare(spec, spec_path.parent, assets, warns)
    filenames = build(spec, out, warns)
    check_qr(spec["events"], assets, warns)
    print(f"网页：{out / '小红书.html'}")
    try:
        shoot(out, filenames, warns)
    except PlaywrightError as ex:
        warns.append(f"[出图] Playwright 启动或截图失败：{str(ex).splitlines()[0]}；PNG 和浏览器排版自检未完成")
        reason = next((line.strip() for line in str(ex).splitlines() if re.search(r"Operation not permitted|Permission denied|FATAL:", line)), "")
        if reason:
            print("浏览器日志：" + reason)
    else:
        print(f"出图：{out}（1536×2048）\n  " + "、".join(filenames))
        print(f"总览：{out / '总览.png'}")
    print("自检：" + (f"{len(warns)} 处要看" if warns else "没有问题"))
    for x in warns:
        print("  - " + x)
    return 1 if warns else 0


if __name__ == "__main__":
    sys.exit(main())
