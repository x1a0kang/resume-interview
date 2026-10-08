# 09｜Smart Appointment AI Agent 代码分析与 HP 迁移建议

> 审阅对象：`E:\project\smart-appointment-ai-agent`，本地提交 `2bd2dba`。  
> 审阅日期：2026-09-10。  
> 目标：将该仓库作为 Agent 学习样本，区分可学习的设计思想、仅适用于 Demo 的实现，以及可以迁移到 HP 的工程能力。

## 1. 结论先行

这个项目适合用于学习 Agent 应用的早期组成部分，但不应作为 HP 的目标架构直接照搬。

它最有价值的地方是把一个预约业务拆成了五类问题：

1. 判断当前请求属于什么任务；
2. 在多轮对话中收集缺失参数；
3. 用确定性服务查询技师、排班并保存预约；
4. 用 RAG 回答门店知识问题；
5. 让模型调用一个天气工具生成预约提示。

但从代码事实看，README 所称的“多 Agent”主要是模块命名和手工路由，不是多个具备独立工具循环、checkpoint 和协作协议的现代 Agent：

| 模块名称 | 实际形态 | 是否属于真正的 Agent Loop |
| --- | --- | --- |
| `TaskClassificationAgent` | LLM 五分类 + 手工 `if/else` 路由 | 否 |
| `AppointmentAgent` | LLM 提取 JSON + 手写槽位状态机 + 确定性业务流程 | 主体不是；只有天气提示部分是 |
| `ConsultantAgent` | 固定“向量检索 → 拼 Prompt → 生成答案” | 否，是 RAG Workflow |
| `UserBehaviorAgent` | 行为记录、确定性统计 + LLM 生成提醒 | 否，是分析服务/生成 Workflow |
| `WeatherMCPTool` + `AgentExecutor` | 模型选择并调用天气 Tool，再根据 observation 生成提示 | 是，但只有一个 Tool，场景很小 |

因此最正确的学习方式不是模仿它建立多个 `XxxAgent` 类，而是用它理解：什么时候是分类器、什么时候是 Workflow、什么时候才需要 Agent。

## 2. 项目实际技术栈与代码结构

```text
FastAPI / Uvicorn
LangChain 0.3 系列
OpenAI 兼容 Chat/Embedding Provider
SQLAlchemy + SQLite
FAISS IndexFlatIP / IndexFlatL2
Jinja2 页面
schedule 后台调度
```

代码分为 Web、API、Agents、Services、Repository/DB 五层，依赖方向基本表达为：

```text
Web/API
→ Agent/应用编排
→ Service
→ Repository
→ SQLite
```

这一分层思想值得保留。Agent 不应直接拼 SQL 或操作数据库；它应调用有稳定输入输出的业务能力，业务校验和持久化由 Service/Repository 完成。

需要注意：仓库使用 `langchain>=0.3,<1.0`，没有 LangGraph，也没有 checkpoint；它反映的是较早期的 LangChain Agent 写法，不是 HP 最终选定的 2026 技术方案。

## 3. 五条核心执行链

### 3.1 总入口：分类后手工路由

```text
POST /chat/stream
→ ProcessUserInput_stream
→ TaskClassificationAgent
→ TaskClassifier 调用 LLM 返回 appointment/query/pay/statistics/other
→ ClassificationProcessor 使用 if/else 路由
→ AppointmentAgent 或 ConsultantAgent
```

`StateManager` 只保存 `CLASSIFY/APPOINTMENT/CONSULT` 三种内存状态。如果正在预约，后续消息不再分类，而是继续进入预约流程；完成后再重置到分类状态。

这能帮助理解有限状态机，但它正是 HP 已经决定取消的“前置意图识别 + 路由状态”模式。HP 不应迁移这一层。

### 3.2 预约：LLM 槽位提取 + 确定性 Workflow

```text
用户输入
→ InputParser 让 LLM 输出 JSON
→ appointment_history 合并已知参数
→ 缺时间/项目/时长/性别时手写追问
→ TechnicianFinder 查询技师与档期
→ 指定技师不可用时推荐替代者并等待确认
→ AppointmentService 保存排班
```

这里最值得学习的是“模型理解自然语言，代码负责业务规则”：

- 模型提取时间、项目、时长、性别和技师偏好；
- 代码判断哪些字段必填；
- 代码检查档期冲突；
- 代码控制替代技师必须确认；
- Service/Repository 执行保存。

但当前实现通过裸 `json.loads` 解析模型文本，失败后把所有字段回退为“未知”。HP 应改成 Pydantic Structured Output，并区分格式错误、字段缺失、无权限和业务不存在等错误。

### 3.3 咨询：固定 RAG Workflow

```text
用户问题
→ 生成 query embedding
→ FAISS TopK
→ 取得 SQLite 中的知识全文
→ 拼接 Prompt
→ LLM 生成回答
```

这不是 Agent 自主规划，而是完全固定的 RAG 链。它适合学习 Retriever 的基本职责：把“知识如何存储和检索”封装在 `KnowledgeService/KnowledgeRetriever` 中，不让上层关心 FAISS 细节。

### 3.4 用户行为：确定性分析 + LLM 文案

项目记录预约与咨询行为，统计偏好技师、服务、时间和访问频率，再由 LLM 生成回访提醒。这与 HP 的 ChatBI 思路相似：事实和统计由代码产生，大模型负责解释或生成自然语言，而不是让模型从原始数据自行计算。

### 3.5 天气：仓库中真正的 Tool Calling 示例

`AppointmentProcessor` 使用 `create_openai_tools_agent + AgentExecutor + BaseTool` 注册 `get_current_weather`。模型先提出 Tool Call，程序执行天气查询，再把 observation 交回模型生成提示。

这一小段可以用来学习最基本的 Agent Loop：

```text
Model
→ Tool Call(name, arguments)
→ Tool Executor
→ Observation
→ Model
→ Final Answer
```

但是 `WeatherMCPTool` 只是 LangChain `BaseTool` 包装的 HTTP 请求，不是 MCP Server；类名不应被当成项目已经实现 MCP 的证据。

## 4. 值得迁移到 HP 的知识点

### 4.1 Agent 只负责编排，业务规则留在领域服务

预约项目没有让模型直接操作 SQLite，而是经过 `TechnicianFinder → AppointmentService → Repository`。HP 应使用同样的边界，但做得更严格：

```text
HP Agent
→ 高层 Tool Schema
→ Python Tool Adapter / Policy Guard
→ Java HP 或 ChatBI Facade
→ Domain Service
→ DB / MQ
```

### 4.2 多轮任务需要显式状态

`appointment_history` 证明了多轮对话不能只保存聊天文本，还要保存已经确定的结构化条件。迁移到 HP 后，对应字段应放入 LangGraph State/checkpoint：

```text
messages
activeGoal
knownConstraints
pageContext
lastToolObservations
currentDraftRef
```

### 4.3 信息收集与业务计算必须分离

模型可以理解“最近一段时间”“只看数学”“换成下周末”，但正确率、得分率、样本量和趋势基础值必须由 ChatBI/HP 确定性计算。模型只解释结果和生成报告。

### 4.4 Retriever 应成为稳定接口

参考项目用 `KnowledgeRetriever` 隔离了 FAISS。HP 继续采用同一思想，定义稳定的 `DocumentRetriever` 协议，使底层 VikingDB、Elasticsearch 或未来其他检索引擎可以替换，而 Agent Tool Schema 不变。

### 4.5 模型 Provider 需要适配层

`create_chat_model/create_embedding_model` 把 Azure OpenAI 与 OpenAI 兼容服务封装起来，值得迁移。HP 应进一步补充模型能力声明、超时、重试、fallback、限流、成本和 trace，而不是在业务代码中直接创建模型客户端。

### 4.6 流式响应是产品能力

参考项目已经把聊天入口设计成 `StreamingResponse`。HP 可以保留 SSE，但必须使用模型原生异步流，而不是先等待完整回答后逐字符输出。

### 4.7 测试应按业务场景组织

仓库测试覆盖预约缺参、连续补充、无关请求、知识查询和用户行为等场景。它的测试实现不够稳定，但“以场景组织用例”的方法可以迁移到 HP Evaluation Harness。

## 5. 不能原样迁移的部分

### 5.1 不迁移前置意图分类器

参考项目每个新任务先调用一次分类模型，再路由到另一个 Agent；咨询 Agent 内部还会再次判断是否属于咨询，存在重复分类和状态切换复杂度。

HP 已收敛为：

```text
按钮 + actionCode → 固定 Workflow
任意自由文本 → 当前角色 Agent
```

Agent 在自己的模型—工具循环中理解用户目标，不维护独立的意图分类服务。

### 5.2 不按角色或意图复制多个 Agent Runtime

HP 的 Teacher/Student/Parent 不是三个进程或三套状态机，而是同一 Runtime 的不同 `AgentProfile`：不同 System Prompt、Tool 白名单、数据域和回答规范。只有当子任务拥有独立目标、独立工具、独立上下文，并确实需要协作时，才引入真正的多 Agent。

### 5.3 不使用全局内存会话

参考项目在 `api/chat_handler.py` 创建一个全局 `session_id` 和全局 `task_agent`，所有请求共享状态；`AppointmentAgent` 又把历史保存在进程内字典中。多用户部署时会产生串话、数据泄露、进程重启丢失和多副本状态不一致。

HP 必须使用登录身份 + 服务端 `threadId`，通过 LangGraph checkpointer 持久化每个会话状态，并在每次请求重新验证身份和资源绑定。

### 5.4 不让 Agent 自动执行已有业务写操作

参考项目在预约字段齐全后直接保存排班，普通成功路径没有统一的二次确认、幂等键和并发冲突保护。HP 第一版已经决定不开放修改答案、分数、批改结果和重批 Tool；识别到写意图时只提示用户到已有页面操作。

保存讲评、学习计划和生成 DOC/PDF 属于新建 Agent 产物，可以保留，但必须版本化和幂等。

### 5.5 不暴露模型“思考过程”

参考项目把 `[THOUGHT]` 文本直接流式返回前端。HP 只展示用户需要的状态，例如“正在读取班级分析”“正在查找教材资料”；不展示隐藏推理链。内部使用结构化 trace 记录节点、Tool Call、耗时和错误。

### 5.6 不使用伪造兜底

天气 Tool 在缺少 API Key 或请求失败时直接返回“北京天气晴朗”。RAG Prompt 也允许资料不足时使用模型的一般知识补充。二者都会把未知事实包装成确定事实。

HP 必须明确返回 `NO_EVIDENCE/UPSTREAM_UNAVAILABLE`，教学资料不足时允许给一般性解释，但不能伪造教材出处、页码、学生数据或班级结论。

## 6. RAG 实现的可学习点与缺口

### 6.1 可以学习

- 原始知识持久化与向量索引分离；
- 文档 ID 与 FAISS index position 建立映射；
- 知识增删改后同步维护索引；
- Retriever 对上层返回统一文档对象和 score；
- Chat/Embedding 模型使用 Provider Factory。

### 6.2 不能满足 HP 的原因

| 当前实现 | 对 HP 的问题 | HP 目标实现 |
| --- | --- | --- |
| 一条知识就是一个完整向量 | 没有文档、章节和语义 chunk 层级 | 文档解析、章节识别、语义分块 |
| embedding 以 JSON 存 SQLite | 数据量和检索并发有限 | 元数据 DB + 独立 VikingDB Collection |
| `IndexFlatIP` 直接内积 | 未显式归一化时不一定等价于余弦相似度 | 明确相似度、归一化与离线验证 |
| 只做 Dense TopK | 专有名词、章节号和公式召回不足 | BM25 + Dense + RRF/加权融合 |
| 先召回 `top_k*2` 再按 category 过滤 | 过滤后可能不足 K 条或漏掉正确结果 | ACL/教材版本等过滤尽量前置 |
| 没有阈值和 rerank | 无关片段也会进入 Prompt | candidate recall → rerank → evidence threshold |
| 返回全文，无 citation | 不能定位版本、章节、页码 | Evidence Pack + `citationList` |
| CRUD 后全量重建 FAISS | 数据增大后写操作阻塞、并发不一致 | 异步增量索引 + 版本切换 |
| Prompt 允许模型自由补充 | 容易产生无依据答案 | 区分业务事实、资料证据和一般建议 |
| 无 ACL、组织和版权字段 | 无法隔离学校资料和授权范围 | 检索前权限过滤、删除与撤权同步 |

## 7. 代码层面的生产化风险

### 7.1 会话与权限

- 全站共用一个 `global_session_id`；
- 用户行为默认写入 `default_user`；
- API 没有登录鉴权、角色和资源归属校验；
- 知识库、技师和排班管理接口没有管理员权限；
- CORS 使用 `allow_origins=["*"]` 且允许凭据。

这些都说明它是单用户学习 Demo，不能作为 HP 的权限实现参考。

### 7.2 API 与代码已经发生漂移

静态审查发现多处接口对不上：

- `/api/task/classify` 无参构造 `TaskClassificationAgent`，但构造器要求两个 Agent；同时读取 `request.message`，请求模型字段实际叫 `text`；
- `/api/appointment/create` 调用不存在的 `AppointmentAgent.process_appointment_request`；
- `/api/consultation/ask` 调用不存在的 `ConsultantAgent.process_consultation`；
- 新增知识接口引用未定义的 `app.get_knowledge_service()`；
- Web 注册了 `admin_dashboard.html/database_admin.html`，本地模板目录没有对应文件。

所以 README 的“可直接运行所有能力”不能仅凭文档相信，学习时必须以调用链和测试结果为准。

### 7.3 并发与一致性

预约流程先查询档期再插入 busy schedule，数据库没有唯一约束、行锁或原子占用机制，并发请求可能重复预约。`busy_periods_dict` 又是单进程全局内存，多副本之间不会同步。

这能迁移为 HP 的反例：Tool 返回“可用”不代表提交时仍然可用，真正写入必须在领域服务内再次校验版本、权限和并发条件。

### 7.4 流式输出

咨询回答先执行一次完整 `ainvoke`，再逐字符 `yield`，不是模型原生流式；预约的同步 `.stream` 也可能阻塞异步接口。HP 应使用异步 `astream`/事件流，并定义 token、tool status、final answer 和 error 的事件协议。

### 7.5 测试与评测

当前测试大多直接调用真实 LLM、Embedding 和本地数据库，没有 fixture 隔离、模型 mock、record/replay 和固定数据集；部分断言只判断字符串非空或包含关键词，容易受模型波动影响。测试代码与当前方法签名也有漂移。

HP 需要两层测试：

```text
确定性单元/集成测试
→ Tool Schema、权限、领域聚合、错误码、checkpoint、幂等

Agent/RAG Evaluation
→ 工具序列、任务完成、越权、资料召回、引用忠实度、无证据回答
```

### 7.6 依赖与版权

- `aiohttp` 被代码直接导入，但未在 `requirements.txt` 声明；
- 依赖多为宽范围版本，缺少 lock file，重装后可能不兼容；
- 仓库没有 LangGraph，不能把它描述成 LangGraph 项目；
- 本地仓库未发现 LICENSE/COPYING/NOTICE 文件。可以学习思想并自行实现，但不应直接复制代码进入公司或个人项目后重新发布。

## 8. 对 HP Agent 的迁移映射

| 参考项目概念 | HP 中的正确落点 | 迁移结论 |
| --- | --- | --- |
| TaskClassificationAgent | 删除；按钮进 Workflow，自由文本进 Agent | 不迁移 |
| StateManager 三态枚举 | LangGraph State + checkpointer | 重写 |
| appointment_history | `activeGoal + knownConstraints + pageContext` | 保留思想 |
| InputParser 裸 JSON | Pydantic Structured Output / Tool Schema | 升级 |
| TechnicianFinder | Java Domain Facade 内的确定性查询/推荐 | 保留分层 |
| ConsultantAgent | `search_teaching_resources` RAG Tool | 重构 |
| KnowledgeRetriever | `DocumentRetriever` 接口和 VikingDB Adapter | 保留抽象 |
| Weather BaseTool | HP 高层 Domain Tool 的最小调用范例 | 学习 Tool Loop |
| UserBehaviorAgent | ChatBI 确定性分析 + LLM 报告/计划 | 改名并复用业务层 |
| InMemory history | MongoDB/PostgreSQL checkpointer + 会话业务表 | 替换 |
| default_user | 网关注入 AuthContext，Tool 端重新鉴权 | 替换 |
| `[THOUGHT]` 输出 | 内部 Trace + 用户可读状态事件 | 替换 |

## 9. HP 的目标 Agent Loop

```text
用户自由文本
→ 加载 AuthContext、AgentProfile、pageContext、checkpoint
→ 模型判断：回答、追问或 Tool Call
→ Policy Guard 校验本轮 Tool 是否可见
→ Tool Adapter 校验 Schema
→ Java HP/ChatBI Facade 再次鉴权并执行
→ 标准化 Observation 写回 Graph
→ 模型决定继续调用、生成草案或结束
→ 保存 checkpoint、trace、引用和产物版本
```

RAG 只是其中一个 Tool：

```text
业务事实 → HP/ChatBI Domain Tool
教材、教参、辅导资料 → RAG Tool
练习题 → Question Recommendation Tool
DOC/PDF → Artifact Tool
```

## 10. 建议的学习与动手顺序

### 第一阶段：读懂参考项目，不急着改

手工追踪四个问题：

1. “你们几点营业”为什么进入固定 RAG；
2. “预约明天下午数学……”如何分轮补齐字段；
3. 指定技师不可用后，确认状态在哪里保存；
4. 天气 Tool Call 与普通函数调用的区别。

完成后应能用自己的话解释分类器、槽位填充、Workflow、Retriever 和 Agent Loop 的边界。

### 第二阶段：把参考项目改造成现代最小 Agent

建议在独立练习分支完成，不把代码复制进 HP：

1. 删除 TaskClassificationAgent，让所有文本进入一个 LangGraph Agent；
2. 把“查询门店知识、查询可用技师、创建预约草案”封装成三个 Tool；
3. 使用 Pydantic 定义 Tool 输入和 observation；
4. 使用 SQLite/PostgreSQL checkpointer 替换全局内存状态；
5. 预约只生成草案，增加显式确认和幂等键；
6. 使用 fake model/tool fixture 建立可重复测试；
7. 把假流式改为原生异步流式事件。

这一阶段完成后，才算真正掌握“模型—工具—观察—继续/结束”的 Agent Runtime。

### 第三阶段：迁移到 HP 设计

优先实现一个最小垂直切片，而不是一次接完 10 个 Tool：

```text
家长：“分析孩子最近的数学学习情况”
→ get_student_learning_report（ChatBI）
→ 信息不足时追问时间范围
→ checkpoint 续接
→ 生成基于确定性事实的报告
→ 保存 trace 和评测结果
```

第二个切片再实现：

```text
学生：“用课本的方法讲解这道已批改题”
→ get_student_question_context（HP）
→ search_teaching_resources（RAG）
→ 生成带 citation 的讲解
```

## 11. 可以形成的面试认识

可以这样介绍对该参考项目的吸收：

> 我分析过一个预约类多 Agent 项目，发现它的大部分模块实际是“意图分类 + 手写状态机 + 固定 RAG Workflow”，真正的 Tool Calling 只出现在天气查询。这个分析让我明确了 Agent 与 Workflow 的边界。因此在教育项目中，我没有照搬多 Agent 和前置分类器，而是将按钮任务保留为确定性 Workflow，所有自由文本进入同一个角色感知 Agent；使用 LangGraph checkpoint 管理跨轮约束，通过受控 Domain Tool 调用 HP 和 ChatBI，并把教学资源 RAG 作为可选工具接入。

这个表述比“参考项目用了多 Agent，所以 HP 也使用多 Agent”更能体现架构判断。

## 12. 审阅范围与验证边界

- 已阅读 README、依赖、Agent、API、Service、Repository、数据模型和测试代码；
- 73 个 Python 文件均通过 AST 语法解析；
- 未修改参考项目源码；
- 未配置外部模型 Key，因此没有把依赖真实 LLM/Embedding 的测试结果当成已验证事实；
- 架构图尺寸为 24951×17676，超过常规安全图像解码阈值，未作为代码结论依据；
- 结论以实际源码为准，不把 README 中的宣传性命名直接视为已实现能力。

## 13. 技术栈：与 HP 的重合、差异和取舍

### 13.1 先回答结论

**有重合，但不是“同一套方案”。**

这个预约项目是一个 Python 单机学习 Demo；HP 的目标是“Python AI 服务 + 已有 Java 业务中台/ChatBI + 既有数据基础设施”的生产化架构。可以参考其分层和最小 Tool Calling，不应复制它的多 Agent、内存状态和 FAISS + SQLite 组合。

| 技术层 | 预约参考项目 | HP / RunHub 应采用的目标 | 结论 |
| --- | --- | --- | --- |
| 应用语言与 HTTP 服务 | Python、FastAPI、Uvicorn | Python 3.12、FastAPI、异步 SSE | 可以采用，完全合理 |
| 数据模型 | Pydantic 2，但模型输出再手工 `json.loads` | Pydantic 2 Structured Output、Tool Schema、统一 Observation | 保留 Pydantic；不能保留裸 JSON 解析 |
| LLM 编排 | LangChain 0.3、`AgentExecutor`、手工状态机 | LangChain Core / `create_agent` + LangGraph State、checkpoint | 概念可学；Runtime 升级 |
| Agent 形态 | 分类器和几个命名为 Agent 的业务类 | 一个角色感知 Agent Runtime；按钮走 Workflow | 不采用多 Agent 路由 |
| 会话状态 | 全局 `session_id` + 进程内字典 | `threadId` + LangGraph checkpointer + 业务会话表 | 必须替换 |
| 关系数据 | SQLite + SQLAlchemy | Java 继续拥有 HP/ChatBI 的 MySQL/MongoDB 领域数据；AI 服务只调 Facade | 不让 AI 服务直连、改写业务库 |
| RAG 向量检索 | SQLite 存全文/向量 + 内存 FAISS | ES 关键词检索 + 独立 VikingDB 教学资料 Collection + 元数据存储 | 仅学习 Retriever 抽象；不采用 FAISS 单机实现 |
| 异步任务 | `schedule` 进程内定时任务 | RabbitMQ / XXL-Job / 独立消费者 | 使用 HP 已有可靠基础设施 |
| 可观测性 | 几乎没有 | OpenTelemetry + Langfuse（或等价 Trace 平台）+ Prometheus | 新增必需能力 |
| 测试与评测 | 真实 LLM 的脆弱测试 | pytest、fixture、mock/record-replay、Tool/ACL/RAG Eval | 必须重建 |

### 13.2 可以直接吸收的部分

1. **FastAPI 作为 AI 服务边界**：负责 `/chat/stream`、知识入库、评测触发等 AI 能力；Java 仍负责登录、作业、批改、权限和数据口径。
2. **Pydantic 作为系统契约**：Tool 入参、Tool 返回值、RAG Evidence、流事件均应该有明确结构，避免模型文本直接进入业务逻辑。
3. **Service / Repository 与 Agent 分层**：Agent 调“高层业务能力”，不调 SQL、不理解底层检索细节。
4. **Provider Factory**：模型和 embedding 客户端在一处适配，便于更换供应商、限流、重试、成本统计与追踪。
5. **RAG Retriever 抽象**：上层只知道 `search_teaching_resources`，不绑定 VikingDB、ES 或 reranker 的实现细节。

### 13.3 不建议采用的部分

1. 为每个业务场景建一个 `XxxAgent` 类并靠分类器切换；
2. 把会话、用户和跨轮变量放在单个 Python 进程的全局变量；
3. SQLite JSON 向量 + 全量重建内存 FAISS 作为正式 RAG；
4. 一个 Tool 自动写入领域数据；
5. 逐字符伪流式、真实模型参与单元测试、无鉴权/审计/评测；
6. 将 Java Controller 或数据表直接暴露给模型。

## 14. 它如何处理状态、会话、上下文、Harness 与评测

这里要把五件看似相近的东西分开。预约项目只实现了其中的一小部分。

| 关注点 | 参考项目实际做法 | 它缺少什么 | HP 的正确做法 |
| --- | --- | --- | --- |
| **状态（State）** | `CLASSIFY/APPOINTMENT/CONSULT` 枚举；预约参数放 `appointment_history` 内存字典 | 进程重启丢失、所有用户共享、无法恢复某一轮执行 | LangGraph State 保存 `activeGoal`、`knownConstraints`、`pageContext`、最近 observation；每次节点推进写 checkpoint |
| **对话保存（Conversation）** | 用 LangChain `InMemoryChatMessageHistory` 保存预约轮次；没有数据库持久化，入口又只创建一个全局 Agent/session | 重启丢失、无法按真实用户隔离、审计、回放、跨设备继续 | 会话表/消息表保存产品层的 thread、用户消息、最终回答、引用、产物；与 checkpoint 分开 |
| **上下文（Context）** | 把本轮输入、预约历史或 TopK 文档直接拼 Prompt | 没有摘要、窗口控制、页面上下文、身份数据域、工具观察结果选择 | `Context Builder` 按每轮动态组装：AuthContext、角色规则、页面上下文、压缩历史、当前目标/约束、必要 observation、RAG Evidence |
| **Runtime Harness** | 没有完整 Harness；只有 LangChain `AgentExecutor` 包住一个天气 Tool | 没有 Tool Registry、Policy、checkpointer、预算、超时、Trace、审计、异步桥接 | 建立 Runtime Harness：Gateway → Context Builder → Tool Registry/Policy Guard → Executor → Checkpointer/Trace；Java Facade 再鉴权 |
| **评估（Evaluation）** | 有测试文件，但主要依赖真实 LLM/Embedding，断言非常宽松 | 不可复现、无法验证越权/工具序列/引用正确性 | 脱敏 fixture、fake model/tool、record-replay；断言工具序列、领域事实、ACL、citation、任务完成率与成本/时延 |

### 14.1 为什么“会话保存”与“状态 checkpoint”不是一回事

它们都会持久化，但目的不同：

```text
产品会话记录：用户和运营能看见什么
thread、消息、最终回答、下载文件、citation、审计索引

运行时 checkpoint：系统下一轮怎样接着执行
Graph State、已提取约束、上轮 Tool Observation、当前节点、失败恢复信息
```

例如家长说“看看孩子最近数学怎么样”，Agent 追问“想看近一周还是近一个月？”：

- 对话记录负责把这一问一答展示在聊天页，并可供审计；
- checkpoint 负责记住 `activeGoal=学习情况分析`、`subject=数学`，只缺 `timeRange`。下一句话“近一个月”到来后，图从原状态继续，而不用让模型从长聊天记录重新猜一次。

### 14.2 HP 的一轮上下文不是“把所有聊天记录和所有 Tool 都塞进模型”

每轮调用应由 `Context Builder` 选择性构建：

```text
固定：角色 Prompt + 安全规则 + 该角色可见 Tool Schema
当前：登录身份、当前页面/作业/题目 ID、用户本轮消息
延续：近期关键消息 + 压缩摘要 + LangGraph State
按需：上轮 Tool Observation、教学资料 Evidence
```

这里的“上下文”是运行时给模型的有效工作集；数据库里的完整消息历史和完整批改数据不应全部放入 Prompt。

### 14.3 HP Runtime Harness 的最小边界

不要把 Harness 神化为一个框架名。它就是让模型调用业务能力时可控、可恢复、可观察的一层运行底座：

```text
前端 /chat
→ Gateway（JWT、threadId、限流）
→ Context Builder
→ LangGraph Agent Loop
→ Tool Registry + Policy Guard（角色白名单、Schema、调用上限）
→ Tool Adapter
→ HP / ChatBI Java Facade（资源归属二次鉴权）
→ Observation
→ Checkpoint + Trace/Audit + SSE Event
```

这正是参考项目最值得补齐、也最能体现工程深度的部分。

## 15. 调度与 ReAct：它到底是一个循环还是两个循环？

先澄清术语：你写的 `React` 在这里通常指 **ReAct**（Reason + Act），不是前端 React。

ReAct 的外显执行结构是：

```text
模型决定下一步
→ 请求调用 Tool（Action）
→ 程序执行 Tool，产生 Observation
→ 模型据此决定再调 Tool 或生成最终回复
```

系统不需要、也不应把模型的原始“思考过程”展示给用户；只保存和展示结构化的 Tool Trace 与用户可读进度。

### 15.1 参考项目有三种不同的执行模式，不是一个统一的多 Agent 循环

| 链路 | 实际循环 | 是否 ReAct |
| --- | --- | --- |
| 总入口分类 | 每条新任务先分类一次，随后 `if/else` 路由；预约中不再分类 | 否 |
| 预约 | 每轮“LLM 提取字段 → 代码补字段/校验 → 追问或保存”；跨用户轮次反复 | 是槽位填充状态机，不是 Tool-Observation ReAct |
| 知识咨询 | `retrieve → generate` 一次完成 | 否，是固定 RAG Workflow |
| 天气提示 | `AgentExecutor` 可让模型调天气 Tool，得到 observation 后再回答 | 是最小 ReAct 式循环 |

所以如果一定要描述为“两个循环”，只能说预约成功后可能嵌套：

```text
外层：预约多轮槽位状态机（用户回合驱动）
内层：天气 AgentExecutor 的 Model → Tool → Observation 小循环
```

它们没有共同的 checkpoint、调度器或 agent-to-agent 协作机制，不能称为“两个协作 Agent Loop”。

### 15.2 HP 应只有一个在线 Agent Loop

```text
按钮入口 → 直接运行固定 Workflow（没有 Agent Loop）

自由文本 → 一个 LangGraph Agent Loop
            模型 → 0~N 次高层 Domain Tool / RAG Tool → 最终回复
```

工具内部可以执行固定的确定性子流程，例如 `get_student_learning_report` 在 ChatBI 聚合多个统计表；这只是 Tool 的实现，不是第二个 LLM 循环。RAG 也只是 `search_teaching_resources` Tool 的内部检索链。

## 16. 多 Agent、A2A 与四类参考项目的学习优先级

### 16.1 HP 第一版不需要多 Agent，我同意

Teacher / Student / Parent 是同一个 Agent Runtime 的三种 Profile：不同 Prompt、Tool 白名单、数据域和回答规范；不是三个互相发消息的 Agent。HP 当前任务均能由一个 Agent 在 1~3 次受控 Tool 调用内完成，没有独立代理协作的必要。

**A2A 先学概念，不做一期实现。**A2A 是独立 Agent 之间发现、委派和交付结果的通信协议；它不是 LangGraph 这样的开发框架，也不规定一个 Agent 如何调自己的 Tool。MCP 解决 Agent-to-Tool，A2A 解决 Agent-to-Agent。详见 [A2A 官方说明](https://a2a-protocol.org/latest/)。

对 HP 而言，Python AI 服务调 Java HP/ChatBI Facade 是普通服务调用，不是 A2A。只有将来真的出现一个**独立部署、有自己的长期任务/工具/上下文/负责人**的 Agent 服务，例如跨校教研资源研究代理，才评估 A2A；当前不应为“看起来先进”引入它。

### 16.2 参考优先级：先学什么、各自学什么

注意：以下都是**学习架构和局部实现**，不是让 HP 复制一个 coding agent。实际落地代码仍应优先遵循 Python/LangGraph 官方能力和 HP 的领域边界。

| 优先级 | 参考对象 | 应学什么 | 不应照搬什么 |
| --- | --- | --- | --- |
| 1 | **Pi Agent Core** | 最小 Agent Runtime：模型事件、Tool Call、Observation、状态管理、事件流；它明确把这些做成独立 core | TypeScript 技术栈、coding 工具、默认进程权限；Pi 官方也说明其本身没有内建权限系统 |
| 2 | **DeepSeek Harness** | Harness 的系统视角：插件化模型/工具/会话/存储/循环/调度，以及如何把“模型”与“运行环境”分开 | 一期直接引入；它是 Node 生态且官方标注 Developer Preview、会有破坏性变更 |
| 3 | **Claude Code 文档** | 上下文隔离、工具权限、何时才用 subagent；子 Agent 的价值在于隔离大量探索结果或限制工具 | 把它的 coding 场景直接映射到教育产品；它不是 HP 运行时的 SDK |
| 4 | **OpenCode** | 持久会话、上下文压缩、Provider/Tool 抽象的工程问题 | 它是 coding CLI；且用户列出的旧 `opencode-ai/opencode` 仓库已归档，应只作历史实现阅读 |
| 5 | **Smart Appointment** | 业务 Tool 分层、槽位填充、固定 RAG 与 Agent Tool Calling 的边界 | 多 Agent 命名、全局状态、FAISS/SQLite、自动写操作 |

选择“先参考哪一个”的明确答案是：

1. **先读 Pi Agent Core**，把 Agent Loop 的最小结构读透；Pi 官方把它定位为带 Tool Calling 和状态管理的 Agent Runtime。[Pi 项目说明](https://github.com/earendil-works/pi)
2. 再看 **DeepSeek Harness**，学习你关心的 Harness 应包含哪些能力，但只作架构阅读；其官方仓库明确标注仍在 developer preview、会有不兼容变更。[DeepSeek Harness README](https://github.com/deepseek-ai/deepseek-harness)
3. 随后用 **Claude Code / OpenCode** 补“上下文、权限、会话压缩”这些成熟 coding agent 已处理过的问题；Claude Code 的 subagent 文档尤其能解释“什么时候值得为上下文隔离而启用子代理”。[Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
4. 预约项目放在最后：它最适合作为“如何把基础机制变成一个业务产品”以及“哪些 Demo 写法不能上生产”的对照样本。

### 16.3 你需要掌握到什么程度

对面试和 HP 一期，掌握下列边界就足够：

- 能画出单 Agent 的 Model → Tool → Observation → Final 循环；
- 能解释 product conversation、runtime checkpoint 和 model context 三者的区别；
- 能说明按钮 Workflow 与自由文本 Agent 的入口分工；
- 能设计 Tool 白名单、服务端二次鉴权、Trace 和 fixture evaluation；
- 能说明“多 Agent / A2A 暂不做”的工程理由，而不是笼统地说“太复杂”。

不要把 A2A、MCP、多 Agent 作为简历的技术标签；先在 RunHub 把单 Agent + RAG + Harness + Evaluation 做成真实可演示的闭环。

## 17. 补充：参考项目的 Memory、Pi 的会话机制，以及非对话触发 Agent

### 17.1 预约项目不是没有 Memory，而是只有单机内存 Memory

预约 Agent 初始化了 `InMemoryChatMessageHistory`，每轮先追加用户消息；随后将**全部**历史消息格式化成如下文本，和当前输入一起交给 LLM 做字段提取：

```text
当前已知信息：
用户：明天下午预约按摩
机器人：{上一轮 LLM 输出的 JSON}
用户：女技师，两个小时

用户输入：女技师，两个小时
```

这条链路是：

```text
InMemoryChatMessageHistory（原始聊天全文）
→ history_str（全部转字符串）
→ InputParser Prompt
→ LLM 输出 JSON
→ 代码合并到 appointment_history（gender/time/duration/...）
```

因此它同时维护两份内存：

- `chat_history`：帮助模型理解“是”“明天改成下午”等前文指代；
- `appointment_history`：给确定性代码检查预约必填字段、确认状态和档期。

这个思路正确，但实现只适合单用户 Demo：`chat_handler.py` 在模块加载时创建一个全局 `task_agent` 和一个全局 `session_id`；`AppointmentAgent.chats_by_session_id` 也只属于这一实例。服务重启或多副本部署后历史消失，多个真实用户还会共享该实例。咨询 RAG 则更简单：Prompt 只拼“本轮问题 + TopK 知识全文”，基本不利用多轮对话历史。

### 17.2 Pi：Agent Core 和 Coding Agent 各自负责什么

不要把 Pi 的两个层混为一谈：

```text
pi-agent-core
  Agent.state.messages / tools / systemPrompt
  Model → Tool → Observation 循环、事件、并发/中断 Hook
  本身是进程内 Runtime，不是业务数据库会话系统

pi-coding-agent
  SessionManager
  把每轮用户消息、模型回答、Tool Result、配置变化写入 JSONL 文件
  恢复会话、分叉分支、压缩过长上下文
```

Pi 的会话文件是 append-only JSONL，不是关系数据库。每条 entry 有 `id` 和 `parentId`，所以一个会话可以分叉；文件还记录模型切换、thinking level、压缩摘要与扩展自定义状态。

它的上下文构建逻辑值得学习：

```text
选择当前分支叶子节点
→ 从叶子沿 parentId 回溯到根
→ 找到最近一次 compaction
→ 较早消息用 compaction summary 代替
→ 保留摘要之后的关键原始消息、Tool Result 和最新消息
→ 组装成 Agent.state.messages 给下一轮模型
```

Pi 不只是“把所有历史原样塞进去”：达到阈值或上下文溢出时，它生成 summary，写入 compaction entry，再用“summary + 保留最近消息”重建模型上下文；溢出时还可以 compact 后重试一次。

HP 可以迁移的原则是“完整历史可审计、模型上下文可压缩”，不能直接照搬 JSONL 文件和 coding-agent 分支语义：

```text
HP 会话表：保存完整产品消息、文件、citation、Trace 索引
LangGraph Checkpoint：保存 Agent 执行状态
Context Builder：摘要 + 最近消息 + 当前任务结构化状态 + 必要业务证据
```

### 17.3 Agent 不必由聊天触发，但不是所有自动化都值得用 Agent

入口可以是聊天、按钮、定时任务、事件消息、告警或 API。判断标准不是入口，而是任务是否存在“过程无法提前写死，需要根据 observation 决定下一步查什么、何时证据足够、怎样产出”的空间。

| 触发方式 | 例子 | 该不该用 Agent |
| --- | --- | --- |
| 聊天 | 家长说“帮我看看孩子最近数学怎么样” | 应用 Agent：需要理解模糊范围、追问、选 Tool、解释事实 |
| 按钮 | “查看近一周数学周报” | 固定 Workflow：时间、学科、数据源和输出已确定 |
| 定时 | 每周一生成全班周报 | 固定 Workflow：不需要模型决定取哪些数据；模型最多负责文案 |
| 事件 | RabbitMQ 收到“批改任务失败且重试后仍失败” | 可用诊断 Agent：依据错误码、工作流 Trace、模型/回调状态按需查证，产出根因与人工处置建议草案 |
| 告警 | 某学校当日正确率分布异常 | 先规则检测；若需要跨作业、题型、版本、算法日志收集证据并形成解释，可触发只读分析 Agent |
| 文档上传 | 上传教材后解析、切块、embedding、建索引 | 固定 RAG Ingestion Workflow：步骤明确，不需要 Agent |

对 HP 一期，真正应该优先做的仍是多角色对话 Agent；“批改异常诊断 Agent”可以作为后续非聊天扩展，但只输出诊断草案/创建人工复核建议，不能自行修改批改结果或重试任务。

## 18. RunHub 部署：个人作品阶段的成本与推荐

> 计价核对日期：2026-09-10；价格会随活动、地域和套餐变化，以购买页/控制台结算页为准。以下只比较**计算实例**，不含大模型 Token、数据库、对象存储、域名备案或额外公网流量。

### 18.1 云托管：两个常驻服务的估算

RunHub 的正确边界是 Java 服务和 Python Agent/RAG 服务分别部署；模型推理通过 API 调用，不在容器中本地部署大模型。

当前 CloudBase 的云托管计价为 1 核 2GiB 服务运行 1 秒等于 0.2 CU，CU 单价为 0.00011108 元；官方示例给出 1 核 2GiB、1 个实例运行 30 天约 57.58 元。

| 服务组合（最小副本均为 1） | 月容器算力估算 | 适用判断 |
| --- | ---: | --- |
| Java `0.5C/1G` + Python `0.5C/1G` | 约 57.58 元 | 能启动但 Java 内存余量偏小，只适合作品演示早期验证 |
| Java `1C/2G` + Python `0.5C/1G` | 约 86.37 元 | 推荐的云托管起步规格；Python 不做本地推理时够用 |
| Java `1C/2G` + Python `1C/2G` | 约 115.16 元 | 并发、RAG rerank 或依赖变多后的保守配置 |

说明：CloudBase Run CLI 当前文档显示 `minNum` 默认可为 0；如果控制台/业务要求两个服务最小副本都保持 1，则使用上表估算。即使允许缩到 0，Java + Python Chat 首次请求的冷启动体验也未必适合演示。

### 18.2 轻量服务器：一机运行两个服务

推荐使用 Tencent Cloud Lighthouse，以 Docker Compose 部署：

```text
Nginx / HTTPS
├── Java RunHub API
├── Python FastAPI Agent/RAG Service
└── 可选 Redis（仅在确有缓存/队列需求时）
```

当前中国大陆购买页列出的基础套餐：

| 规格 | 当前标价 | 是否推荐 |
| --- | ---: | --- |
| 2C2G / 50GB SSD / 4Mbps | 50 元/月、510 元/年 | 不推荐两个服务长期共用；Docker 和 Java 容易内存紧张 |
| **2C4G / 100GB SSD / 7Mbps** | **100 元/月、1020 元/年** | **推荐的个人作品起步方案** |
| 4C8G / 180GB SSD / 12Mbps | 245 元/月、2499 元/年 | 只有要同机承载本地数据库、Qdrant/检索、较多用户或后台任务时再考虑 |

### 18.3 最终建议

1. **未来两周**：继续用现有微信云托管，单独新建 Python Agent/RAG 服务，完成真实链路、SSE、会话、Tool、Trace 和 RAG Demo；不要为了省几元钱中途改变架构。
2. **免费额度结束后，若 RunHub 是长期求职作品**：购买 2C4G Lighthouse，Java 与 Python 继续分成两个 Docker Container，但部署到同一台机器；配置 Nginx、HTTPS、日志轮转、自动重启和每日数据库备份。
3. **不要在 2C4G 上同时部署 MySQL、Elasticsearch 和向量库**。优先复用 RunHub 已有托管数据能力；RAG 初期使用托管 Postgres/向量服务或轻量的远程检索服务。等确实需要本地全套基础设施，再升至 4C8G 或拆分服务。
4. 使用轻量服务器前，需要准备域名、HTTPS 和中国大陆 ICP 备案，并把域名配置到微信小程序的合法请求域名；若短期内不想处理这些事项，云托管虽然稍贵但更省事。

## 19. Pi Agent Harness：面向 HP / RunHub 的学习路线

### 19.1 它是什么

`https://github.com/earendil-works/pi` 是 Pi 官方的 monorepo，仓库名称是 **Pi Agent Harness**。它不是只有一个聊天 Agent，而是分成多层：

```text
packages/agent（发布包名：@earendil-works/pi-agent-core）
  最小 Agent Runtime：状态、模型—Tool 循环、事件、Hook

packages/coding-agent
  在 core 上实现的终端 Coding Agent：会话文件、上下文压缩、扩展、命令、工具权限接入

packages/ai
  多模型 Provider 适配

packages/tui / coding-agent UI
  终端交互界面
```

对于 HP / RunHub，学习目标不是把 Pi 接进 Python 项目，也不是做 Coding Agent；目标是理解“一个可用 Agent Runtime 必须怎样管理状态、Tool、事件和长会话”。

### 19.2 先学什么，不学什么

| 优先级 | 阅读范围 | 要回答的问题 | HP 对应物 |
| --- | --- | --- | --- |
| 1 | 根目录 README、`packages/agent` | `pi-agent-core` 与 CLI 的边界是什么？ | Python Agent Runtime 与小程序 UI 的边界 |
| 2 | `packages/agent/src/agent.ts` | 一次 `prompt` 如何变成消息、Tool Call、Tool Result、下一轮？事件有哪些？ | LangGraph 单 Agent Loop、SSE 事件协议 |
| 3 | `packages/coding-agent/src/core/session-manager.ts` | 原始消息如何持久化？如何用 `id/parentId` 表示分支？ | Conversation 表/Trace 审计模型 |
| 4 | `packages/coding-agent/src/core/agent-session.ts` 的 compaction 部分 | 长对话怎样变为“摘要 + 最近消息”？何时重试？ | Context Builder、会话摘要策略 |
| 5 | Hook、`beforeToolCall/afterToolCall` | Tool 前后如何插入权限、日志、策略？ | Policy Guard、Tool Executor、Trace |
| 6 | 扩展和 Coding Tools | 只在前五步理解后按兴趣阅读 | 不作为 HP 一期实现目标 |

第一轮**不要**阅读 TUI、Bash、文件编辑、沙箱、MCP 扩展、多代理、插件生态；它们属于 Coding Agent 的产品功能，会把学习焦点从 Runtime 基础带偏。

### 19.3 建议的七天学习节奏

| 天数 | 学习与输出 | 达标标准 |
| --- | --- | --- |
| Day 1 | 阅读根 README 与包关系，画出 core / coding-agent / Provider / UI 四层图 | 能说清 `pi-agent-core` 不是完整会话系统 |
| Day 2 | 阅读 `agent.ts`，只追踪 `prompt → runAgentLoop → event → state.messages` | 能画出 Model → Tool → Observation → Final 的单循环 |
| Day 3 | 阅读 Tool 事件、`beforeToolCall/afterToolCall` | 能解释鉴权不能只靠 Prompt，必须在 Tool 执行侧做 |
| Day 4 | 阅读 `session-manager.ts`：JSONL、entry、`parentId`、`buildSessionContext` | 能区分“完整历史”与“本轮给模型的上下文” |
| Day 5 | 阅读 `agent-session.ts`：threshold / overflow compaction | 能说明为什么不能永久拼接所有消息 |
| Day 6 | 写一个 **TypeScript 学习实验**：两个 fake Tool、打印事件、一次 Tool 再回答 | 不接业务、不接真实数据库，观察完整事件序列 |
| Day 7 | 用 Python + LangGraph 重写同一实验：`get_student_learning_report` fake Tool + `search_teaching_resources` fake Tool | 能把 Pi 的思想映射到 HP / RunHub 技术栈 |

### 19.4 最小实验的范围

实验不要从聊天 UI、RAG 入库或多 Agent 开始，只实现：

```text
用户：分析小明近一周数学作业
→ Agent 事件：agent_start
→ Tool Call：get_student_learning_report(studentId, subject, timeRange)
→ Tool Result：确定性 fixture
→ Agent 事件：message_end / agent_end
→ 最终回答：引用 fixture 中的事实
```

第二步再加入 `search_teaching_resources`，模拟“业务事实 + RAG 证据”联合回答。只有这两个实验都跑通，再研究 Pi 的上下文压缩、扩展和 subagent。

### 19.5 学习时必须带着的四个问题

1. 这段代码在维护**完整历史**、**运行状态**，还是**模型上下文**？三者不要混为一谈。
2. Tool Result 是如何重新成为下一轮模型输入的？
3. 如果服务重启、用户中断、模型超时或上下文溢出，系统如何恢复？
4. 将 Pi 的机制换成 HP 的 Python + LangGraph 后，哪个组件负责实现它？

Pi 是 TypeScript Coding Agent，不是 HP 的代码模板。正确目标是：借它学 Runtime 的底层结构，再在 RunHub 使用 Python/LangGraph 做功能等价、领域安全的实现。

## 20. Python 学习参考与“框架是否必要”的结论

### 20.1 Pi 不用 LangChain/LangGraph，不等于它没有框架

Pi 没有采用 LangChain 或 LangGraph，因为它自己实现了：

```text
pi-agent-core = 自定义 Agent Runtime
  message state + tool loop + event + hook

pi-coding-agent = 自定义会话框架
  session persistence + compaction + resume + extension

pi-ai = 自定义多模型 Provider 适配层
```

从零写 Agent，真正的最小代码可以只有：

```text
messages = load(threadId)
while True:
    response = model(messages, tools)
    persist(response)
    if response 没有 tool call:
        return response
    result = execute_and_authorize(response.tool_call)
    persist(result)
    messages.append(result)
```

因此 **LangChain/LangGraph 在技术上都不是必须的**。但省略框架意味着团队自己要承担 Tool 参数校验、Tool Call/Result 配对、流事件、重试、中断、checkpoint、上下文溢出恢复、回放和测试等长期工作。Pi 正是选择了自己承担这套工作。

对 RunHub/HP，不值得从零重复造 Pi：

```text
FastAPI + Pydantic v2 + LangGraph
  = 推荐的一期实现主线

LangChain Core
  = 可选的模型/Tool/Retriever 适配层；不是必须使用完整 LangChain
```

LangGraph 最有价值的是 `StateGraph + Checkpointer + threadId`，它使“多轮状态与失败恢复”不需要自己手写；业务 Tool、权限、会话表、RAG 和评测仍然由 RunHub 自己实现。

### 20.2 最适合阅读的 Python 项目 / 文档

| 优先级 | 参考 | 为什么适合 | 学习范围 | 与 RunHub 的关系 |
| --- | --- | --- | --- | --- |
| 1 | `pydantic/pydantic-ai` | 纯 Python、类型清晰、Tool 和消息历史文档直白 | `Agent`、`@agent.tool`、`RunContext`、`message_history` | **学习样本**，不要求作为 RunHub 框架 |
| 2 | `langchain-ai/langgraph` 官方文档 | 直接对应 State、thread、checkpointer、short/long-term memory | memory、checkpointer、interrupt、stream | **RunHub / HP 的实现框架** |
| 3 | `langchain-ai/open_deep_research` | 一个真实复杂 Agent，展示图、研究循环、工具和评测组合 | 后期只追一个完整任务链 | 架构参考，不复制多 Agent |
| 4 | `langchain-ai/langmem` | 聚焦摘要、长期记忆和检索 memory | 在已有对话/状态基础稳固后再看 | 可选，不作为一期依赖 |

不建议一开始阅读 AutoGen、CrewAI、OpenDevin / OpenHands、Coding Agent 全仓库或多 Agent 框架；它们的业务复杂度会盖住你真正需要的单 Agent 基础。

### 20.3 面向小白的 Python 学习顺序

1. 先阅读 Pydantic AI 的最小 Tool 示例：一个 Python 函数如何成为 Tool，模型如何拿到 Tool Result 后回答；
2. 再看它的 `message_history` 文档，理解“服务端保存历史、下一轮再传回 Agent”，但不复制其完整框架；
3. 转到 LangGraph 官方的 checkpointer 与 memory 示例，理解 `thread_id`、`State` 和 checkpoint；
4. 在 RunHub 用 LangGraph 写最小的两个 Tool，不同时接 RAG、文件、评测；
5. 运行稳定后，才补 Context Builder、摘要、RAG、Trace 和 Evaluation。

学习中只需始终区分：

```text
message_history：完整聊天与 Tool 事件的记录
graph state / checkpoint：下一步怎样继续执行
model context：本轮实际发送给模型的精简内容
```
