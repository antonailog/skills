#!/usr/bin/env python3
"""用浏览器打开报名页、官网（跑完页面里的 JS 再读），把正文、链接、大图写成文本，顺手截一屏。
活动行这类页面直接抓只拿到 {{ativityData.ativityTime}} 这样的空模板，要用它读。

用法：python3 read_page.py <输出目录> <名字=网址> [<名字=网址> ...]
产出：<输出目录>/<名字>.txt（网址、标题、正文、== 链接 ==、== 大图 ==）和 <名字>.png（首屏截图）

微信文章常被「环境异常，完成验证后即可继续访问」挡住，浏览器打开也一样；遇到会提示，改读 fetch_events.py 导出的「原文」。
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
WALL = ("环境异常", "完成验证后即可继续访问")


def main():
    if len(sys.argv) < 3 or not all("=" in x for x in sys.argv[2:]):
        sys.exit(__doc__)
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900}, user_agent=UA, locale="zh-CN")
        for arg in sys.argv[2:]:
            name, url = arg.split("=", 1)
            try:
                pg.goto(url, wait_until="networkidle", timeout=60000)
            except Exception as e:   # 有的页面一直有长连接，等不到 networkidle；已经加载出来的内容照样读
                if "Timeout" not in type(e).__name__:
                    print(f"!! {name}：打不开（{type(e).__name__}）{url[:60]}")
                    bad += 1
                    continue
            pg.wait_for_timeout(2000)
            for _ in range(8):   # 往下滚，触发懒加载的议程、嘉宾
                pg.mouse.wheel(0, 3000)
                pg.wait_for_timeout(300)
            text = pg.inner_text("body")
            links = pg.evaluate("() => [...document.querySelectorAll('a[href]')].map(a => a.innerText.trim().replace(/\\s+/g, ' ').slice(0, 40) + ' | ' + a.href)")
            imgs = pg.evaluate("() => [...document.querySelectorAll('img')].filter(i => i.naturalWidth >= 300).map(i => i.naturalWidth + 'x' + i.naturalHeight + ' ' + (i.currentSrc || i.src))")
            (out / f"{name}.txt").write_text(
                f"网址：{pg.url}\n标题：{pg.title()}\n\n{text}\n\n== 链接 ==\n" + "\n".join(dict.fromkeys(links)) +
                "\n\n== 大图 ==\n" + "\n".join(dict.fromkeys(imgs)) + "\n", encoding="utf-8")
            pg.evaluate("window.scrollTo(0, 0)")
            pg.screenshot(path=str(out / f"{name}.png"))
            if any(w in text for w in WALL):
                print(f"!! {name}：微信验证墙，正文读不到，改读「原文」")
                bad += 1
            elif "{{" in text and "}}" in text:
                print(f"!! {name}：页面里还有没渲染的 {{{{…}}}} 模板，内容可能不全，看一眼 {name}.png")
            else:
                print(f"OK {name}：{len(text)} 字 → {out / (name + '.txt')}")
        b.close()
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
