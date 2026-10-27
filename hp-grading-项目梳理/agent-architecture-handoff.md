# Agent 对话架构与滚动摘要：技术交接

> 用途：将当前讨论交给后续 ChatGPT 对话继续设计与实现。本文按可读取的原始对话记录整理，并补充截至 2026-10-23 可核实的 LangChain/LangGraph 技术说明。原线程中早期助手答复正文只剩引用标记，因此本文不声称逐字复原那些答复；遇到无法从记录确认的细节，明确标为实现时核实项。

## 1. 交接摘要

用户正在已有 Java 后端的项目中增加 Python Agent 对话能力，计划使用 LangChain `create_agent`（底层使用 LangGraph 运行状态图）及 PostgreSQL checkpointer。设计目标是：Java 继续作为前端唯一后端入口并拥有业务对话记录；Python/LangGraph 管理 Agent 执行状态与短期上下文。对话较长时，在下一轮 Agent 模型调用前进行同步滚动摘要；摘要/消息状态随 checkpoint 保存，不单独创建摘要表。摘要触发时通过 SSE 告知前端。

### 用户已明确确认的三条架构决策

1. **请求链路**：所有接口由前端调用 Java，再由 Java 转发到 Python；前端不直接调用 Python。
2. **双重持久化职责**：Java 将用户提问与大模型最终回答保存到业务历史表；Python 也通过 LangGraph checkpoint 保存 Agent 状态。
3. **摘要存储**：使用 LangChain `create_agent`，短期记忆压缩采用 LangChain 的 summarization 能力；摘要/压缩后的 Agent 消息状态放在 checkpoint，不另建摘要表。

> 以上是用户确认的架构方向。表结构、事务边界、保留策略、具体版本与参数还没有定案。

## 2. 问答式讨论记录与技术说明

### Q1：前端应直接连 Python/LangGraph，还是先到 Java？历史记录由谁负责？

**用户问题**：项目已有 Java 后端，Agent 用 Python/LangGraph。前端要直接连接 Python，还是经 Java 再调用 Python？如果直连，历史记录是否就由 Python 保存、查询？实际项目该怎样选？

**当前决定**：前端 → Java → Python。Java 是对前端提供的业务 API 入口；Java 负责会话列表及业务消息的查询/写入。Python 提供 Agent 执行能力，不让前端绕开 Java 直接访问。

**实现含义**：
- Java 负责鉴权、租户/用户权限、会话元数据、对话列表和用户可见消息的持久化/查询。
- Java 调用 Python 时，把稳定的会话标识、当前用户输入、必要的运行参数传过去。
- Python 返回/流式转发 Agent 输出；Java 可把最终答案写入业务消息表。
- Java 与 Python 各自保存数据不是重复保存同一用途：业务历史服务产品查询、审计和展示；checkpoint 服务 Agent 恢复与状态延续。

### Q2：Java 业务历史和 Python checkpoint 里分别有什么？后续构造上下文是否必须查询 Java？

**用户问题**：如果 Java 保存用户问题和最终回答，Python 保存 checkpoint，那么 checkpoint 是否也有用户提问和模型最终回答？后续 Python 构造上下文要从哪里取历史？如果 checkpoint 没有，就必须调用 Java 查历史，这是否合适？

**技术说明**：LangGraph checkpoint 保存某一 `thread_id` 的图状态快照/更新；若 Agent 的状态包含 `messages`，经过状态更新的用户消息、AI 消息以及工具消息通常会随状态 checkpoint 持久化。但它不是与 Java 业务消息表自动同步的镜像，也不保证只含最终展示给用户的问答。工具调用、工具结果、中间 AI 消息、摘要替换后的消息序列、运行期间状态等都可能存在。具体保存哪些内容由 Agent state、执行过程、checkpoint 配置及版本决定。

在选定 LangChain `SummarizationMiddleware` 后，后续模型上下文通常由同一 LangGraph thread 恢复的 Agent state 提供；不能据此推断系统会在每轮主动调用 Java 查询完整业务历史。Java 历史与 Agent 状态必须按各自职责管理。若需要用 Java 历史重建或纠正 Agent 状态，应明确实现导入/重建逻辑，而非假设 checkpointer 会自行查询 Java。

**工程注意**：业务消息落库与 Python checkpoint 写入通常不是跨库原子事务。设计幂等键、状态标记、重试/补偿与最终一致性检查，避免出现 Java 已记录用户消息但 Agent 运行未成功、或 Agent 成功而业务最终回答未落库的孤儿状态。

### Q3：conversation_id、thread_id、run_id、message_id 分别是什么？

**用户问题**：新聊天对应整个聊天还是某次提问？LangGraph thread ID 是哪个？Java 把 conversation ID 传 Python 时两者差异是什么？

**推荐映射**：

| 标识 | 含义 | 生命周期/用途 |
|---|---|---|
| `conversation_id` | 产品层一段持续聊天/会话的 ID | Java 业务主键，用户可打开并继续提问的整段聊天 |
| `thread_id` | LangGraph checkpoint 的状态分区键 | 同一会话持续传同一个值，以恢复该会话的 Agent state；推荐 `thread_id = conversation_id` |
| `run_id` | 一次 Agent 执行/一次用户请求的运行标识 | 每轮新建，用于追踪、日志、取消、重试及 SSE 关联；不是会话 ID |
| `message_id` | 一条业务消息的 ID | 每条用户消息/最终 AI 回复各自唯一，用于消息表、幂等和前端展示 |

`thread_id = conversation_id` 是本方案推荐的一对一映射，不是 LangGraph 强制要求。若需要环境/租户隔离，可在授权边界内使用 namespaced thread key，但要保留到业务会话的映射。`run_id`、`message_id` 应分开；一次 run 可产生多条内部消息，但对业务表而言往往只将最终回答作为 assistant 展示消息（是否另存工具/中间过程由产品要求决定）。

### Q4：LangGraph 的删减、裁剪、摘要能力如何理解？`SummarizationMiddleware` 做什么？

**用户问题**：此前提到 LangGraph 支持裁剪、删除、摘要等管理方式，摘要怎么使用？计划在上下文占 60% 或 70% 时压缩前 N 轮或 X tokens。

**技术说明**：不要把“LangGraph 有通用摘要开关”与 LangChain Agent 的中间件混为一谈。当前 LangChain Python `create_agent` 可配置预置 `SummarizationMiddleware`；LangGraph 提供状态、checkpoint、线程与图执行基础设施。具体摘要行为由 middleware/自定义状态逻辑实现。

当前参考 API 中 `SummarizationMiddleware` 的关键参数：
- `trigger`：达到何种消息数、token 数或模型上下文比例时触发；可以用一个条件或条件组合。列表的多个条件表示满足其中任一项即可触发，单个 dict 内多个条件表示需同时满足。
- `keep`：摘要后保留多少近期消息/ token / 上下文比例；默认值和支持项应以项目锁定版本的 API 为准。
- `trim_tokens_to_summarize`：准备摘要模型输入时，可限制送去生成摘要的消息 token 数；这是摘要调用输入的裁减上限，不等同于摘要后保留的近期上下文。
- `token_counter`：用于估算消息 token 的计数器；模型提供商/工具 schema 等实际请求开销可能使估算与服务端计数不同。

中间件的核心效果是：在模型调用前检查上下文，达到条件时对较旧消息生成摘要，并保留近期消息，避免工具调用与工具结果等消息对被不安全地拆开。具体行为、默认值、参数格式、支持的模型与版本可能随 LangChain 版本变化；实施时以锁定版本的官方 API 和实际 state 检查为准。

配置概念示意（**不是已确认阈值，也不是可直接照搬的最终生产参数**）：

```python
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware

agent = create_agent(
    model,
    tools=tools,
    middleware=[
        SummarizationMiddleware(
            model=summary_model,
            trigger=("fraction", 0.7),  # 示例：模型上下文约 70% 时触发
            keep=("messages", 20),     # 示例：摘要后保留最近消息
        )
    ],
    checkpointer=checkpointer,
)
```

`trigger`、`keep` 的具体值必须依据模型上下文窗口、消息规模、工具定义、提示词、成本和延迟测试决定。用户在早期举的 60%/70%、前 N 轮/X tokens 是设计讨论示例，不是产品已确定参数。

### Q5：摘要应该在第二轮结束后台做，还是第三轮提问时同步做？压缩期间新请求会不会卡住？

**用户问题**：是在第三轮用户提问时开始压缩，还是第二轮结束后自动检查/压缩？若压缩期间用户马上发第三轮，是否需要等之前任务？

**用户最终选择**：在下一次（讨论中举例为第三轮）模型调用开始前检测；如达到阈值，先同步压缩，再生成该轮回答。可接受增加首字延迟。压缩时通过 SSE 给前端提示“正在压缩上下文”。

**重要语义**：该决定表达的是“摘要发生在下一轮模型回答之前”，不必然表示必须等到 HTTP 请求进入后才开始计算阈值；可在请求进入后、Agent 模型调用前由 middleware 执行。后台在上一轮结束后预先压缩是另一种调度方案，不是用户当前选定方案。

**并发问题**：同一 `thread_id` 上同时运行两个 turn 时，不能假设第二个请求会自动知道或等待第一个正在执行的摘要。需要应用层协调，通常按 conversation/thread 做串行化或分布式互斥，并定义队列、拒绝/重试、超时及取消行为。单进程内锁不能保护多 Python 实例；多实例部署需共享协调机制（例如数据库 advisory lock/锁表或具租约的分布式锁），同时防止锁过期后旧执行仍写回造成状态覆盖。具体选型待定。

### Q6：summarize 会自动存数据库吗？能否单独建摘要表？

**用户问题**：使用 LangChain `create_agent` 和 summarize 后，摘要是否会自动保存到数据库，能否配置单独的摘要表？

**用户决策**：不单独创建摘要表；让压缩后的状态随 LangGraph checkpoint 保存。

**精确说明**：`SummarizationMiddleware` 本身负责处理 Agent 消息状态中的摘要与保留，不等于“自己连接并写入某张业务数据库表”。持久化由 Agent 配置的 LangGraph checkpointer 承担。运行时需要给 `create_agent` 配置 PostgreSQL checkpointer，并在调用时提供稳定的 `thread_id`；checkpoint 中保存的是图状态，不是一张专门的“摘要记录表”。PostgreSQL saver 自己会有其 checkpoint/schema 存储结构，这是 checkpointer 的基础设施表，不等于另建业务摘要表。

“summarize 自动保存摘要到数据库”应理解为组合行为：middleware 更新 agent state + checkpointer 按执行策略保存 state。确认生产持久化还需检查 checkpointer 已正确配置、PostgreSQL schema 初始化完成、执行确实写入 checkpoint，以及 durability/异常行为符合要求。不能只安装 middleware 就假设摘要已持久化。

### Q7：第三轮已生成摘要后，第四轮会主动取摘要还是重新取完整历史？

**用户问题**：第三轮生成的摘要会不会保存并被第四轮使用，而不再取之前所有原始历史？

**技术说明**：若同一个 `thread_id` 恢复 checkpoint，且摘要 middleware 更新了持久化的 messages/state，那么后续执行恢复的是摘要后的 Agent state，下一轮上下文基于该 state 继续，而非自动从 Java 表重新拉取全部消息。该行为取决于 checkpoint 写入成功、thread key 一致、未另行把 Java 全量历史拼回 prompt，以及 Agent 状态 schema/中间件处理方式。

Java 历史仍可保留完整业务展示记录；不要把“业务历史表有全部消息”误解为“每轮必须把完整历史全部发送给模型”。

### Q8：第 5–10 轮再次压缩时，会把旧摘要与近期消息合并吗？

**用户问题**：新一轮压缩是基于之前摘要加最近几轮重新压缩，还是把所有历史重新摘要？

**设计预期**：滚动摘要应在已经摘要过的 state 上继续处理：旧摘要/保留的消息作为当前状态的一部分，再与达到阈值后需要归纳的较旧消息合并，产生更新的摘要并继续保留近期窗口；不应每次从 Java 业务表取全量历史后重做全量摘要，除非产品明确要求全量重建。

**边界**：摘要不是可逆压缩，已经舍弃的原文细节不会因 checkpoint 自动恢复。要保留可追溯性，应以 Java 业务历史为完整来源；必要时按需检索历史消息或对话档案补充信息。实际中间件对旧摘要如何拼接/替换及 messages 结构的行为，要在锁定版本下验证，不能只靠“summarize”这个名字推断。

## 3. SSE 与请求生命周期建议

```text
前端 ──SSE/HTTP──> Java ──流式转发──> Python Agent
                         │                 │
                         │                 ├─恢复 thread_id 对应 checkpoint
                         │                 ├─检查/执行同步摘要
                         │                 ├─发出“正在压缩上下文”状态事件
                         │                 ├─继续模型/工具执行并流式输出
                         │                 └─checkpoint 保存 Agent state
                         └─写 Java 用户消息与最终 assistant 消息
```

推荐把 SSE 事件协议显式化，例如 `status: summarizing`、`token`/`message_delta`、`completed`、`error`；事件名称仅为设计示例。Java 需透传事件并处理代理缓冲、心跳、超时、客户端断开与上游取消。用户要求的是压缩时可以给前端提示，不表示 UI 文案、协议格式已定。

通常先收到用户请求并写入/登记 user message，再由 Python 执行模型前摘要；Java 保存最终 AI 回答。若用户消息写入和 Python run 之间失败，按异常补偿设计处理。具体“用户消息何时落表”、是否草稿状态、取消后是否保留等待定。

## 4. 必须纳入实现设计的风险与约束

### 4.1 多实例和同会话并发

- 对同一 `thread_id` 的运行需要定义串行规则；两个并发请求可能读取相同旧 checkpoint 并产生竞态更新。
- 多实例部署时使用跨实例共享的锁/队列机制；锁应有超时/租约和故障恢复设计。
- 采用请求幂等键，确保 Java 重试或网络重连不会重复产生业务消息或重复执行工具副作用。
- 明确同会话第二个请求是等待、排队、返回冲突，还是允许并发；用户尚未选定。

### 4.2 异常补偿与一致性

- Python 摘要调用失败：向调用方报告可识别错误；不要把失败伪造成有效摘要。是否自动重试应受限并可观测。
- 摘要完成但 checkpoint 未持久化：需要明确 durable checkpoint 的写入时机、成功判据与重试行为。
- Agent 成功但 Java 最终回复写入失败：通过 run/message 标识重试落库，避免重复执行模型和工具。
- Java 用户消息已写入但 Python 不可用：记录待处理状态并提供重试/失败状态，避免界面显示永久“无回答”。
- SSE 断开不等于 Agent 一定停止；服务端应明确是否继续执行、如何通知/恢复、如何保存最终结果。

### 4.3 Token 估算与上下文预算

- 触发阈值统计通常针对消息内容估算；真实模型请求还包含 system prompt、工具 schema、结构化输出约束、额外 provider 参数、图片/多模态 payload 等。
- 预留安全余量，不能把模型上下文最大值直接当作可用对话 token 预算。
- 工具调用消息与工具结果可能很长；评估摘要是否要压缩工具输出、工具输出是否存完整业务日志，以及其对安全与可追溯性的影响。
- 60%/70%仅为此前讨论的候选比例；需按模型的实际上下文容量、工具数量、提示词长度、平均请求与摘要延迟测定。

### 4.4 Checkpoint 与业务历史不完全一致

- Java 表是业务侧权威记录，决定会话列表、用户可见问答和业务保留政策。
- LangGraph checkpoint 是 Agent 运行状态，可能含工具/中间消息、摘要状态、待恢复任务信息；不等同于面向用户的聊天记录。
- 两边要有 conversation、message、run 的关联键和可观测性；保留期限、删除会话时清除 checkpoint 的流程需一致规划。
- 不要让前端把 checkpoint 内部消息直接当作展示历史，也不要默认 Python 自动查询 Java 全量历史。

## 5. 已决定与未决定事项

### 已决定

- 前端只请求 Java；Java 转发 Agent 请求到 Python。
- Java 保存会话业务历史中的用户问题和模型最终回答。
- Python 使用 LangChain `create_agent`/LangGraph 执行 Agent，并在 PostgreSQL 中通过 checkpointer 保存状态。
- 建议将稳定的 `conversation_id` 映射为 LangGraph `thread_id`。
- 短期记忆采用 LangChain summarization 能力，压缩后的 Agent 状态由 checkpoint 持久化，不单独建业务摘要表。
- 在下一轮模型调用前同步检查并压缩；接受增加首字延迟；压缩过程中前端可通过 SSE 显示状态。
- 后续轮次从 checkpoint 中的摘要后 state 继续；滚动摘要按当前状态推进，而不是默认重读全量 Java 历史。

### 待实现时确认

- LangChain、LangGraph 与 PostgreSQL checkpointer 的具体版本及 API，尤其是 `SummarizationMiddleware` 参数/默认行为。
- `trigger`、`keep`、`trim_tokens_to_summarize` 和 token 估算器的生产配置。
- `create_agent` 的具体 state 中间件配置、PostgreSQL saver 初始化与 migration/schema 管理。
- 同一 conversation 并发策略、多实例锁/队列、run 幂等、取消与断线行为。
- SSE 事件格式、Java 到 Python 的流转协议、超时/心跳/反向代理配置。
- Java 消息表字段与消息落库时机、失败状态、补偿/重试机制。
- checkpoint 保留/清理、用户删除会话时的双边删除与合规策略。
- 是否需要保留工具调用/中间消息、是否按需从业务历史检索旧原文。

## 6. 可交由下一段对话继续推进的工作

1. 根据实际 LangChain/LangGraph 版本，给出一份可运行的 Python `create_agent + SummarizationMiddleware + PostgreSQL checkpointer + thread_id` 配置示例，并核实 state/checkpoint 行为。
2. 设计前端—Java—Python 的 SSE 事件协议和请求/响应数据结构，覆盖摘要状态、增量输出、错误、取消与断线重连。
3. 为 `conversation_id`、`run_id`、`message_id` 设计最小关联字段与幂等流程。
4. 选定同一会话并发策略及多实例协调方案。
5. 画出用户消息写入、checkpoint 更新、最终回答写入之间的成功/失败时序，并确定补偿策略。
6. 依据目标模型、工具集和典型对话压测上下文预算，确定触发阈值和保留策略；当前不把 60%/70% 当成定值。

## 7. 官方技术参考

以下链接用于后续实现时核对版本化行为；代码示意和默认参数都应以项目实际锁定版本为准。

- [LangChain Python `SummarizationMiddleware` API 参考](https://reference.langchain.com/python/langchain/agents/middleware/summarization/SummarizationMiddleware)：`trigger`、`keep`、`token_counter`、`trim_tokens_to_summarize` 与模型调用前摘要行为。
- [LangChain Agent middleware 概览](https://docs.langchain.com/oss/python/langchain/middleware)：如何将 middleware 配置到 Agent。
- [LangGraph 持久化概念](https://docs.langchain.com/oss/python/langgraph/persistence)：checkpoint、thread 与持久化基础。
- [LangGraph 添加短期记忆](https://docs.langchain.com/oss/python/langgraph/add-memory)：通过 thread/checkpointer 恢复跨轮 Agent 状态。
- [LangGraph PostgreSQL checkpointer / production memory setup](https://docs.langchain.com/oss/python/langgraph/add-memory)：具体 Postgres saver 用法请核对当前官方页面和锁定版本。

---

**交接提醒**：请后续对话把本文的“三条用户确认决策”视为已定方向；将阈值、并发、消息协议和异常补偿视为待设计事项。不要把示例值当成产品要求，也不要把 middleware 本身描述成会独立写入某张摘要业务表。

