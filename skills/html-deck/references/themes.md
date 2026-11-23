# 4 套风格

功能完全一样，只换外观：颜色、字体、线条、卡片样子、默认翻页动效。每份稿的 `讲稿/deck/themes/` 里四套都有，换风格就是改 index.html 里这一行：

```html
<link rel="stylesheet" href="deck/themes/swiss.css" data-theme-link>
```

| 风格 | 文件 | 样子 | 适合 | 默认翻页 |
|---|---|---|---|---|
| 瑞士网格 | `swiss.css` | 白底黑字、粗线标题、红色只给重点；信息密度高、克制 | 观点型演讲、行业分享 | 淡入 |
| 编辑书卷 | `editorial.css` | 纸色底、衬线标题、细线和斜体引用；安静、有书卷气 | 课程、思想分享、读书会 | 淡入 |
| 暗场发布会 | `keynote.css` | 深色底、蓝青渐变强调、发光背景；有现场感 | 产品演示、发布会、技术分享 | 推移 |
| 新野兽派 | `brutal.css` | 米黄底、粗黑框加硬阴影、亮色块；活泼、有记忆点 | 社区分享、轻松的课、年轻听众 | 推移 |

## 怎么帮用户挑

1. 先按场合推荐 1—2 套（上表「适合」那列），说一句为什么
2. 用 `scripts/render_styles.py <讲稿目录> --pages 1,3,6 --recommend keynote` 拿大纲里的封面加 2—3 页有代表性的内容（有数字、有流程、有观点的各一页）渲染 4 套，生成风格讨论页
3. 用户选定后改那一行 link；不要为一份稿改风格文件本身

## 小调整

用户要「这套再亮一点」「重点色换成品牌色」：在 index.html 的 `<head>` 里、风格 link 后面加一段 `<style>`，只覆盖变量：

```html
<style>:root { --accent: #0a7cff; --c1: #0a7cff; }</style>
```

常用变量：`--bg` 底色、`--bg-art` 背景（可渐变）、`--ink` 正文、`--mute` 次要文字、`--line` 粗线、`--hair` 细线、`--accent` 重点色、`--font-head` / `--font-body` 字体、`--title-size` 标题字号、`--radius` 圆角、`--card-shadow` 卡片阴影、`--c1`…`--c5` 图表配色、`--transition` 默认翻页（`fade` / `push` / `none`）。

改字体要连 `scripts/fontpack.py` 里的 `FAMILIES` 一起看：打包时按它下载字体子集，表里没有的字体会落到系统字体。

## 字体

都是 Google Fonts 上的开源字体（SIL OFL）：Inter、Noto Sans SC、Noto Serif SC、Space Grotesk、JetBrains Mono。写稿时在线加载，没网落到系统字体（苹方、雅黑、宋体）；打包和生成网站版时只下载用到的字，一份稿几百 KB，换电脑显示一样。
