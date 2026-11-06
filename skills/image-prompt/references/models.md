# 模型参数卡

核实日期：2026-11-06（北京时间）。来源全部是官方文档原文，链接在文末。模型更新很快，用户提到这里没有的版本，或者离核实日期已过去两个月以上，交付时说一句「参数卡是 11-06 核的」。

这里没写的参数，一律当作不存在。

| 节 | 内容 |
|---|---|
| 0 | 怎么选 |
| 1 | GPT Image 2.6（Flare / Sunburst） |
| 2 | GPT Image 2.5（Flare / Sunburst） |
| 3 | codex 内置生图 |
| 4 | Nano Banana Pro |
| 5 | Nano Banana 2.1 |
| 6 | Seedream 5.0 Pro |
| 7 | 渠道：Lovart、ChatGPT、Gemini App |

---

## 0 怎么选

| 需求 | 先试 | 依据 |
|---|---|---|
| 密集小字、复杂版式、精确局部编辑 | GPT Image 2.6 Sunburst | OpenAI：细节、版式、编辑精度要求高时从 Sunburst 开始 |
| 快速出草稿、多数常规图 | GPT Image 2.6 Flare | OpenAI：Flare 偏速度 |
| GIF 动图、SVG 矢量 | GPT Image 2.6 | 只有它有这两种输出 |
| 在图上圈出要改的地方 | GPT Image 2.5 / 2.6（markup）或 Seedream 5.0 Pro（框选坐标） | 两家都有标注编辑 |
| 多张参考图融合、要风格参考图、专业物料 | Nano Banana Pro | Google：Pro 面向专业物料，只有它有风格参考图名额 |
| 出图量大要省钱、超长横幅或竖幅（1:4、8:1） | Nano Banana 2.1 | Google：Pro 的高效版；极端比例只有它有 |
| 要按真实世界的事物画（真实地点、当下的事） | Nano Banana Pro / 2.1（搜索 grounding） | 两者都能联网搜索；2.1 还能搜图片 |
| 要指定 Hex 色值、用坐标精确框选编辑 | Seedream 5.0 Pro | 字节：Pro 支持 Hex 色值和 `<bbox>` 坐标 |

谁画得更好看，官方没有可比的数据，不替用户下结论。

## 1 GPT Image 2.6（Flare / Sunburst）

- **模型 ID**：`gpt-image-2.6-flare`（偏速度）、`gpt-image-2.6-sunburst`（偏细节、版式、编辑精度）。2026-11-04（美国时间）发布。
- **接口**：只能走 Image API 的 `POST /v1/images/generations` 和 `POST /v1/images/edits`。Responses API、Batch 都不支持。
- **quality**：`auto`（默认）/ `low` / `medium` / `high` / `xhigh` / `max`。从 `medium` 起步；密集标注、图表、要放进幻灯片的图用 `high`；`xhigh` / `max` 只在看得出提升时用。
- **complexity**（2.6 独有）：`low` / `medium` / `high`，不传默认 `high`。管的是「规划」，和 quality 互相独立，不另收费；档位越高越慢，也可能带进不想要的改动。
  - 只改一个细节的编辑：从 `low` 开始。
  - prompt 把版式、文字、风格都写死了：调高 complexity 差别不大。
  - 设计细节留给模型发挥：用 `high`。
  - 一次只调一个：比 complexity 时固定 quality；版式对了但小字看不清，就在同一个 complexity 下调 quality。
- **size**：自定义尺寸两边都是 16 的倍数，宽高比在 1:3 到 3:1 之间。官方示例：`1024x1024`、`1536x1024`、`1024x1536`、`1536x864`（16:9 幻灯片）。2.6 的单边上限和像素上限官方没写，别承诺 4K。
- **background**：要透明设 `transparent`，prompt 里同时写「孤立的主体，无背景」。
- **output_format**：
  - `svg`：只能用在 generations，`n` 必须是 1，不支持流式。实际是先出一张参考图再转成 SVG，quality 和 complexity 作用在那张参考图上。可以配透明背景。账号可能要开通权限。
  - `gif`：generations 和 edits 都能用，返回原生动图。`frame_count` 2–16（默认 9），`frame_duration_ms` 20–2000（默认 200），`size` 指每一帧。动作和循环方式写在 prompt 里。账号可能要开通 GIF 预览权限。
- **markup**（edits）：另传一张透明 PNG，上面画圈、草图或标注；和第一张输入图同尺寸，必须有透明像素，不能直接画在原图上。只作用于第一张输入图，后面的图只当参考。不能和 mask 同时用。改什么写在 prompt 里，结尾加「成图里去掉红圈」。
- **没有的**：seed、sampler、steps、CFG、negative_prompt；`style` 是给已退役模型的旧参数，风格写进 prompt；2.6 的编辑不传 `input_fidelity`。prompt 最长 32000 字符。

## 2 GPT Image 2.5（Flare / Sunburst）

- **模型 ID**：`gpt-image-2.5-flare`、`gpt-image-2.5-sunburst`（快照带 `-2026-09-08`）。2026-09-08 发布。Image API 和 Responses API 的生图工具都能用。
- **quality**：和 2.6 一样六档。没有 complexity。
- **size**：两边 16 的倍数，单边不超过 3840，长短边比不超过 3:1，总像素 655,360 到 8,294,400；超过 3,686,400（2560x1440）算实验性。常用：`1024x1024`、`1536x1024`、`1024x1536`、`2048x2048`、`2048x1152`、`3840x2160`、`2160x3840`。
- **markup**：支持，用法同 2.6。
- **没有的**：GIF、SVG 输出，以及 2.6 那一节列的那些。

已经在 2.5 上跑顺的流程，换 2.6 前用同一套 prompt 和参数先对比一轮。

## 3 codex 内置生图

- 没有可调参数。画幅、尺寸写进 prompt（「横版 16:9」）和给 codex 的任务说明里。
- 背后是 GPT Image 系的模型，按 GPT Image 的写法写。
- 改图、多图合成：codex 能不能把传入的图当底图改、能不能用 markup，都没核过。这类需求提醒用户指定一个模型。具体型号没核到；codex 走的接口 2.6 不支持，所以不是 2.6，要 GIF、SVG、complexity 得改走 API 或 ChatGPT。

## 4 Nano Banana Pro

- **模型 ID**：`gemini-3-pro-image`，2026-05-28 正式版。`gemini-3-pro-image-preview` 已于 2026-06-25 关停，别再写。
- **思考**：默认开启，API 里关不掉。
- **参数写在哪**：Gemini API 现在默认用 Interactions API，写在 `response_format={"type": "image", "aspect_ratio": "16:9", "image_size": "2K"}`。老的 `generateContent` 写在 `imageConfig` 里（`aspectRatio`、`imageSize`），官方标为旧接口。
- **image_size**：`1K` / `2K` / `4K`，K 必须大写，不传默认 `1K`。探索用 1K，定稿 2K，要印刷或裁切再上 4K。
- **aspect_ratio**：`1:1` `2:3` `3:2` `3:4` `4:3` `4:5` `5:4` `9:16` `16:9` `21:9`。不设的话，有输入图就跟输入图一样大，没有就出 1:1 方图——所以总要设。1:4、4:1、1:8、8:1 Gemini API 文档说只有 2.1 有，Vertex 的 Pro 页却列了，两处矛盾，Pro 别用这几个。
- **参考图**：最多 14 张，其中物体最多 6 张、人物最多 5 张、风格参考最多 3 张。prompt 里逐张写角色。
- **搜索 grounding**：能联网搜网页（不能搜图片）。
- **改图**：官方推荐多轮对话迭代；关键细节（脸、logo）编辑时要再详细描述一遍。
- **没有的**：negative prompt、guidance、CFG。Imagen 已整体关停，网上那些 Imagen 的 `negativePrompt`、`guidanceScale`、`seed` 和这里无关。
- **价格参考**：约 0.134 美元一张（1K / 2K），4K 约 0.24 美元。

## 5 Nano Banana 2.1

- **模型 ID**：`gemini-nano-banana-2.1`，2026-10-06 正式版，是 Nano Banana 2（`gemini-3.1-flash-image`，已标弃用）的更新版。Google 的定位是 Pro 的「高效版」，没说它比 Pro 强。
- **参数**：同 Pro 的写法（`response_format` 或旧的 `imageConfig`），另有思考档位 `generation_config={"thinking_level": ...}`：`minimal` / `medium` / `high`，默认 `medium`。
- **image_size**：`1K` / `2K` / `4K`（大写 K）。
- **aspect_ratio**：Pro 那 10 种，再加 `1:4` `4:1` `1:8` `8:1`。
- **参考图**：最多 14 张，其中物体最多 10 张、人物最多 4 张，没有风格参考名额。
- **搜索 grounding**：网页搜索和图片搜索都有；但不能用搜到的真人照片当参考。
- **会报错的参数**（Vertex 文档）：`seed`、`temperature`、`topP`、`topK`、`logprobs`。
- **价格参考**：约 0.034 美元一张（1K），2K 约 0.050，4K 约 0.113。

Google 没有给 2.1 单独的写法指南，按 Nano Banana 通用建议写（SKILL.md 的写法已经覆盖）。两条 Google 特别强调的：

- 说清要出图（「生成一张……的图」），否则模型可能只回文字。
- 要文字准确时，可以先在对话里把文案定好，再让它出带字的图。

## 6 Seedream 5.0 Pro

- **模型 ID**：`doubao-seedream-5-0-pro-260628`（火山方舟），2026-07-08 发布。另有 Flash `doubao-seedream-5-0-flash-260915`，能力同 Pro，更快更便宜。5.0 Lite（`doubao-seedream-5-0-260128`）2026-11-24 14:00（北京时间）关停，别再用。
- **prompt 长度**：中文不超过 300 字，英文不超过 600 词。字太多，模型会只抓重点、漏元素。这是几家里最短的，写 Seedream 时先压长度。
- **size**：`1K` / `1.5K` / `2K`（默认 `2K`），或直接写「宽x高」，总像素 921,600 到 4,624,220。Pro 没有 4K。
- **宽高比**：官方推荐的做法是 size 只给档位，宽高比用自然语言写进 prompt（「竖版 9:16 的教育信息图海报」）。这是唯一一家建议把比例写进 prompt 的。
- **画面文字**：放在双引号里。中英文都支持，另支持 14 种语言。颜色可以直接写 Hex 值。
- **参考图**：最多 10 张，用「图1、图2」指代，写清每张图编辑或参考什么（「用图1 的人物替换图2 的人物，参考图3 的风格」）。
- **编辑定位**：可以在图上画箭头、框、涂鸦标出位置；Pro 还认坐标标签 `<point>x y</point>`、`<bbox>x1 y1 x2 y2</bbox>`，取值 0–999，左上角是原点。编辑时别用含糊的代词，写明其余保持不变。
- **watermark**：默认 `true`，右下角加「AI 生成」字样，不要就设 `false`。
- **不支持**：组图（`sequential_image_generation`，Pro 不能配）、联网搜索、流式输出；参数表里没有 `seed`、`guidance_scale`。要一组图就一张一张出，每张带同一段角色描述。

火山的提示词指南写明适用于 5.0 Lite / 4.5 / 4.0，Pro 没有专门的指南；上面关于写法的几条照搬自通用指南，是推断。

## 7 渠道

**Lovart 命令行**：用 `--include-tools generate_image_<模型>` 指定模型，这只是强提示，出图后要核实际用了哪个模型。画幅和分辨率写在发给 Lovart 的前置说明里，再接 prompt 原文，例如：

```text
请只调用一次生图工具，原样使用下面这段提示词，不要改写、不要扩写、不要翻译，生成 1 张图，画幅 16:9，分辨率选 2K。提示词：
<prompt 原文>
```

Lovart 只出静态图，2.6 的 GIF 要去 ChatGPT 或 API。

**ChatGPT**：GIF 和 markup 在 ChatGPT 里也能用，SVG 只有 API 有。模型选择器里能调「推理强度」，它和 API 的 complexity 是不是一回事、能不能选 Flare / Sunburst 和 quality，官方没写清，别替用户断言。出 GIF 时 prompt 开头明说「做一张能无限循环的 GIF 动图」。

**Gemini App**：界面里选不了的参数（比例、分辨率）写进 prompt 末尾。

## 来源

- OpenAI 图像生成指南：https://developers.openai.com/api/docs/guides/image-generation
- OpenAI 图像 prompt 指南：https://developers.openai.com/api/docs/guides/image-prompting
- OpenAI 更新日志：https://developers.openai.com/api/docs/changelog
- OpenAI 模型页：https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst
- ChatGPT Images 2.6 系统卡：https://deploymentsafety.openai.com/chatgpt-images-2-6
- Gemini 图像生成文档：https://aistudio.google.com/docs/image-generation
- Gemini 更新日志与弃用：https://aistudio.google.com/docs/changelog 、https://aistudio.google.com/docs/deprecations
- Nano Banana 2.1 模型页：https://aistudio.google.com/docs/models/gemini-nano-banana-2.1
- Vertex Nano Banana 2.1：https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/nano-banana-2-1
- Google Nano Banana Pro 写法建议：https://blog.google/products-and-platforms/products/gemini/prompting-tips-nano-banana-pro/
- 火山方舟生图 API：https://www.volcengine.com/docs/82379/1541523
- 火山方舟提示词指南：https://www.volcengine.com/docs/82379/1829186
- Seedream 5.0 Pro 编辑指南：https://docs.volcengine.com/docs/zh/ark/seedream-5-0-pro-editing-guide.md
- 火山方舟模型下线公告：https://docs.volcengine.com/docs/zh/ark/model-deprecation-notice.md
