#!/usr/bin/env python3
"""自有信息流召回：先从用户自己长期筛过的信息流（Info2Action）里找相关原文，再做网页搜索。

用法：
  python3 own_feed_recall.py <research_notes/课题目录> --keywords 关键词1 关键词2 ... [--days 90] [--top 100]

关键词：从信息需求清单拆出 5—15 个，用品类名、产品名、公司名及中英文别名，**不要整句**。
  整句会让关键词检索失效（2026-10-11 实测：整句命中 0 条，「AI陪伴」命中 96 条）。

怎么排：每个关键词各召回一次，合并去重后自己重排，不用 Info2Action 的排序（它只按向量相似度排，
  只被关键词命中的条目会沉底）：两路都命中 > 只有关键词命中 > 只有向量命中且相似度 ≥ 0.5；
  同一层里，被越多关键词命中、相似度越高的越靠前。

输出（写到课题目录）：
  05-自有信源池.json  每条：排名、标题、URL、平台、作者、时间、命中关键词、AI 摘要、关键要点、原文、封面
  05-自有信源池.md    索引：研究员先读它，挑相关的再去 JSON 里读原文

连接方式：
  现在：本机 Info2Action 仓库 + 只读数据库连接（default_transaction_read_only=on、30 秒超时），
    不建搜索任务、不占额度、不调写作模型。仓库位置取环境变量 INFO2ACTION_REPO，
    默认 ~/claudecode_workspace/项目/info2action。
  以后：Info2Action 提供带密钥的接口后改走接口，密钥放环境变量或 ~/.config/deep-survey/secrets.env，
    不写进 skill、报告和笔记。

退出码：0 成功；3 不可用（找不到仓库、凭证或连接失败）→ 协调者跳过这一步，在「口径与来源」注明没用上。
"""
import contextlib
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_REPO = Path.home() / "claudecode_workspace" / "项目" / "info2action"
VECTOR_SIM_MIN = 0.5


def arg_list(argv, name):
    if name not in argv:
        return []
    i = argv.index(name) + 1
    out = []
    while i < len(argv) and not argv[i].startswith("--"):
        out.append(argv[i])
        i += 1
    return out


def arg_val(argv, name, default):
    return argv[argv.index(name) + 1] if name in argv else default


def unavailable(msg):
    print(f"不可用：{msg}。跳过自有信息流召回，在报告「口径与来源」注明。")
    return 3


def connect_readonly(repo: Path):
    """接管 Info2Action 的连接函数，改成只读连接。返回 (ai_search 模块, 关闭函数)。"""
    env = repo / ".env"
    if not env.exists():
        raise RuntimeError(f"{env} 不存在")
    url = None
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("SUPABASE_DB_URL="):
            url = line.split("=", 1)[1].strip().strip("'\"")
    if not url:
        raise RuntimeError(".env 里没有数据库地址")
    sys.path.insert(0, str(repo / "src"))
    os.chdir(repo)
    import psycopg  # noqa: E402
    from psycopg.rows import dict_row  # noqa: E402
    from remote_db import _core  # noqa: E402
    from remote_db import ai_search  # noqa: E402

    @contextlib.contextmanager
    def ro_connect():
        conn = psycopg.connect(re.sub(r":\d+/", ":5432/", url, count=1), row_factory=dict_row, connect_timeout=15,
                               options="-c statement_timeout=30000 -c default_transaction_read_only=on")
        try:
            yield conn
        finally:
            conn.rollback()
            conn.close()

    _core.connect = ro_connect
    ai_search._core.connect = ro_connect
    return ai_search


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 2
    out_dir = Path(argv[0]).resolve()
    keywords = arg_list(argv, "--keywords")
    if not keywords:
        print("缺 --keywords：从信息需求清单拆 5—15 个关键词")
        return 2
    long_kw = [k for k in keywords if len(re.findall(r"[\u4e00-\u9fff]", k)) > 10 or len(k.split()) > 4]
    if long_kw:
        print(f"提示：这些关键词像整句，关键词检索可能失效：{long_kw}")
    days = int(arg_val(argv, "--days", 90))
    top = int(arg_val(argv, "--top", 100))
    repo = Path(os.environ.get("INFO2ACTION_REPO", DEFAULT_REPO)).expanduser()
    if not (repo / "src" / "remote_db" / "ai_search.py").exists():
        return unavailable(f"找不到 Info2Action 仓库（{repo}）")
    cwd = os.getcwd()
    try:
        search = connect_readonly(repo)
    except Exception as exc:  # noqa: BLE001
        return unavailable(f"连接准备失败：{exc}")

    pool: dict[str, dict] = {}
    per_kw = []
    vec_ok = False
    for kw in keywords:
        try:
            r = search.retrieve(kw, window_days=days, max_items=5000)
        except Exception as exc:  # noqa: BLE001
            os.chdir(cwd)
            return unavailable(f"检索「{kw}」失败：{exc}")
        kept = 0
        for it in r["items"]:
            legs = set(it.get("legs") or [])
            sim = it.get("sim") or 0.0
            if legs == {"vector"} and sim < VECTOR_SIM_MIN:
                continue
            key = str(it["id"])
            e = pool.setdefault(key, {"id": key, "legs": set(), "sim": 0.0, "keywords": []})
            e["legs"] |= legs
            e["sim"] = max(e["sim"], sim)
            e["keywords"].append(kw)
            kept += 1
        per_kw.append((kw, r.get("lexical_hits", 0), r.get("vector_hits", 0), kept))
        vec_ok = vec_ok or bool(r.get("vector_ok"))

    def tier(e):
        if {"lexical", "vector"} <= e["legs"]:
            return 0
        return 1 if "lexical" in e["legs"] else 2

    ranked = sorted(pool.values(), key=lambda e: (tier(e), -len(e["keywords"]), -e["sim"]))[:top]
    try:
        full = search.get_candidates([e["id"] for e in ranked], full_text=True)
    except Exception as exc:  # noqa: BLE001
        os.chdir(cwd)
        return unavailable(f"取回原文失败：{exc}")
    os.chdir(cwd)
    by_id = {str(x["id"]): x for x in full}

    tier_name = {0: "两路命中", 1: "关键词命中", 2: "向量命中"}
    items = []
    for e in ranked:
        x = by_id.get(e["id"])
        if not x:
            continue
        content = x.get("content") or ""
        items.append({
            "rank": len(items) + 1,
            "title": re.sub(r"\s+", " ", x.get("title") or "").strip(),
            "url": x.get("url") or "",
            "platform": x.get("platform") or "",
            "source": x.get("source") or "",
            "author": x.get("author_name") or "",
            "published_at": str(x.get("published_at") or "")[:10],
            "hit": tier_name[tier(e)],
            "keywords": e["keywords"],
            "similarity": round(e["sim"], 3),
            "ai_summary": x.get("ai_summary") or "",
            "ai_key_points": x.get("ai_key_points") or "",
            "content_chars": len(content),
            "content": content,
            "cover_url": x.get("cover_url") or "",
            "media": x.get("media_json") or None,
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "05-自有信源池.json").write_text(json.dumps(items, ensure_ascii=False, indent=1, default=str),
                                             encoding="utf-8")
    md = ["# 自有信源池（Info2Action 召回）", "",
          f"关键词 {len(keywords)} 个，近 {days} 天，取前 {top} 条，实得 {len(items)} 条。"
          "研究员先读这份索引，相关的去同名 JSON 里读原文（content 字段）。引用时照常写标题和 URL，行尾加「自有信源」。"
          "平台是 lingowhale 的是公众号文章：链接是语鲸阅读器，外人要登录才能看，引用时写成「公众号「作者」《标题》」，"
          "核查以 JSON 里的原文为准。", "",
          "| 关键词 | 关键词命中 | 向量命中 | 进池 |", "|---|---|---|---|"]
    md += [f"| {k} | {lx} | {vx} | {kept} |" for k, lx, vx, kept in per_kw]
    md += [""]
    for it in items:
        summ = re.sub(r"\s+", " ", it["ai_summary"])[:120]
        md.append(f"{it['rank']}. **{it['title'][:60]}** — {it['author']} · {it['platform']} · {it['published_at']} · "
                  f"{it['hit']}：{'、'.join(it['keywords'])} · 原文 {it['content_chars']} 字")
        md.append(f"   {summ}")
        md.append(f"   {it['url']}")
    (out_dir / "05-自有信源池.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    long_n = sum(1 for it in items if it["content_chars"] >= 1500)
    if not vec_ok:
        print("注意：向量检索没跑通（Info2Action 的嵌入接口不可用），这次只有关键词命中；多给几个别名关键词补召回。")
    print(f"ok  自有信源池 {len(items)} 条（原文 ≥1500 字 {long_n} 条）→ {out_dir / '05-自有信源池.md'}")
    for k, lx, vx, kept in per_kw:
        print(f"  {k}：关键词 {lx}，向量 {vx}，进池 {kept}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
