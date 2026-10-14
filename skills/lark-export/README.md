# lark-export

飞书 wiki 镜像到本地 Markdown

## 要解决的问题

飞书知识库里的内容想放进本地仓库，能 grep、能离线看，常见的导出结果是正文转成了 Markdown，图片还是 `feishu://media/…` 这样的引用，图片和附件没真正下载下来。作者试过 feishu2md、自写的 Node 导出链路、浏览器补图的混合方案，要么图片权限不稳，要么正文排版差、维护太重。最后选了 Markdown 结构保留最好的 feishu-cli，打补丁让图片和附件下载走 User Token。

## 运行方式

![lark-export 结构图](../../docs/diagrams/lark-export.jpg)

先从本机已有的 `.mcp.json` 里读出飞书应用凭证；User Token 过期时，要用户在浏览器里重新登录一次。没指定输出目录时，先按项目结构推荐一个，用户确认后再拉。给的是知识库链接就按节点树导出整棵子树，给的是单篇文档就单独导出；更新和首次拉取是同一条命令，重跑即原地覆盖。

## 关键设计

- **首次拉取和更新是同一条命令，重跑即覆盖**：本地副本当只读镜像，不手改，覆盖才安全；只想补新文档时加 `--skip-existing`
- **凭证不进 Skill，运行时从 MCP 配置里读**：Skill 会被 symlink、打包、推到 GitHub
- **没指定输出目录就按项目结构推荐，确认后再拉**：不悄悄写死一个默认路径
- **两种令牌分工**：App Token 读知识库结构和正文，User Token 只负责下载图片、附件和导出文件；User Token 缺读权限时，正文导出不会被卡住

## 其他

- 不处理：在会话里读、引用、总结单篇飞书文档（直接用飞书 MCP）；写回或发布到飞书（用 lark-cli）
- 前提：打过补丁的 feishu-cli 工具链目录（`FEISHU_EXPORT_HOME`，缺二进制时用 Go 编译）；`FEISHU_APP_ID`、`FEISHU_APP_SECRET`；User Token 要带导出和媒体下载权限，飞书应用的回调白名单里要加本地回调地址
- 注意：补丁版 feishu-cli 和批量导出脚本不在本仓库里，Skill 只负责驱动它们
- 注意：上游改名或删除的文档，本地旧文件会留着，目前没有清理步骤

---

完整指令见 [SKILL.md](SKILL.md)；安装方法见仓库首页的 [README](../../README.md)。
