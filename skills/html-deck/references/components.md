# 组件和写法

写稿时照着用。所有组件在 `assets/components.html` 里各有一页样张，打开就能看到 4 套风格下的样子（`?theme=editorial` 换风格）。

## 每页的骨架

```html
<section class="slide">
  <h2>一句观点，可以用 <em>重点</em></h2>      <!-- 标题在粗线上方；em 是重点色，一页最多一处 -->
  <div class="body">                            <!-- 主组件放这里；内容少时加 mid 上下居中 -->
    …一个主组件…
  </div>
  <div class="foot"><span class="src">来源：…</span><span class="pg"></span></div>   <!-- pg 引擎自动填页码 -->
  <aside class="note"><p>讲这页时说什么</p></aside>   <!-- 备注，按 N 或在演讲者视图里看 -->
</section>
```

- **标题写观点，不写分区名**。「周会超时，问题不在时间」比「问题分析」好：观众扫一眼就知道这页要说什么
- **一页一个观点、一个主组件**。两件事就拆两页
- **重点色只给重点**。少用实心色块，大面积填色会抢掉真正的重点
- **数据用引用样式带出处**；表格看不懂时改成陈述句或大数字
- **样例页讲做法和输入输出**，不直接嵌一个原始页面让观众自己看
- 封面和结尾用 `class="slide cover"`：`.hd` 顶上一行场合信息，`h1` 标题，`.by` 署名一行

## 组件清单

| 组件 | 用在 | 写法要点 |
|---|---|---|
| 要点 `ul.k` | 3—5 条并列要点 | `li.r` 红点标重点；`ul.k.s` 小一号；`ul.k.two` 两栏 |
| 引用 `.qt` | 数据、别人的话 | `<div class="qt">原话 <i>—— 出处</i></div>` |
| 标签 + 观点 `.lab` `.t` | 一块内容的小标题和观点句 | `.lab.r` 标签用重点色；`.t.m` 小一号 |
| 观点 + 原因 `.split` | 左窄右宽的两块 | 两个 div；左边观点、右边原因 |
| 并排 `.cols.c2/.c3` + `.col` | 两三栏并列 | 栏之间有竖线 |
| 箭头链 `.chev` + `.under` | 三段递进 | `.chev` 三个 div（`<b>1</b><div>名称<span>说明</span></div>`），`.under` 三栏要点 |
| 流程卡 `.steps` | A → B → C | `.st` 卡片、`.ar` 箭头；`.st.r` 标重点 |
| 行列 `.rows` | 三四件事各有标签、观点、要点 | `.row` 里 `.rk` 标签、`.t` 观点、`ul` 要点，首行文字对齐 |
| 大数字 `.stats` | 一组关键数字 | `style="--n:3"` 一行几格；`.stat` 里 `.k` 标签、`.v` 数字（出现时滚动）、`.d` 一句话、`.x` 补充 |
| 前后对比 `.compare` | 原来 vs 改后 | 两个 `.side`（改后加 `.after`），中间 `.ar` |
| 图表 `figure.chart` | 趋势、占比、排名 | 见下 |
| 表格 `table.g` | 多维对比 | 列少于 5 列；看不懂就换成大数字或陈述句 |
| 一句话 `.big-line` | 全篇要记住的话 | 配 `.body.mid` |
| 目录 `.toc` | 分几部分 | 编号和标题交替写 div |
| 代码 `pre.code` | 讲代码 | 字号 18px，投影上看得清；超过 15 行就拆 |
| 页签 `.tabs` + `.panes` | 一页里放几个样例 | 按钮和 `.pane` 一一对应；`.duo` 左右两栏、`.gal` 一列图、`.scroll` 可滚动 |
| 嵌入网页 `.box` | 现场演示网页 | `<div class="box" style="--k:.75"><img class="shot" src="嵌入/截图/x.png"><iframe data-src="https://…"></iframe></div>`：`--k` 缩小比例，`.shot` 断网时的备用截图（在线页一定要配） |
| 视频 | 录屏演示 | `<div class="box"><video src="嵌入/视频/x.mp4" muted loop playsinline></video></div>`，翻到这页自动播放；用 H.264 的 mp4 |
| 图片 `figure.img` | 截图、照片 | `<figure class="img"><img src="…"><figcaption>说明</figcaption></figure>` |
| 二维码 `.qr` | 结尾留联系方式 | `<div class="qrs"><figure><div class="qr" data-qr="https://…"></div>名称<small>网址</small></figure></div>`，引擎生成 |
| 结尾 `.end` | 最后一页 | 左边一句话（`h1` + `.like`），右边 `.qrs` |

### 图表

```html
<figure class="chart" data-type="bar" data-labels="第1周,第2周,第3周" data-values="58,51,40" data-hl="2" data-unit=" 分钟"><figcaption>说明</figcaption></figure>
```

- `data-type`：`bar` 柱状（比大小、看趋势）、`hbar` 横条（类别名长、排名）、`line` 折线（多个时间点，多组用 `;` 分开，`data-series="A,B"`）、`donut` 环形（占比，3—5 块）
- `data-hl` 标重点（第几个，从 0 数，可写多个 `1,3`）：bar、hbar 里标了的用主色、其余用次色，不标就全用主色；line 在这几个点上加数值（最后一个点总有）；donut 不看它。多组柱子（`data-values` 用 `;` 分组）按组上色，写 `data-series="A,B"` 会在右上角出图例
- `data-max` 定纵轴最大值；`data-h` 定高度；数值个数比标签多时按数值个数排
- 颜色跟风格走（`--c1`…`--c5`），出现时柱子长出来、折线画出来；数字来自用户材料，不编

## 分步出现：只在需要渐进讲的页用

分步是控制观众此刻看什么，不是装饰。一张图、一组并列要点，一次全出来更好；只有「先讲 A 再揭晓 B」「先问题后答案」这种讲法才分步。

- 按选择器：`<section class="slide" data-steps=".chev>div:nth-child(2) | .chev>div:nth-child(3)">`，`|` 分开每一步，同一步里多个元素用逗号
- 按元素：在元素上写 `data-step="1"`、`data-step="2"`
- 想让前面的变淡、突出当前这条：section 上加 `data-focus`
- 页签也算步：按 → 先走完本页的步，再切页签，最后翻页；页码前的圆点显示走到第几步
- 有页签的页，分步只标在页签外面的元素上；标在第二个页签里的步会在第一个页签显示时就走掉

## 备注

每页一个 `aside.note`，写讲这页时要说的话和数据出处链接。现场版和离线包里都有备注（离线包是拷给别人放的，对方按 N 就能看到），网站版会删掉。所以离线包要外发时，备注也按「对外」写：给自己的私人提醒不要写，要写就在打包前删掉。
