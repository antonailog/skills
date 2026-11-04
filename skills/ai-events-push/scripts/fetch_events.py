#!/usr/bin/env python3
"""从线上「国内AI活动追踪」拉活动数据，挑出要推送的几场，顺手起一份海报数据草稿。

用法：
  python3 fetch_events.py --range 2026-11-02 2026-11-08 [--city 北京 上海]   列出这段日期里的活动（对截图上的名字用）
  python3 fetch_events.py --match 聚上地 "AI Engineer" --out 选中.json       按名字片段挑，完整字段写进 选中.json
  python3 fetch_events.py --ids aie-sh-1105 dbd5e2aace --draft 活动.json \
      --week 2026-11-02 2026-11-08                                            挑好的几场直接起海报数据草稿（介绍留空，要自己写）
  python3 fetch_events.py --ids … --out 选中.json --xhs 小红书.json \
      --week 2026-11-04 2026-11-10                                            小红书多图的数据草稿（排在哪天、钟点、地点、价格已填，介绍留空）

线上数据拉不下来时退回活动监测项目里的 页面/app/src/data.json（可能不是最新，会提示）；
项目目录取环境变量 AI_EVENTS_DIR，没设就用 ~/claudecode_workspace/工具/活动监测。
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

BASE = "https://antonailog.com/more/ai-events/"
PROJECT = Path(os.environ.get("AI_EVENTS_DIR") or Path.home() / "claudecode_workspace" / "工具" / "活动监测").expanduser()   # 活动监测项目目录
LOCAL_DATA = PROJECT / "页面" / "app" / "src" / "data.json"
WD = "一二三四五六日"
KEEP = ("id", "name", "time", "start", "end", "city", "venue", "form", "type", "fee", "feeShort", "deadline", "deadlineLabel",
        "org", "orgCred", "brief", "agenda", "speakers", "scale", "focus", "cover", "thumbs", "register", "article", "timeNote",
        "category", "text", "layer", "status")


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ai-events-push"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def load_live():
    """页面 → page-*.js → data-*.js（构建产物名字带哈希，每次发布会变），用 node 执行模块取出活动列表"""
    html = get(BASE).decode("utf-8")
    page_js = re.search(r"assets/page-[\w-]+\.js", html).group(0)
    data_js = re.search(r"\./(data-[\w-]+\.js)", get(BASE + page_js).decode("utf-8")).group(1)
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "data.mjs"
        f.write_bytes(get(BASE + "assets/" + data_js, timeout=60))
        code = ("const m = await import(process.argv[1]);"
                "const v = Object.values(m).find((x) => x && Array.isArray(x.items));"
                "process.stdout.write(JSON.stringify(v.items));")
        if not shutil.which("node"):
            raise RuntimeError("没装 node，解析不了网站数据")
        out = subprocess.run(["node", "--input-type=module", "-e", code, f.as_uri()], capture_output=True, check=True)
    return json.loads(out.stdout)


def load():
    try:
        return load_live(), "线上"
    except Exception as e:  # 网络、页面结构变了都退回本地
        if not LOCAL_DATA.is_file():
            sys.exit(f"线上数据没拉下来（{e}），本地也没有 {LOCAL_DATA}（项目目录由环境变量 AI_EVENTS_DIR 指定）")
        print(f"!! 线上数据没拉下来（{e!r}），改用本地 {LOCAL_DATA}，可能不是最新", file=sys.stderr)
        return json.loads(LOCAL_DATA.read_text(encoding="utf-8"))["items"], "本地"


def original_text(i, live=True):
    """网站把活动原文（多半是公众号文章、活动行详情）存成 text/<id>.txt；微信文章常被验证墙挡住，核实时先读这份。
    live=False（线上数据已经拉不下来）时只读本地构建产物，不再一场场等超时"""
    t = (i.get("text") or "").strip()
    if not t:
        return ""
    if not re.fullmatch(r"text/[\w./-]+\.txt", t) or ".." in t:
        if t.startswith(("text/", "http")):
            print(f"!! {i['id']}：原文字段「{t[:40]}」不是 text/<id>.txt，没取", file=sys.stderr)
            return ""
        return t   # 直接写在字段里的原文
    if live:
        try:
            return get(BASE + t).decode("utf-8")
        except Exception:
            pass
    f = PROJECT / "页面" / "app" / "dist-site" / t
    if f.is_file():
        return f.read_text(encoding="utf-8")
    print(f"!! {i['id']}：原文 {t} 线上和本地都没取到", file=sys.stderr)
    return ""


def day(s):
    return dt.date.fromisoformat(s[:10]) if s else None


def clock(s):
    return s[11:16] if s and len(s) >= 16 and s[11:16] != "00:00" else ""


def date_label(i):
    s, e = day(i["start"]), day(i["end"] or i["start"])
    if not s:
        return "日期未定"
    if e == s:
        return f"{s.month}/{s.day}"
    return f"{s.month}/{s.day}–{e.day}" if e.month == s.month else f"{s.month}/{s.day}–{e.month}/{e.day}"


def when_label(i):
    s, e = day(i["start"]), day(i["end"] or i["start"])
    if not s:
        return ""
    sc, ec = clock(i["start"]), clock(i["end"])
    if e == s:
        return f"周{WD[s.weekday()]} " + (f"{sc}–{ec}" if sc and ec else sc or "钟点未写")
    return f"周{WD[s.weekday()]}–{WD[e.weekday()]}" + (f" {sc} 起" if sc else "")


def venue_label(i):
    """「上海闵行·虹桥祥源希尔顿酒店（红松东路 1116 号）」→「闵行 · 虹桥祥源希尔顿酒店」：城市在分区标题里，括号里的门牌放不下"""
    v = re.sub(r"（[^）]*）|\([^)]*\)", "", i.get("venue") or "").strip()
    v = re.split(r"[，,；;]", v)[0].strip()   # 逗号后面多是门牌、楼层，海报上放不下
    v = re.sub(rf"^{re.escape(i.get('city') or '')}(市)?\s*[·・]?\s*", "", v)
    return re.sub(r"\s*[·・]\s*", " · ", v).strip(" ·") or (i.get("city") or "")


def cover_of(i):
    """海报用原图：网站的列表小图是按 16:9 框缩的，长海报缩完只剩一窄条，放大就糊；太长的竖图交给 make_poster 截顶上一块"""
    return i.get("cover") or ""


def draft(items, week):
    evs = []
    for i in sorted(items, key=lambda i: i["start"] or "9"):
        due = ""
        if i.get("category") == "征集榜单" and i.get("deadline"):
            due = "申报截止"
        evs.append({
            "id": i["id"], "city": i["city"], "date": date_label(i), "when": when_label(i), "due": due,
            "name": i["name"], "venue": venue_label(i), "venue_hl": "", "org": i.get("org", ""),
            "intro": "", "price": i.get("feeShort", ""), "cover": cover_of(i), "category": i.get("category", ""),
        })
    return {"week": week, "title": "本周活动推荐", "events": evs}


def xhs_draft(items, rng):
    """小红书.json 草稿：每场排在哪一天（征集类排在截止那天，开始得比范围早、还在进行的排在范围第一天），钟点只写开始和结束。
    完全在范围外的照它自己的日子排，并报出来（单日活动票上只印钟点，挪到别的天就是排错天）。
    介绍、封面挑哪几场、跨天活动的钟点要自己写；地点、价格核实后再定"""
    r0, r1 = (dt.date.fromisoformat(x) for x in rng)
    evs = []
    for i in items:
        s, e = day(i["start"]), day(i["end"] or i["start"])
        sc, ec = clock(i["start"]), clock(i["end"])
        online = i.get("form") == "线上"
        collect = i.get("category") == "征集榜单" and day(i.get("deadline") or "")
        if collect:   # 征集、榜单是线上申报：排在截止那天，算线上（网站上的地点多半是颁奖地）
            d = day(i["deadline"])
            date, time, online = f"{d.month}/{d.day}", "申报截止", True
        else:
            d = max(s, r0) if s and s <= r1 and e >= r0 else (s or r0)
            date = date_label(i)
            time = (f"{sc}–{ec}" if sc and ec else sc or "钟点未写") if e == s else (f"{sc} 起" if sc else "钟点未写")
        if not r0 <= d <= r1:
            print(f"!! {i['id']} 排在 {d.month}/{d.day}，不在范围 {r0.month}/{r0.day}–{r1.month}/{r1.day} 里，确认要不要放", file=sys.stderr)
        evs.append({
            "id": i["id"], "day": d.isoformat(), "form": "线上" if online else "线下",
            "city": "线上" if online else i["city"], "date": date, "time": time, "due": "",
            "name": i["name"], "venue": "线上申报" if collect else "线上直播" if online and not i.get("venue") else venue_label(i),
            "org": i.get("org", ""), "intro": "", "price": i.get("feeShort", ""), "cover": cover_of(i),
            "category": i.get("category", ""),
        })
    evs.sort(key=lambda x: (x["day"], next((i["start"] for i in items if i["id"] == x["id"]), "")))
    return {"range": list(rng), "title": "AI 活动推荐", "sign": "by 阿東", "cover_ids": [], "events": evs}


def overlaps(i, a, b):
    s, e = day(i["start"]), day(i["end"] or i["start"])
    return bool(s) and s <= b and e >= a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", nargs=2, metavar=("起", "止"))
    ap.add_argument("--city", nargs="*")
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--match", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--draft")
    ap.add_argument("--week", nargs=2, metavar=("周一", "周日"))
    ap.add_argument("--xhs", help="写小红书.json 草稿，日期范围取 --week（没给就取 --range）")
    ap.add_argument("--force", action="store_true", help="--draft / --xhs 的文件已经存在时照样覆盖")
    a = ap.parse_args()

    items, src = load()
    print(f"数据：{src}，{len(items)} 场", file=sys.stderr)
    picked = []
    if a.ids:
        by = {i["id"]: i for i in items}
        for k in a.ids:
            if k in by:
                picked.append(by[k])
            else:
                print(f"!! 没有这个 id：{k}", file=sys.stderr)
    if a.match:
        for k in a.match:
            hit = [i for i in items if k.lower() in i["name"].lower()]
            if not hit:
                print(f"!! 名字里没有「{k}」的活动", file=sys.stderr)
            picked += [i for i in hit if i not in picked]
    if a.range:
        r0, r1 = dt.date.fromisoformat(a.range[0]), dt.date.fromisoformat(a.range[1])
        listed = [i for i in items if i.get("layer") == 1 and i.get("status") != "不去" and overlaps(i, r0, r1)
                  and (not a.city or i["city"] in a.city)]
        long = lambda i: (day(i["end"] or i["start"]) - day(i["start"])).days > 7
        listed.sort(key=lambda i: (long(i), i["start"]))   # 跨好几周的长期活动放最后，别淹掉这周的
        for i in listed:
            print(f"{i['id']:<22} {date_label(i):<10} {i['city']:<4} {i.get('feeShort') or '-':<8} {i['name'][:46]}")
        print(f"共 {len(listed)} 场", file=sys.stderr)
        if not picked:
            return

    for i in picked:
        print(f"选中 {i['id']:<22} {date_label(i):<10} {i['city']:<4} {i['name'][:46]}", file=sys.stderr)
    if a.out:
        rows = [{k: i.get(k) for k in KEEP} for i in picked]
        for r in rows:
            r["原文"] = original_text(r, live=(src == "线上"))
        Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"完整字段 → {a.out}（「原文」是网站存下的活动原文，微信文章读不到时用它）", file=sys.stderr)
    for target in (a.draft, a.xhs):
        if target and Path(target).exists() and not a.force:
            sys.exit(f"{target} 已经存在（可能是改过的稿），不覆盖；确定要重起草稿加 --force")
    if a.draft:
        if not a.week:
            sys.exit("--draft 要同时给 --week 周一 周日")
        Path(a.draft).write_text(json.dumps(draft(picked, a.week), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"海报数据草稿 → {a.draft}（intro 还空着，地点、钟点、价格要核对）", file=sys.stderr)
    if a.xhs:
        rng = a.week or a.range
        if not rng:
            sys.exit("--xhs 要同时给 --week 起 止（或 --range 起 止）")
        Path(a.xhs).write_text(json.dumps(xhs_draft(picked, rng), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"小红书数据草稿 → {a.xhs}（intro、cover_ids 还空着；跨天活动的钟点、地点、价格要核对）", file=sys.stderr)


if __name__ == "__main__":
    main()
