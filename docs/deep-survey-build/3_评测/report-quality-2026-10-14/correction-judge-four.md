# R64 定向修复复核 · judge-four

**三项均为 resolved。** 新增身份和联系入口与原始快照相符，重复边界已减少，必要限定仍在。

此次已知是根据评审进行的定向修订，明确不是盲测。只复核三类问题，不重打整体分，不修改已冻结的 judge-four 原件，也不构成全报告重新评分或跨课题质量提升证明。

## 哈希与冻结

- R64 SHA-256：`f83c7a9947cb3044ee33602437eca27095423d44f250ba208094ee7915a5e1b4`
- R63 SHA-256：`0dbb0f8bc2617d294343e781fd0ea4bf03de4178e41bf6138b71b45b3b30710a`
- 指定差异 SHA-256：`3fdf87b84baee1a260fcf047109add8bce51beccda3ba08c874a6524082888cd`
- Policy SHA-256：`d7be83d23b882db74b6225cb3720c1f247b9399eb67552f68424cd160f4abf7a`
- 冻结时间：2026-10-15T02:55:07+00:00

原始 judge-four.json / .md 的哈希均与首次冻结值一致，见JSON记录。

## 首用 Harness 及重要人物身份/相关性是否解释

**resolved**；位置：R64.md:11；R64.md:70,76,80,82；R64.md:96；R64.md:100-109。

- 第11行在首次出现Harness时即解释提供任务资料、接入工具和检查执行结果；与evidence-r63/14.txt原文L5-L6的上下文/工具/流程及L32的机械检查、独立审核、偏航反馈相容，是入门解释而非排他的完整定义。
- 第76、96行补齐Exa和Daytona讲者身份；104-107行的11项新身份（含前两位）均已逐项回查01.html嘉宾卡片，见role_checks。
- 第102-109行继续以读者问题—讲者身份/方向—验证问题组织，身份补充没有变成无关履历堆叠。第70行已以Vercel与d0文章作者身份说明Andrew Qu的相关性，无需为本次修复强制加完整职衔。
- 第106行HTML“中间格式”、107行机器人数据“增量处理”分别由02.js的bin-liu（字符11885-12760）和xuanwo（18784-19658）摘要支持。

残留边界：

- Harness解释简化但足够建立本文所需概念，不是完整技术规范。
- 公开讲者角色仍不能证明普通参会者岗位分布或保证接触机会；第113行保留该界线。此未知不妨碍本项修复成立。

## 核实动作是否对应已知可用入口且没有扩大入口职责

**resolved**；位置：R64.md:147-149。

- 第147行给出确实存在的#schedule锚点和官网General inquiry邮箱，分别用于先看预览和询问缺项。
- 第148行把实际结算留给国内购票页面，将渠道资格、票种权益和退转问题交给原条款明确的票务咨询邮箱。
- 第149行使用一般咨询邮箱询问社交与语言，并将Standup Partners账号仅列为观察信息入口；明确尚未取得公开配对或预约入口。
- 具体锚点、邮箱和职责标签均已回查01.html及07.js，见contact_checks；未向任何地址发送消息。

残留边界：

- “可用”限于给定快照中确实公布且链接正确，不表示本次已验证邮箱投递、回复速度、账号最新状态或预约成功。
- 普通票细分权益仍待会务回答，修订提供了合理询问路径，没有把问题本身写成已解决。

## 重复边界是否减少且仍保留必要限定

**resolved**；位置：R64.md:17,23,28,30,36,46；R64.md:62,66,72,76,82,94,96,100,109；R64.md:119-124,132-149,158-160。

- 对照指定diff：旧第17行的长快照/结算说明缩成导向文末；旧第30、46、148、160行重复的未下单核验被收束到新第17、23、28、158行不同用途的说明。
- 技术材料不等于上海讲义或现场效果的总边界集中至第66行；旧第76、82、100行的重复警示缩减，旧第151行总括段删除，来源说明也缩短。
- 必要限定仍在：第28行不保证优惠资格；36行不保证阅读时仍能转让；62行未看Maker全录像；72行厂商自报五个查询及迁移前提；94、96行非性能实测/不采用未核基准；119-124行样本、利益关系和语言范围；138行等待代价；147-149行入口职责。
- 第158行仍保留UTC/洛杉矶时点、批次采集不是精确请求时间、访问时间不是发表时间，以及没有重新联网核验购票状态；第160行保留官方同源边界。

残留边界：

- 第13、66、132-138、147行仍提及日程或交流条件未知，但分别承担摘要、材料解释、决策门槛和核实动作，属于功能性复现。
- 本项只判断三类修订中的重复与限定，没有据此重新评价整篇信息密度或声称全报告质量提升。

## 新增人物身份逐项核对

均依据[大会官网](https://ai.engineer/shanghai/2026)的 evidence-r63/01.html 嘉宾卡片，采集时点为 2026-10-15T01:14:00Z。

| 人物 | 修订后的身份 | 报告位置 | 原文卡片定位 | 结果 |
| --- | --- | --- | --- | --- |
| Jeff Wang | Exa 联合创始人 | R64.md:76 | `speaker-jeff-wang` | supported |
| Ivan Burazin | Daytona 联合创始人兼 CEO | R64.md:96 | `speaker-ivan-burazin` | supported |
| Nancy Wang | 1Password 首席技术官 | R64.md:104 | `speaker-nancy-wang` | supported |
| Faye Zhang | Google Cloud Gemini Agents 工程师 | R64.md:104 | `speaker-faye-zhang` | supported |
| 小刀老师 / Tang Feihu | Kimi Agent 工程负责人 | R64.md:104 | `speaker-tang-feihu` | supported |
| Meder Kamalov | Oimo 创始人 | R64.md:105 | `speaker-meder-kamalov` | supported |
| Do Tuan Anh | Techcombank 数据与 AI 工程高级经理 | R64.md:105 | `speaker-do-tuan-anh` | supported |
| Sarah Chieng | Cerebras 开发者体验负责人 | R64.md:106 | `speaker-sarah-chieng` | supported |
| Bin Liu | HeyGen 工程副总裁 | R64.md:106 | `speaker-bin-liu` | supported |
| Christoph Lassner | World Labs 联合创始人 | R64.md:107 | `speaker-christoph-lassner` | supported |
| Ding Hao（Xuanwo） | LanceDB 高级工程师 | R64.md:107 | `speaker-xuanwo` | supported |

Faye Zhang 原卡片为 Staff AI Engineer, Gemini Agents；修订省略资深级别，未夸大。HTML“中间格式”及机器人数据“增量处理”另回查02.js对应摘要，均有依据。

## 新增联系入口逐项核对

### 官网 Program

- 修订位置：R64.md:147
- 来源：[原始来源](https://ai.engineer/shanghai/2026)
- 定位：evidence-r63/01.html：href="#schedule"（字符6565、9572、57655）与 id="schedule"（字符39052）；对应 Program preview。
- 结果：**supported**。锚点存在且指向议程预览。修订明确它不是最终安排已确定的保证。

### General inquiry：hello@ai.engineer

- 修订位置：R64.md:147,149
- 来源：[原始来源](https://ai.engineer/shanghai/2026)
- 定位：evidence-r63/01.html：页脚 Contact 中 mailto 位于字符57835，标签 General inquiry 位于57897。
- 结果：**supported**。官网一般咨询入口，可合理询问议程、普通票社交准入与语言支持；报告未保证回复、权威确认或预约成功。

### 国内票务邮箱：infoaieshanghai@gmail.com

- 修订位置：R64.md:148
- 来源：[原始来源](https://aie.anruicloud.com/assets/Footer-395108d9.js)
- 定位：evidence-r63/07.js：service 第九条称购票疑问可通过官方邮箱联系，字符7502起标为票务咨询；Footer 链接字符15142起同样标为票务咨询；转让条款字符6125。
- 结果：**supported**。渠道资格、票种权益和退转属于明确票务语境；修订保留“未保证其能回答全部议程问题”，没有扩大为大会全部事项负责人。

### Standup Partners 公开账号

- 修订位置：R64.md:149
- 来源：[原始来源](https://ai.engineer/shanghai/2026)
- 定位：evidence-r63/01.html：organizer-links 内该URL位于字符56981，标签 X / @StandupPartners；相邻主办方介绍。
- 结果：**supported**。只建议留意公开账号，并明确不是已确认的预约渠道；没有把社媒账号变成配对、预约或票务保证。

## 复核边界

- 只阅读修订稿、指定差异及对应原始证据；未读取作者修订说明、其他评审或Skill改动。
- 未联网扩研；未重跑其他无关已核事实；未创建订单或发送询问。
- 字符定位从0起按Unicode字符计数；网页工具原文的L编号沿用原摘录。
- 所有结论限定于已保存快照，不证明新网页或现场状态。
