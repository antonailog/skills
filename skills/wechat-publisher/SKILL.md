---
name: wechat-publisher
description: 把写好的 Markdown 文章推到微信公众号草稿箱：图片压缩后传阿里云 OSS，生成发布版、校对完等你确认，再套排版主题推进草稿箱（4 个自定义 + 8 个内置主题，可多选，每个主题一篇草稿）；推完主动给朋友圈和群聊两版推广文案、发布时间与投放建议，最后 git 提交归档。只推草稿，不替你点发表。用户说「发布微信」「发公众号」「推到草稿箱」「微信排版」「/wechat」时用；拿着一篇写好的 md 说想发公众号，也用。不处理：写文章本身、小红书笔记（走 xhs-note）、公众号后台的数据分析。
---

# 微信公众号文章发布 (WeChat Publisher)

将 Markdown 文章一键发布到微信公众号草稿箱，支持图片压缩上传 OSS、自定义排版主题、自动校对。

## 触发关键词

发布微信, 公众号文章, 微信排版, publish wechat, /wechat

## 默认配置

- **默认主题**：落日晚霞（sunset-glow）—— 暖橙红渐变，温暖优雅
- **代码高亮**：atom-one-dark（深色 macOS 终端风格）；荧光笔（marker）用 atom-one-light 浅色代码块，不加 Mac 风格三个点
- **排版对齐**：正文和列表两端对齐，带网址、路径这类长串的段落左对齐（长串不能断行，两端对齐会把前一行字距拉开）；`WECHAT_JUSTIFY=0` 关掉

## 完整工作流

当用户要求发布微信公众号文章时，按以下步骤操作。下面的命令都在本 skill 目录下运行（install.sh 安装后是 `~/.claude/skills/wechat-publisher` 或 `~/.agents/skills/wechat-publisher`）。

### Step 1: 解析文章

用户提供 Markdown 文件路径（可以是手写的、也可以是 wechat-article-writer 生成的）。阅读文件，确认内容正确。

### Step 2: 处理图片

运行图片处理脚本：提取 Markdown 中的远程图片和本地图片 → 用 macOS sips 压缩（max 1600px, JPEG 80%）→ 上传到阿里云 OSS。

```bash
python3 scripts/process_images.py <md_file> <folder_name>
```

参数说明：
- `<md_file>`: Markdown 文件路径
- `<folder_name>`: OSS 上的文件夹名，推荐格式 `YYYY-MM-DD_文章简称`

输出：`image_urls.json`（原始路径 → OSS URL 映射）

**注意**：如果有额外图片未在文章正文中引用（如 16:9 封面图），需要单独上传到 OSS。可以用以下 Python 片段：
```python
import oss2, subprocess, tempfile, os
# 压缩
tmp = tempfile.mktemp(suffix='.jpg')
subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '80', '-Z', '1600', '<src>', '--out', tmp])
# 上传（凭据从环境变量读，见文末「凭据」）
auth = oss2.Auth('<KEY_ID>', '<KEY_SECRET>')
bucket = oss2.Bucket(auth, '<ENDPOINT>', '<BUCKET>')
bucket.put_object_from_file('<oss_key>', tmp)
```

### Step 3: 生成发布版

运行文章准备脚本：替换图片 URL 为 OSS URL + 添加 `{width=340}` + 生成 frontmatter。

```bash
python3 scripts/prepare_article.py <md_file> <url_mapping_json> [output_path]
```

输出：`xxx_发布版.md`

**图片宽度：脚本按尺寸自动加，不用手改**

prepare_article.py 读本地图片的尺寸：横图和方图加 `{width=340}`；竖图（高大于宽，手机竖拍的照片按转正后的方向算）不加，按正文宽度显示。读不出尺寸的（网络图片、没装 Pillow）按横图处理。

**图集和图注的写法**

- 几张图连着写、中间不空行 → 发布时排成横滑图集（每张 80% 宽，左右滑）；单独一段的一张图照常显示
- 图片下面写 `*▲ 图注*`（紧贴图片或空一行都行）→ 居中灰色小字；图集下面紧贴的那行斜体是图集的图注
- 表格都自动套横向滚动，列多的表格左右滑

同时检查 frontmatter 的 cover 字段，如果有 16:9 封面图应使用封面图的 OSS URL。

### Step 4: 校对

阅读发布版文章全文，检查：
- 错别字、语病
- 格式问题（标题层级、列表缩进等）
- 图片链接是否都已替换为 OSS URL
- 列表项是否去掉了装饰性 emoji
- 向用户报告发现的问题，等待确认后继续

### Step 5: 选择主题

默认使用 **落日晚霞（sunset-glow）**。如果用户需要其他主题，可选：

**自定义主题（4 个）：**
| ID | 名称 | 风格 |
|----|------|------|
| `sunset-glow` | 落日晚霞（默认） | 暖橙红渐变，温暖优雅，两端对齐，深色代码块 |
| `ink-bamboo` | 墨竹清韵 | 中国风水墨绿，古雅端庄 |
| `starry-geek` | 星空极客 | 深色科技风，紫蓝渐变 |
| `marker` | 荧光笔 | 中性灰正文 + 黄绿荧光笔加粗，小一号字、宽字距、两倍行距，不铺底色，浅色代码块 |

**wenyan-mcp 内置主题（8 个）：**
default, orangeheart, rainbow, lapis, pie, maize, purple, phycat

用户可选择多个主题，每个主题会生成一篇独立的草稿。

### Step 6: 发布

运行发布脚本：注册自定义主题 → 渲染 HTML → 推送到微信草稿箱。

```bash
node scripts/publish.mjs <md_发布版_file> <theme_ids>
```

参数说明：
- `<md_发布版_file>`: 发布版 Markdown 文件路径
- `<theme_ids>`: 逗号分隔的主题 ID，默认 `sunset-glow`

**常见问题**：
- **IP 白名单错误**（40164）：需要在微信公众号后台 → 设置与开发 → 基本配置 → IP 白名单中添加当前 IP
- **主题不存在**：检查主题 ID 是否在上述列表中

### Step 7: 生成推广文案

发布成功后，生成两个版本的推广文案，保存到文章目录下的 `推广文案.md`：

**版本 1：朋友圈**
- 简短，3-4 段
- 第一行说"写了篇文章，关于 XX"
- 中间分点列出"对你可能有用的场景"（分三种读者：不懂的 / 知道但没深究的 / 已经在用的）
- 附仓库链接（如有开源项目）
- 最后"详细分析见文章👇"

**版本 2：群聊转发**
- 稍长，结构化
- 第一行"分享一篇我写的关于 XX 的文章"
- "背景："一句话说为什么写
- "文章包含："用 📌 分点列出核心内容
- "对你可能有用的场景："用 - 分点列出 3-4 个痛点 → 文章中的对应解法
- 附仓库链接
- "欢迎试用👇"

**语气要求：**
- 参考用户历史推广文案的风格——像跟朋友说"做了个什么、参考了什么、解决了什么、欢迎试用"
- 不要高大上，不要营销腔
- 分段分行，不要一整段话
- 重点是描述对别人的价值，让人明白为什么要看

### Step 8: 发布时间分析 + 投放建议

发布到草稿箱后，**主动**分析文章内容并给出发布时间和投放建议，不等用户问。

**分析维度：**
1. **文章类型**：技术干货 / 工具推荐 / 经验分享 / 观点输出
2. **目标读者**：技术人 / 产品经理 / 泛 AI 爱好者 / 混合
3. **阅读场景**：需要专注阅读 / 可以碎片化浏览

**发布时间建议规则：**
- 技术干货/长文 → **周一至周四早上 8:00-9:00**（通勤学习时间，有讨论情绪）
- 工具推荐/短文 → **工作日午休 12:00-13:00**
- 观点/热点 → 事件发生后 **24 小时内**
- **避开**：周日下午/晚上（没心力）、周五晚上（周末模式）、节假日

**投放建议：**
- 发布和投放**分开**：文章可以提前发，投放等最佳时间
- 朋友圈：跟文章同时或早上发
- 群聊投放：选在目标群最活跃的时间段（通常是工作日上午）
- 不要把所有渠道在同一时间消耗完，可以分批：早上群聊 → 中午朋友圈 → 下午社区

**输出格式：**
```
📅 发布时间建议：
- 文章类型：[技术干货/工具推荐/...]
- 建议发布：[具体日期 + 时间段]
- 理由：[一句话]

📣 投放建议：
- 第一波（[时间]）：[渠道]
- 第二波（[时间]）：[渠道]
```

### Step 9: Git 提交

在微信文章仓库中提交所有变更并推送：

```bash
cd <微信文章目录>
git add .
git commit -m "发布: <文章标题>"
git push
```

## 主题设计规范（落日晚霞 v3 — 2026-03-29）

| 属性 | 值 | 说明 |
|------|-----|------|
| 正文字号 | 16px | |
| 行间距 | 1.85 | |
| 段间距 | margin 22px 0 | 段落呼吸感 |
| 字色 | #3f3f3f | 中灰 |
| 字间距 | 0.5px | |
| 对齐方式 | 正文、列表 justify；带网址的段落 left | publish.mjs 处理，标题、代码块、图注不动 |
| 标题色 | #1a1a1a | 全部黑色，靠字号区分 |
| h1 | 24px bold | 居中 |
| h2 | 20px bold | 左边框 4px #e67e22 |
| h3 | 18px bold | |
| strong | #1a1a1a bold | 不用强调色 |
| 代码块背景 | #2d2d2d | 圆角8px，max-height 400px |
| 行内代码 | transparent 背景 | 正文色 |
| 引用块 | transparent + #e0e0e0 左边框 | 灰色字 |
| 图片 | 圆角 8px + 居中 | |
| 图集 | 几张图连着写、中间不空行 → 横滑图集，每张 80% 宽 | publish.mjs 处理，所有主题；单独一张图不变 |
| 有序列表 | padding-left 2.2em | 24px 放不下「1.」 |
| 表格 | 灰色表头 + 左右滑动 | nowrap；publish.mjs 给每张表套横向滚动容器（所有主题） |
| 分割线 | 橙色渐变但不在正文中使用 | |
| 图片注释 | 图片下面紧贴的斜体，或单独一段 `*▲ 图注*`：居中 + #999、0.85em | 其他斜体是普通斜体；publish.mjs 处理 |
| 脚注 | display: none | 不显示 |

## 目录结构

```
wechat-publisher/
├── SKILL.md                          # 本文件
├── scripts/
│   ├── process_images.py             # 图片下载、压缩、上传 OSS
│   ├── prepare_article.py            # 生成发布版 MD
│   └── publish.mjs                   # 注册主题 + 渲染 + 发布草稿箱
└── assets/
    └── themes/
        ├── sunset-glow.css           # 落日晚霞（默认）
        ├── ink-bamboo.css            # 墨竹清韵
        ├── starry-geek.css           # 星空极客
        └── marker.css                # 荧光笔
```

## 前置依赖

- Python 3 + `oss2` 库: `pip3 install oss2`
- Python 3 + Pillow（prepare_article.py 读图片尺寸判断竖图；没装时所有图都按横图加 `{width=340}`）
- Node.js + `@wenyan-md/mcp` 全局安装
- macOS `sips` 命令（系统自带）

## 凭据

都从环境变量读，仓库里不放任何密钥：

- 阿里云 OSS：`OSS_ACCESS_KEY_ID`、`OSS_ACCESS_KEY_SECRET`，可选 `OSS_ENDPOINT`、`OSS_BUCKET`（`process_images.py` 读取）
- 微信公众号：`WECHAT_APP_ID`、`WECHAT_APP_SECRET`（`publish.mjs` 读取）；当前出口 IP 要先加进公众号后台的 IP 白名单

`publish.mjs` 另外认两个可选环境变量：`WECHAT_DIGEST` 写进草稿的摘要栏（不设时微信截取正文开头）；`WECHAT_JUSTIFY=0` 关掉两端对齐
