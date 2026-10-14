<div align="center">

# yikegunshi-skill

**一套精选的 Claude Code / Codex Agent Skill 合集。**

面向内容工作流、产品分析与知识管理的实用 skill，由 [@yike-gunshi](https://github.com/yike-gunshi) 构建与维护。

![Skills](https://img.shields.io/badge/skills-11-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/Claude%20Code-compatible-8A2BE2)

**简体中文** · [English](./README.en.md)

</div>

---

## 这是什么？

**Agent Skill** 是一个带 `SKILL.md` 的文件夹，用来教 AI 编码代理（Claude Code、Codex）一套可复用的工作流——什么时候触发、执行哪些步骤、调用哪些脚本。把一个 skill 放进代理的 skills 目录，它就会在匹配的触发词上生效。

这个仓库用来对我自己可复用的 skill 做版本管理，方便在任何机器上快速恢复完整环境，并把其中通用的部分分享出来。

## Skill 一览

| Skill | 作用 | 触发词 |
|-------|------|--------|
| **[knowledge-canvas](./skills/knowledge-canvas/)** | 把代码、PDF、书籍、课程与文档整理为可缩放、可平移的中文 HTML 知识画布，展开关键节点与关系，悬停查看说明和原始输入输出样例。附交互模板、浏览器回归脚本与飞书正文交付指引。 | `梳理完整链路`、`做一张能交互的全图`、`$knowledge-canvas` |
| **[lark-export](./skills/lark-export/)** | 把飞书/Lark 知识库或单篇文档镜像成本地 Markdown，图片和附件一并下载到本地。重复运行即同步更新。 | `同步飞书`、`导出飞书知识库` |
| **[wechat-publisher](./skills/wechat-publisher/)** | 把 Markdown 文章发布到微信公众号草稿箱：图片压缩 → OSS 上传 → 排版 → 草稿箱。 | `发布微信`、`/wechat` |
| **[prompt-craft](./skills/prompt-craft/)** | 写、改、评审任何 LLM prompt：问清需求 → 按九模块架构撰写 → 对抗审查，产出可验收、可回归、防注入的生产级 prompt（基于 14 组外部框架调研）。 | `写prompt`、`优化prompt`、`评审prompt` |
| **[book-to-mindmap](./skills/book-to-mindmap/)** | 把书籍、长笔记转成高信息密度的思维导图：判断式枝干 + 图面短句 + notes 长解释 + 默认折叠，产出 .xmind 与多级 bullet。 | `做成思维导图`、`转导图`、`生成xmind` |
| **[xhs-note](./skills/xhs-note/)** | 写小红书笔记：收料 → 读范文起草 → 去 AI 味终审 → Codex 生封面 → 归档。范文优先，不编造作者没经历过的事。 | `写小红书`、`发小红书`、`/xhs-note` |
| **[skill-build](./skills/skill-build/)** | 造 skill 的 skill：判该不该做 → 访谈收料 → 设计文档 → 完备性门禁 → 写 SKILL.md → 评测跑基线对照 → 归因迭代。自带包体检与考点区分度审计脚本。 | `做个skill`、`建个skill`、`skill不触发` |
| **[pm-doc-write](./skills/pm-doc-write/)** | 写 PM 工作文档：结论先行、表格承载、数字带基线、责任到人。覆盖周报、OKR、项目总结、指标需求、策略迭代说明、评测结论、LR 评审、调研报告 9 类场景模板 + 通用写法约束与终审清单，产出飞书就绪 markdown。 | `写周报`、`出个文档`、`按我的风格捋一遍` |
| **[paper-card](./skills/paper-card/)** | 把论文、官方最佳实践、cookbook 读透，产出学习卡片：每个数字带读法、术语用类比讲透、结论落到可执行动作，配一张分层底板风 SVG 结构图并渲染自查。结构随资料形态调整，不套固定模板。 | `读一下这篇论文`、`整理成卡片`、`这批参考资料做成学习资料` |
| **[codex-delegate](./skills/codex-delegate/)** | Claude Code 把代码实现派给本机 Codex CLI 后台作业：写任务书 → 派活 → 判活 → 按任务书验收 → 返工接回原会话（最多两轮）→ 收回 → 提交；附盲解仲裁。脚本 `delegate.sh` 管作业状态与 resume，需本机装有 ChatGPT App 内置的 Codex CLI。 | `派给codex`、`让codex实现你验收`、`codex后台跑` |
| **[deep-survey](./skills/deep-survey/)** | 调研产品、行业、公司或 AI 工具，产出外行读得懂、读完能做决定的深度报告：信息需求清单与覆盖率门禁 → 并行研究（先查自有信息流，知乎、即刻、36 氪走专用通道）→ 对抗分析 → 逐条核查来源与口径 → 论证地图 → 报告与主题图表 → 终稿核查。每个数字带来源编号，查不到写明而不估算。设计与评测记录见 [docs/deep-survey-build](./docs/deep-survey-build/)。 | `调研一下`、`竞品分析`、`值不值得做` |

## 已归档

暂时不维护的 skill 移到了 [`archive/`](./archive/)：不随 `install.sh` 安装，代码和文档原样保留，以后优化后可能移回 `skills/`。

- [prd-analyzer](./archive/prd-analyzer/)
- [project-context](./archive/project-context/)
- [project-learner](./archive/project-learner/)
- [repo-study](./archive/repo-study/)
- [staged-file-review](./archive/staged-file-review/)
- [twitter-watchdog](./archive/twitter-watchdog/)
- [work-logger](./archive/work-logger/)

## 安装

克隆仓库，用 `install.sh` 以 symlink 方式安装（不要手动 cp——复制副本会随源仓库更新而漂移）：

```bash
git clone https://github.com/yike-gunshi/yikegunshi-skill.git
cd yikegunshi-skill

# 安装全部 skill 到 ~/.claude/skills
./install.sh

# 只安装指定 skill
./install.sh --only lark-export --only prompt-craft

# 查看安装状态（含坏链检测）/ 卸载
./install.sh --status
./install.sh --uninstall
```

Codex 用户加 `--target codex`（装到 `~/.agents/skills`），`--target both` 两边都装。

重启代理（或开新会话），skill 会在其触发词上激活。

## 配置与密钥

部分 skill 会调用第三方 API，需要凭证。**本仓库不包含任何密钥**——请自行提供：

| Skill | 需要设置 | 方式 |
|-------|----------|------|
| lark-export | `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_EXPORT_HOME` | 环境变量（见该 skill 的 `SKILL.md`） |
| wechat-publisher | `WECHAT_APP_ID`、`WECHAT_APP_SECRET`、`OSS_ACCESS_KEY_ID`、`OSS_ACCESS_KEY_SECRET`、`OSS_BUCKET` | 环境变量 |
| deep-survey | `ZHIHU_ACCESS_SECRET`（可选，知乎数据开放平台）；`INFO2ACTION_REPO`（可选，作者自用的信息流） | 环境变量，或写进 `~/.config/deep-survey/secrets.env`；都没有时自动退回网页搜索 |

`config/config.yaml`、`.env` 等本地密钥文件已被 git 忽略。

## 仓库结构

```
yikegunshi-skill/
├── skills/
│   ├── book-to-mindmap/
│   ├── codex-delegate/
│   ├── deep-survey/
│   ├── knowledge-canvas/
│   ├── lark-export/
│   ├── paper-card/
│   ├── pm-doc-write/
│   ├── prompt-craft/
│   ├── skill-build/
│   ├── wechat-publisher/
│   └── xhs-note/
├── archive/         # 已归档、暂不维护的 skill（不随 install.sh 安装）
├── docs/            # 部分 skill 的设计与评测记录
├── LICENSE
└── README.md
```

## 贡献

这些 skill 以现状分享，供参考与复用。欢迎提交改善可移植性或修复 bug 的 issue 与 PR。

## 许可

[MIT](./LICENSE) © 2026 yike-gunshi
