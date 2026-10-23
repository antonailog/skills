# 飞书创建、精确更新与验收

## 工具边界

优先连接器或当前官方 `lark-cli`。使用 CLI 前读取版本对应的内嵌技能；不凭旧笔记猜测字段。

```bash
lark-cli skills read lark-doc
lark-cli skills read lark-doc references/lark-doc-fetch.md
lark-cli skills read lark-doc references/lark-doc-update.md
lark-cli skills read lark-doc references/lark-doc-xml.md
lark-cli skills read lark-doc references/style/lark-doc-style.md
lark-cli skills read lark-doc references/style/lark-doc-update-workflow.md
```

图片／附件时读 `references/lark-doc-media-insert.md`；画板时读 `references/lark-doc-whiteboard.md` 和 `lark-whiteboard` 及其按需引用。路径以当前返回的技能链接为准。工具技能要求分派画板工作时据此分工；主线程保留正文写入与资源替换协调，避免多个任务改同一块。

当前用户指令、已有结构与同范围授权优先于默认写作模板。无需为已经授权的常规文档更新反复确认；工具权限审批照常处理。

## 写前基线

1. 从用户目标解析 wiki／doc；目标不明时只暂停远端写入，继续本地稿。
2. 新页先查目标父目录是否已有相同单集，避免重复。已有页读取最新内容、block ID、revision 和资源。
3. 局部修订默认只读所需章节及相邻结构；整页整理或需要证明用户内容保留时保存完整基线。
4. 记录此次允许修改的 block ID，其他内容、标题、顺序、个人记录、附件删除与画板手改均为保护对象。
5. 画板另外导出原生节点，对比本地版本；只有文档 token 相同不证明画板内容没有变化。将用户手改合并进新源。

## 更新正文

用当前工具支持的 XML 富文本，段落、标题、列表的语义清晰；样式语法以当前技能为准。更新具体 block 或行内文本，尽量不用全文 overwrite，因为它可能丢失评论、图片或用户内容。

传最新 revision；冲突先回读重新合并。`block_replace/delete` 后旧 ID 可能失效，后续操作重新取 ID。多个模块的依赖更新串行执行；独立只读检查可并行。

各级标题前如果是正文／列表／资源，留一个空段落；已有空段不再加，连续标题不硬插。把用户维护的名字和层级作为基线；新页按新页模板（播客信息、关键要点、AI 总结、问答、个人思考、延伸资料、原始资料附件），已有页在用户现有栏目下放对应内容，单元细分放在 AI 总结下。

先完成本地可审阅稿，再执行已授权更新。写入成功后逐项回读正文与富文本，确认关键内容、问答、正文单元与定稿一致，并跑一遍对账（关键内容对骨架、骨架对正文标题、总结图对正文、问答对锚点），不能只读返回的 `success`。

## 建页、问答锚点与收尾

新页：本地笔记用 `scripts/md_to_feishu_xml.py 笔记.md note.xml --img-map '{"images/封面.png":"<网络地址>"}'` 转 XML，在笔记所在目录执行 `lark-cli docs +create --parent-token <父节点> --content @note.xml`（`@` 路径只收相对当前目录）。SVG 图在 XML 里写成 `<whiteboard type="svg" path="@x.svg">`，创建时一并建板；返回的 `new_blocks` 按出现顺序给出各画板 token，再用 `scripts/write_boards.py` 按飞书字宽重写一遍。

问答的答案直接跟在问题后，末尾写「→ A1」。建页后跑 `scripts/link_and_check.py <docx token> <wiki 节点 URL>`：它取各单元标题的 block id，把「→ A1」换成锚点链接，再回读核对一级标题顺序、标题前空段、锚点有效性和强调计数。锚点用 wiki 节点 URL，不用 create 返回的 docx URL（节点 token 用 `wiki/v2/spaces/get_node` 以 obj_type=docx 反查）。已链接过的页只加 `--check-only`。

## 图片与附件

Shownotes 内容图按来源位置插入，核对 token、类型、尺寸与实际显示。已有未变图片保留；上传前检查同名／校验值和目标段落，避免重复。

附件用 `docs +media-insert --file <相对路径> --type file`，不加 `--type file` 会当图片插入（实测把 .md 插成了 100×100 的图）。附件保留 SVG、XMind、Markdown 真源与原始资料包等用户认可的格式。已移除的附件不从历史恢复；更换资源时先确认新文件存在、大小或可用校验值匹配，再移除明确被替代的旧块。

文件名或字节数匹配只是上传的一层证据，不能代替内容或浏览器显示。对缺少下载核验权限的情况记录边界，不擅自扩大授权。

## 原生画板的替换

当前工具的 raw 写入可能是追加，而不是按 ID 更新。先核对真实语义，避免把整个 payload 重复追加到旧板。

对于重制：回读旧板和用户修改 → 合并到本地真源 → 生成新原生数据 → 在授权栏目创建新空板 → 确认空板 → 一次幂等写入 → 回读、预览、实机验证 → 替换旧文档画板块与相应附件。

工具支持安全的定点修复时，也可在原板修复并记录几何差异，保留文字、颜色与无关节点。

未知结果或部分成功时先回读；同一幂等键仅重试同一参数。移除文档旧块不等于删除云端原始板，本地历史也保留。

## 回读与本地同步

保存最终回读，并运行本 Skill 的只读核对工具：

```bash
python3 scripts/audit_document.py \
  --before before.json --after after.json \
  --allow-changes allowed-blocks.json --output audit.json
```

输入可为 CLI fetch JSON（含 `data.document.content`）或 XML。`allowed-blocks.json` 为明确授权变更的旧 block ID 数组。被允许替换的资源块，其后代也在该范围；其他旧块的文字、样式和相对顺序应相同。脚本报告标题空行、重复资源、画板与附件变化，不检查事实、图中内容或实际图片像素。

另外核对：正文单元与定稿一致、图文中的数字和条件一致、问答锚点可点、完整来源清单未变、新图片／附件数量及落位符合计划、明确替换的旧块已移除。新建文档没有旧基线时按新页检查，不伪造保护校验。

最终本地笔记从远端回读合并生成，资源链接指向结果区文件，检查每个本地链接存在。飞书用户手改不会自动回写本地 SVG／XMind；下一次更新仍需回读合并。

## 页面验收与报告

实际打开读者页面检查标题、强调、图片与图文位置；进入画板逐区检查全部文本，确认单个文本能编辑、退出重开显示正常。保存截图和检查范围；浏览器操作后再回读节点，排除误拖或误改。

报告分别写本地生成、API 写入、回读校验、浏览器显示与可编辑验证的真实状态。图片缺失、权限不足、字段为空、实机未查，都指出具体缺口。用户的审美和阅读评价留给用户，不代填。
