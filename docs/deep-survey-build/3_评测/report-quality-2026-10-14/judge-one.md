# 独立质量评审：judge-one

本评审先对 R42 绝对评分并冻结，再读取及评估 R17。**R42：82.5 / 100；R17：85.0 / 100。**均未发现 policy 定义的关键失败；抽查的关键支撑事实均已核清，因此本次总分不标暂定。两份各有一条非核心措辞未获证据支持，不能把结果表述为所有事实都通过。

使用 policy 1.0.0（本机原件，未公开）与 原始需求（本机原件，未公开）。未参与报告研究/写作/修改。只使用匿名报告、task、policy、原始快照和只读公开原文；未读 manifest-private.json、其他评审分数、作者研究结论、历史性能或 Skill 改造材料。R42 先绝对评分并冻结，再读 R17。未推断新旧。

## 分数

| 维度 | 权重 | R42 | R17 |
|---|---:|---:|---:|
| 真实性与可核验性 | 25 | 3 | 3 |
| 问题覆盖与相关性 | 15 | 3 | 3 |
| 分析、解释与综合 | 15 | 3 | 3 |
| 对读者的有用性 | 15 | 4 | 4 |
| 信息密度 | 10 | 3 | 4 |
| 表达与信息组织 | 10 | 4 | 4 |
| 信源权威性与适配性 | 5 | 3 | 3 |
| 时效、局限与不确定性 | 5 | 4 | 4 |
| 加权总分 | 100 | **82.5** | **85.0** |

分数按 Σ（维度分 ÷ 4 × 权重）计算。2.5 分差仅来自信息密度维度，不是测量精度，也不表示其他维度的具体优缺点完全相同。另一名评审尚未纳入本记录，不计算跨评审分差或均值。

## 核验覆盖与关键缺陷

| 报告 | 抽查论断 | 关键 / 非关键 | supported | derived_correct | unsupported | contradicted | unverifiable | 未核清关键事实 | critical_failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R42 | 19 | 13 / 6 | 15 | 3 | 1 | 0 | 0 | 0 | 0 |
| R17 | 18 | 13 / 5 | 13 | 4 | 1 | 0 | 0 | 0 | 0 |

R42 的局部事实问题是 L85 所称 Luma 分会票显示与内嵌数据冲突：现存同期快照两者都显示余 1，未保存能支撑冲突的记录。因快照时间不是逐请求精确时间，记 `unsupported`，不据此断言历史上绝无冲突。

R17 的局部事实问题是 L71 的“总支出与占用时间都更高”：公开票价与会期足以推出门票更贵、会议更长，不能证明这位读者两次含交通住宿的总投入一定更高。后文正确承认个人差旅未知，故属于局部措辞越界，不构成核心结论反转。

这两处都没有作为关键结论不可缺少的未核前提；未触发 policy 的关键未核事实封顶规则。其余重要局限包括：未来上海实际交付尚不可测，Maker 个人满意原因与实际听过内容未知；两份都只能提出条件式判断。

## R42：绝对评分依据

冻结时间：2026-10-15 02:06:35 UTC。报告哈希：`d5b4d2b12cc9163544388d7a6227330802f7b6e6fd72aa813f3198bda2c7d8dd`。

### 真实性与可核验性：3 / 4

3/4。L13–17、L36、L78–87 的日期、讲者/摘要数量、票价票权及退转条款经官方原始快照核对；L30–32 的 Maker 上海比较基线与原文相符。L38 清楚区分摘要与建议追问。局部缺陷是 L85 所称 Luma 分会票状态冲突未获现有同期快照支持（F10）；其余未抽查引用不视为已经核实，因此不打 4。

### 问题覆盖与相关性：3 / 4

3/4。时间地点、费用结构、技术内容、Maker 上海增量、交流对象/机制及票权均正面回答，且纠正北京链接与上海经历的实体差异（L24、L76–106）。不足是技术筛选明显围绕 Agent/编程，主办方的 Open Models & AI Infra 与 Physical AI 两主线及跨两天内容分配没有完整呈现；读者仅确认学习交流并重，尚未确认如此具体的技术偏好。

### 分析、解释与综合：3 / 4

3/4。L28–34 把 Maker 的具体问题与 AIE 候选问题对应，L48–50 把背景资料与现场深度分开，L56–72 解释品牌、组织方、交流收益之间的关系。主要缺失是对增量仍只能作候选推断；尤其 Qoder 原文已谈恢复/停止，L30 的状态恢复补充并未证明实质新增。没有充分证据把本地机会成本与线上替代做更强比较。

### 对读者的有用性：4 / 4

4/4。L40–46 的问题—讲者—追问表可以直接使用，L89–104 的预算结构和场景门槛能由读者填入个人成本后应用，L114–119 逐项说明未知如何改变选择。技术学习与同行交流均有会前、现场、会后办法，未以好友数量或厂商性能作为回报保证。下一步与参会决策目标匹配。

### 信息密度：3 / 4

3/4。技术表、票种、退转规则、未知表大多增加实质信息，几乎无泛泛活动赞词。但本地/专程/特定内容三个判断在 L9、L18、L98–104 反复出现，图与 L70–72 的说明也有复述；压缩这些重复会提高密度。

### 表达与信息组织：4 / 4

4/4。结论在开头可定位，随后按增量—人和交流—成本—缺口展开，顺序符合决策逻辑。比较表把事实与判断分列，讲者表明确建议问题不是承诺。实际查看 R42-figure.png：两条路径字清楚、终点与正文对应，无暗示量化收益；图文足以让读者复述如何获取收益。

### 信源权威性与适配性：3 / 4

3/4。安排/价格用官网和公开票务，技术背景用团队原文，体验用两位亲历者，L132 明示公司自述与个人样本的适用边界。主要缺口是 Maker 普通参会体验样本不足及上海实际参会者构成未核；虽诚实披露，仍不能给关键体验判断最高强度证据分。

### 时效、局限与不确定性：4 / 4

4/4。L24、L50、L62、L78–87、L104–119 将未知直接用于推荐条件；过去会议与未来上海、公开票价与结算、正式日程与摘要、官方录像承诺与具体发布范围均有区分，并指出哪些安排落实会改变建议。L85 的局部冲突措辞问题计入真实性；整体不确定性处理贯穿推理。

### 主要缺陷

- **R42-D1 · minor · L85：**Luma 分会票状态冲突的说法没有现存同期原始快照支撑，需补当时冲突证据或删除该措辞。
- **R42-D2 · moderate · L26–52：**技术样本偏 Agent 与编程，未充分呈现官方两大主线；Maker Qoder 已谈恢复，所谓补充角度仍是待证实差异。

### 推断检查

**L9、L98–104 — 本地/顺路倾向去；专程或依赖特定内容先核安排。**这是条件式建议，不是已核事实。题目、票权、退票限制是已核前提；愿意交流、工作时间和总成本可接受由读者判断。理由链合理，但无法证明该用户具体学习增量。

### 逐条事实核验

**R42-F01 · 关键 · derived_correct**

报告位置：L13–14、L76。短摘：“11 月 5—6 日，周四、周五；上海虹桥祥源希尔顿酒店”。

来源：[原文](https://ai.engineer/shanghai/2026)。证据定位：evidence/aie-home-public.html；judge-one-evidence/aie-home-public.txt 的首屏及 Program；Python datetime 校验 2026-11-05/06。

核验说明：日期与场地见官方快照；星期由日期推算，确为周四/周五。

**R42-F02 · 关键 · derived_correct**

报告位置：L15、L36。短摘：“22 位讲者，其中 21 位有题目和摘要；缺最终时间、房间”。

来源：[原文](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。证据定位：evidence/aie-main-public.js；judge-one-evidence/roster-count.json；首页 Program preview。

核验说明：按唯一 slug 去重得到 22 位，只有 Marco Casalaina 无 sessionTitle/sessionAbstract；首页仍称 final titles/timings/rooms will follow。已公开方向与最终排期有区分。

**R42-F03 · 关键 · supported**

报告位置：L30–46。短摘：“Andrew 状态记忆、Jeff Agent 搜索、Chen 真实评测、Ivan 沙箱生命周期、Sarah 界面生成”。

来源：[原文](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。证据定位：judge-one-evidence/aie-selected-speakers.json；原始文件各相同 slug 的 sessionAbstract。

核验说明：五人的所属团队与主题简述均对应官方摘要；右栏额外问题明确是作者建议，没有冒充讲者承诺。

**R42-F04 · 关键 · supported**

报告位置：L30。短摘：“Qoder：长任务如何获得反馈并收敛”。

来源：[原文](https://aimakersummit.com/2026/shanghai/track/harness.html)。证据定位：judge-one-evidence/web-batch-a.json；Harness L32 的泮圣伟条目。

核验说明：原文明确长任务反馈、偏航、继续/恢复/停止。简述成立；但这也表示恢复并非 Maker 未覆盖，因此 AIE 的补充价值只能作为待验证假设。

**R42-F05 · 关键 · supported**

报告位置：L31。短摘：“得物：需求到验证的关口；Chatbox：审核带宽”。

来源：[原文](https://aimakersummit.com/2026/shanghai/track/coding.html)。证据定位：judge-one-evidence/web-batch-a.json；Coding L35 孙计划、曾宪条目。

核验说明：得物五道关口含需求澄清、TDD 和验证；Chatbox 条目指出 Agent 产出超过人审核能力。比较基线引用准确。

**R42-F06 · 关键 · supported**

报告位置：L32、L52。短摘：“美团、智源机器人评测；NVIDIA Agent 优化”。

来源：[原文](https://aimakersummit.com/2026/shanghai/track/eval.html)。证据定位：judge-one-evidence/web-batch-a.json；Eval L35 三位讲者条目。

核验说明：原文分别为具身泛化评测、机器人过程诊断、Agent 开发与评测优化，概括与实体匹配。

**R42-F07 · 关键 · supported**

报告位置：L78–85。短摘：“标准票 1,999 元含主会、分会、展览；展览票 299 元；未标售罄”。

来源：[原文](https://aie.anruicloud.com/api/api/tickets)。证据定位：evidence/aie-tickets-public.json；Data.items 的 currentPrice、description、soldOut。

核验说明：两个标准票记录 currentPrice 均为 1999，展览票 299，各 soldOut=false。报告正确保留公开字段与真实结算之间的边界。

**R42-F08 · 关键 · supported**

报告位置：L87。短摘：“10 月 1 日 23:59 后不退款；10 月 15 日 23:59 前可申请转让；中文未标时区”。

来源：[原文](https://aie.anruicloud.com/assets/pay-0b8ec5e2.js)。证据定位：evidence/aie-pay-page-public.js 的退票及退款政策须知；evidence/aie-luma-public.html 的 Refund Policy。

核验说明：中文原文给出相应日期和申请措辞；Luma 明示 PT。报告按调查日期判断已过退款期，未把申请权写成转让保证。

**R42-F09 · 关键 · derived_correct**

报告位置：L85。短摘：“Luma All Access USD 278、Expo USD 43”。

来源：[原文](https://luma.com/j9iqfmh8)。证据定位：evidence/aie-luma-public.html；ticket_types 的 cents=27800/4300、currency=usd、name。

核验说明：美分除以 100 为 278/43；报告未声称结算验证或做汇率价差推算。

**R42-F10 · 非关键 · unsupported**

报告位置：L85。短摘：“分会票存在页面与内嵌数据状态冲突”。

来源：[原文](https://luma.com/j9iqfmh8)。证据定位：evidence/aie-luma-public.html；显示 Breakout Session Pass / 1 Left；内嵌 spots_remaining=1、is_disabled=false。

核验说明：提供的同期快照中可见状态与内嵌数据一致，未找到所称冲突的原始记录。采集时间为统一核验时点，不能据此断言更早从未冲突；该措辞目前证据不足，且未用于核心推荐。

**R42-F11 · 关键 · supported**

报告位置：L7、L56。短摘：“伙伴独立组织；Standup Partners、AIE/Arogo；北京安锐承办收款”。

来源：[原文](https://ai.engineer/)。证据定位：judge-one-evidence/web-batch-a.json 的 AIE L68–74；evidence/aie-home-public.html 的 organizing team；evidence/aie-pay-page-public.js 的服务主体声明。

核验说明：AIE 主站明确 Independently-organized，并列上海由 Standup；上海官网和中文售票主体均与报告一致。未把品牌支持等同旗舰交付。

**R42-F12 · 关键 · supported**

报告位置：L58–60。短摘：“场间与展区可交流；面向工程师研究者技术负责人；英语普通话实时翻译”。

来源：[原文](https://ai.engineer/shanghai/2026)。证据定位：evidence/aie-home-public.html 的首屏、Program；evidence/aie-luma-public.html 的 Who should attend。

核验说明：公开形式和目标人群明确；这些只是组织者安排与招募定位，报告也未将其写成实际购票者统计或指定面谈权。

**R42-F13 · 关键 · supported**

报告位置：L52、L85、L114。短摘：“工作坊只有形式宣传；课程教师名额预约办法未查到”。

来源：[原文](https://luma.com/j9iqfmh8)。证据定位：evidence/aie-luma-public.html 的 Format；evidence/aie-home-public.html 的 Call for Speakers。

核验说明：所提供网页只见 hands-on workshops、征稿时长等，未见可报名课程清单。这里只确认其在报告所列渠道范围内未查到，非证明全网不存在。

**R42-F14 · 关键 · supported**

报告位置：L76、L106。短摘：“Maker 上海 9 月 12 日周六、历史全价 599 元、包含回看”。

来源：[原文](https://aimakersummit.com/2026/shanghai/)。证据定位：judge-one-evidence/web-batch-a.json；Maker 首页 L4、L70–80；日期星期计算。

核验说明：官方历史页面与票权直接支撑；报告没有把 599 写成用户实付或承诺其当前账户仍能回看。

**R42-F15 · 非关键 · supported**

报告位置：L106。短摘：“AIE 官方计划公开演讲录制；上海发布范围日期直播未知”。

来源：[原文](https://ai.engineer/shanghai/2026)。证据定位：evidence/aie-home-public.html 的 Call for Speakers：talk professionally recorded and published。

核验说明：征稿说明有录制并公开的承诺；没有给出每场覆盖、发布日期或上海直播安排。报告没有把通用承诺扩张为全部必可回看。

**R42-F16 · 非关键 · supported**

报告位置：L48、L125。短摘：“Andrew 署名的工具精简案例依赖清楚的数据语义文档”。

来源：[原文](https://vercel.com/blog/we-removed-80-percent-of-our-agents-tools)。证据定位：judge-one-evidence/web-batch-b.json；Vercel L124–139、L232–235、L353–359。

核验说明：作者、发布日期、文件系统探索与语义层文档前提均有原文支撑；未将厂商案例效果普遍化。

**R42-F17 · 非关键 · supported**

报告位置：L48、L126–127。短摘：“Exa 保留搜索决策路径；Arena 用真实交互比较组件”。

来源：[原文](https://exa.ai/blog/composing-a-search-engine)。证据定位：judge-one-evidence/web-batch-e.json；Exa L180–186、L217；judge-one-evidence/web-batch-d.json 中 https://arena.ai/blog/agent-arena-methodology L27–33、L72–92。

核验说明：Exa 有路径和决策追踪；Arena 用组件随机化及多信号比较，当前实现为 orchestrator。报告归为团队材料而非讲者个人贡献，且没有声称所有组件现已实测。

**R42-F18 · 非关键 · supported**

报告位置：L62。短摘：“Kai 认可同行讨论但不够亲密；Charlie 内容评价高但批评后勤”。

来源：[原文](https://kaizau.com/sita/2024-aiewf/)。证据定位：judge-one-evidence/web-batch-d.json 中 Kai L5–9；judge-one-evidence/web-batch-f.json 中 https://www.ignorance.ai/p/the-state-of-ai-engineering-2025 L19–22、L167。

核验说明：原文直接支撑两种个人体验，年份和会议地点未混用；报告清楚限制它们不能代表上海满意度。

**R42-F19 · 非关键 · supported**

报告位置：L76。短摘：“酒店地址红松东路 1116 号”。

来源：[原文](https://www.hilton.com/zh-hant/hotels/shashhi-hilton-shanghai-hongqiao/)。证据定位：judge-one-evidence/web-batch-d.json；Hilton L26–28；同期 Luma 原始快照 Location。

核验说明：酒店官方中文页与 Luma 快照地址一致。英文入口最初抓取失败，改用同酒店官方中文页核对；未以搜索摘要替代正文。

### 关键失败与局限

未发现 policy 定义的 `critical_failure`；`provisional=false`。这不是所有内容全量核验或现场效果已兑现的保证。

- 抽查 19 项论断，并非全量核验 22 个引用。Faye 论文作者背景、Skills 发布、Daytona 文章及全部来源日期未逐项复核。
- 原始 AIE/票务快照的捕获时间均注明为统一核验时点，不能据此断定网页在整天内从未变化；F10 因此记 unsupported 而非断言历史事实错误。
- Maker、AIE 主站、酒店与工程资料/个人复盘使用评审时访问的公开原文，访问日期记于证据文件；未用后续网页变化反向判错。
- 实际现场交付、购票结算、读者旅费和 Maker 所听场次均不可由这份公开材料评估；未创建订单。

## R17：绝对评分依据

冻结时间：2026-10-15 02:10:54 UTC。报告哈希：`9253ee72370723aa517542b7113de3a85d3ea48567e650def09b86734cea71eb`。

### 真实性与可核验性：3 / 4

3/4。L21–45 的 Maker 基线、讲者机构/摘要和数量，L61–78 的日期、时区转换、票价/票权、退款例外及平台转票状态经原文核对，抽样的两份亲历者转述也准确。唯一明确的局部越界是 L71 从门票/会期推出总支出与总占用时间都更高：该读者两次行程成本没有证据（F14）。不影响核心条件式结论，但使措辞准确性未达到 4。

### 问题覆盖与相关性：3 / 4

3/4。原任务要求的时间地点、费用、具体技术、Maker 增量、交流和条件均有正面答案，额外覆盖退款例外、不同票种、录像替代与语言支持边界。主要缺失是未交代上海为伙伴独立组织的活动及本地实际服务主体，这会帮助读者理解海外旗舰经验为何不能直接迁移；技术内容仍偏软件 Agent，只简述 Physical AI，尚非完整技术兴趣地图。

### 分析、解释与综合：3 / 4

3/4。L23–37 承认 Maker 的工程深度和恢复主题重合，再把增量定位为不同环节的案例与人；L51–57 比较明确社交权益与自由交流，L45–47、L80–84 把现场追问与录播替代、撞场、差旅取舍连接起来。限度是这些主要来自议题/宣传与少数海外经验；尚不能检验分享深度、相对 Maker 的实际新知识或上海交流兑现程度。

### 对读者的有用性：4 / 4

4/4。L27–33 的问题清单让读者自查相关性；L63–78 给出预算起点、三类票权及退转风险；L80–84 的三个议题/两个交流目标明确标为筛选建议，读者可以据此做自己的决定而不把阈值当收益测算。未知都连接到全通/分会/放弃及差旅选择，操作性充分。

### 信息密度：4 / 4

4/4。L21–39 的段落各自补充比较基线、案例、重叠与范围，L43–57 分别处理可听性与交流兑现，L61–84 集中成本票权与放弃条件。篇幅取舍服务决策，重申主要限于开头结论与最终执行门槛；没有依靠删掉解释来变短，也没有多余的讲者履历或不用于决定的数字。

### 表达与信息组织：4 / 4

4/4。组织从增量到可听性、交流、成本与放弃条件，读者可顺着问题完成判断。Harness 有通俗解释；题目/摘要、实测效果与作者建议有明确边界；票种并列表清楚，时间范围提醒避免误读。没有图也不影响表达，未因无图扣分。

### 信源权威性与适配性：3 / 4

3/4。官方数据用于计划、票价和条款，亲历者用于自己的经历，L101 明示两人同一海外场次、商业关系未审计、非上海满意度证明。对票务和摘要适配充分；上海实际交流对象和 Maker 个人满意来源仍无直接证据，关键体验争点缺少更直接资料，未达最高锚点。

### 时效、局限与不确定性：4 / 4

4/4。日期同时处理洛杉矶归档与上海核验；L25 区分准备讲与已兑现，L43–47 把排程/工作坊/翻译/录像未知映射到建议，L69–78 保留结算和退款例外，L88–91 明确什么新信息会改变结论。L71 的成本过度概括已在真实性扣分，周边预算与最终条件没有将其当保证。

### 主要缺陷

- **R17-D1 · minor · L71：**公开票价/会期证据不能保证这位读者总出行支出和总占用时间更高；应缩窄措辞。
- **R17-D2 · moderate · L49–55、L101：**虽正确限制旧金山经验外推，但未交代上海独立伙伴组织及实际服务主体，解释这一边界仍可更完整。

### 推断检查

**L37、L80–84 — 三个相关议题与两个明确交流目标作为购票门槛。**作者明确这是决策启发而非效益统计；可以帮助读者验证自己动机，但没有证据证明 3/2 是最优门槛。评分认可可用性而不把阈值视为经实证校准。

### 逐条事实核验

**R17-F01 · 关键 · supported**

报告位置：L21。短摘：“Maker 上海为 9 月 12 日、浦东滨江喜来登，公开全价 599，含会议、人脉群、面对面及回看”。

来源：[原文](https://aimakersummit.com/2026/shanghai/)。证据定位：judge-one-evidence/web-batch-a.json；Maker 首页 L4–6、L70–80。

核验说明：日期、上海场实体与公开历史权益全部对应原文；报告没有将公开价写成用户实付或用北京代替上海。

**R17-F02 · 关键 · supported**

报告位置：L23。短摘：“Maker 有 OpenSpec/规则检查、独立 Agent 审核、Qoder 恢复与 MiniMax 模型产品协同”。

来源：[原文](https://aimakersummit.com/2026/shanghai/track/harness.html)。证据定位：judge-one-evidence/web-batch-a.json；Harness L32 的赵志浩、泮圣伟、何涛条目。

核验说明：专题摘要确实列出相应内容，且报告据此明确两会有重合，没有用工程/应用二分制造虚假的差异。

**R17-F03 · 关键 · supported**

报告位置：L29–30、L33。短摘：“Jeff 讲检索新鲜度/归因，Andrew 讲状态/记忆/可观测性，Sarah 讲设计系统/交互状态/截图”。

来源：[原文](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。证据定位：evidence/aie-main-public.js；judge-one-evidence/aie-selected-speakers.json 对应 slug。

核验说明：摘要逐项支撑，问题栏是读者应用场景，第三列为追问建议，并未冒充承诺达到的效果。

**R17-F04 · 关键 · supported**

报告位置：L31。短摘：“Nancy 的任务证据与确定性校验；Faye 的诊断、修复、评测闭环”。

来源：[原文](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。证据定位：judge-one-evidence/R17-additional-speakers.json 中 nancy-wang；aie-selected-speakers.json 中 faye-zhang。

核验说明：Nancy 摘要包含 job manifests/runtime evidence/deterministic verification，Faye 摘要包含 diagnose–fix–evaluate、attempt memory。人物与机构均相符。

**R17-F05 · 关键 · supported**

报告位置：L32。短摘：“Kimi 唐飞虎讲上下文、工具、可靠性和成本；Ivan 讲沙箱生命周期”。

来源：[原文](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。证据定位：judge-one-evidence/R17-additional-speakers.json 中 tang-feihu；aie-selected-speakers.json 中 ivan-burazin。

核验说明：官方摘要直接支撑这些范围。报告没有采用摘要中的性能倍数证明参会收益。

**R17-F06 · 关键 · derived_correct**

报告位置：L13、L43。短摘：“22 位讲者、21 份题目摘要，Marco 只有简介”。

来源：[原文](https://ai.engineer/_next/static/chunks/5144-8308f14f8d639ccb.js)。证据定位：judge-one-evidence/roster-count.json；evidence/aie-main-public.js 中 marco-casalaina。

核验说明：唯一 slug 计数为 22，Marco 无题目/摘要，其他 21 位有；静态首页与交互详情展开程度不同的说明合理。

**R17-F07 · 关键 · supported**

报告位置：L43–45。短摘：“最终排期未定；工作坊名单、准入不足；中英翻译承诺但覆盖形式不明”。

来源：[原文](https://ai.engineer/shanghai/2026)。证据定位：evidence/aie-home-public.html 的 Program preview、Call for Speakers、首屏 Live translation。

核验说明：原始快照明确日程暂定；工作坊有征集和形式但无可报名细则；翻译仅一般声明。未查到只按列明页面范围判断。

**R17-F08 · 关键 · supported**

报告位置：L51–53。短摘：“官网有场间见讲者、Demo 和实现细节讨论；不能由名单推出实际参会者构成”。

来源：[原文](https://ai.engineer/shanghai/2026)。证据定位：evidence/aie-home-public.html 的 Program/Across the day；evidence/aie-luma-public.html 的 show_guest_list=false；Maker 页 L70–80。

核验说明：上海官网确有场间/展区交流宣传，未见排定定向匹配与保证席位。Maker 明示人脉群/面对面；报告只比较可核承诺，没有把不同组合写成组织更好。

**R17-F09 · 非关键 · supported**

报告位置：L55、L97。短摘：“Earl 2025 复盘有工作坊、午餐展位交谈、满场进不去、网络故障与偏概览内容”。

来源：[原文](https://slyracoon23.github.io/blog/posts/2025-06-06_ai_engineer_worlds_fair.html)。证据定位：judge-one-evidence/web-batch-g.json；原文 L0–6、L52、L69、L92、L101、L105–113、L133、L150。

核验说明：个人原文逐项支撑，日期/城市/作者匹配；报告仅用于现场预期，不把个人讲述当实际上海安排或总体调查。

**R17-F10 · 非关键 · supported**

报告位置：L55。短摘：“Charlie 认可内容，商业化感改善，提到拥挤与临期酒店成本”。

来源：[原文](https://www.ignorance.ai/p/the-state-of-ai-engineering-2025)。证据定位：judge-one-evidence/web-batch-f.json；Charlie L19–22。

核验说明：原文说跨会议人潮、庆幸避开临期高酒店价，随后认可内容及商业化感改善；概括没有将这些限定经验写成统计结论。

**R17-F11 · 关键 · derived_correct**

报告位置：L61。短摘：“11 月 5–6 日周四周五、闵行红松东路 1116；整体为首日 09:00 至次日 18:30”。

来源：[原文](https://luma.com/j9iqfmh8)。证据定位：evidence/aie-home-public.html；evidence/aie-pay-legal-public.js 活动基本信息；judge-one-evidence/R17-luma-excerpts.json。

核验说明：UTC start/end 与 Asia/Shanghai 转换分别为 11/05 09:00、11/06 18:30；星期计算正确。报告特意排除了每天均 09:00–18:30 的误读。

**R17-F12 · 关键 · derived_correct**

报告位置：L63–69。短摘：“中文 1999/299；Luma 全通 278、分会 97、展览 43 美元及对应准入”。

来源：[原文](https://aie.anruicloud.com/api/api/tickets)。证据定位：evidence/aie-tickets-public.json；evidence/aie-luma-public.html 的 ticket_types；judge-one-evidence/R17-luma-excerpts.json。

核验说明：中文普通价格与范围一致；Luma cents 27800/9700/4300 正确转换，分会说明仅 Breakout+Expo，当前快照可售。报告同时保留结算/库存/优惠资格边界。

**R17-F13 · 关键 · derived_correct**

报告位置：L71。短摘：“全通公开票价相对 Maker 599 多 1400，覆盖两天而非一天”。

来源：[原文](https://aie.anruicloud.com/api/api/tickets)。证据定位：evidence/aie-tickets-public.json；judge-one-evidence/web-batch-a.json 中 Maker 首页 L15、L74；计算 1999-599=1400。

核验说明：差价和会期比较正确，且明确比较的是两场公开全价，不是读者历史实付。

**R17-F14 · 非关键 · unsupported**

报告位置：L71。短摘：“总支出与占用时间都更高”。

来源：[原文](https://aimakersummit.com/2026/shanghai/)。证据定位：L71 上下文；evidence/aie-tickets-public.json；judge-one-evidence/web-batch-a.json 的 Maker 日期/票价；task.md 的出发地和预算未知。

核验说明：证据足以证明公开门票更贵、会期更长，但不足以断言这位读者含交通住宿的总支出及总占用时间一定更高。后文 L73–74 又正确承认出发地与住宿晚数未知。宜缩窄为门票支出与会期；这是局部措辞越界，不改变条件式推荐所依赖的已核票价/会期。

**R17-F15 · 关键 · supported**

报告位置：L76。短摘：“一般退款已截止；中文取消/延期有退款例外；嘉宾议程变化不自动同权；不赔差旅”。

来源：[原文](https://aie.anruicloud.com/assets/Footer-395108d9.js)。证据定位：evidence/aie-pay-legal-public.js 第三条、第五条；judge-one-evidence/R17-legal-excerpts.json；evidence/aie-luma-public.html Refund Policy。

核验说明：协议分别写明一般退票、活动取消全额退票/延期无法参加可申请退票、调整权及间接损失排除。报告保留一般/例外区别，且没有把中文例外自动套给 Luma。

**R17-F16 · 关键 · supported**

报告位置：L78、L90。短摘：“中文 10/15 23:59 前申请转让、未写时区；Luma 平台转票未启用”。

来源：[原文](https://aie.anruicloud.com/assets/Footer-395108d9.js)。证据定位：evidence/aie-pay-legal-public.js 与 aie-pay-page-public.js 退转条款；evidence/aie-luma-public.html 的 ticket_transfer_enabled=false；R17-luma-excerpts.json。

核验说明：原始条款与字段均支撑；报告将平台功能关闭与中文人工规则适用性区分，没有声称所有人工转让都绝对不可能。

**R17-F17 · 非关键 · supported**

报告位置：L47。短摘：“官方承诺录制并公开视频；上海发布时间与覆盖范围未知”。

来源：[原文](https://ai.engineer/shanghai/2026)。证据定位：evidence/aie-home-public.html；Call for Speakers 的 recorded and published 说明。

核验说明：官网征稿说明有公开录制承诺，但无上海具体覆盖与发布时间；报告建议等录播保留了前一句不确定性。

**R17-F18 · 非关键 · supported**

报告位置：L7、L39。短摘：“覆盖基础设施、空间表示、仿真、3D 世界等 Physical AI 内容”。

来源：[原文](https://ai.engineer/shanghai/2026)。证据定位：evidence/aie-home-public.html 的 Tracks/Program；judge-one-evidence/R17-additional-speakers.json 中 christoph-lassner。

核验说明：主线与具体空间智能摘要支持；报告把它作为软件 Agent 读者的可选拓展，没有将全部内容计入个人收益。

### 关键失败与局限

未发现 policy 定义的 `critical_failure`；`provisional=false`。这不是所有内容全量核验或现场效果已兑现的保证。

- 抽查 18 项论断，不等于所有句子全量核验；其中 5 项为非核心或补充事实/推断措辞。
- 现场演讲质量、交流兑现与实际普通参会者构成均不能由官方未来安排证实，报告对此作了保留。
- 公开价格、可售标记和平台转票字段来自同期快照；未登录、下单、验证最终附加费，也未联系主办方。
- Maker 及亲历者文章为评审时访问原文，已保存工具摘录与访问日期；不会把后续网页变化当作旧报告错误。

## 比较解释

本评审的绝对评分为 R42 82.5、R17 85.0。差分来自信息密度，不能解释成精密测量。两份均未发现 policy 所定义的 critical_failure，抽查关键支撑事实均已核；各有一条非核心措辞 unsupported。R17 的票种/退款例外与放弃条件更集中，R42 保留较多团队工程背景与会前会后方法。两者在本评审其余七维同分，不表示优缺点完全相同。本记录不能替代另一名独立评审，亦不作版本先后、效率或跨主题质量结论。

R17 对 Qoder 长任务恢复重合、中文退款例外、分会票范围与放弃门槛交代集中；R42 则提供更多可提前阅读的团队工程背景、现场追问问题和会后验证方法。对本课题而言，两者都能支持读者作条件式决定；这一份报告、这一名评审不能证明某个未知版本普遍更好或效率优化有效。

## 证据与冻结记录

本地 AIE/票务快照捕获时间来自 evidence/index.json，为统一核验时点而非逐请求时刻，全部 hash 已核对。新增公开原文访问日期为 UTC 2026-10-15（洛杉矶 2026-10-14）；web-batch-a 至 f 的 accessed_at 为本次核验批次参考时间，不声称是逐请求精确时间，g 单独记时。

- [原始评分 JSON](judge-one.json)
- R42 单份冻结记录（本机原件，未公开）
- R17 单份冻结记录（本机原件，未公开）
- 原始快照索引（本机原件，未公开）
- 本评审证据索引（本机原件，未公开）

Policy SHA-256：`d7be83d23b882db74b6225cb3720c1f247b9399eb67552f68424cd160f4abf7a`。需求 SHA-256：`2d8c8142ee11f7b30ad27f007b07f4a3948aa033bbf812051a791288f6ddd7d9`。R42 图 SHA-256：`3234ca16a11daceec5ac6f754e62c49b64cead6e13cfae75c96e6ad49c7edc64`。报告与 policy 未修改。

维度分、依据与比较前单份判断冻结。仅修正过证据定位词误植和非核心样本数量的笔误；没有因另一报告效果回改评分。

