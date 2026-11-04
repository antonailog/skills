#!/usr/bin/env python3
"""查小红书文字稿：标题字数、正文加标签字数、网址和引流 / 限流词、正文里写的场数和数据对不对。

用法：python3 -I check_xhs_text.py <文案.md> <小红书.json>

文案.md 里每一套以「**标题…**」开头（下面是「1. 」这样编号的标题候选），「**正文**」到「**标签**」之间是正文，
「**标签**」后第一段是标签行。可以有好几套（清单版、重点版）：新的「## 」一节、或者又一个「**正文**」都算新的一套，
没有自己标题块的那套只查正文和标签。读到「## 核实记录」为止。
先打印从 JSON 算出的统计（写正文时照抄），再逐条打印问题。没有问题退出 0，有问题退出 1。
"""
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

TITLE_MAX, TEXT_MAX = 20, 1000           # 小红书标题 20 字、正文连标签 1000 字，中英文标点空格都算 1
TAGS_MIN, TAGS_MAX = 3, 10
# 网址：和 make_xhs.py 的 URL 正则一致（那边加载时要 import playwright，这里只用标准库，复制一份）
URL = re.compile(r"(?:https?://|www\.)[^\s<>\"'，。；！？）]+|"
                 r"(?<![\w@])(?:[a-z0-9-]+\.)+(?:com|cn|net|org|io|ai|app|dev|co|me|xyz|top|site)"
                 r"\b(?:/[^\s<>\"'，。；！？）]*)?", re.I)
# 引流：平台判成把人往站外、私域带，笔记会被限流甚至删
LEAD = ["二维码", "扫码", "私信", "加微信", "微信号", "加群", "进群", "联系方式", "手机号"]
LEAD_RE = re.compile(r"(?<![A-Za-z])vx(?![A-Za-z])", re.I)
# 限流：营销腔和绝对化的词，平台会降权，读者也会当成广告划走
HYPE = ["震惊", "必看", "不看后悔", "全网第一", "史上最", "建议收藏", "码住", "干货满满", "绝绝子", "家人们", "宝子们"]


def stats(spec):
    evs = spec["events"]
    city = Counter("线上" if e.get("form") == "线上" else e["city"] for e in evs)
    free = sum(1 for e in evs if (e.get("price") or "").startswith("免费") or e.get("price") in ("普通票免费", "全程免费"))
    days = Counter(e["day"] for e in evs)
    weekend = sum(n for d, n in days.items() if dt.date.fromisoformat(d).weekday() >= 5)
    return {"total": len(evs), "city": city, "free": free, "weekend": weekend, "days": days}


def sets_of(text):
    """按「**标题」切成几套；每套带上它前面最近的二级标题当名字"""
    text = text.split("\n## 核实记录")[0]
    lines = text.splitlines()
    out, h2, cur, mode = [], "", None, None
    for line in lines:
        s = line.strip()
        if s.startswith("## "):
            h2 = re.split(r"[（(]", s[3:])[0].strip()
            cur, mode = None, None   # 新的一节就是新的一套，没有自己的标题块也不并进上一套
            continue
        if s.startswith("**标题"):
            cur = {"name": h2 or f"第 {len(out) + 1} 套", "titles": [], "body": [], "tags": []}
            out.append(cur)
            h2, mode = "", "titles"
            continue
        if s == "**正文**" and (cur is None or cur["body"]):
            cur = {"name": h2 or f"第 {len(out) + 1} 套", "titles": [], "body": [], "tags": []}
            out.append(cur)
            h2 = ""
        if cur is None:
            continue
        if s == "**正文**":
            mode = "body"
            continue
        if s == "**标签**":
            mode = "tags"
            continue
        if mode == "titles":
            if s.startswith("**"):
                mode = None
            else:
                m = re.match(r"\d+[.、]\s*(.+)$", s)
                if m:
                    cur["titles"].append(m.group(1).strip())
        elif mode == "body":
            cur["body"].append(line)
        elif mode == "tags":
            if s.startswith(("---", "**")):
                mode = None
            elif s:
                cur["tags"].append(s)
            elif cur["tags"]:
                mode = None
    for c in out:
        c["body"] = "\n".join(c["body"]).strip()
        c["tags"] = " ".join(c["tags"]).strip()
    return out


def check_words(where, text, issues):
    for m in URL.finditer(text):
        issues.append(f"{where}：有网址「{m.group(0)}」")
    for w in LEAD:
        if w in text:
            issues.append(f"{where}：有引流词「{w}」")
    if LEAD_RE.search(text):
        issues.append(f"{where}：有引流词「vx」")
    for w in HYPE:
        if w in text:
            issues.append(f"{where}：有营销 / 限流词「{w}」")


NOT_EVENTS = r"(?!\s*(?:演讲|分享|圆桌|论坛|报告|对话|讲座|课|比赛|直播|路演|主题|专场))"


def check_counts(where, text, st, issues, whole=False):
    """只核对认得出的几种写法；「51 场演讲」「限 10 人」「第 200 期」这类不是场数，不管。
    标题整条查（「上海AI人这周去哪？12场排好了」不能在问号处切开），正文按句查"""
    cities = "|".join(sorted(map(re.escape, st["city"]), key=len, reverse=True))
    day_ns = set(st["days"].values())
    for sent in ([text] if whole else re.split(r"[。！？!?\n]", text)):
        found = []
        for pat in (r"(?:共|一共|这周有|这周|本周有|本周)\s*(\d+)\s*场", r"(\d+)\s*场\s*(?:AI\s*)?(?:线下)?活动", r"｜\s*(\d+)\s*场",
                    r"活动[，,]\s*(\d+)\s*场(?!\s*(?:可以)?免费)"):
            found += [int(m.group(1)) for m in re.finditer(pat + NOT_EVENTS, sent)]
        dated = re.search(r"\d{1,2}/\d{1,2}|周末|当天|其中", sent)
        for n in sorted(set(found)):
            if n == st["total"] or any(st["city"].get(c) == n for c in st["city"] if c in sent):
                continue
            if dated and (n in day_ns or n == st["weekend"]):   # 「11/5 当天 6 场」「周末 10 场活动」说的是那几天
                continue
            issues.append(f"{where}：写了 {n} 场，数据里共 {st['total']} 场（「{sent.strip()[:30]}」）")
        if cities:   # 城市后面紧跟的数字，后面只能是「场」、顿号、逗号或句尾，才算这个城市的场数
            for m in re.finditer(rf"({cities})(?:有|共)?\s*(\d{{1,3}})(?=\s*(?:场|、|，|,|；|。|）|$))", sent):
                c, n = m.group(1), int(m.group(2))
                if st["city"][c] != n:
                    issues.append(f"{where}：写了「{c} {n}」，数据里{c} {st['city'][c]} 场")
        for pat in (r"(\d+)\s*场\s*(?:可以)?免费", r"免费的有\s*(\d+)\s*场", r"免费\s*(\d+)\s*场"):
            for m in re.finditer(pat, sent):
                if int(m.group(1)) != st["free"]:
                    issues.append(f"{where}：写了 {m.group(1)} 场免费，数据里免费 {st['free']} 场")
        for m in re.finditer(r"周末(?:两天)?(?:有|共)?\s*(\d+)\s*场", sent):
            if int(m.group(1)) != st["weekend"]:
                issues.append(f"{where}：写了周末 {m.group(1)} 场，数据里周末 {st['weekend']} 场")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 0 if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help") else 1
    try:
        text = Path(sys.argv[1]).read_text(encoding="utf-8")
        spec = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        st = stats(spec)
    except (OSError, ValueError, KeyError) as ex:
        print(f"读不了输入：{ex}")
        return 1
    city = "、".join(f"{c} {n}" for c, n in sorted(st["city"].items(), key=lambda x: (x[0] != "北京", x[0] == "线上", -x[1])))
    days = "、".join(f"{int(d[5:7])}/{int(d[8:10])} {n}" for d, n in sorted(st["days"].items()))
    print(f"统计：共 {st['total']} 场；{city}；免费 {st['free']} 场；周末 {st['weekend']} 场\n  每天：{days}")
    sets = sets_of(text)
    if not sets:
        print("文案.md 里没找到「**标题…**」开头的一套，没法检查")
        return 1
    issues = []
    for s in sets:
        name = s["name"]
        if not any(x["titles"] for x in sets) and s is sets[0]:
            issues.append(f"[{name}] 没有标题候选")
        if not s["body"]:
            issues.append(f"[{name}] 没有正文")
        for k, t in enumerate(s["titles"], 1):
            if len(t) > TITLE_MAX:
                issues.append(f"[{name}] 标题 {k}：{len(t)} 字，超了 {len(t) - TITLE_MAX} 字（{t}）")
            check_words(f"[{name}] 标题 {k}", t, issues)
            check_counts(f"[{name}] 标题 {k}", t, st, issues, whole=True)
        n = len(s["body"]) + 1 + len(s["tags"])
        print(f"[{name}] 标题 {len(s['titles'])} 个，正文 {len(s['body'])} 字 + 标签 {len(s['tags'])} 字 = {n} 字")
        if n > TEXT_MAX:
            issues.append(f"[{name}] 正文加标签 {n} 字，超了 {n - TEXT_MAX} 字")
        check_words(f"[{name}] 正文", s["body"], issues)
        check_counts(f"[{name}] 正文", s["body"], st, issues)
        check_words(f"[{name}] 标签", s["tags"], issues)
        tags = s["tags"].split()
        if not TAGS_MIN <= len(tags) <= TAGS_MAX:
            issues.append(f"[{name}] 标签 {len(tags)} 个，要在 {TAGS_MIN}–{TAGS_MAX} 个之间")
        for t in tags:
            if not t.startswith("#") or len(t) < 2:
                issues.append(f"[{name}] 标签「{t}」要以 # 开头，中间不留空格")
    print("文字检查：" + (f"{len(issues)} 处要看" if issues else "没有问题"))
    for x in issues:
        print("  - " + x)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
