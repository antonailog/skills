# figkit

把「图稿」渲染成可转飞书原生画板的 SVG，并按出图规范自动校验。供本仓库的总结类 skill 共用（如 podcast-summary），不是独立 skill（目录名以 `_` 开头，`install.sh` 不安装它）。

## 用法

```bash
FIGKIT_THEME=themes/editorial-forest.json python3 figkit.py 图稿.json 输出.svg
FIGKIT_THEME=themes/editorial-forest.json python3 check_figure.py 输出.svg --wb
```

- `figkit.py`：图稿 JSON → SVG。模板：信息图、层级图、条件汇合、流程图、组成条、柱状图。文字按词折行（数字、百分比、英文串不拆），宽卡说明自动分栏，箭头用 `marker-end` 转原生连接器。
- `check_figure.py`：最小字号 16、卡内行长 30 字、只用主题颜色、每屏强色面用量；`--wb` 同时跑 `@larksuite/whiteboard-cli --check`。
- `oklch.py`：OKLCH 与对比度计算，录入新主题时校验文字对比度。

## 图稿

一张图一个 JSON：`task`（比较／看结构／顺路径／看因果／看占比／带走全局）、`type`（模板名）、`title`（判断句）、`items`（每项 `id`、`text`、可选 `big`、`lines`、`group`、`role`、`span`、`source`）、`relations`（`下一步` 会画箭头）、`notes`。信息图的 `modules` 是一组子图稿。

## 主题

`themes/*.json` 的色值原样取自 [zarazhangrui/beautiful-feishu-whiteboard](https://github.com/zarazhangrui/beautiful-feishu-whiteboard)（MIT License）的 `templates/<slug>/design.md`：Editorial Forest（默认）、Grove、Avocado Press、Long Table、Monochrome。模型是「画布 + 四种面（base／strong／accent／plain）+ 文字颜色跟随所在的面」；每个模块最多一张 strong、一张 accent，其余 base。
