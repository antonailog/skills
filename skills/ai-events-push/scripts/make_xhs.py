#!/usr/bin/env python3
"""按 小红书.json 出一组活动推荐图：封面 + 每天的活动页（头条大票版式），768×1024 按 2 倍截图 → 自检。

用法：python3 -I make_xhs.py <小红书.json> [输出目录，默认和 JSON 同目录]

小红书.json：
{
  "range": ["2026-11-04", "2026-11-10"],       封面大字的日期范围
  "title": "AI 活动推荐", "sign": "by 阿東",
  "cities": ["北京", "上海", "线上"],           可省略：北京在前，其余按场数，线上最后
  "cover_ids": ["aie-sh-1105"],                封面叠放 1–5 张，引用 events 里的 id
  "events": [{
    "id": "aie-sh-1105", "day": "2026-11-05", "form": "线下", "city": "上海",
    "date": "11/5–6", "time": "09:30 起", "due": "",   day 决定排在哪天，date 是票上的跨天日期
    "name": "AI Engineer Shanghai 2026",              名称里写 \\n 手动换行
    "venue": "闵行 · 虹桥祥源希尔顿酒店", "org": "AI Engineer × Arogo Intelligence",
    "intro": "AI Engineer 大会首次来华……", "price": "¥1999",
    "cover": "原图/aie-sh-1105.jpg",                   相对 JSON 的本地文件 / 网站 covers/ 路径 / 网址
    "cover_big": "原图-大/aie-sh-1105.jpg",            可省略：更大的宣传图；不写就去活动行找原图（800 宽），写 false 不找
    "cover_blur": [[0.52, 0.78, 1, 1]],               可省略：宣传图里要虚化的框（比例坐标，盖掉「扫码报名」、网址）
    "hero": true,                                     可省略：指定这场当这页的头条大票
    "category": "大会峰会"                             可省略：没拿到宣传图时挑分类默认图
  }]
}

分页：一天单独占页。6 场拆 3+3，5 → 3+2，4 → 2+2；3 张的页第一张放大成大票，2 张、1 张的页都是大票。
头条：写了 hero 的那场；没写就挑这页第一张横版宣传图（宽 ≥ 高 × 1.5）的；放最上面，其余保持顺序。
产出：01-封面.png、02-11月4日-1.png …、小红书.html、素材/、总览.png。
图上不放网址和二维码。自检会报 id：票面溢出、孤字、介绍超三行或空着、地点主办方或介绍被截断、价格超 6 字、默认图、
头条宣传图太小、宣传图里的二维码、虚化框写错、尺寸不对、封面引用不对、总图数超 18。没有问题退出 0，有问题照样出图、退出 1。
"""
import ast
import datetime as dt
import hashlib
import html
import io
import importlib.util
import json
import math
import os
import re
import shutil
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageFilter
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout, sync_playwright

SKILL = Path(__file__).resolve().parents[1]
W, H, SCALE = 768, 1024, 2
PW = W - 44                      # 页面内容宽：左右各留 22
CONTENT_H = H - 22 - 20 - 60     # 日期行（50 + 下边距 10）以下能放票的高度
HERO_MIN_W = 600                 # 头条宣传图原图比这窄，放大到 664 宽 × 2 倍截图会糊（网站存的图多是 640 宽，放大还看得过去）
# -I 不把脚本目录放进 sys.path，按文件加载同目录的老脚本，复用下载、裁图、默认图和城市排序。
sys.dont_write_bytecode = True
_module = importlib.util.spec_from_file_location("make_poster", SKILL / "scripts" / "make_poster.py")
poster = importlib.util.module_from_spec(_module)
_module.loader.exec_module(poster)
esc = poster.esc
CITY = dict(poster.CITY, 线上="#7B5BC4")   # 小红书样图里线上用紫色
PROJECT = Path(os.environ.get("AI_EVENTS_DIR") or Path.home() / "claudecode_workspace" / "工具" / "活动监测").expanduser()
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
        if e.get("cover_big") not in (None, False) and not isinstance(e["cover_big"], str):
            errs.append(f"[{label}] cover_big 要写路径、网址，或者 false（不去活动行找原图）")
        if e.get("hero") is not None and not isinstance(e["hero"], bool):
            errs.append(f"[{label}] hero 要写 true 或 false")
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


def hdx_logos(ids):
    """活动行原图：活动库里每场的 extra.logo 是列表小图（_v2small），换成 _v2 就是 800 宽的原图。
    没有活动库（换了电脑、没设 AI_EVENTS_DIR）就不找，静默用 cover。"""
    f = PROJECT / "活动库" / "活动.jsonl"
    out = {}
    try:
        fh = f.open(encoding="utf-8", errors="replace")
    except OSError:
        return out
    with fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict) or not isinstance(r.get("id"), str) or r["id"] not in ids:
                continue
            extra = r.get("extra")
            if isinstance(extra, str):
                try:
                    extra = ast.literal_eval(extra)
                except (ValueError, SyntaxError, MemoryError, RecursionError):
                    extra = {}
            logo = extra.get("logo") if isinstance(extra, dict) else ""
            if not isinstance(logo, str):
                continue
            if logo.startswith("/logo/"):
                logo = "https://cdn.huodongxing.com" + logo
            if "huodongxing.com/" in logo:
                out[r["id"]] = logo.replace("_v2small.jpg", "_v2.jpg")
    return out


def load_big(e, src, spec_dir, assets, net, warns, explicit):
    """更大的宣传图：本地文件直接读；网址下载、验过是图片再缓存到 素材/大图/（文件名带网址的哈希，换了网址会重下）。
    作者在 cover_big 里写的拿不到要报；自动去活动行找的拿不到就静默用 cover，这一轮连不上就不再试。"""
    try:
        if not src.startswith(("http://", "https://")):
            p = Path(src).expanduser()
            p = p if p.is_absolute() else spec_dir / p
            if not p.is_file():
                raise FileNotFoundError(f"没有 {src}")
            return Image.open(p).convert("RGB")
        cache = assets / "大图" / f"{e['id']}-{hashlib.sha1(src.encode()).hexdigest()[:8]}.jpg"
        if not cache.is_file():
            if net["down"]:
                raise OSError("这一轮连不上，跳过")
            cache.parent.mkdir(exist_ok=True)
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.huodongxing.com/"})
            try:
                data = urllib.request.urlopen(req, timeout=20).read()
            except OSError:
                net["down"] = True
                raise
            finally:
                time.sleep(0.5)
            Image.open(io.BytesIO(data)).verify()
            cache.write_bytes(data)
            net["got"] += 1
        return Image.open(cache).convert("RGB")
    except Exception as ex:
        if explicit:
            warns.append(f"[{e['id']}] cover_big 没拿到（{str(ex)[:60]}），用的是 cover")
        return None


def blur_boxes(e, path, warns):
    """cover_blur 的每个框高斯模糊盖掉：宣传图里印着「扫码报名」、二维码、网址的那块，小红书会判引流"""
    boxes = e.get("cover_blur")
    num = lambda v: type(v) in (int, float)
    if boxes == []:
        return
    ok = isinstance(boxes, list) and all(isinstance(b, list) and len(b) == 4 and all(map(num, b)) for b in boxes)
    if not ok or any(not (0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1) for b in boxes):
        warns.append(f"[{e['id']}] cover_blur 写错了：要写成 [[x0, y0, x1, y1]]，0–1 之间、x0 < x1、y0 < y1；这张没虚化")
        return
    im = Image.open(path).convert("RGB")
    radius = max(4, round(im.width * 0.02))
    for x0, y0, x1, y1 in boxes:
        box = (round(x0 * im.width), round(y0 * im.height), round(x1 * im.width), round(y1 * im.height))
        im.paste(im.crop(box).filter(ImageFilter.GaussianBlur(radius)), box[:2])
    im.save(path, "JPEG", quality=92)


def prepare(spec, spec_dir, assets, warns):
    spec = dict(spec)
    for key in ("title", "sign"):
        spec[key] = clean_text(spec[key], f"[封面] {key}", warns)
    spec["events"] = [dict(e) for e in spec["events"]]
    logos = hdx_logos({e["id"] for e in spec["events"] if e.get("cover_big") is None or e.get("cover_big") == ""})
    if logos:
        print(f"活动行原图：找到 {len(logos)} 场的地址，比现有的图宽就换上（没下过的要下载，每张停 0.5 秒）")
    net, swapped = {"down": False, "got": 0}, []
    r0, r1 = (dt.date.fromisoformat(x) for x in spec["range"])
    for e in spec["events"]:
        d = dt.date.fromisoformat(e["day"])
        if not r0 <= d <= r1:
            warns.append(f"[{e['id']}] day {e['day']} 不在封面写的范围 {spec['range'][0]}–{spec['range'][1]} 里")
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", (e.get("date") or "").strip())
        if m and (int(m[1]), int(m[2])) != (d.month, d.day):
            warns.append(f"[{e['id']}] 票上日期 {e['date']} 和排在的那天 {d.month}/{d.day} 对不上，单日活动只印钟点，会排错天")
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
        cb = e.get("cover_big")
        explicit = isinstance(cb, str) and bool(cb.strip())
        big_src = cb.strip() if explicit else ("" if cb is False else logos.get(e["id"], ""))
        big = load_big(e, big_src, spec_dir, assets, net, warns, explicit) if big_src else None
        if big is not None:
            if big.height > big.width * 1.5:
                big = big.crop((0, 0, big.width, big.width))
            cur_w = 0 if fallback else Image.open(assets / filename).width
            if big.width > cur_w:
                filename, fallback = e["id"] + ".jpg", False
                big.save(assets / filename, "JPEG", quality=92)
                if not explicit:
                    swapped.append(e["id"])
        if not fallback and e.get("cover_blur") is not None:
            blur_boxes(e, assets / filename, warns)
        with Image.open(assets / filename) as im:
            e["_w"], e["_h"] = im.size
        e["_image"], e["_default"] = filename, fallback
        if fallback:
            warns.append(f"[{e['id']}] 宣传图没拿到，用了默认图" + (f"（{'；'.join(notes)}）" if notes else "（没给宣传图）"))
    if swapped:
        print(f"宣传图换成活动行原图：{len(swapped)} 场（不想换的在那场写 \"cover_big\": false）")
    if net["down"]:
        print("活动行原图：这一轮连不上，后面的没再试，用的是 cover")
    if "cities" in spec:
        spec["cities"] = [clean_text(c, "[封面] cities", warns) for c in spec["cities"]]
    else:
        spec["cities"] = poster.city_order({"events": [dict(e, city="线上" if e["form"] == "线上" else e["city"]) for e in spec["events"]]})
    return spec


def check_qr(events, assets, warns):
    """扫处理后（裁过、虚化过）的图：长海报底部被裁掉的二维码不算，票根里还留着的要报。"""
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
                warns.append(f"[{e['id']}] 处理后的票根宣传图里扫到二维码，请换一张或用 cover_blur 盖掉")
        except cv2.error as ex:
            warns.append(f"[{e['id']}] 二维码没扫（opencv 检测失败：{str(ex).splitlines()[0]}）")


def color(e):
    return CITY.get("线上" if e["form"] == "线上" else e["city"], "#CB912F")


def mask(*pts, r=8):
    """门票缺口：在每段的角上挖半圆，几段拼起来就是撕线两头的缺口"""
    g = ", ".join(f"radial-gradient(circle {r}px at {p}, transparent {r - .5}px, #000 {r}px)" for p in pts)
    return f"-webkit-mask:{g};-webkit-mask-composite:source-in;"


def width_units(s, fs):
    return sum(1.0 if ord(c) > 0x2E80 else 0.58 for c in s) * fs


def name_lines(e, avail, fs=15.5):
    return sum(max(1, math.ceil(width_units(x, fs) / avail)) for x in e["name"].split("\n"))


def parts(e, show_date=False):
    src = "素材/" + quote(e["_image"])
    tag = ('<span class="tag on">线上</span>' if e["form"] == "线上" else
           f'<span class="tag">线下<i></i>{esc(e["city"])}</span>')
    due = f'<span class="due">{esc(e["due"])}</span>' if e["due"] else ""
    name = "<br>".join(esc(x) for x in e["name"].split("\n"))
    cross_day = bool(re.search(r"[–—~～至]|\d\s*-\s*\d", e["date"]))
    when = f'{e["date"]} {e["time"]}' if show_date or cross_day else e["time"]
    return src, f'<p class="r1">{tag}<b>{esc(when)}</b>{due}</p>', f'<p class="name">{name}</p>'


def price_html(e, cls="", style=""):
    st = f' style="{style}"' if style else ""
    return f'<b class="price {cls}"{st}>{esc(e["price"])}</b>' if e["price"] else f'<b class="price dim {cls}"{st}>费用未写</b>'


def ticket(e, show_date=False):
    """普通票：338×190 票根｜正文｜副券。封面和活动页用同一张；活动页只有跨天的才在时间前写日期。"""
    src, r1, name = parts(e, show_date)
    return f'''<article class="ticket" style="--c:{color(e)}" data-id="{html.escape(e['id'], quote=True)}"><div class="tk">
  <div class="seg stub"><img class="bg" src="{src}"><img class="fg" src="{src}"></div>
  <div class="seg body">
    {r1}{name}
    <p class="meta">{poster.PIN}<span>{esc(e["venue"])}</span></p>
    <p class="meta">{poster.ORG}<span>{esc(e["org"])}</span></p>
    <p class="why">{esc(e["intro"])}</p>
  </div>
  <div class="seg tail">{price_html(e)}</div>
</div></article>'''


def hero(e, height):
    """大票：宣传图 16:9 放大在左上，副券在图右边（够宽就横写价格），正文在图下面、地点和主办方并一行。
    正文高度按名称行数和介绍行数估，剩下的高度给宣传图。"""
    src, r1, name = parts(e)
    nl = name_lines(e, PW - 28)
    il = min(2, max(1, math.ceil(width_units(e["intro"], 12.5) / (PW - 32))))
    bh = round(106 + nl * 21 + il * 19.4)
    sw = min(PW - 60, round((height - bh) * 16 / 9))
    sh = round(sw * 9 / 16)
    tw = PW - sw
    # 副券里的价格：够宽就横写，字号按宽度收（最大 30）；收到 16 以下就竖写，字号按高度收（最大 24）
    units = width_units(e["price"] or "费用未写", 1)
    fs = min(30, int((tw - 24) / units))
    pcls, pst = ("hz", f"font-size:{fs}px") if fs >= 16 else ("", f"font-size:{min(24, int((sh - 36) / units))}px")
    meta = (f'<p class="m1"><span class="v">{poster.PIN}<em>{esc(e["venue"])}</em></span>'
            f'<span class="o">{poster.ORG}<em>{esc(e["org"])}</em></span></p>')
    return f'''<article class="ticket hero" style="--c:{color(e)}" data-id="{html.escape(e['id'], quote=True)}"><div class="hg" style="grid-template-columns:{sw}px {tw}px;grid-template-rows:{sh}px {bh}px">
  <div class="seg im" style="border-radius:12px 0 0 0;{mask("0 100%", "100% 0")}"><img class="bg" src="{src}"><img class="fg" src="{src}"></div>
  <div class="seg htail pv" style="border-radius:0 12px 0 0;{mask("0 0", "100% 100%")}">{price_html(e, pcls, pst)}</div>
  <div class="seg hb ph" style="grid-column:1/3;border-radius:0 0 12px 12px;{mask("0 0", "100% 0")}">{r1}{name}{meta}<p class="why clamp" style="--cl:2">{esc(e["intro"])}</p></div>
</div></article>'''


def split(n):
    """一天的场数拆成每页几张：3 张一页，余 2 补一页 2 张，余 1 就把最后两页拆成 2+2"""
    if n <= 3:
        return [n]
    if n == 4:
        return [2, 2]
    q, r = divmod(n, 3)
    return [3] * q + [2] if r == 2 else [3] * (q - 1) + [2, 2] if r == 1 else [3] * q


def wide(e):
    return not e["_default"] and e["_w"] >= e["_h"] * 1.5


def paginate(events):
    """一天单独占页，同一天保持 JSON 顺序；3 张的页挑头条放最上面"""
    days = defaultdict(list)
    for e in events:
        days[e["day"]].append(e)
    pages = []
    for day, evs in sorted(days.items()):
        sizes, start = split(len(evs)), 0
        for k, size in enumerate(sizes, 1):
            pg = evs[start:start + size]
            start += size
            if size == 3:
                hi = next((i for i, e in enumerate(pg) if e.get("hero")), None)
                if hi is None:
                    hi = next((i for i, e in enumerate(pg) if wide(e)), next((i for i, e in enumerate(pg) if not e["_default"]), 0))
                pg = [pg[hi]] + [e for i, e in enumerate(pg) if i != hi]
            pages.append((day, k, len(sizes), pg))
    return pages


def day_page(day, pg, sign):
    d = dt.date.fromisoformat(day)
    head = (f'<h2 class="sh"><span class="md">{d.month}/{d.day}</span><span class="wd">周{"一二三四五六日"[d.weekday()]}</span>'
            f'<i></i><span class="sign">{esc(sign)}</span></h2>')
    if len(pg) == 3:
        body = hero(pg[0], CONTENT_H - 2 * 190 - 2 * 10) + "".join(ticket(e) for e in pg[1:])
        return head + f'<div class="stack" style="gap:10px">{body}</div>', [pg[0]]
    if len(pg) == 2:
        return head + '<div class="stack" style="gap:12px">' + "".join(hero(e, (CONTENT_H - 12) // 2) for e in pg) + "</div>", pg
    return head + f'<div class="stack">{hero(pg[0], CONTENT_H)}</div>', pg


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
    if "per_page" in spec:
        print("per_page 已不用：分页按「6 → 3+3、5 → 3+2、4 → 2+2」固定")
    pages = [("封面", "cover", cover(spec, warns))]
    plan = []
    for day, k, n, pg in paginate(spec["events"]):
        d = dt.date.fromisoformat(day)
        label = f"{d.month}月{d.day}日" + (f"-{k}" if n > 1 else "")
        body, heroes = day_page(day, pg, spec["sign"])
        for e in heroes:
            if e["_default"]:
                warns.append(f"[{e['id']}]（{label}）当了头条大票，却用的是默认图；换一张宣传图，或给同页别的场次写 hero")
            elif e["_w"] < HERO_MIN_W:
                warns.append(f"[{e['id']}]（{label}）头条宣传图只有 {e['_w']} 宽，放大会糊；在 cover_big 给一张更大的")
        pages.append((label, "pg tight", body))
        plan.append((label, pg, len(pg) == 3))
    if len(pages) > 18:
        warns.append(f"[整组] 总图数 {len(pages)} 张，超过小红书上限 18 张")
    filenames = [f"{k:02d}-{label}.png" for k, (label, _, _) in enumerate(pages, 1)]
    for fn, (label, pg, three) in zip(filenames[1:], plan):
        ids = [e["id"] for e in pg]
        print(f"{fn[:-4]}：" + (f"头条 {ids[0]} + {'、'.join(ids[1:])}" if three else f"大票 {'、'.join(ids)}"))
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
      const why = el.classList.contains('why');
      if (lines.length > 1 && chars <= 2)
        out.push(`${label(el)}${why ? '介绍' : '名称'}最后一行只剩约 ${chars} 个字（孤字）`);
      if (why && !el.classList.contains('clamp') && lines.length > 3)
        out.push(`${label(el)}介绍有 ${lines.length} 行，超过三行`);
    }
    for (const el of document.querySelectorAll('.ticket .body, .ticket .hb')) {
      if (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1)
        out.push(`${label(el)}票面正文放不下：高多 ${Math.max(0, el.scrollHeight - el.clientHeight)}px，宽多 ${Math.max(0, el.scrollWidth - el.clientWidth)}px`);
    }
    for (const el of document.querySelectorAll('.m1 em'))
      if (el.scrollWidth > el.clientWidth + 1) out.push(`${label(el)}地点或主办方被截断成「…」：${el.textContent}，请缩短`);
    for (const el of document.querySelectorAll('.tail .price, .htail .price')) {
      const a = el.getBoundingClientRect(), b = el.parentElement.getBoundingClientRect();
      if (a.width > b.width - 4 || a.height > b.height - 4) out.push(`${label(el)}副券里的价格「${el.textContent}」放不下，请缩短`);
    }
    for (const el of document.querySelectorAll('.why.clamp'))
      if (el.scrollHeight > el.clientHeight + 1) out.push(`${label(el)}大票介绍超过两行被截断，请缩短`);
    for (const el of document.querySelectorAll('.pg .ticket')) {
      const page = el.closest('.page');
      if (el.getBoundingClientRect().bottom > page.getBoundingClientRect().bottom - 10)
        out.push(`${label(el)}门票超出页面`);
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
            if "Noto Sans SC" not in fonts:
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
    cols = min(5, len(filenames))
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
