# 网页采集与原始证据

`fetch_page.py` 是统一的公开页面证据采集入口。借鉴 Info2Action `src/fetch_url.py` 的请求、正文解析和错误页识别，新增内嵌 JSON、公开应用脚本和静态 GET 配置提取；不依赖该项目的运行服务、数据库或凭证。

```bash
python3 <skill>/scripts/fetch_page.py 'https://example.org/page' \
  --out-dir research_notes/evidence/example \
  --out research_notes/evidence/example.json
```

可一次传多个 URL，共用本次缓存和请求上限。默认最多 12 次请求、单次 15 秒、响应 8 MiB；可按目标和任务预算调整，不是抓满的配额。默认自动模式在取得丰富且未截断的内嵌 JSON，或完整 `article` 容器已超过 5,000 字符时，不继续下载应用脚本，并在 `resource_decisions` 记录原因。后者防止读一篇文章却下载整个网站应用；这只是提取启发式，不能证明关键字段齐全，仍缺时可用 `--all-resources`。`--no-resources` 只提取 HTML 和内嵌 JSON。已知 36 氪、即刻专用页面继续用 `fetch_article.py`；其他网页优先本脚本。

## 返回什么

- 按原始 URL 保存响应、时间、哈希和索引；正文、内嵌数据与脚本摘录分开标明出处和提取方法。不会默默把正文截成 5,000 字。
- 应用脚本只提取字面量和明确的同源依赖/GET 配置，不执行代码，不猜散列文件名，不扫描任意站点接口。`js_literal_heuristic` 不是结构化事实，研究员必须在原文件中核对关系与上下文。
- 分别输出 `network_attempts`（入口与关联资源的联网尝试）、`actual_network_requests`（HTTP 传输尝试，含重定向及传输失败）和 `evidence_reads`（含离线读取）。DNS 预校验失败只增加前者；HTTP 计数不代表服务端一定收到请求。每项保留日志，重定向也受共享上限约束。离线回放的两个联网计数均为零。一次脚本调用可能产生多次请求，不能隐去失败或将它们伪装成一次抓取。
- `coverage=not_assessed`：抓取器不判断用户的问题是否回答完整。`ok` 仅代表发现的提取路径成功；仍需研究员核关键字段、口径、页面位置。应用数据中某个词出现不等于事实已经证实。

## 状态与后续

`partial`：某些关联资源缺失、超预算或结构化提取达到容量上限；可用部分保留，指出尚缺什么再决定下一步。`blocked`：验证或拦截页；不当作正文。`network_error`：传输或平台权限问题；按照运行环境权限处理，不反复换 UA 或绕过限制。`needs_browser` / `empty`：静态路径没有取得内容；用现有浏览器能力获取渲染结果并保留原文，不能写成来源不存在。

通用脚本不能保证读取登录后、受验证限制或任意复杂交互中的全部内容。需要浏览器时选择已有受支持的浏览器工具或渲染运行时，不为一次调研安装环境。不要把脚本的状态直接抄成报告结论；“未提取到”与“未公布”是不同事实。

PDF、图片、音视频保存原始响应但返回 `unsupported`，交给相应读取工具；不会将二进制误报成网页正文。

## 固定证据回放

```bash
python3 <skill>/scripts/fetch_page.py 'https://example.org/page' \
  --replay existing-evidence/index.json \
  --out-dir research_notes/replay --out research_notes/replay.json
```

索引为 JSON 数组，每项含 `url`、`path`（相对索引目录或绝对路径）、可选 `sha256` 与 `captured_at`。脚本自身生成的 `index.json` 可直接回放。缺失快照明确返回 partial，不在离线测试中悄悄联网；采集时间与回放时间分开。

抓取器逻辑修改应验证：普通正文、短但有效的数据页、内嵌 JSON、关联脚本和公开数据、空壳/拦截、失败状态、预算、URL/重定向约束、原文哈希及回放一致性。真实复杂页面再做只读冒烟检查。完整性需要针对目标内容验证，不只数输出字数。
