#!/usr/bin/env python3
"""对照两版稿子：别的模型改完的，和改之前的。只报数，不改文。

用法：python3 compare_revision.py <改之前.md> <改之后.md>

列出：
- 少了的图、视频、二维码，原文的标题、第一句和最后三行在不在；
- 改之后新出现的数字、英文名字、「」里的说法、括号里的话、程度词；
- 两版并排的字数、段数、一句一段的比例、每千字「我」「你」；
- 最后对改之后那版跑 check_prose.py。
新出现的东西不一定是错的，要回原文和材料核对。
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEDIA = re.compile(r"^\s*(\[(?:图|视频)\d+\]|\[公众号二维码\]|!\[[^\]]*\]\([^)]*\)|<video[^>]*>.*?</video>)\s*$")
DEGREE = ["很火", "重点", "全部", "所有", "首个", "唯一", "非常", "特别", "一定", "完全", "绝对", "最好", "最大", "最多", "最火"]


def read(p):
    return Path(p).read_text()


def paras(text):
    return [l.strip() for l in text.splitlines() if l.strip() and l.strip() != "---"]


def body(text):
    return [p for p in paras(text) if not MEDIA.match(p) and not p.startswith("#")]


def media(text):
    out = []
    for p in paras(text):
        m = MEDIA.match(p)
        if m:
            s = m.group(1)
            n = re.search(r"\[(图\d+|视频\d+|公众号二维码)\]", s) or re.search(r"!\[([^\]]*)\]", s)
            out.append(n.group(1) if n else s)
    return out


def stats(text):
    ps = body(text)
    joined = "".join(ps)
    n = len(re.sub(r"\s", "", joined)) or 1
    one = sum(1 for p in ps if len(re.findall(r"[。？！?!]", p.rstrip("。？！?!*"))) == 0)
    wo = len(re.findall(r"我(?!们)", joined))
    ni = len(re.findall(r"你", joined))
    return {
        "字数": n,
        "段数": len(ps),
        "一句一段": f"{one * 100 // max(len(ps), 1)}%",
        "每千字「我」": f"{wo * 1000 / n:.1f}（{wo}）",
        "每千字「你」": f"{ni * 1000 / n:.1f}（{ni}）",
    }


def tokens(text, pattern):
    return re.findall(pattern, "\n".join(body(text)))


def ctx(text, tok, width=18):
    t = "\n".join(body(text))
    i = t.find(tok)
    return t[max(0, i - width): i + len(tok) + width].replace("\n", " ") if i >= 0 else ""


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    a_path, b_path = sys.argv[1], sys.argv[2]
    a, b = read(a_path), read(b_path)

    print("## 少了的东西\n")
    lost = [m for m in media(a) if m not in media(b)]
    print("- 图和视频：" + ("、".join(lost) if lost else "都在"))
    pa, pb = paras(a), paras(b)
    pa_text = [p for p in pa if not MEDIA.match(p)]
    keep = []
    if pa_text:
        keep.append(("标题", pa_text[0]))
    first = next((p for p in pa_text[1:] if not p.startswith("#")), None)
    if first:
        keep.append(("第一句", first.split("。")[0] + "。"))
    for p in pa_text[-3:]:
        keep.append(("结尾", p))
    flat_b = "\n".join(pb)
    for name, s in keep:
        if s.lstrip("# ").strip() not in flat_b:
            print(f"- {name}变了或没了：{s[:60]}")
    print()

    print("## 改之后新出现的\n")
    checks = [
        ("数字", r"\d+(?:\.\d+)?|[一二两三四五六七八九十]+[十百千万][多余]?"),
        ("英文名字", r"[A-Za-z][A-Za-z0-9.\-]+"),
        ("「」里的说法", r"「[^」]{1,20}」"),
        ("括号里的话", r"[（(][^）)]{1,40}[）)]"),
    ]
    for name, pat in checks:
        olds = set(tokens(a, pat))
        news = []
        for t in tokens(b, pat):
            if t not in olds and t not in news:
                news.append(t)
        if news:
            print(f"- {name}：")
            for t in news[:15]:
                print(f"  - {t}　…{ctx(b, t)}…")
    ja, jb = "".join(body(a)), "".join(body(b))
    more = [f"{w} {ja.count(w)}→{jb.count(w)}" for w in DEGREE if jb.count(w) > ja.count(w)]
    if more:
        print("- 程度词变多：" + "，".join(more))
    print()

    print("## 并排\n")
    sa, sb = stats(a), stats(b)
    print("| | 改之前 | 改之后 |\n|---|---|---|")
    for k in sa:
        print(f"| {k} | {sa[k]} | {sb[k]} |")
    print()

    print("## check_prose（改之后）\n")
    r = subprocess.run([sys.executable, str(HERE / "check_prose.py"), b_path], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())


if __name__ == "__main__":
    main()
