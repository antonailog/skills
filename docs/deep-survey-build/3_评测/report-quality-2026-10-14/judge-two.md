# 独立报告质量评审：judge-two

Policy 1.0.0 · 冻结时点 2026-10-15T02:07:58Z · 阅读顺序 R17 → R42。

先完成 R17 绝对评分并留存，再阅读评估 R42，最后比较。优先核原始快照；现网页只访问报告引用的原文或其规范 URL。证据中的字符偏移为 Python Unicode 字符计数，从 0 开始；网页行号为本次工具提取文本。所有原始快照哈希已与索引核对相符。

只读盲评报告、原始任务、policy 和公开原始证据；未读版本映射、其他评分、研究笔记、旧性能评估或 Skill 改造材料。未使用记忆，未委派子评审。

| 报告 | 加权分 | 真实性 | 核验条数 | 未核（关键） | critical_failure | 状态 |
|---|---:|---:|---:|---:|---|---|
| R17 | 90.0 | 3/4 | 22 | 1（0） | 无 | 本次抽核非暂定 |
| R42 | 78.8 | 2/4 | 24 | 3（1） | 无 | 暂定 |

总分以 policy 权重计算，一位小数仅为展示。未核数指本账本的抽样条目，不代表逐句全覆盖。

## R17：90.0

| 维度 | 权重 | 分数 | 依据与主要不足 |
|---|---:|---:|---|
| 真实性与可核验性 | 25 | 3 | 抽核 22 条：20 supported、1 derived_correct、1 unverifiable。日期、票种范围、关键议题、退转例外都能核到原始材料；R17:55 的 Charlie 转述未能读取原文，故未达 4 分。没有关键未核支撑或实质错配。 |
| 问题覆盖与相关性 | 15 | 4 | R17:19–55、59–91 正面回答时间地点、总成本结构、具体技术内容、相对 Maker 上海增量、交流机制和参会条件；还识别了北京链接与上海体验不同、用户实付及满意环节未知、工作日机会成本等隐含前提。 |
| 分析、解释与综合 | 15 | 4 | R17:23、27–39 用具体工程问题比较案例，未把会议标签当深度；45–55 区分议程计划、交流机会与海外体验；47、80–84 给出现场追问和录播替代的条件。机制、公平比较与反面条件均充分。 |
| 对读者的有用性 | 15 | 4 | R17:63–91 的票种范围、费用公式、放弃条件和下一步使读者能自行带入预算与目标；三题/两人的门槛明确是建议，未伪装成收益模型。 |
| 信息密度 | 10 | 3 | 多数段落增加事实或解释，但“等排程、接受撞场、一般不可退”在 15–17、43–47、76–90 多次复述；仍有可压缩的重复，因此为 3。 |
| 表达与信息组织 | 10 | 4 | 一分钟表格—具体议题—交流—票务条件的顺序与决策一致；Harness 有解释，主体、价格口径和推断标签明确。关键结论容易定位和复述。 |
| 信源权威性与适配性 | 5 | 3 | 官方材料适合证明题目、票价和规则；R17:101 把主办方承诺与现场效果分开。独立反馈仍仅两名同一海外场次作者，商业关系未审计；并不足以验证上海交付质量，故为 3。 |
| 时效、局限与不确定性 | 5 | 4 | R17:3、25、45–55、69、76–91、101 将日期/时区、票务最终结算、官方承诺、样本外推与未知的购买影响持续写入判断；退款使用一般条件并保留例外，明确哪些新安排会改变建议。 |

### 事实核验账本

快照统一采集标记：2026-10-15T01:14:00Z。现网页访问日：2026-10-15 UTC / 洛杉矶 2026-10-14；未用网页后续变化直接否定旧状态。

**R17-F01 · supported · 关键支撑**

- 报告位置：R17.md:61。短摘：11 月 5 日周四至 6 日周五；上海虹桥祥源希尔顿酒店，红松东路 1116 号
- 来源：[原文1](https://ai.engineer/shanghai/2026)、[原文2](https://aie.anruicloud.com/assets/Footer-395108d9.js)。
- 定位：evidence/aie-pay-legal-public.js 字符偏移 4940–5007；aie-home-public.html 页首活动日期；日历计算复核星期。
- 判断：日期、酒店和地址相符，两个日期的星期计算也一致。

**R17-F02 · supported · 关键支撑**

- 报告位置：R17.md:63–69。短摘：中文全通票 ¥1,999，展览票 ¥299；普通入口未见单售分会票
- 来源：[原文1](https://aie.anruicloud.com/api/api/tickets)、[原文2](https://aie.anruicloud.com/pay)、[原文3](https://aie.anruicloud.com/assets/pay-0b8ec5e2.js)。
- 定位：evidence/aie-tickets-public.json Data.items 的无 salesChannels 标准票及展览票；aie-pay-page-public.js 字符 3750–4900 的渠道筛选。
- 判断：普通入口应排除需要匹配渠道的优惠配置；剩余票种、价格、范围与表格一致。

**R17-F03 · supported · 关键支撑**

- 报告位置：R17.md:65–69。短摘：Luma 全通 US$278、分会 US$97、展览 US$43，准入范围各异
- 来源：[原文1](https://luma.com/j9iqfmh8)。
- 定位：evidence/aie-luma-public.html 字符 104915–106399：ticket_types cents/currency/description；可见票种区域约 82325–85835。
- 判断：美元分值、币种与主会/分会/展览范围吻合；报告正确保留未核最终结算限制。

**R17-F04 · supported · 关键支撑**

- 报告位置：R17.md:43。短摘：22 位讲者，21 位有题目和摘要；Marco 只有简介
- 来源：[原文1](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。
- 定位：evidence/aie-main-public.js speaker 对象起始字符 1001–19660；独立统计 22 个 slug，Marco 对象无 sessionTitle/sessionAbstract，其余 21 个有。
- 判断：不是仅看首页标签推断；公开对象计数和字段核对支持完整措辞。

**R17-F05 · supported · 关键支撑**

- 报告位置：R17.md:29。短摘：Jeff Wang：检索新鲜度、相关性、来源归因
- 来源：[原文1](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。
- 定位：evidence/aie-main-public.js jeff-wang 对象字符 5601–6437，sessionAbstract。
- 判断：摘要明确覆盖这些议题；报告将其标为准备讲的内容，没有推成效果。

**R17-F06 · supported · 关键支撑**

- 报告位置：R17.md:30。短摘：Andrew Qu：持久状态、跨会话记忆、可观测性
- 来源：[原文1](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。
- 定位：evidence/aie-main-public.js andrew-qu 对象字符 9258–10132，sessionAbstract。
- 判断：三个主题都有摘要直接依据。

**R17-F07 · supported · 关键支撑**

- 报告位置：R17.md:31。短摘：Nancy：任务证据与确定性校验；Faye：诊断、修复、评测闭环
- 来源：[原文1](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。
- 定位：evidence/aie-main-public.js nancy-wang 字符 3819–4713；faye-zhang 字符 10132–10991。
- 判断：两位讲者的摘要分别覆盖可验证闭环及诊断—修复—评测，不是公司职位推断。

**R17-F08 · supported · 关键支撑**

- 报告位置：R17.md:32。短摘：唐飞虎：上下文、工具编排与成本取舍；Ivan：沙箱生命周期成本
- 来源：[原文1](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。
- 定位：evidence/aie-main-public.js tang-feihu 字符 16171–17002；ivan-burazin 字符 4713–5601。
- 判断：两项均为官方摘要主题；报告没有把摘要中的性能数字当作可迁移收益。

**R17-F09 · supported · 关键支撑**

- 报告位置：R17.md:33。短摘：Sarah：设计系统、交互状态与截图反馈
- 来源：[原文1](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。
- 定位：evidence/aie-main-public.js sarah-chieng 字符 10991–11885。
- 判断：摘要包含设计系统约束、交互状态、跨尺寸布局审阅与截图反馈。

**R17-F10 · supported · 关键支撑**

- 报告位置：R17.md:43–45。短摘：日程仍暂定；工作坊准入未明确；双语与现场翻译是官方承诺
- 来源：[原文1](https://ai.engineer/shanghai/2026)、[原文2](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。
- 定位：evidence/aie-main-public.js 字符 37985 附近暂定说明、27723 附近翻译文案、30015/61582 附近征集和形式；对应 home 快照。
- 判断：快照有日程预览和工作坊形式，未给目标场次的具体准入安排；报告把无法确认的部分写成证据范围内的未知。

**R17-F11 · supported · 关键支撑**

- 报告位置：R17.md:47。短摘：官方承诺录制演讲并向公开视频渠道发布，上海发布时间和范围未明确
- 来源：[原文1](https://ai.engineer/shanghai/2026)、[原文2](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。
- 定位：evidence/aie-main-public.js 字符 31103 附近演讲征集说明；home 同节。
- 判断：公开渠道为 YouTube、X、LinkedIn；快照未给出上海发布日程或逐场覆盖名单。

**R17-F12 · supported · 关键支撑**

- 报告位置：R17.md:21。短摘：Maker 上海是 2026-09-12、浦东滨江喜来登，历史全价 ¥599
- 来源：[原文1](https://aimakersummit.com/2026/shanghai)。
- 定位：现网页第 0–6、47、72–80 行；访问日期见 evidence_time。
- 判断：上海实体、日期、场地与历史公开全价一致；未将其说成用户实付。

**R17-F13 · supported · 关键支撑**

- 报告位置：R17.md:21、53。短摘：Maker 全价权益含全天会议、人脉群、讲师面对面及视频回看
- 来源：[原文1](https://aimakersummit.com/2026/shanghai)。
- 定位：现网页第 70–80 行票权。
- 判断：四项均列于票权；用于交流机制比较适当，未证明用户已经实际使用。

**R17-F14 · supported · 关键支撑**

- 报告位置：R17.md:23。短摘：Maker Harness 已涉及 OpenSpec、独立 Agent 审核、Qoder 长任务恢复及 MiniMax 协同
- 来源：[原文1](https://aimakersummit.com/2026/shanghai/track/harness.html)。
- 定位：现网页第 32 行讲者卡片摘要，分别为赵志浩、泮圣伟、何涛。
- 判断：原摘要覆盖这些内容，支撑不能以工程标签推定 AIE 更深的前提。

**R17-F15 · supported · 非核心抽样**

- 报告位置：R17.md:35。短摘：Maker Eval 包含具身、机器人及 NVIDIA Agent 评测
- 来源：[原文1](https://aimakersummit.com/2026/shanghai/track/eval.html)。
- 定位：现网页第 35 行陈凤娇、冀昱衡、周劲松卡片。
- 判断：三个候选方向均存在；此非核心扩展事实也已抽核。

**R17-F16 · supported · 关键支撑**

- 报告位置：R17.md:51。短摘：官网提到场间见讲者、展区 Demo 和实现细节讨论
- 来源：[原文1](https://ai.engineer/shanghai/2026)、[原文2](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。
- 定位：evidence/aie-main-public.js 字符 39363 和 40442 附近。
- 判断：能支撑公开计划的接触方式；不能证明已经排定专场或保证面谈，报告保留了这个区别。

**R17-F17 · supported · 非核心抽样**

- 报告位置：R17.md:55。短摘：Earl 的旧金山 2025 复盘含工作坊、午餐/展位交谈、拥挤、网络故障及部分概览内容
- 来源：[原文1](https://slyracoon23.github.io/blog/posts/2025-06-06_ai_engineer_worlds_fair.html)。
- 定位：现网页第 52、65、69、92、101、108、113、133、150 行。
- 判断：报告对个人经历的转述有原文依据，且注明海外年份与个体样本限制。

**R17-F18 · unverifiable · 非核心抽样**

- 报告位置：R17.md:55。短摘：Charlie 认可内容、商业化改善，同时记录拥挤及临期住宿成本
- 来源：[原文1](https://ignorance.ai/p/the-state-of-ai-engineering-2025)。
- 定位：原 URL 及尾斜杠 URL 的 web 访问均失败；备用只读 urllib 请求为 DNS 错误；索引无此原文快照。
- 判断：没有原文正文可检查完整转述；不能因链接存在而判实，也不能因不可访问而判错。该项不是本报告购票结论的关键前提。

**R17-F19 · supported · 关键支撑**

- 报告位置：R17.md:76。短摘：一般退款期已过，但取消、延期等仍有退款例外，嘉宾调整不自动退款
- 来源：[原文1](https://aie.anruicloud.com/assets/Footer-395108d9.js)、[原文2](https://luma.com/j9iqfmh8)。
- 定位：evidence/aie-pay-legal-public.js 字符 5709–6152、6593–6800；aie-luma-public.html Refund Policy。
- 判断：一般个人原因期限和取消/延期条款被正确区分；中文差旅免责、Luma PT 标记也有依据。

**R17-F20 · supported · 关键支撑**

- 报告位置：R17.md:78。短摘：中文 10 月 15 日 23:59 前可申请转让但时区未写；Luma 平台转票未启用
- 来源：[原文1](https://aie.anruicloud.com/assets/Footer-395108d9.js)、[原文2](https://luma.com/j9iqfmh8)。
- 定位：evidence/aie-pay-legal-public.js 字符 6060；aie-luma-public.html 字符 107646 的 ticket_transfer_enabled:false。
- 判断：申请截止与平台开关都可核；报告没有把中文人工规则外推到 Luma 订单。

**R17-F21 · derived_correct · 关键支撑**

- 报告位置：R17.md:71。短摘：相对 Maker ¥599，全通票多出 ¥1,400
- 来源：[原文1](https://aie.anruicloud.com/api/api/tickets)、[原文2](https://aimakersummit.com/2026/shanghai)。
- 定位：中文普通票 currentPrice=1999；Maker 官网第 74 行 599；算式 1999−599=1400。
- 判断：计算正确，比较的是公开票款而非用户实付，并明示天数与总成本不相同。

**R17-F22 · supported · 非核心抽样**

- 报告位置：R17.md:61。短摘：Luma 整体活动范围是首日 09:00 至次日 18:30，不代表每日作息
- 来源：[原文1](https://luma.com/j9iqfmh8)。
- 定位：evidence/aie-luma-public.html 字符 101536 end_at=2026-11-06T10:30:00Z、101849 start_at=2026-11-05T01:00:00Z、timezone=Asia/Shanghai。
- 判断：UTC+8 转换正确，且报告没有把活动跨度误当两天相同的开闭会时间。

### 推断检查

- R17.md:15–17、37、80–84：本地建议以议题/人选、机会成本和承受未知为前提，清楚说明仅听课者可以等录制；三题两人是筛选建议而非事实收益预测。

### 重大缺陷与限制

未发现达到 policy 定义的关键失败，也未发现会反转购票建议的已证实错误。

- Charlie Guo 的原文未能访问，1 条非核心转述未核；不将其当已证实或错误。
- 非官方本地历史快照的材料以本次现网页核验；不能排除网页日后变化。
- 已提供快照的 SHA-256 全部与 evidence/index.json 相符，但采集时点是统一标记，并非每个请求的精确时间。
- 不是穷尽式逐句核验；现场未来效果及用户实际体验没有可核事实，按推断边界评估。

报告 SHA-256：`9253ee72370723aa517542b7113de3a85d3ea48567e650def09b86734cea71eb`。

## R42：78.8（暂定）

| 维度 | 权重 | 分数 | 依据与主要不足 |
|---|---:|---:|---|
| 真实性与可核验性 | 25 | 2 | 抽核 24 条：20 supported、1 contradicted、3 unverifiable。R42:87 的绝对不退款与完整协议的取消/延期例外不符；85 的分会票页面/数据冲突缺少同一访问时点证据，是影响票种建议的关键未核事实，按 policy 上限为 2，报告总分暂定。另有 Charlie 转述、Faye 同名作者身份连接未核。 |
| 问题覆盖与相关性 | 15 | 3 | 主要问题均有回答，内容和成本尤其具体；但相对 Maker 上海的交流增量比较不足。R42:54–72 没有把 Maker 已公开的人脉群、讲师面对面机制纳入对照，技术学习与交流并重的比较少了一侧。 |
| 分析、解释与综合 | 15 | 4 | R42:28–50 把旧会具体问题、候选主题和建议追问分开；工程文章提炼前提而不借用宣传性能数字；56–72 区分品牌/组织方、个人/团队材料和海外/上海。学习、交流两条机制与线上替代解释可复述。 |
| 对读者的有用性 | 15 | 4 | R42:40–50、64–72、89–119 给出准备材料、要问的问题、会后验证、预算填法及多种放弃条件；读者可以独立执行。票务瑕疵须修正，但准备与验证方法本身仍达到 4 分锚点。 |
| 信息密度 | 10 | 3 | 开头 9、18 与 96–104 重复条件结论，36/52/85/114 也多次重复未排定事项；大部分材料有作用，尚未达到极少复述的 4 分。没有按篇幅或来源数量直接扣分。 |
| 表达与信息组织 | 10 | 4 | 内容—人—交流—成本—条件的层次连贯，问题表把技术术语落到具体故障；已直接查看 R42-figure.png，两条路径可读且标明结果不保证。图的价值是解释过程，不因有图加分。 |
| 信源权威性与适配性 | 5 | 3 | Vercel/Daytona 的具名材料、Exa/Arena 团队资料与各自主张匹配，利益关系和未复现边界有说明；仍缺 Maker 普通听众独立样本，Faye 履历归属也缺连接证据。不能把来源更多等同更有权威。 |
| 时效、局限与不确定性 | 5 | 3 | R42:24、38、50、58–68、94、108–132 对个人经历、公司效果、旅费和未知安排的影响交代充分；但 87 的退款绝对化没有保留条款例外，85 的状态冲突也未给能复核的时点，故不达 4。 |

### 事实核验账本

快照统一采集标记：2026-10-15T01:14:00Z。现网页访问日：2026-10-15 UTC / 洛杉矶 2026-10-14；未用网页后续变化直接否定旧状态。

**R42-F01 · supported · 关键支撑**

- 报告位置：R42.md:13–14、76。短摘：11 月 5—6 日周四周五；虹桥祥源希尔顿，红松东路 1116 号
- 来源：[原文1](https://ai.engineer/shanghai/2026)、[原文2](https://aie.anruicloud.com/assets/Footer-395108d9.js)。
- 定位：evidence/aie-home-public.html 活动页首；aie-pay-legal-public.js 字符 4940–5007；日历星期复算。
- 判断：日期和地址可由活动原始材料互证。报告的 Hilton 链接本次不可访问，但同一地址仍有直接官方活动证据。

**R42-F02 · supported · 关键支撑**

- 报告位置：R42.md:15、36。短摘：22 位讲者中 21 位有题目与摘要，时刻/房间未定
- 来源：[原文1](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)、[原文2](https://ai.engineer/shanghai/2026)。
- 定位：evidence/aie-main-public.js speaker 数组 22 个 slug、21 组 sessionTitle/sessionAbstract；字符 37985 附近日程说明。
- 判断：计数和具体安排的未知均与快照一致。

**R42-F03 · supported · 关键支撑**

- 报告位置：R42.md:40–46。短摘：Andrew 状态与记忆；Jeff 搜索；Chen 真实评测；Ivan 沙箱；Sarah 界面生成
- 来源：[原文1](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。
- 定位：evidence/aie-main-public.js 对象：andrew-qu 9258、jeff-wang 5601、chen-peng 12762、ivan-burazin 4713、sarah-chieng 10991。
- 判断：五个候选主题都吻合摘要；右栏额外问题被明确标成建议追问，没有伪装成议程承诺。

**R42-F04 · supported · 关键支撑**

- 报告位置：R42.md:30。短摘：Maker Qoder 已谈长任务反馈与收敛
- 来源：[原文1](https://aimakersummit.com/2026/shanghai/track/harness.html)。
- 定位：现网页第 32 行泮圣伟 / Qoder Cloud Agent 摘要。
- 判断：包含长任务目标、反馈、偏航、继续/恢复/停止；恢复并非 Maker 完全缺席的新层，报告的“可能补上”仍需谨慎理解为另一案例。

**R42-F05 · supported · 关键支撑**

- 报告位置：R42.md:31。短摘：Maker 得物谈需求到验证关口，Chatbox 谈审核带宽
- 来源：[原文1](https://aimakersummit.com/2026/shanghai/track/coding.html)。
- 定位：现网页第 35 行孙计划及曾宪卡片摘要。
- 判断：两个方向有直接依据，支撑流程治理与视觉验收的对照。

**R42-F06 · supported · 关键支撑**

- 报告位置：R42.md:32、52。短摘：Maker 美团/智源谈机器人评测，NVIDIA 谈 Agent 优化
- 来源：[原文1](https://aimakersummit.com/2026/shanghai/track/eval.html)。
- 定位：现网页第 35 行三位讲者摘要。
- 判断：比较对象与内容方向一致。

**R42-F07 · supported · 关键支撑**

- 报告位置：R42.md:48。短摘：Andrew 署名案例：删专用工具、改文件系统探索，前提是清楚的数据语义文档
- 来源：[原文1](https://vercel.com/blog/we-removed-80-percent-of-our-agents-tools)。
- 定位：现网页第 126、130、138–141、219–235、350–359 行。
- 判断：署名、设计改变和文档前提均可核；报告没有引用小样本成功率来保证迁移效果。

**R42-F08 · supported · 非核心抽样**

- 报告位置：R42.md:48、146。短摘：Andrew 的 Skills 工具发布；发布日期 2026-01-20
- 来源：[原文1](https://vercel.com/changelog/introducing-skills-the-open-agent-skills-ecosystem)。
- 定位：现网页第 124–150 行。
- 判断：署名为 Andrew Qu，日期与 CLI/目录的发布内容相符。普通事实抽样。

**R42-F09 · supported · 关键支撑**

- 报告位置：R42.md:48。短摘：Ivan 的文章讨论跨沙箱共享文件与持久化
- 来源：[原文1](https://www.daytona.io/dotfiles/volumes)。
- 定位：现网页第 14、25、31–50、88–101 行；不带 www 的链接本次失败，报告推荐阅读中的 www 地址成功。
- 判断：作者、共享文件系统、跨任务持久化都可核；只用于工程背景而非独立性能证据。

**R42-F10 · supported · 关键支撑**

- 报告位置：R42.md:48、126。短摘：Exa 团队公开能保留搜索决策路径的编排设计
- 来源：[原文1](https://exa.ai/blog/composing-a-search-engine)。
- 定位：现网页第 44–48、183–186、208–219、244–245 行。
- 判断：作者是 Rohit Prakash 与 Nitya Sridhar，正文有可追踪的图与运行时；报告将其归为团队材料，没有归到 Jeff 个人。

**R42-F11 · supported · 关键支撑**

- 报告位置：R42.md:48、127、143。短摘：Arena 团队通过真实交互比较系统组件；2026-06-04 发布，10-01 有方法更新
- 来源：[原文1](https://arena.ai/blog/agent-arena-methodology)。
- 定位：现网页第 16–33、41–46、72–92 行；页首 Last updated 仍为 6 月 4 日，但第 27 行明确链接 10/1/26 方法更新。
- 判断：组件随机化和交互信号确有说明；更新日期有正文依据，应理解为方法更新提示，不是把网页页首元数据改成该日。

**R42-F12 · unverifiable · 非核心抽样**

- 报告位置：R42.md:50。短摘：她（上海讲者 Faye Zhang）参与的论文确有多模态检索与 Agent 系统经历
- 来源：[原文1](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)、[原文2](https://arxiv.org/html/2602.02961v1)。
- 定位：官方快照 faye-zhang 对象字符 10132–10991 为 Google Cloud；arXiv 原文第 59–73 行有同名 Faye Zhang，署名机构 Pinterest / Stanford，主题吻合。
- 判断：论文内容和同名作者已核实，但这些被引原文没有直接把该作者与上海讲者身份连接起来；任职变更可能成立，不能据机构不同判错，也不能只凭同名认定完整个人履历。该附加候选的身份归属仍待可核的链接。

**R42-F13 · supported · 关键支撑**

- 报告位置：R42.md:7、56。短摘：上海是伙伴独立组织；Standup Partners 与 AIE/Arogo 合作，安锐承办及收款
- 来源：[原文1](https://ai.engineer/)、[原文2](https://ai.engineer/shanghai/2026)、[原文3](https://aie.anruicloud.com/assets/pay-0b8ec5e2.js)。
- 定位：AIE 主站现网页第 68–74 行；evidence/aie-home-public.html 字符 42952–43005；aie-pay-page-public.js 字符 13776。
- 判断：品牌伙伴关系、现场组织方和票务主体分开陈述，原文分别支持。

**R42-F14 · supported · 关键支撑**

- 报告位置：R42.md:58–60。短摘：接触位置主要是场间与展区；双语和实时翻译承诺不等于场外翻译
- 来源：[原文1](https://ai.engineer/shanghai/2026)、[原文2](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)、[原文3](https://luma.com/j9iqfmh8)。
- 定位：evidence/aie-main-public.js 字符 27723、39363、40442；aie-luma-public.html Who should attend。
- 判断：官方活动计划和招募对象可核；实际购票者结构、场外翻译在所审范围内未列，报告保留未知。

**R42-F15 · supported · 非核心抽样**

- 报告位置：R42.md:62。短摘：Kai 对 2024 旧金山场认可同行讨论，也未获得期待的亲密技术小聚
- 来源：[原文1](https://kaizau.com/sita/2024-aiewf/)。
- 定位：现网页第 5–9 行，另第 28–31 行给出工作坊/走廊交谈例子。
- 判断：作者对期待落差与交流收获的完整意思被保留，没有被扩大成上海满意度。

**R42-F16 · unverifiable · 非核心抽样**

- 报告位置：R42.md:62。短摘：Charlie 对 2025 旧金山内容评价高，同时批评后勤
- 来源：[原文1](https://ignorance.ai/p/the-state-of-ai-engineering-2025)。
- 定位：原 URL 与尾斜杠 URL 无法读取；备用 urllib 请求 DNS 失败；索引没有原文快照。
- 判断：无法核对原文完整转述；属于海外个人旁证，不能因抓取失败判错。

**R42-F17 · supported · 关键支撑**

- 报告位置：R42.md:78–85。短摘：中文标准票 1,999 元含主会/分会/展览；展览票 299 元
- 来源：[原文1](https://aie.anruicloud.com/api/api/tickets)、[原文2](https://aie.anruicloud.com/pay)、[原文3](https://aie.anruicloud.com/assets/pay-0b8ec5e2.js)。
- 定位：evidence/aie-tickets-public.json 无渠道标准票和展览票对象；aie-pay-page-public.js 字符 3750–4900。
- 判断：公共标价和票权一致，数据非售罄；没有订单验证的限制也写清。

**R42-F18 · supported · 关键支撑**

- 报告位置：R42.md:85。短摘：Luma All Access USD278，Expo USD43
- 来源：[原文1](https://luma.com/j9iqfmh8)。
- 定位：evidence/aie-luma-public.html 字符 104915、106041 的 cents 与 currency 字段。
- 判断：金额与币种可核，没有进行未经核验的汇率或最终费率比较。

**R42-F19 · unverifiable · 关键支撑**

- 报告位置：R42.md:85。短摘：分会票存在页面与内嵌数据状态冲突，不据此推荐购买
- 来源：[原文1](https://luma.com/j9iqfmh8)。
- 定位：evidence/aie-luma-public.html 可见区字符 84000 显示 1 Left；内嵌区字符 105487–106041 为 USD97、spots_remaining=1、is_disabled=false；索引只有统一采集标记。
- 判断：提供的快照里两者一致，无法复现报告所称冲突；但缺少报告那次具体访问时点的双端记录，不能用后续状态直接判旧说法错误。该事实排除了较便宜的分会票，对购票选择重要，列为关键未核事实并触发暂定/真实性上限 2。

**R42-F20 · contradicted · 关键支撑**

- 报告位置：R42.md:87；亦见 9、17、98。短摘：现在购票已不能退款
- 来源：[原文1](https://aie.anruicloud.com/assets/pay-0b8ec5e2.js)、[原文2](https://aie.anruicloud.com/assets/Footer-395108d9.js)、[原文3](https://luma.com/j9iqfmh8)。
- 定位：evidence/aie-pay-page-public.js 字符 12651–12800 为简版个人退款说明，且字符 469 导入 Footer；完整 aie-pay-legal-public.js 字符 6673–6800 保留取消/延期退款情形。
- 判断：一般个人原因退款期确已过；但绝对措辞扩大了适用范围，完整协议保留活动取消全退和延期无法参加可退等例外。它不会反转常规购票建议，因此不是 policy 定义的 critical_failure。

**R42-F21 · supported · 关键支撑**

- 报告位置：R42.md:87、116。短摘：中文转让须在 10 月 15 日 23:59 前申请且未写时区；不能直接沿用到 Luma
- 来源：[原文1](https://aie.anruicloud.com/assets/pay-0b8ec5e2.js)、[原文2](https://aie.anruicloud.com/assets/Footer-395108d9.js)、[原文3](https://luma.com/j9iqfmh8)。
- 定位：evidence/aie-pay-page-public.js 字符 12800 附近；aie-pay-legal-public.js 字符 6060；Luma 未列同一人工转让规则。
- 判断：准确区分申请与保证成功，也保留跨渠道适用性的未知。

**R42-F22 · supported · 关键支撑**

- 报告位置：R42.md:76、106。短摘：Maker 上海 9 月 12 日周六，历史全价 599 元，票权含会后录像
- 来源：[原文1](https://aimakersummit.com/2026/shanghai)。
- 定位：现网页第 0–6、47、70–80 行；日历复算为周六。
- 判断：历史标价和录像票权相符，报告没有假定用户当前账户仍可访问。

**R42-F23 · supported · 关键支撑**

- 报告位置：R42.md:106。短摘：AIE 计划公开演讲录制，发布范围、日期及直播尚未核到
- 来源：[原文1](https://ai.engineer/shanghai/2026)、[原文2](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。
- 定位：evidence/aie-main-public.js 字符 31103 的录制/发布承诺；home 征集部分。
- 判断：可支持未来公开录制计划，不能支持即时可观看；报告没有承诺上线时间。

**R42-F24 · supported · 非核心抽样**

- 报告位置：R42.md:126、128。短摘：Exa 文发布日期 2026-04-17；Daytona 文发布日期 2025-06-04
- 来源：[原文1](https://exa.ai/blog/composing-a-search-engine)、[原文2](https://www.daytona.io/dotfiles/volumes)。
- 定位：Exa 现网页第 48 行；Daytona 第 14 行。
- 判断：两个非核心日期均与页面标记一致。

### 推断检查

- R42.md:28–34：从工程案例差异推潜在增量有条件支持；Qoder 本已提恢复，跨会话状态是否增加新内容仍需场次细节。
- R42.md:64–72、96–104：学习/交流的准备与验证路径可操作，并明确结果不保证。普通购票路径可用，但较便宜的分会选项被一个未核冲突前提排除，需要补证。

### 重大缺陷与限制

- R42.md:87：把一般个人原因不退票扩成现在购票不能退款，漏掉完整协议的取消/延期例外。（material_noncritical）
- R42.md:85：分会票状态冲突是拒绝较低价选项的事实前提，但所给快照中页面和数据一致；没有那次访问的双端证据。（key_evidence_gap）
- R42.md:54–72：没有用 Maker 已公开的人脉群、讲师面对面权益对照交流机制，双重目标下的增量比较不完整。（coverage_gap）

- 3 条抽样事实未核：分会票历史冲突（关键）、Charlie 转述（非核心）、Faye 论文作者与讲者的同一身份（非核心）。
- 分会票缺少精确采集时间，不把现有快照的一致状态直接判成旧报告造假或错误。
- 论文同名及机构不同不证明不同人；此处只标身份连接未核，不作误认指控。
- Hilton 链接未访问成功；活动官方快照可独立支撑同一地点和地址，故该事实没有算未核。
- 图已直接查看。工程文章没有复现性能效果，官方活动计划不能证明未来交付。

报告 SHA-256：`d5b4d2b12cc9163544388d7a6227330802f7b6e6fd72aa813f3198bda2c7d8dd`。
图片 SHA-256：`3234ca16a11daceec5ac6f754e62c49b64cead6e13cfae75c96e6ad49c7edc64`。

## 两份报告的本次比较

本评审分数 R17 为 90.0，R42 为 78.8（暂定）。R42 的工程背景与参会方法有价值，但退款措辞和关键票务未核不能被综合/表达分抵消。关键未核事实补齐前，不能据此宣布任何版本质量提高或未退化；本记录不推断版本顺序，不外推至其他课题。

差异集中在真实性、覆盖和不确定性表达；两份的解释、方法实用性与组织均有可取处。R42 的具体工程材料与路径图没有因数量或形式自动加分，R17 也没有因为更短自动加分。

本评审分差为 11.3 分；这不是两位评审的分差。另一位评审的原始结果未读取，不能在此报告一致性。

Policy SHA-256：`d7be83d23b882db74b6225cb3720c1f247b9399eb67552f68424cd160f4abf7a`。
原始任务 SHA-256：`2d8c8142ee11f7b30ad27f007b07f4a3948aa033bbf812051a791288f6ddd7d9`。

本 JSON 与 Markdown 为本评审冻结结果；后续若需复核，应另外记录证据澄清，不回改此原始评分。
