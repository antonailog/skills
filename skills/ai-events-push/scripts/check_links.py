#!/usr/bin/env python3
"""核对 文案.md 里要发出去的链接：网站详情链接（?e=id）逐条在浏览器里打开，看弹出的是不是这一场；
报名、申报这类外部链接看能不能打开。只读两条横线之间要发的那段，核实记录里的链接不管。

用法：python3 check_links.py <文案.md>
退出码：0 都对；1 有详情链接没弹出、弹错了场次，外部链接打不开，有带网址的行认不出来，或一条链接都没找到
"""
import re
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

LINK = re.compile(r"^([^：:（\s]{1,16})(?:（[^）]*）)?[：:]\s*(https?://\S+)\s*$")
NUM = re.compile(r"^[\u2460-\u2473\u3251-\u325f\u32b1-\u32bf]|^预告")   # ①—⑳、㉑—㉟、㊱—㊿


def blocks(md):
    """返回 (链接列表, 认不出的行)：链接是 (场次名, 链接名, 网址)；带网址却不是「名字：网址」写法的行单独报出来"""
    parts = re.split(r"^---\s*$", md, flags=re.M)
    body = parts[1] if len(parts) >= 3 else md
    out, odd, name = [], [], ""
    lines = body.splitlines()
    for k, line in enumerate(lines):
        if NUM.match(line) and k + 1 < len(lines):
            name = lines[k + 1].strip()
        m = LINK.match(line.strip())
        if m:
            out.append((name, m.group(1), m.group(2)))
        elif "http" in line:
            odd.append(line.strip())
    return out, odd


# 城市名 → 统一叫法：中英文写法算同一个城市
CITY = {c: c for c in ("北京", "上海", "深圳", "杭州", "广州", "成都", "南京", "苏州", "武汉", "西安", "重庆", "天津", "长沙",
                       "厦门", "合肥", "青岛", "大连", "宁波", "郑州", "济南", "福州", "无锡", "珠海", "东莞", "香港", "澳门",
                       "台北", "新加坡", "东京", "线上")}
CITY.update({"beijing": "北京", "shanghai": "上海", "shenzhen": "深圳", "hangzhou": "杭州", "guangzhou": "广州", "chengdu": "成都",
             "nanjing": "南京", "suzhou": "苏州", "wuhan": "武汉", "xian": "西安", "chongqing": "重庆", "tianjin": "天津",
             "changsha": "长沙", "xiamen": "厦门", "hefei": "合肥", "qingdao": "青岛", "hongkong": "香港", "singapore": "新加坡",
             "tokyo": "东京", "online": "线上"})


def similar(a, b):
    """弹窗标题和文案里的名字写法常不一样（「GTC2026 全球流量大会」和「GTC 全球流量大会」）。
    去掉空格标点、忽略大小写后：两边点名的城市不同就不是同一场（同系列的上海站、北京站）；
    一个包含另一个算同一场；否则按数字把名字切开（「2026」连着后面的字不能凑数），段内有两段以上 4 字相同才算"""
    a, b = (re.sub(r"[\W_]", "", x).casefold() for x in (a, b))
    if not a or not b:
        return False
    ca, cb = ({v for k, v in CITY.items() if k in x} for x in (a, b))
    if ca and cb and not ca & cb:
        return False
    if a in b or b in a:
        return True
    frags = lambda x: {seg[k:k + 4] for seg in re.split(r"\d+", x) for k in range(len(seg) - 3)}
    return len(frags(a) & frags(b)) >= 2


def status(url):
    if "mp.weixin.qq.com" in url:
        return "微信文章，不检查"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) ai-events-push"})
        return str(urllib.request.urlopen(req, timeout=20).status)
    except Exception as e:
        code = getattr(e, "code", None)
        if code and 300 <= code < 400:
            return f"跳转（{code}），手机上点开看一眼"   # 短链跳到 App 或微信内页时 Python 跟不过去，不算坏
        return f"打不开（{code or type(e).__name__}）"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    items, odd = blocks(Path(sys.argv[1]).read_text(encoding="utf-8"))
    bad = len(odd)
    for line in odd:
        print(f"!! 认不出这一行，没检查：{line[:70]}（链接要单独一行，写成「详情：网址」）")
    if not items:
        print("!! 一条链接都没找到：两条横线之间的段落里，链接要写成「详情：网址」「报名：网址」")
        sys.exit(1)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        for name, kind, url in items:
            detail = re.search(r"antonailog\.com/more/ai-events/?\?e=", url)
            if kind == "详情" and not detail:
                bad += 1
                print(f"!! {kind}  {name[:24]} → 详情链接要指向网站这一场（…/ai-events/?e=<id>）：{url[:60]}")
            elif detail:
                try:
                    pg.goto(url, wait_until="networkidle", timeout=60000)
                    pg.wait_for_timeout(1200)
                    d = pg.locator('[role="dialog"]')
                    title = d.first.inner_text(timeout=5000).split("\n")[0] if d.count() else ""
                except Exception as e:
                    title = ""
                    print(f"   （打开 {url[:60]} 出错：{type(e).__name__}）")
                ok = bool(title) and bool(name) and similar(name, title)   # 场次名为空（链接写在第一个编号之前）算没对上
                bad += not ok
                print(f"{'OK ' if ok else '!! '}{kind}  {name[:24]} → 弹窗「{title[:30] or '没弹出'}」")
            else:
                s = status(url)
                ok = s.isdigit() and int(s) < 400 or s.startswith(("微信", "跳转"))
                bad += not ok
                print(f"{'OK ' if ok else '!! '}{kind}  {name[:24]} → {s}  {url[:60]}")
        b.close()
    print(f"共 {len(items)} 条链接，{bad} 条要看" if bad else f"共 {len(items)} 条链接，都对")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
