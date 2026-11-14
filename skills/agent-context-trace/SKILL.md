---
name: agent-context-trace
description: 看清 Claude Code 一次运行到底加载了什么、按什么顺序做了什么：圈出影响某个产出的那段 agent 链路（主 Agent、子 Agent），从本机会话记录还原每个 Agent 的上下文（系统提示词、工具定义、自动带上的 CLAUDE.md 和记忆、任务提示词）、读过的文件和图片、执行的命令、写出的文件，出一个本地 trace 页面。用户在调 skill 或 prompt，说「看看它加载了啥」「看下这次运行的 trace / 链路」「子 agent 读到我改的 SKILL.md 没有」「references 哪些没读」「派下去的 prompt 原文是什么」「写这段之前它读了什么」时用；哪怕他只是嘀咕「它怎么没照 skill 做」「是不是没读到」，也用。不处理：token 和花费统计、会话复盘（forge-fupan）、改 skill 本身（skill-build）、Codex 作业进度（codex-delegate）。
---

# agent-context-trace — 看清一次运行加载了什么

交付一个本地 HTML 页面，加回复里不超过 3 行事实。

## 定位与边界

像调试器的变量面板：把「它当时手里到底有什么、先后做了什么」原样摆出来，作者自己判断该改 skill 还是改 prompt。

作者要的是证据，不是结论。页面和回复只放原文和客观事实（第几轮进来、怎么进来的、读全没读全、和现在的文件一不一致），不打分、不替他下「该怎么改」的判断。替他下了结论，他就得先怀疑结论，再回头翻原文。

只认 Claude Code 的会话记录，而且要带完整请求的那种（VS Code 扩展 2.1.301 起）。

## S1 定范围

把用户的话换成脚本参数。三种圈法可以叠加。命令里直接写完整路径，不要先存进变量：权限检查看不懂变量，无界面会话会卡在那里。

| 用户说的 | 参数 |
|---|---|
| 点名一个产出文件（「刚才写的文章.md」「这篇稿子」） | `--from-output <文件>`：脚本自己找写它的 Agent，补上派活的上游和写了它读过文件的其他子 Agent |
| 点名 agent（「写稿的那个子 agent」「刚才那个子 agent」） | 先 `list --grep <词> --since <日期>` 找候选，再 `--node <jsonl>` |
| 说的是文件或 skill（「SKILL.md 读到没有」「references 哪些没读」） | `--focus <文件或目录>`；说的是 skill 名，就用 `~/.claude/skills/<名>` 软链指向的真实目录 |

「刚才」「最近一次」按今天的会话找。候选只有一个就直接出；有几个说得通的，列出来（会话标题、Agent 描述、时间、轮数）问一句，不要猜一个就出：范围错了，页面再好看也是看错了东西。

```bash
python3 -I ~/.claude/skills/agent-context-trace/scripts/trace.py list --since 2026-11-03 --grep 文章
python3 -I ~/.claude/skills/agent-context-trace/scripts/trace.py find --file <产出文件>
```

## S2 出页面

```bash
python3 -I ~/.claude/skills/agent-context-trace/scripts/trace.py build <S1 的参数> -o ~/claude-context-trace/<2026-11-05-0501 这样的日期时分>-<范围名>.html
python3 -I ~/.claude/skills/agent-context-trace/scripts/trace.py data <S1 的参数> --tree     # 同一结构的文字版，用来写回复、回答追问
```

用户给了位置就用他的。位置在某个 git 仓库里面时先问一句，页面里的私人内容不能被顺手提交。页面模板在 `assets/`（viewer.html/js/css 和内联的 markdown-it、OverlayScrollbars），build 时整个打包进一个离线文件，出页面不用动它。

页面的结构（用户问「在哪看」时照这个指给他）：

- 左栏：Agent → 上下文 → 段「N 次操作 → 写入 X」→ 每次操作。段 = 两次写入文档之间的所有操作加结尾那次写入；调用子 Agent 的段下面直接挂着子 Agent。连着的执行、列出、代码文件读写折成「代码与命令 ×N」。橙红色文件名是用户自己的文件或改过的文件。
- 用 Skill 工具调起的 skill，它的 SKILL.md 记成一次「读取」，方式写 Skill。
- 点一行：中间看原文，最下面是那一轮的模型、时间和模型说的话。点段：看写出的内容和写之前上下文里有什么。
- 点原文里的文件名：右栏看全文，左栏同时定位它出现的每一处。目录点开用 VS Code 打开。
- Command+点击或右键「在 Finder 中显示」要本机装一次小程序（`scripts/finder-handler/install.sh`，卸载用同目录 `uninstall.sh`）。没装时先问用户要不要装，不替他装。

## S3 回复

```
页面：<绝对路径>
<最多 3 行事实>
```

事实从 `--tree` 和页面数据里挑，按这个顺序，有就写，没有就少写：关注文件读没读、读了全文还是一部分、和现在的文件一不一致 → 被截断只看到开头的读 → Agent 数、轮数、上下文首末 tokens。只写看到的事实，不加「建议你改」。

## 失败时

| 情况 | 怎么办 |
|---|---|
| 记录里没有完整请求（终端旧版 claude） | 直接说这份记录不支持和原因，建议在 VS Code 扩展里重跑；不拿残缺数据拼一个页面 |
| 找不到写这个产出的操作 | 说找过哪些会话、哪段时间，请用户给会话或 Agent |
| 有消息对不上哈希 | 页面照出，回复里写对不上几条 |

## 红线

1. **页面和数据只留本机**。里面有 CLAUDE.md、记忆原文，还可能有命令里的密钥明文。不上传、不发布成 Artifact、不贴进飞书或 GitHub。
2. **会话记录只读**。`~/.claude/` 下的任何文件都不改、不挪。
