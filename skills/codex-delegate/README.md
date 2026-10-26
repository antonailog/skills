# codex-delegate

派活给 Codex，Claude 验收

## 要解决的问题

代码交给 Codex 写、Claude 负责编排和验收时，没有这个 Skill，每次派活都要手拼二进制路径、代理和 stdin 参数，靠翻会话文件判断 Codex 还活着没有；返工要重开会话，让 Codex 从头读一遍仓库。验收只能靠 Claude 自觉，只看 diff 就会漏掉根本没做的任务。

## 运行方式

![codex-delegate 结构图](../../docs/diagrams/codex-delegate.jpg)

Claude 写好任务书，用 `delegate.sh` 把活交给后台的 Codex；Codex 只在沙箱里改文件，不提交、不推送。验收不过就写返工意见发回原会话，Codex 带着上一轮的上下文改，最多两轮，还不过由 Claude 收回自己改，通过后由 Claude 提交。另有一个只读入口用于仲裁：结论有争议时，Claude 先封存自己的答案，再让 Codex 盲解同一道题，两份对比后裁定。

## 关键设计

把代码交给 Codex 写，要同时做到两件事：活在后台跑、进度随时查得到，交回来的改动又经得起逐条验收。codex-delegate 让 Claude 当总包，负责写任务书、验收和提交，Codex 只在沙箱里改文件；两边靠一个个后台作业接力，每个作业在任务所在的 worktree 里留一个目录，任务书、改动前的基线、事件日志和最终回复都存在里面。

- **Claude 签字的依据是任务书里的验收标准**：任务书照 `references/packet.md` 的模板写背景、一句话任务、可二值判断的验收标准、范围和收尾要求，写不出可验证的标准就退回重拆。验收时逐条对照这些标准、读完整改动、亲自跑门禁，做法在 `references/acceptance.md`。
- **每个作业留一个目录当证据**：`delegate.sh` 派活时为作业建目录，存下任务书、改动前的基线、事件日志、错误输出和最终回复；收结果时对照基线算出改动，没有改动或沙箱拦了写入都会直接标出来，再按三种原因分别处理。
- **作业死活看事件日志来判**：`delegate.sh` 按事件流把作业分成启动中、启动卡死、运行中、静默、完成、失败、已取消；每种状态怎么处理列在 `references/acceptance.md` 的判活表里，静默时先读最后一个事件和错误输出再决定。脚本改过要跑 `selftest.sh`，它用一个假的 Codex 把这些状态逐一过一遍。
- **返工意见一条对应一个可复现的事实**：返工发回原会话，Codex 已经有上一轮的背景，意见只写哪条标准没过、观察到什么、怎么复现，以及哪些部分保持不变；模板在 `references/acceptance.md`。
- **仲裁的两份答案互不知情**：Claude 先把自己的结论写进文件封存，再给 Codex 一份只含问题和中立证据的题面，以只读模式派出；题面带了任何一方的倾向就重写重派，要补证据也开新作业，规则在 `references/arbiter.md`。

```text
codex-delegate/
├── SKILL.md            预检到提交的流程、意图分流、小结格式
├── references/
│   ├── packet.md       任务书模板和写法要点
│   ├── acceptance.md   判活表、验收、返工意见、何时收回
│   └── arbiter.md      盲解仲裁：封存答案、写题面、防污染
├── scripts/
│   ├── delegate.sh     后台作业：派活、判活、收结果、返工
│   └── selftest.sh     用假的 Codex 自测 delegate.sh
└── examples/
    └── pomodoro/       例子：番茄钟网页里派给 Codex 的代码任务
```

## 其他

- 前提：宿主是 Claude Code；本机装有 Codex CLI，默认找 ChatGPT 桌面版自带的那份，可用 `CODEX_DELEGATE_BIN` 指定；任务在 git worktree 里做
- 注意：脚本默认让 Codex 走本机代理，网络环境不同要设 `CODEX_DELEGATE_PROXY`；每个会话第一次派活前先跑 `delegate.sh doctor`
- 注意：任务书里写明不推送、不部署、不改 `.env`、不连生产库；Codex 跑在 `approval_policy=never` 下，没有人会拦它

---

完整指令见 [SKILL.md](SKILL.md)；安装方法见仓库首页的 [README](../../README.md)。
