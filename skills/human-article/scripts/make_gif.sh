#!/bin/bash
# 把一段录屏转成能放进文章的动图。
# 用法：bash make_gif.sh <视频> <输出.gif> [宽度，默认 960] [开始秒] [时长秒]
set -euo pipefail
SRC="$1"; OUT="$2"; W="${3:-960}"
CUT=()
[ -n "${4:-}" ] && CUT+=(-ss "$4")
[ -n "${5:-}" ] && CUT+=(-t "$5")
ffmpeg -v error -y ${CUT[@]+"${CUT[@]}"} -i "$SRC" -vf "fps=12,scale=${W}:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=160:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" "$OUT"
du -h "$OUT" | cut -f1
