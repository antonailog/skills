#!/usr/bin/env python3
"""知乎搜索：调知乎数据开放平台的官方搜索接口，拿回答和文章的摘要、赞同数、作者认证。

用法：
  python3 zhihu_search.py "关键词" [--min-vote 0] [--json]

为什么要这个脚本：知乎页面不登录时直接抓全部 403（curl、WebFetch、无头浏览器都一样，2026-10-11 实测），
  搜狗知乎搜索进反爬页，公共 RSSHub 被拦。官方接口是唯一稳定的不登录通道。

密钥：先读环境变量 ZHIHU_ACCESS_SECRET，没有再读 ~/.config/deep-survey/secrets.env。
  密钥由用户在 developer.zhihu.com 注册后生成；不写进 skill、报告和笔记。
  没有密钥时退出码 3：改用 WebSearch 限定 zhihu.com，只能拿到标题和链接，正文不可读，不能当结论依据。

怎么查：同一个关键词按「相关度」和「赞同数」各查一次（每次最多 10 条，接口不能翻页），合并去重。
  只按赞同数排会混进带货帖（实测「AI陪伴」赞同前三里有两条是硬件带货），所以两种都查，
  并给疑似带货的条目打标记，不自动删。
  每次运行算 2 次搜索。

输出：每条一行可直接贴进笔记的引用（标题 — 作者（认证）· 赞同 · 日期 · URL），下一行是摘要。
  --json 输出原始字段。
退出码：0 成功；3 没有密钥；1 接口报错。
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://developer.zhihu.com/api/v1/content/zhihu_search"
SECRETS = Path.home() / ".config" / "deep-survey" / "secrets.env"
AD_WORDS = ("京东", "淘宝", "天猫", "拼多多", "下单", "到手价", "优惠券", "入手", "种草", "618", "双11", "双十一",
            "好物", "测评推荐", "购买链接", "折扣", "领券")


def secret():
    v = os.environ.get("ZHIHU_ACCESS_SECRET")
    if v:
        return v.strip()
    if SECRETS.exists():
        for line in SECRETS.read_text(encoding="utf-8").splitlines():
            if line.startswith("ZHIHU_ACCESS_SECRET="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return None


def call(key, query, sort=None):
    params = {"Query": query, "Count": 10}
    if sort:
        params["SortBy"] = sort
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers={
        "Authorization": "Bearer " + key, "X-Request-Timestamp": str(int(time.time())),
        "User-Agent": "deep-survey/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read().decode("utf-8"))
    if d.get("Code") not in (0, None):
        raise RuntimeError(f"接口返回 {d.get('Code')}：{d.get('Message')}")
    data = d.get("Data") or {}
    return data.get("Items") or []


def clean_url(u):
    p = urllib.parse.urlsplit(u or "")
    q = "&".join(x for x in p.query.split("&") if x and not x.startswith("utm_"))
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, q, ""))


def day(ts):
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return str(ts or "")[:10]


def main() -> int:
    a = sys.argv[1:]
    if not a or a[0].startswith("--"):
        print(__doc__)
        return 2
    query = a[0]
    min_vote = int(a[a.index("--min-vote") + 1]) if "--min-vote" in a else 0
    key = secret()
    if not key:
        print("没有知乎密钥（ZHIHU_ACCESS_SECRET）。改用 WebSearch 加 allowed_domains: zhihu.com，"
              "只拿标题和链接；正文读不到，不能当结论依据。")
        return 3
    merged: dict[str, dict] = {}
    for sort in (None, "VoteUpCount:desc"):
        try:
            items = call(key, query, sort)
        except urllib.error.HTTPError as e:
            print(f"接口报错 HTTP {e.code}：{e.read()[:200].decode('utf-8', 'ignore')}")
            return 1
        except Exception as e:  # noqa: BLE001
            print(f"接口报错：{e}")
            return 1
        for it in items:
            u = clean_url(it.get("Url"))
            e = merged.setdefault(u, dict(it, Url=u, _sorts=[]))
            e["_sorts"].append("相关度" if sort is None else "赞同数")
    rows = [x for x in merged.values() if (x.get("VoteUpCount") or 0) >= min_vote]
    for x in rows:
        text = (x.get("Title") or "") + (x.get("ContentText") or "")
        x["_ad"] = any(w in text for w in AD_WORDS)
    rows.sort(key=lambda x: (x["_ad"], -(x.get("VoteUpCount") or 0)))
    if "--json" in a:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    print(f"# 知乎搜索「{query}」：{len(rows)} 条（相关度、赞同数两种排序合并）\n")
    for x in rows:
        title = re.sub(r"\s*-\s*知乎\s*$", "", (x.get("Title") or "").strip())
        badge = x.get("AuthorBadgeText") or ""
        who = (x.get("AuthorName") or "匿名") + (f"（{badge}）" if badge else "")
        flag = " · 疑似带货" if x["_ad"] else ""
        kind = {"answer": "回答", "article": "文章", "question": "问题"}.get(str(x.get("ContentType", "")).lower(),
                                                                       x.get("ContentType") or "")
        summ = re.sub(r"\s+", " ", x.get("ContentText") or "")[:160]
        print(f"- {title} — 知乎{kind} · {who} · 赞同 {x.get('VoteUpCount', 0)} · 评论 {x.get('CommentCount', 0)}"
              f"（{x['Url']}，{day(x.get('EditTime'))}）{flag}")
        print(f"  摘要：{summ}")
    print("\n知乎条目只有摘要：摘要能撑住的事实可以引用并注明「知乎摘要」；要用全文的观点，先请用户在自己浏览器里打开确认。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
