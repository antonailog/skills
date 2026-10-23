#!/usr/bin/env bash
# 用法：scripts/make_figure.sh 图稿.json 输出.svg [主题 slug，默认 editorial-forest]
# 按《出图规范》渲染并校验：figkit 渲染 → check_figure（含画板转换检查）。渲染库在同仓库 skills/_shared/figkit。
set -euo pipefail
HERE="$(cd "$(dirname "$(realpath "$0")")" && pwd)"; K="$HERE/../../_shared/figkit"
THEME="${3:-editorial-forest}"
FIGKIT_THEME="$K/themes/$THEME.json" python3 "$K/figkit.py" "$1" "$2"
FIGKIT_THEME="$K/themes/$THEME.json" python3 "$K/check_figure.py" "$2" --wb
