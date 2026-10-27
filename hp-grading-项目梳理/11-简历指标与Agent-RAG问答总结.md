# 简历指标与 Agent / RAG 问答总结

> 架构口径更新（2026-10-23）：以 [Agent 架构确认基线](agent-architecture-handoff.md) 为准。前端只访问 Java；Java 保存业务问答；Python 使用 LangChain `create_agent`（底层 LangGraph）及 PostgreSQL checkpointer。同步滚动摘要保存在 checkpoint，不另建摘要表。本文描述确认方案，不据此新增上线或个人成果声明。

> 整理日期：2026-09-11  
> 范围：简历内容取舍、HP-Grading 业务指标、Agent/RAG 目标架构、取消控制、流式渲染与参考项目审查。  
> 使用方式：可作为简历编辑器改稿和面试复盘的依据；其中“已实现”和“方案设计”必须分开表述。

## 0. 先明确事实边界

| 内容 | 当前结论 | 简历/面试表述原则 |
| --- | --- | --- |
| HP-Grading 与 xEduAI | 已有 Java 业务中台、Python 算法服务、RabbitMQ 异步处理等代码基础。 | 可按源码和个人实际职责描述。 |
| 多角色 Agent、教学资源 RAG | 用户于 2026-10-09 确认已有开发代码，但代码不在当前 `hp/` 仓库；本目录的 05、06 是产品与技术文档，不能据此否定仓库外的实现。当前尚未取得该代码路径、提交记录和运行/评测证据。 | 按真实开发经历准备面试，可以写“开发”“研发验证”；具体已实现的模块、部署状态及指标须以仓库外代码和记录为准，不能仅从方案文档推定已生产上线。 |
| 人工审核、取消与跨实例恢复 | 现有文档详细描述了目标架构；尚未核对仓库外 Agent 代码中各项能力的完成情况。 | 只对实际实现的能力使用“完成/实现”，其余作为技术取舍或下一步改进回答。 |
| HP 学校量、频次、耗时、准确率 | 来自本人回忆和测试集口径，不是线上日志导出的统计。 | 可写已确认的范围值，并标记为测试或业务口径；不要再延伸为未经验证的 GMV、DAU 等。 |
| Agent/RAG 的用户量、文档量、转化率 | 当前资料未提供上线范围、真实用户量、入库文档量或转化率；仓库外代码的部署状态待核对。 | 没有统计记录前不写成成果指标；20% 使用率只能作为容量规划假设。 |

## 1. 简历内容与版式

### Q：简历的顺序和“工作经历 / 项目经历”应怎样组织？

**结论：教育经历置顶；工作经历和项目经历分为两个独立板块。**

- 工作经历应保留两段：
  - 深启智能科技有限公司，后端开发工程师，2025-08-11 至 2026-08-26；
  - 东方财富信息股份有限公司，2021-07 至 2024-06。
- 项目经历分别写在两段工作期间完成的项目，而不是把项目条目混入“工作经历”。
- HTML 简历编辑器已采用 A4 双页、可编辑内容、右上角照片上传/更换、浏览器打印导出 PDF 的方式。教育经历三列已改为等宽网格，学校名称居中，避免原先列距不均。

### Q：证书、个人项目、东财“资讯接口与日志仓库”和“智能在线客服”是否保留？

**建议保留，但压缩为高信息密度的一行或一条。**

- 证书能补强后端基础；个人项目展示产品意识、持续交付和非工作时段的自主性。
- 东财的高并发资讯接口与日志仓库应至少保留一条，分别支撑服务端吞吐和数据工程能力。
- 智能在线客服也建议保留一条，它能把“模型应用”与传统后端项目区分开。
- 不建议为了凑版面删掉上述内容；优先删除空泛形容词和重复技术栈。

### Q：内容不足两页，是压成一页，还是扩展成两页？

**选择信息密度合理的两页，而不是靠增大字号填空。**

- 字号保持约 10–10.2pt，标题层级清晰，避免为了填满页面把字体和行距放大。
- 第一页应完整容纳 HP 的主要项目要点，减少工作经历中的重复职责描述。
- 第二页用于东财项目、技能、证书与 RunHub 等个人项目；留少量呼吸空间正常，避免人为填充无效内容。

### Q：RunHub 小程序可以加入吗？

**可以，优先替换较弱的跑鞋个人项目。**

已知的项目资料显示其采用 Java 21、Spring Boot 3.5.9、Maven 多模块、MyBatis 和 Supabase PostgreSQL，包含赛事、身份、通知等模块，并有文章解析、OCR/LLM 结构化和确定性工作流的设计。正式写入前仍需补齐本人确认的：开发时间、实际负责模块、是否已发布、真实用户/内容量和可公开的成果链接；未确认的数据不编造。

## 2. HP-Grading 可用于简历的指标

### Q：根据学校、班级和学科信息，日均作业量与批改量大约是多少？

已确认的业务口径：累计试用学校超过 100 所；常规使用约 50 所；其中约 5–10 所为跨三个初中年级、接近每日或隔日布置作业的高频学校。每年级约 5 个班、每班约 50 人；主要为语文、数学、英语，数学量较语文/英语各高约 20%。

用于容量估算的假设为：高频学校平均每 1.5 天覆盖一次全部班级与三科；其余常规学校平均每周覆盖一次。单校有 `3 × 5 × 3 = 45` 个“班级-学科”作业批次，每批约 50 份学生作答。

| 指标 | 估算区间 | 中位示例（8 所高频） |
| --- | ---: | ---: |
| 日均班级-学科作业批次 | 439–557 批 | 510 批 |
| 日均学生提交 / 批改份数 | 21,964–27,857 份 | 25,500 份 |
| 其中语文批改量 | 约总量 31.25% | 约 7,969 份/日 |
| 其中英语批改量 | 约总量 31.25% | 约 7,969 份/日 |
| 其中数学批改量 | 约总量 37.5% | 约 9,563 份/日 |

计算式：日均批次为 `30H + (50-H)×45/7`，其中 `H` 是 5–10 所高频学校；日均学生作答为批次乘以 50。

**注意：这是面向容量规划的推算，不能在简历中表述为真实线上日均量。** 简历可安全使用“累计试用 100+ 所、常规使用 50+ 所、高频学校 5–10 所”等本人确认范围。

### Q：批改耗时和准确率怎样写？

- 定标通常在 5 分钟内完成；常规批改通常在 3 分钟内完成，具体随图片数量、OCR 与模型调用耗时波动。
- 测试集综合批改准确率超过 96%，数学超过 97%。这里应明确是**测试集**准确率，不等同于全部线上样本准确率。
- 对应的简历语句可为：“完善定标、批改与结果回写链路，定标通常 5 分钟内、常规批改通常 3 分钟内完成（随图片数波动）；测试集综合准确率超过 96%，数学超过 97%。”

### Q：能否按 20% 用户使用 Agent/RAG 来补指标？

不能把这个比例写成既成事实。用户已确认 Agent/RAG 有仓库外开发代码，但当前资料没有其上线范围和使用统计；20% 只能作为内部容量规划的情景假设，而非用户量、调用量或文档规模的简历成果。对外可以按实际开发事实写“开发/研发验证”，是否可写“上线”及服务规模须另有记录支持。

## 3. Agent 的双向交互、审核与取消

### Q：这类体验是 WebSocket 吗？用户审核后，结果如何回到模型？

**不一定需要 WebSocket。推荐的 Web 架构是 SSE 下行 + HTTP 上行。**

1. 前端 `POST /runs` 创建一次运行，后端返回 `run_id` 和 `thread_id`；前端以 SSE 订阅该运行的输出。
2. 模型文本、工具进度和状态从服务端单向推至前端；这部分使用 SSE 即可。
3. 当流程进入人工审核，LangGraph 将状态持久化并在 `interrupt()` 暂停。前端收到 `approval_required` 后展示确认/取消界面。
4. 用户点击确认、拒绝或补充信息，前端再 `POST /runs/{run_id}/approval`；后端使用同一个 `thread_id` 和 `Command(resume=...)` 恢复图执行。恢复值就是 `interrupt()` 的返回值。

所以产品看起来像“全双工”，但不是把一个模型连接一直挂在 WebSocket 上；它是“流式下行 + 事件化上行 + 持久状态恢复”。LangGraph 的中断与恢复语义见 [官方 interrupts 文档](https://docs.langchain.com/oss/python/langgraph/interrupts)。

### Q：审核取消和“正在运行时取消”是同一件事吗？

不是，应该分两种状态处理。

| 场景 | 建议操作 | 是否需要继续调用模型 |
| --- | --- | --- |
| 审核等待中（图已暂停） | 将审批标记为取消；需要清理/审计时，以同一 `thread_id` 用 `Command(resume={decision: 'cancel'})` 进入取消分支。 | 通常不需要。 |
| 模型/工具正在运行 | `POST /runs/{run_id}/cancel`，将运行原子置为 `CANCEL_REQUESTED`，通知执行者停止。 | 不把它伪装成一条聊天消息。 |

恢复节点会从节点开头重执行，而非从 `interrupt()` 那一行精确续跑。因此中断前的写操作必须使用幂等键或移到中断之后，避免确认后重复创建记录。

### Q：多实例部署时，请求落到 B 实例，实际任务跑在 A 实例，怎么把取消传过去？要用数据库吗？

**数据库保存真相；进程内映射负责快速中断；消息系统只是加速通知。**

推荐模型：

```text
浏览器 --POST cancel--> 实例 B
                         │
                         ├─ 原子更新 agent_run：RUNNING → CANCEL_REQUESTED
                         └─ 发布 cancel(run_id, owner=A)
                                      │
                    Redis Pub/Sub / RabbitMQ / NATS / Kafka
                                      │
实例 A 订阅到消息 → activeRuns[run_id].cancel_event.set() / task.cancel()
                                      │
模型客户端与工具收到取消信号，在安全点退出
```

- 持久表（MySQL/PostgreSQL 均可）建议保存 `run_id`、状态、所属实例、租约、取消标记和审计时间；这是故障恢复的依据。
- A 实例在内存维护 `activeRuns[run_id] = {task, cancel_event, ...}` 很常见，但它只是本实例的短生命周期索引，不能替代数据库。
- A 即使漏掉通知，也应在模型调用前、工具调用前后、长任务分段处轮询持久状态；实例宕机后由租约机制接管，已取消的任务不可恢复执行。
- 浏览器断开 SSE 不等于取消任务；必须有显式取消接口。

### Q：Redis Pub/Sub 是不是消息队列？分布式 Agent 中常用吗？没有 Redis 怎么办？

Redis Pub/Sub 常用于**低延迟、尽力而为的控制通知**，但它不是带持久消费确认的可靠队列：订阅者离线时消息会丢失。因此不能只靠它保存取消事实。

- 小型多实例服务常见组合是“数据库状态 + Redis Pub/Sub”；Redis 负责让 owner 实例尽快得到取消信号，数据库负责最终一致性。
- 需要可回放、消费确认或削峰时，可选 Redis Streams、RabbitMQ、Kafka、NATS JetStream，或 Temporal 等任务编排系统。
- 没有 Redis 时，HP 已有 RabbitMQ 可承载通知；也可以使用数据库轮询作为保底。若使用 RabbitMQ 的多个竞争消费者，取消消息可能被非 owner 实例消费，因此要使用按实例路由/每实例队列或广播机制。

## 4. Pi 本地 Agent 的取消逻辑

### Q：Pi 没有 Redis 时如何取消？双层循环会不会等到外层才能停？

Pi 运行在单一 Node.js 进程内，不需要跨实例传递控制。其 `Agent` 在内存中保存当前运行的 `activeRun`，其中含 `AbortController`；调用 `agent.abort()` 会执行 `abortController.abort()`。

```text
UI 点击取消
  → agent.abort()
  → activeRun.abortController.abort()
  → AbortSignal 传入模型流请求和工具执行
  → SDK / 工具响应信号后中止，写入 stopReason: aborted，结束本次 run
```

这不是“必须等内层循环结束、再到外层循环才检查”的设计。取消信号会向正在执行的流请求和工具传播；但它仍是协作式取消——模型 SDK 或工具若不响应 `AbortSignal`，无法凭空强杀远端调用。Pi 也会在工具前后检查中断状态。

Pi 的两层循环含义不同：内层负责模型输出 → 工具 → 工具观察结果的连续回合；外层用于 agent 看似停止后接收后续消息。`steer()` 是在当前 assistant 回合边界插入引导信息，并非硬取消。源码可见 [agent.ts](https://github.com/badlogic/pi-mono/blob/main/packages/agent/src/agent.ts) 与 [agent-loop.ts](https://github.com/badlogic/pi-mono/blob/main/packages/agent/src/agent-loop.ts)。

## 5. 流式 Markdown 与 LaTex 的渲染

### Q：后端要不要等 Markdown 或公式闭合后再推送？前端缓冲是不是“压输出”？

**后端不等待闭合，立即发送原始增量；前端的缓冲只服务于视觉渲染，不是截留网络输出。**

以 Markdown 加粗为例：

| 时刻 | 模型输出块 | 后端 | 前端状态 / 显示 |
| --- | --- | --- | --- |
| 1 | `这道题的` | 立即发 `text_delta` | `rawText = 这道题的`，显示普通文本。 |
| 2 | ` **关键` | 立即发 `text_delta` | `rawText = 这道题的 **关键`，闭合前可显示普通/转义文本。 |
| 3 | `结论** 是先通分。` | 立即发 `text_delta` | 重新解析全文，`关键结论` 显示为加粗。 |

前端可采用两种任选其一的策略：

1. **简单策略**：使用 `requestAnimationFrame` 或约 50ms 防抖，把累计 `rawText` 交给 Markdown 解析器；未闭合语法降级为普通文本，闭合后重渲染。
2. **精细策略**：对未闭合的块保留“安全尾部”，已完成段落立即渲染，未完成部分以纯文本或“生成中”展示。网络中的 token 仍已即时到达。

表格和代码块更适合按块缓冲：表格至少等到表头和分隔行完整后再转为表格；大型表格、图表或卡片最好让模型输出经过 schema 校验的 JSON，而非依赖流式 Markdown。渲染 HTML 前必须做白名单清洗，避免模型输出造成 XSS。

以 LaTex 为例：

| 时刻 | 模型输出块 | 前端处理 |
| --- | --- | --- |
| 1 | `解为 $x = ` | 累计原文；尚未出现结束 `$`，不交给 KaTeX/MathJax。 |
| 2 | `\\frac{-b \\pm` | 继续以文本或公式生成占位显示。SSE JSON 中的 `\\` 被浏览器解析为单个反斜杠。 |
| 3 | `\\sqrt{b^2-4ac}}{2a}$` | 检测到成对 `$`，由 `remark-math + KaTeX` 或 MathJax 渲染完整公式。 |

HP 的作业批改现有 MQ 回调不是逐 token 的公式展示。若 RAG 展示教材公式，应同时保存公式原图/原始对象和可检索的 Math OCR LaTex；切块时不要把一个公式拆开。

## 6. 为什么要划分事件类型

### Q：`text_delta`、`tool_status`、`approval_required`、`artifact_ready` 是谁做的？是否过于复杂？

这是**后端适配层定义的稳定产品协议**。框架和模型的原始事件不稳定、语义也不同；后端将其映射为前端能稳定消费的少量 SSE 事件。前端负责按事件类型渲染，不应从模型自然语言里猜“工具是否完成”。

| 事件 | 后端何时发出 | 前端动作 |
| --- | --- | --- |
| `text_delta` | 收到模型文字增量 | 追加到本轮 `rawText`，按上一节规则渲染。 |
| `tool_status` | 工具开始、进度更新、成功或失败 | 展示“正在查询 / 已完成”等状态卡，而非伪造模型文本。 |
| `approval_required` | 图执行命中人工审核中断 | 显示确认、拒绝、补充信息控件，并保存 `approval_id`。 |
| `artifact_ready` | 报告/PDF/文件已生成并安全存储 | 显示下载或预览入口。 |
| `completed` / `cancelled` / `error` | 本次 run 终态 | 收尾 UI、停止 loading、允许下一轮请求。 |

例子：“生成小明的数学学习报告 PDF”。后端可依次发送：

```text
text_delta:       “我已汇总小明近期的错题情况。”
tool_status:      get_learning_report = succeeded
approval_required: { action: "generate_pdf", draft_id: "..." }
（用户确认，POST approval）
tool_status:      generate_pdf = queued / running
artifact_ready:   { url: "..." }
completed
```

对于普通问答，只有 `text_delta + completed` 就够了。不要一开始就为全部事件建立复杂前端；有真实工具、审批或产物后再逐类加入。

### Q：LangChain/LangGraph 能自动完成事件划分吗？

它们能提供**原始流事件和状态能力**，但不能替产品决定最终 SSE 协议。

- LangGraph 的 `astream` 可使用 `messages`（模型 token）、`updates`（节点/状态变化）、`values`（状态快照）和 `custom`（业务自定义进度）等流模式；中断状态也可以从图状态读取。
- 应用后端仍需把这些映射成上述 `text_delta`、`tool_status`、`approval_required`、`artifact_ready` 等领域事件，补上 `run_id`、时间、序号、重连游标和错误码。
- LangChain 的回调/事件流可帮助获取模型和工具过程，但“审核按钮”“文件下载”“取消终态”是应用层职责。

官方流式能力见 [LangGraph streaming 文档](https://docs.langchain.com/oss/python/langgraph/event-streaming) 和 [Graph API 文档](https://docs.langchain.com/oss/python/langgraph/graph-api)。

## 7. smart-appointment-ai-agent 参考项目审查

### Q：参考项目是否有取消功能，如何实现？

**当前代码没有通用的“停止本次模型生成 / 取消 run”功能。**

- [web/routes.py](../../smart-appointment-ai-agent/web/routes.py) 只有 `POST /chat/stream`，返回 `StreamingResponse(token_generator(), media_type="text/plain")`；接口没有 `run_id`、取消端点或运行状态存储。
- [web/templates/index.html](../../smart-appointment-ai-agent/web/templates/index.html) 用 `fetch('/chat/stream')` 和 `res.body.getReader()` 接收内容；没有取消按钮，也没有 `AbortController`。
- [agents/consultant/response_generator.py](../../smart-appointment-ai-agent/agents/consultant/response_generator.py) 先 `await self.llm.ainvoke(...)` 拿到完整回答，再逐字符 `yield`；这是一种“模拟流式”，并不等同于原生模型 token 流，用户无法在模型生成期间中止远端调用。

项目中出现的“取消”是预约业务领域的取消，而非 Agent 运行控制。其 README 对“流式输出”的描述宽于当前实现，应以代码审查结果为准。

## 8. 可落地的最小实施顺序

1. 先实现 `run_id`、持久运行表、SSE 的 `text_delta / completed / error` 和显式取消接口；取消状态以数据库为准。
2. 在单实例使用 `activeRuns` 与 `asyncio.Task` / 取消事件，保证模型客户端与工具接收取消信号。
3. 扩展到多实例时再加入 Redis Pub/Sub 或 HP 已有 RabbitMQ 的定向通知，并保留数据库轮询保底。
4. 需要人工确认的低风险动作才接 LangGraph `interrupt + Command(resume)`；涉及成绩、答案、批改记录的写入继续由 Java 业务系统进行最终鉴权和审计。
5. 前端先实现原始 token 累积和安全 Markdown/LaTex 降级渲染；复杂表格、报表和文件使用结构化事件，而非依赖 Markdown 文本猜测。

## 9. Agent 历史、Checkpoint 与跨实例恢复

### Q：Codex 本地用 JSONL 保存历史；线上分布式 Agent 应如何保存？

Codex 本地会把会话历史保存在 `CODEX_HOME` 下的 JSONL 文件中，例如 `~/.codex/history.jsonl`。这适合单机追加写、离线回放和本地调试；其历史文件可配置上限，超限时淘汰最旧记录。[OpenAI Docs：Codex 历史记录持久化](https://learn.chatgpt.com/zh-Hans/docs/config-file/config-advanced)

线上分布式 Agent 不应把单个 JSONL 当作主数据源，而应分层保存：

```text
thread（会话）
  ├─ message（用户、助手、工具消息）
  ├─ run（一次 Agent 执行）
  │   ├─ event（流式事件、工具状态、审批）
  │   ├─ checkpoint（图状态快照）
  │   └─ artifact（PDF、图片、报告）
  └─ memory（摘要、用户偏好、可检索长期记忆）
```

| 数据 | 推荐位置 | 原因 |
| --- | --- | --- |
| 会话、消息、运行状态、审批和审计 | MySQL / PostgreSQL | 跨实例可读、可鉴权、可审计，是业务最终事实。 |
| LangGraph checkpoint | HP 选定 PostgreSQL checkpointer | 审核暂停、故障恢复和同一会话恢复。生产环境不能只用 `InMemorySaver`。 |
| 图片、PDF、批改产物和大 JSON | TOS / OSS / S3 | 数据库只存 URL、摘要、校验值，降低主库负担。 |
| token 增量、工具进度 | 可选 Redis Streams / Kafka / 事件表 | 支持重连与排障；通常不必永久保存每个 token，最终保存完整回答即可。 |
| 长期记忆与 RAG 检索 | PostgreSQL + pgvector，或 ES / 向量库 | 跨会话提取相关偏好与知识，不把全部历史塞进模型上下文。 |
| 缓存、限流、快速取消通知 | Redis | 低延迟辅助设施，不是最终事实来源。 |

模型每轮不应加载全部历史，HP 从同一 thread 的 checkpoint 恢复摘要后 state，再按需加入 RAG 证据；近期保留窗口待测，不固定为 10–20 轮，长期记忆另行设计。学生姓名、成绩和作业图片还需按租户/学校隔离，保存访问审计，并设置脱敏与保留期。

### Q：进入 `WAITING_APPROVAL` 后，原实例上的线程会一直等待吗？

**不应该。** 要区分以下三种东西：

- `thread_id`：Agent 会话/图状态的持久标识；
- 实例 A 上的 Python 协程或工作线程：本次 HTTP/SSE 请求的执行单元；
- checkpoint：由 `thread_id` 索引的、可恢复的图状态快照。

推荐流程：

```text
实例 A 运行 graph(thread_id=th_01)
  → 执行到 interrupt()
  → checkpoint 写入共享持久化存储
  → 向前端发 approval_required
  → 本次 SSE / HTTP handler 正常结束，协程与内存上下文释放
```

因此，审核等待不占用实例 A 的执行线程，也不要求原 SSE 连接一直存在。LangGraph 通过 checkpointer 将图的状态按 `thread_id` 保存；同一 ID 是恢复指针，而不是某个实例线程的句柄。[LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

### Q：确认请求落到实例 B 后，是不是重新开线程继续处理？

**是，实例 B 会新建本次 HTTP handler / 协程；但它恢复的是同一个 Agent 会话，而不是唤醒实例 A 的旧线程。**

```text
用户 → POST /approvals/ap_01/decision
           ↓（负载均衡）
实例 B
  → 校验 run 仍为 WAITING_APPROVAL
  → 原子置为 RESUMING
  → 以同一 thread_id 从共享 checkpointer 读取状态
  → graph.invoke(Command(resume={approved: true}), config={thread_id: th_01})
  → 继续运行，最终写 COMPLETED / FAILED / CANCELLED
```

恢复时必须复用原 `thread_id`；新 ID 会创建一条空状态的新会话。`Command(resume=...)` 的值会成为节点内 `interrupt()` 的返回值。LangGraph 会从包含 `interrupt()` 的节点开头重新执行，而不是从该行精确续跑，所以中断之前的写库、发消息、生成文件等副作用应使用幂等键或后移到中断之后。[LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

建议运行状态为：

```text
RUNNING → WAITING_APPROVAL → RESUMING → RUNNING → COMPLETED / FAILED / CANCELLED
```

确认接口要做条件更新，防止双击、网络重试或两个实例同时恢复：

```sql
UPDATE agent_run
SET status = 'RESUMING', approved_at = NOW()
WHERE id = :run_id
  AND status = 'WAITING_APPROVAL';
```

只有成功更新一行的请求能继续调用 `Command(resume=...)`；其他请求应返回“审批已处理”。运行中的任务仍依赖 `owner_instance + activeRuns` 来快速取消；已经暂停等待审核的任务不再绑定 owner，任意健康实例都可以恢复。

## 10. 后续待补的真实信息

- RunHub：时间、本人模块、发布状态、真实规模和可公开链接。
- HP：如能导出脱敏日志，再用真实日/周/月使用量替换第 2 节的容量估算。
- Agent/RAG：用户已确认仓库外存在开发代码。待补代码路径、本人提交/模块、可运行入口、演示或测试结果、部署状态；核对后再确定哪些能力可写为“实现”、哪些仍属方案或改进计划。

## 11. 2026-10-09 简历逐句对照：面试官可能质疑什么

以下“原句”摘自 `../简历编辑器/简历编辑器.html` 的文件默认内容。编辑器会从浏览器 `localStorage` 恢复用户修改，因此浏览器当前显示的版本可能不同。建议句供比较，不等于已经修改简历。Agent/RAG 按本人确认的仓库外真实开发经历处理；“已开发”不自动等于“已在慧批生产上线”。

| 疑点 | 当前简历原句 | 建议修改后的表达 | 修改理由及面试证据 |
| --- | --- | --- | --- |
| Agent/RAG 与慧批生产系统的关系不清 | “面向中学作业场景的 AI 批改、学情分析与教学助手平台；通过 Java 业务中台和 RabbitMQ 编排 Python 算法平台，结合多角色 Agent 与教学资源 RAG 支撑讲评、答疑、备课及学习报告。” | “面向中学作业场景的 AI 批改与学情分析平台；Java 业务中台通过 RabbitMQ 编排 Python 算法链路。在已有作业与学情数据之上，开发多角色 Agent 与教学资料 RAG，用于讲评、答疑、备课和学习报告的研发验证。” | 保留真实开发事实，同时写清与原有生产业务的关系和当前验证阶段。若确已上线，可将末尾改为明确的上线范围并准备发布记录。参见 [05](05-HP多角色对话Agent产品文档.md)、[06](06-HP教学资源RAG产品与技术方案.md)。 |
| Agent 实现范围、个人贡献和验证深度含混 | “完成教师、学生、家长多角色 Agent 的研发验证：使用 FastAPI、LangChain/LangGraph，以‘任务按钮直达 Workflow、自由文本进入 Agent’分流，并由 checkpoint 保存多轮会话状态。” | “开发教师、学生、家长多角色 Agent 的研发版本：基于 FastAPI 与 LangGraph 区分任务按钮 Workflow 和自由对话入口，使用 checkpoint 延续多轮任务状态；负责【本人实际实现的入口/状态/工具模块】，以【可展示的用例或测试】验证。” | 当前句可保留“研发验证”，但面试官一定会问哪个模块由本人编码、checkpoint 用何种存储、怎样验证。方括号需按仓库外代码补齐，不应凭 05 文档猜测。 |
| “10 个 Tool”容易被追问是否均已可调用 | “将 ChatBI 分析、HP 作业/题目/批改事实、题库推荐及草案/文件产物封装为 10 个高层 Domain Tools，在执行端复核教师—班级、家长—孩子和学生本人数据域。” | “开发面向 ChatBI 分析、HP 批改事实与教学场景的领域工具，按教师、学生、家长角色控制可调用范围，并在工具执行端校验业务数据域；已实现【实际数量及名称】个 Tool。” | 05 文档有产品能力盘点和工具收敛设计，但“10 个”须由真实注册表、代码或测试确认。若确为 10 个，保留数字并备好清单、输入输出和权限拒绝用例。 |
| RAG 流程列得很满，缺少实际验证结果 | “完成教材、教参和辅导资料 RAG Pipeline 的研发验证，覆盖解析/OCR、语义分块、Embedding、BM25 + Dense 混合召回、元数据过滤、Rerank 与 Evidence Pack，并以 Trace、审计和 Evaluation Harness 验证检索、引用、权限与异常恢复。” | “开发教学资料 RAG 研发版本，完成【已实现的解析/OCR、分块、索引和检索环节】，将教材版本等元数据用于检索过滤，并以【实际评测集及结果】检查检索、引用和越权用例。” | 真实开发应如实写；但 BM25、Dense、Rerank、Evidence Pack、审计、Eval Harness 每项都需要代码或产物支持。未完成的环节从已实现清单中删除，放到面试的后续优化部分。[06](06-HP教学资源RAG产品与技术方案.md) 是架构依据。 |
| MQ 可靠性成果写得过满 | “以 requestId + version + 状态机处理任务追踪、回调乱序、幂等重试和异常恢复。” | “通过 requestId 关联算法请求与回调，以 version 比较拦截旧回调，并用任务状态、监控和补偿任务定位及恢复异常；持续完善消息幂等与失败重投。” | `AlgoOutputMessageListener` 存在版本比较、手动 ACK 和耗时记录，但业务处理异常后仍会 ACK，不能概括为完整可靠重试；[07](07-HP图片AI工作流与MQ架构优化.md) 将 outbox、DLQ、条件状态迁移列为改进项。 |
| 指标没有样本与统计口径 | “累计试用学校 100+ 所、常规使用 50+ 所，其中 5—10 所为跨年级高频使用。”、“定标通常 5 分钟内、常规批改通常 3 分钟内完成”、“测试集综合批改准确率超过 96%，数学超过 97%。” | “据业务使用口径，累计试用学校 100+ 所、常规使用约 50 所；定标与常规批改通常分别在 5 分钟、3 分钟内完成（随图片数波动）。在【测试集名称、样本量、统计时间】上，综合批改准确率超过 96%，数学超过 97%。” | 原数字可保留，但应备好“学校去重与活跃定义、耗时起止点、测试集规模、判对单位”。没有样本量时不要补造，面试口头明确测试集而非线上总体；参见本文第 2 节。 |
| 正式岗位与项目负责人称谓可能被误读 | 工作经历：“后端开发工程师”；慧批项目：“后端 / AI应用负责人”；工作经历：“主导 HP-Grading、ChatBI 架构与业务开发”。 | 项目角色改为“HP-Grading、ChatBI 后端负责人；Agent/RAG 研发参与范围：【实际职责】”，或保留原称谓并在项目第一句说明“负责两个既有服务的开发维护，Agent/RAG 负责【具体模块】”。 | 说明“负责人”是项目分工还是正式职级；现有 [04](04-事实依据与简历准备清单.md) 支持 HP/ChatBI 主导、xEduAI 协同，不能自动推定所有 AI 应用模块均由一人主导。 |
| 技能栏的熟练程度无法区分 | “Python、FastAPI、Pydantic、LangChain、LangGraph、OCR、VLM/LLM、Agent、RAG”；另列 ClickHouse、Elasticsearch、VikingDB、RabbitMQ、Kafka、Flink 等。 | “后端主力：Java、Spring Boot、MySQL、Redis、RabbitMQ、MongoDB；AI 应用实践：Python、FastAPI、LangGraph、RAG 检索与评测；其他项目经验：Kafka、Flink、ClickHouse、Elasticsearch、VikingDB。” | 不删除真实技术，但按主力/实践/项目经验分层。每项至少准备一个实际场景、本人修改过的模块和取舍。 |
| 履历时间线没有解释 | 东方财富“2021.07—2024.06”；深启智能“2025.08—2026.08”；标题“4 年经验”。 | 日期保留真实记录；在面试中准备 2024.07—2025.07 和 2026.09 至今的真实经历说明。若这两段有正式工作或可验证项目，再补入简历。 | 两段任职相加约 4 年，标题本身基本合理；空档不应编造。 |

## 12. 模拟面试问答

原 Q1—Q12 已连同追加的技术追问集中到 [12-模拟面试官提问与回答.md](12-模拟面试官提问与回答.md)。后续模拟面试问答统一维护在该文档；本文保留简历指标、技术背景与逐句对照。

2026-10-15 增补的 RAG 优化追问位于该文档 Q19-A～Q19-C：父子 Chunk 的普通存储、动态邻接扩展、存储与上下文代价、父块边界问题；标题路径是否进入 Embedding；LLM 元数据生成的实际用途及成本。技术依据统一维护在 [06 第24节](06-HP教学资源RAG产品与技术方案.md)，参考项目细节见 [10 第12.3节](10-MODULAR-RAG-MCP-SERVER参考项目分析.md)。当前独立本地 PoC 已完成原文递归切片，尚未实现父子扩展、标题路径增强及检索评测，不作为已上线或效果提升指标。
