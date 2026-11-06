#!/usr/bin/env python3
"""把改好的稿子交给 Gemini 再改一遍。

用法：python3 gemini_revise.py <2-改稿.md> <3-gemini改稿.md> [--model 模型名] [--thinking high|low] [--web]

- --web：不调 API，只写 给Gemini网页.md，给作者贴进 Gemini 网页用。

- prompt 取 references/gemini改稿.md 里第一个 ``` 代码块，文章接在它后面。
- key：环境变量 GEMINI_API_KEY，没有就读 ~/.config/gemini/api_key。
- 代理：环境变量 GEMINI_PROXY，默认 http://127.0.0.1:7897；设成空字符串就直连。
- 模型默认 gemini-4-argon，思考强度默认 high。换 gemini-3.8-flash 这类免费层级模型时，额度每天约 20 次，失败的请求也算次数。
- 服务忙（500、503）一共试 3 次，每次隔 30 秒；额度用完（429）和其他错误不重试。
- 发出去的全文（prompt 加文章）存成同目录的 发给Gemini的全文.md。
- 回复按「===改动说明===」那一行切开：前面的全文写进输出文件，后面写进同目录的 gemini改动说明.md。
- 调不通时，在输出文件旁边写一份 给Gemini网页.md（prompt 加文章），退出码 2。
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
PROMPT_FILE = SKILL / "references" / "gemini改稿.md"
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MARK = "===改动说明==="
TRIES = 3
WAIT = 30


def load_prompt():
    text = PROMPT_FILE.read_text()
    m = re.search(r"```\n(.*?)\n```", text, re.S)
    if not m:
        sys.exit(f"没在 {PROMPT_FILE} 里找到 ``` 代码块")
    return m.group(1).strip()


def load_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        f = Path.home() / ".config" / "gemini" / "api_key"
        if f.exists():
            key = f.read_text().strip()
    return key


def call(model, key, text, thinking):
    proxy = os.environ.get("GEMINI_PROXY", "http://127.0.0.1:7897")
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})]
    opener = urllib.request.build_opener(*handlers)
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {"maxOutputTokens": 32768, "thinkingConfig": {"thinkingLevel": thinking}},
    }).encode()
    req = urllib.request.Request(
        API.format(model=model), data=body, method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    with opener.open(req, timeout=900) as r:
        data = json.loads(r.read())
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def strip_fence(s):
    s = s.strip()
    m = re.match(r"^```[a-zA-Z]*\n(.*)\n```$", s, re.S)
    return m.group(1).strip() if m else s


def main():
    args = [a for a in sys.argv[1:]]
    model = "gemini-4-argon"
    thinking = "high"
    if "--thinking" in args:
        i = args.index("--thinking")
        thinking = args[i + 1]
        del args[i:i + 2]
    web_only = "--web" in args
    if web_only:
        args.remove("--web")
    if "--model" in args:
        i = args.index("--model")
        model = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    src, dst = Path(args[0]), Path(args[1])
    prompt = load_prompt()
    full = prompt + "\n\n" + src.read_text().strip() + "\n"
    web = dst.parent / "给Gemini网页.md"
    (dst.parent / "发给Gemini的全文.md").write_text(full)

    def give_up(reason):
        web.write_text(full)
        print(f"没调通：{reason}")
        print(f"已写好 {web}，整段复制进 Gemini 网页，结果贴回来存成 {dst}")
        sys.exit(2)

    if web_only:
        web.write_text(full)
        print(f"已写好 {web}，整段复制进 Gemini 网页，结果贴回来存成 {dst}")
        return

    key = load_key()
    if not key:
        give_up("没有 key（GEMINI_API_KEY 或 ~/.config/gemini/api_key）")

    reply = None
    for n in range(1, TRIES + 1):
        try:
            reply = call(model, key, full, thinking)
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="ignore")[:300]
            if e.code in (500, 503) and n < TRIES:
                print(f"第 {n} 次 {e.code}，服务忙，{WAIT} 秒后重试")
                time.sleep(WAIT)
                continue
            if e.code == 429:
                give_up(f"429，免费额度用完了。{msg}")
            give_up(f"HTTP {e.code}。{msg}")
        except Exception as e:  # 网络、超时、回复格式不对
            give_up(f"{type(e).__name__}: {e}")
    if reply is None:
        give_up("重试用完")

    if MARK in reply:
        article, notes = reply.split(MARK, 1)
    else:
        article, notes = reply, ""
        print(f"回复里没有「{MARK}」，全部当正文写进去了，改动说明要从末尾自己分出来")
    dst.write_text(strip_fence(article) + "\n")
    (dst.parent / "gemini改动说明.md").write_text(notes.strip() + "\n")
    print(f"模型 {model}，思考强度 {thinking}，正文写进 {dst}，改动说明写进 {dst.parent / 'gemini改动说明.md'}")


if __name__ == "__main__":
    main()
