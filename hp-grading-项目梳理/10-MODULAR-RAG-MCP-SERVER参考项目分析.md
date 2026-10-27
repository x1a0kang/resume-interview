# 10｜MODULAR-RAG-MCP-SERVER 参考项目分析与 HP 迁移建议

> 分析对象：[`jerry-ai-dev/MODULAR-RAG-MCP-SERVER`](https://github.com/jerry-ai-dev/MODULAR-RAG-MCP-SERVER)  
> 本地代码：`E:\project\MODULAR-RAG-MCP-SERVER`  
> 分析时间：2026-09-10  
> 用途：学习 RAG 工程原理，筛选可迁移到 HP 教学资源 RAG 的设计；不是为 HP 直接复制代码。  
> 事实边界：以下判断以本地仓库当前 `main` 分支、提交 `f658c5a` 的源码为准。README 中的简历指标和未来能力不视为已经验证的项目事实。

## 1. 先给结论

这个项目值得学习，但它更准确的定位是：

```text
模块化 RAG 检索教学骨架
+
本地单机知识库 Demo
+
通过 MCP 暴露检索能力的工具服务
```

它最值得 HP 吸收的不是 Chroma、MCP 或某个框架名称，而是以下工程思路：

1. 把加载、分块、增强、编码、检索、融合、重排、返回和评测拆成有明确输入输出的模块；
2. 同时使用 Dense Retrieval 与 BM25，再用 RRF 合并两个排序；
3. 使用稳定的文档/Chunk 标识、内容哈希和幂等 Upsert；
4. 为入库和查询的每个阶段记录 Trace、耗时和中间结果；
5. 用 Golden Test Set 做检索回归，而不是靠人工试几次就宣称效果良好；
6. 把检索能力包装成有 Schema 的工具，供上层 Agent 或生成流程调用。

但它不能作为 HP 的生产架构直接照搬。当前实现缺少 HP 必需的资料版本、教材适用范围、ACL、发布/撤回一致性、任务状态、真正有效的中文教育评测，以及针对“题目 + 学生错误”的 Query 构造。其 PDF 图片定位、分块、错误语义和默认评测也只是 Demo 水平。

## 2. 它到底实现了什么

### 2.1 技术栈

| 层次 | 当前项目实现 |
| --- | --- |
| 语言 | Python 3.10+ |
| 配置 | YAML + dataclass 校验 |
| 文档解析 | MarkItDown，当前 Loader 主要面向 PDF |
| 文本分块 | LangChain `RecursiveCharacterTextSplitter` |
| 中文分词 | jieba |
| Dense Embedding | OpenAI、Azure OpenAI、Ollama 适配器 |
| Sparse Retrieval | 自研本地 BM25 倒排索引，按 Collection 保存 JSON |
| Vector Store | Chroma 持久化本地库 |
| 融合 | RRF（Reciprocal Rank Fusion） |
| 重排 | LLM Reranker、CrossEncoder Reranker；默认关闭 |
| 对外协议 | 官方 MCP Python SDK，stdio transport |
| Trace | JSON Lines 文件 |
| 管理界面 | Streamlit Dashboard |
| 评测 | 自定义 Hit Rate/MRR + Ragas |
| 测试 | unit / integration / e2e 三层目录 |

配置和 README 虽然提到 Qdrant、Pinecone 等扩展方向，但当前源码中实际注册的向量存储实现只有 Chroma。它具备可插拔接口骨架，不等于每个宣传的 Provider 都已经实现。

### 2.2 入库链路

```text
PDF 文件
  → SHA256 完整性/重复处理检查
  → MarkItDown 提取文本，PyMuPDF 提取图片
  → RecursiveCharacterTextSplitter 固定字符分块
  → Chunk 文本清理、可选 LLM Refine
  → 标题/摘要/标签等元数据增强
  → 图片 Caption
  → Dense Embedding + BM25 词项统计
  → Chroma 向量数据 + 本地 BM25 JSON + 图片索引
```

可学习点是每个阶段通过统一的 `Document`、`Chunk`、`ChunkRecord` 契约衔接，并把编码和存储分开。文件哈希、稳定 ID 与 Upsert 也体现了基本的幂等意识。

### 2.3 查询链路

```text
用户 Query
  → QueryProcessor：规范化、jieba 分词、停用词、key:value 过滤语法
  ├─ DenseRetriever：原 Query 做 Embedding，在 Chroma 查相似向量
  └─ SparseRetriever：关键词查询本地 BM25，再按 Chunk ID 从 Chroma 补正文
  → RRF 合并两个排名
  → 可选 Reranker
  → ResponseBuilder 返回 Chunk 摘要、引用元数据和图片
  → MCP Client 或上层 Agent 使用结果生成最终回答
```

这里必须纠正一个容易产生的误解：`query_knowledge_hub` 返回的是检索结果，不是完整的最终答案。服务内部没有在主查询链路中根据 Evidence Pack 调用 LLM 生成回答。真正的回答需要由 MCP Client 一侧的模型或另一个上层生成服务完成。因此，它首先是 **Retrieval MCP Server**，其次才是一个可被组装进 RAG 的底座。

### 2.4 MCP 在这里的作用

MCP 不是 RAG 算法。它只是把能力以标准工具形式暴露出来：

- `query_knowledge_hub`：检索指定 Collection；
- `list_collections`：查看知识库集合；
- `get_document_summary`：读取文档摘要。

```text
RAG Retriever = 真正查资料的业务能力
MCP Tool       = 让外部 Agent 按统一协议调用这项能力的适配层
```

HP 自有小程序和内部服务优先使用 FastAPI/内部 HTTP 更直接；如果未来需要被多个 Agent Host 复用，再增加 MCP Adapter，而不是为了简历强行把 MCP 放进核心链路。

## 3. 从项目学习六个 RAG 核心概念

### 3.1 Chunk 不是随便截取的一段字符串

模型和向量数据库不会直接“理解一本书”。入库时需要把文档切成可召回的最小证据单元，即 Chunk。

本项目使用递归字符分块：先尝试按段落、换行、英文标点和空格切分，仍过长时再按字符截断。默认配置是 `chunk_size=1000`、`chunk_overlap=200`。这能快速搭建 Demo，但不适合直接用于 HP 教材：

- 标题可能与正文分离；
- 数学定义、公式、例题、解答可能被截断；
- 中文句号、分号等没有作为默认显式分隔符；
- 相同字符数对语文和数学不是相同的信息密度；
- Chunk 没有天然继承完整的“版本—册次—章—节”路径。

HP 应迁移 `Splitter` 接口和可替换设计，而不是固定参数。至少需要“章节结构优先 + 内容类型识别 + 最大长度兜底”的策略。

### 3.2 Dense Retrieval 解决语义相近

Dense Retrieval 会把 Query 和 Chunk 变成向量，按照向量距离找到语义接近的文本。

```text
Query：分数除法里为什么要把除数翻过来？
Chunk：除以一个不为零的数，等于乘这个数的倒数……
```

两段文字不完全相同，但语义接近，Dense Retrieval 有机会召回。它适合自然语言改写、近义表达和讲解性内容。局限是对精确章节名、公式符号、专有名词和数字未必稳定，也不能代替教材版本等硬过滤。

### 3.3 BM25 解决关键词精确匹配

BM25 是传统全文检索排序算法。直观上，它会提高以下内容的得分：

- Query 中的词在某个 Chunk 中出现；
- 这个词在整个知识库里较少见，区分度高；
- 同一个词出现多次，但收益逐渐饱和；
- 同时校正文档长度，避免长文本仅因词多而占便宜。

查询“分数除法 倒数”时，包含关键词的教材段落容易获得较高 BM25 排名；查询“为什么要翻过来”则未必，因为教材可能没有“翻过来”这个词，此时 Dense 更有价值。

本项目的 BM25 是 Python 本地倒排索引，不是 Chroma 的稀疏向量。索引按 Collection 保存为 JSON，查询时从磁盘载入以获得最新数据。这适合本地学习，不适合 HP 的多实例、高并发和在线版本发布。

### 3.4 RRF 合并两种排序

Dense 和 BM25 的分数尺度不同，不能直接把余弦相似度和 BM25 分数相加。RRF 不关心原始分数，只看结果在各列表中的名次：

```text
RRF_score(d) = Σ 1 / (k + rank(d))
```

一个 Chunk 如果在 Dense 和 BM25 中都排名靠前，融合后通常更靠前；只被一路找到的 Chunk 仍可保留。本项目的 RRF 还支持权重，整体思路值得保留。

HP 应先确认 VikingDB 的混合检索和融合能力。原生能力满足需求时，不必复制本地 BM25 JSON；需要跨多路 Retriever 融合时，可以在应用层保留 RRF。

### 3.5 Reranker 对候选集做二次精排

Retriever 先低成本召回几十条候选；Reranker 再将 `Query + Chunk` 成对判断，选出真正相关的几条。

```text
VikingDB/BM25 召回 Top 30
  → CrossEncoder 或模型重排
  → 最终 Evidence Top 5
```

本项目提供 LLM 和 CrossEncoder 两种接口，但默认关闭，README 也把 CrossEncoder 标为尚未充分测试。可以学习“可选重排 + 失败回退”的结构，不能引用其效果数字。

### 3.6 RAG 评测首先是检索评测

本项目把评测独立成 `EvalRunner`，方向正确：

- Hit Rate@K：前 K 条中是否至少有一条正确证据；
- MRR：第一条正确证据出现越靠前，得分越高；
- Faithfulness：回答是否由检索证据支撑；
- Answer Relevancy：回答是否切中问题；
- Context Precision：取回上下文中有多少真正有用。

但当前 `golden_test_set.json` 的 5 条样例都没有填写 `expected_chunk_ids` 和 `expected_sources`，E2E Recall 测试会跳过无标注样例，阈值也暂为 0。因此它只是评测框架样板，不能证明项目已经达到任何召回率。

## 4. 值得迁移到 HP 的设计

| 参考项目设计 | 学习价值 | HP 的迁移方式 |
| --- | --- | --- |
| `Document / Chunk / RetrievalResult` 统一类型 | 降低流水线耦合 | 扩展为带教材版本、章节目径、ACL、文档版本和内容哈希的领域 Schema |
| Embedding、VectorStore、Reranker、Splitter 接口 | 隔离供应商实现 | 使用 Port/Adapter；首期只实现真实需要的 Provider，避免过度抽象 |
| SHA256 + 稳定 ID + 幂等 Upsert | 避免重复处理和索引 | 使用 `documentId + version + chunkOrdinal/contentHash` 生成稳定 ID |
| Dense + BM25 | 覆盖语义和精确词 | 使用 VikingDB Hybrid，保留各路结果以便独立评测 |
| RRF | 融合不同分数尺度的排名 | 用于多 Query/多 Retriever 融合，不混淆题库与文档库业务类型 |
| Reranker + fallback | 精排并允许降级 | 离线 A/B 后上线；超时回退并记录原因 |
| TraceContext + stage | 定位改写、召回、过滤、重排或生成问题 | MongoDB 保存 `rag_query_trace`，关联 `requestId/runId/toolCallId` |
| Golden Set + EvalRunner | 建立质量回归 | 由教育业务人员标注真实教材章节/Chunk |
| MCP Tool Schema | 让模型按契约调用 | 先实现内部 `retrieveTeachingEvidence` Tool；MCP 仅作可选适配器 |
| unit/integration/e2e 分层 | 防止静默退化 | 增加 Query Builder、ACL、版本切换、错误语义和降级测试 |

## 5. 不能直接搬到 HP 的实现

### 5.1 Chroma + 本地 BM25 JSON 只适合单机 Demo

HP 应为教学资料创建独立 VikingDB Collection/Index，不能与题目近重复 Collection 混用。Chroma 和本地 JSON 没有解决多实例并发、原子版本切换、水平扩展、备份恢复和发布一致性。

```text
MySQL：文档、版本、章节、Chunk 主数据和入库任务状态
对象存储：原始文件和解析产物
VikingDB：Dense/Sparse 检索索引副本
MongoDB：Agent Turn、Tool Execution、RAG Trace、LangGraph Checkpoint
RabbitMQ：耐久入库任务和阶段重试
```

### 5.2 当前 PDF 解析不适合数学教材

代码使用 MarkItDown 提取正文、PyMuPDF 提取图片，但所有图片占位符被简化追加到整篇文档末尾，没有插入图片在原页的真实文本位置，会破坏“图形/公式/例题与附近解释”的关系。

HP 应增加扫描 PDF OCR、版面/标题层级/表格/公式识别、图片与正文锚点、章节和内容类型、解析质量评分与人工抽查。教材定位按“版本 + 册次 + 章节”保存，不把页码作为稳定业务标识。

### 5.3 固定字符分块不能保证教育语义完整

```text
章/节标题
  → 概念定义
  → 方法与推导
  → 教材例题 + 讲解
  → 易错提醒
  → 过长单元再按 Token/字符切分并重叠
```

标题路径应注入每个 Chunk 的检索文本和元数据。第三方资料中的方法正文进文档 RAG，可展示的结构化题目进公共题库。

### 5.4 通用 QueryProcessor 解决不了 HP 的题目检索

本项目的 QueryProcessor 只做规则分词、停用词和 `key:value` 过滤。它不会从题干、标准解析、学生答案和批改详情生成：

```text
题目公共语义：分数除法的计算步骤、除数转倒数的原理
学生错误语义：分数除法中除数没有取倒数的常见错误与纠正方法
教学任务语义：如何从概念到计算步骤组织一次讲解
```

HP 仍需要独立 Query Builder：

```text
定标后预生成 question_retrieval_profile（全体学生共用）
  ← 题干 + 标准答案 + 解析/解题过程

发生学生讲解请求时动态生成 student_error_query（每个学生不同）
  ← 题目 Profile + 学生作答 + 标准答案/步骤 + 批改详情

最终检索
  ← 多 Query 并行召回 + 版本/地域/学科硬过滤 + 融合 + 重排
```

确定性代码只能抽取和拼接已有内容；要生成“除数没有取倒数的常见错误”这类输入中没有直接出现的教学语义，需要 LLM 结构化改写，或未来引入准确、受控的错误分类器。第一版不使用当前准确率不足的知识点标签作为 Query 或硬过滤。

### 5.5 缺少资料生命周期和权限闭环

当前实现没有完整表达资料授权期限、教材版本与适用地区、学校覆盖、文档新旧版本切换、删除/撤权后的全链路清理、索引完成后的原子发布和 ACL 前置过滤。这些不是外围后台功能，而是 HP RAG 能否上线的核心条件。

### 5.6 错误与“没有证据”不能混为一谈

`query_knowledge_hub._perform_search` 捕获 Hybrid Search 异常后返回空列表，上层会包装成“未找到相关结果”。这会把数据库故障、Embedding 超时等系统错误伪装成正常空召回。

HP 必须区分：

```text
SUCCESS_WITH_EVIDENCE
SUCCESS_NO_EVIDENCE
PARTIAL_SUCCESS
DEPENDENCY_ERROR
TIMEOUT
ACL_FILTERED
```

只有 `SUCCESS_NO_EVIDENCE` 才能走无教材证据的生成降级；依赖故障要监控、重试或明确失败。

### 5.7 图片路径需要安全边界

MultimodalAssembler 会优先相信结果元数据中的 `file_path`，存在时直接读取并编码。即使元数据通常由可信入库流程产生，生产系统也不能把可变元数据当作任意文件读取凭证。

HP 应只保存对象存储资源 ID 或受控相对路径，读取前校验租户、资料版本、根目录、MIME 和大小，不让 Query 或 Chunk 元数据直接控制本地绝对路径。

### 5.8 包入口没有完全收口

`pyproject.toml` 把 `mcp-server` 指向 `main:main`，但根目录 `main.py` 仍只打印“Phase E 将实现 MCP Server”后退出；真正的启动实现在 `src/mcp_server/server.py`。迁移时应把可安装命令、容器启动、健康检查和实际服务入口纳入 E2E 验收。

## 6. 适配 HP 后的目标架构

### 6.1 服务边界

```text
HP-Grading（Java/Spring Boot）
  ├─ 作业、题目、答案、批改详情、班级统计等 Domain API
  ├─ 学校/地域/教材版本解析
  └─ 权限与数据域校验

AI Application Service（Python/FastAPI + LangGraph）
  ├─ Agent Runtime / Tool Registry
  ├─ Teaching RAG Query Builder
  ├─ Teaching Document Retriever
  ├─ Evidence Builder / Reranker
  ├─ 回答/讲评生成
  ├─ Evaluation Harness
  └─ 可选 MCP Adapter

Ingestion Worker（Python + RabbitMQ/Celery 或受控 Worker）
  ├─ 文档解析/OCR/版面/公式
  ├─ 结构化分块
  ├─ Embedding/索引
  └─ 版本发布与删除同步
```

Agent 和 RAG 可以部署在同一套 Python AI 应用服务中，但逻辑模块必须分开：Agent 决定任务和工具序列，RAG 只负责把教学资料变成可验证的 Evidence Pack。入库 Worker 可以独立部署和扩缩容。

### 6.2 HP Chunk 最小字段

```text
documentId
documentVersionId
chunkId
contentHash
sourceType              // TEXTBOOK, TEACHING_REFERENCE, STUDY_GUIDE
editionId
subject
grade
semester
volume
chapterPath
sectionTitle
contentType             // DEFINITION, METHOD, EXAMPLE, COMMON_ERROR...
text
embeddingVersion
aclScope
publishStatus
```

VikingDB 保存检索所需的文本、向量和过滤字段副本；MySQL 保存权威主数据。模型实际看到的 Evidence 还要写入 Mongo Trace，便于解释某次回答为何使用这些内容。

### 6.3 HP 在线检索链路

```text
产品入口/Agent 识别“需要外部教学知识”
  → HP Tool 获取题目、标准解析、学生作答和批改详情
  → Textbook Router 解析 editionId/学科/年级/册次
  → Query Builder
      ├─ 读取预生成的 question_retrieval_profile
      ├─ 学生场景动态生成 student_error_query
      └─ 班级讲评生成 teaching_plan_query
  → VikingDB Hybrid Retrieval（硬过滤前置）
  → 多 Query RRF/去重
  → Reranker
  → Evidence Gate：相关度、版本、权限、冲突和最小证据检查
  → Evidence Pack
  → LLM 生成课本化讲解/讲评/备课草案
  → 保存 Query、候选、最终证据、版本和耗时
```

题库仍通过 Question Retriever/Recommendation Tool 提供完整练习题，不能把公共题库题目与教材解释性 Chunk 混成一种结果。

## 7. 建议怎样阅读和动手学习

### 7.1 阅读顺序

1. `src/core/types.py`：模块契约；
2. `src/ingestion/pipeline.py`：入库各阶段；
3. `src/libs/splitter` 与 `src/ingestion/transform`：分块和增强；
4. Dense、Sparse、BM25：两类召回；
5. `fusion.py`、`hybrid_search.py`、`reranker.py`：融合与精排；
6. Response/Citation：Evidence 如何变成工具结果；
7. Trace/Evaluation：可观测和回归；
8. 最后看 MCP：它是适配层，不是 RAG 核心。

### 7.2 四组关键实验

1. **Dense/BM25/Hybrid/Rerank 对比**：固定 30 条人工标注问题，比较 Recall@5、MRR、错误类型和耗时。
2. **原始数学题干与改写 Query 对比**：比较原题、题干加解析、`question_retrieval_profile`、再加 `student_error_query`。
3. **固定字符与结构化分块对比**：同一章教材建立两份索引，比较正确章节召回、证据完整度、重复率和 Token。
4. **故障与降级**：模拟 Dense 超时、Sparse 缺失、Reranker 超时、ACL 全过滤和无相关资料，验证状态是否可区分。

第二个实验会直接回答当前最关键的问题：只有数字、公式和短描述的题干能否稳定召回教材，以及 LLM 改写到底增加了多少收益和误扩展。

## 8. 对 HP 的迁移优先级

### P0：先迁移设计和评测方法

1. 定义 `TeachingDocument / DocumentVersion / TeachingChunk / Evidence` Schema；
2. 建 30～50 条真实教材 Golden Query，人工标注正确章节和可接受 Chunk；
3. 做一章教材的结构化解析与分块样本；
4. 实现 `question_retrieval_profile` 与动态 `student_error_query`；
5. 在 VikingDB 对比 Dense、Sparse、Hybrid、Rerank；
6. 建完整 Trace，保留各路 Query、候选和最终证据。

### P1：再补生产生命周期

文档版本、适用范围、ACL、入库状态机、重试/死信、原子发布、删除/撤权同步、解析质量抽查和索引重建。

### P2：最后增加高级能力

CrossEncoder 的收益验证、多 Query 路由与缓存、MCP Adapter、多模态教材证据和更自主的 Agent 检索。

MCP、Dashboard 和大量供应商 Factory 不应排在有效 Golden Set、正确分块、Query Builder 和资料生命周期之前。

## 9. 面试表达和事实边界

可以说：

> 我分析并复现过一个模块化 RAG MCP 参考项目，重点拆解了 Dense Retrieval、BM25、RRF、Reranker、Trace 和评测链路。分析后没有直接把 Chroma 和本地 BM25 复制到教育项目，而是结合 HP 已有 VikingDB、RabbitMQ、MySQL/MongoDB 和教材版本路由重新设计。参考项目最明显的不足是通用 QueryProcessor 无法从题目和学生错误构造教学检索语义，因此我把题目级 Profile 预生成和学生错误动态 Query 作为 HP 的领域核心，同时补充 ACL、文档版本、原子发布和真实 Golden Set。

不能说：

- README 指标是自己的实测结果；
- HP 已经上线了这套 RAG；
- 使用 MCP 就等于完成 Agentic RAG；
- 使用 Hybrid Search 就自然能准确召回数学教材；
- 有 Ragas 代码就等于评测已经有效。

## 10. 核验范围与限制

本次已核验 README、`DEV_SPEC.md`、依赖与配置、入库/检索/响应/MCP/Trace/评测核心源码、测试目录和 Golden Set。静态统计到 136 个测试函数，但没有把“存在测试代码”当作“全部测试通过”。

当前系统 `python` 指向不可执行的 Windows Store 占位程序；Codex 自带 Python 3.12 环境没有安装 pytest，因此本次没有实际执行测试。该限制只代表当前机器验证环境不足，不等于项目测试失败。正式学习时应创建独立虚拟环境、安装锁定依赖并执行 unit、integration、e2e，保存真实报告。

## 11. 最终迁移判断

```text
直接复用代码：低
学习 RAG 原理：高
学习模块化和测试骨架：中高
作为 HP 生产架构：不足
作为 HP 第一阶段实验基线：合适
```

对 HP 最有价值的迁移不是“把该项目接进来”，而是以它为对照基线，证明以下教育领域设计为什么必要：

```text
结构化教材 Chunk
+ 教材版本/地区硬路由
+ 题目级 Profile 预生成
+ 学生错误动态 Query
+ VikingDB Hybrid Retrieval
+ Evidence Gate
+ 真实 Golden Set
+ 资料版本与 ACL 生命周期
```

这样 HP 的 RAG 叙事不再是通用组件堆砌，而是从真实作业批改上下文出发，解决“该查什么、查哪套教材、怎样证明查对了、没有证据时怎么办”的完整工程问题。

## 12. 补充学习笔记：文件解析、Chunk、存储与本地运行

这一节专门回答“这个项目里面具体怎么做”的问题。结论以当前源码为准，而不是 README 中对未来扩展能力的描述。

### 12.1 它能不能处理一整本教材 PDF 或 Word？

**当前能处理普通 PDF，不能处理 Word。**

虽然依赖中安装了 `markitdown[pdf]`，但实际业务 Loader 是 `PdfLoader`：

    scripts/ingest.py
      → discover_files() 只发现 .pdf / .PDF
      → PdfLoader.load()
          → 明确拒绝文件后缀不是 .pdf 的输入
          → MarkItDown.convert(pdf)
          → Document

因此：

| 输入资料 | 当前代码会怎样处理 | 对 HP 的判断 |
| --- | --- | --- |
| 可复制文字的 PDF | MarkItDown 一次性解析整份文件为 Markdown/纯文本 | 可作为最基础起点，但要评测教材章节、公式和表格保留情况 |
| 扫描版 PDF | 没有 OCR 阶段；PDF 没有文字层时不能指望提取结果可靠 | 不可直接用于 HP，必须加 OCR 与解析质量检测 |
| Word / DOCX | `PdfLoader` 和脚本都直接拒绝 | 当前未支持；需要单独实现 `DocxLoader` |
| PPT / Excel / Markdown / HTML | 当前脚本未发现对应 Loader | 当前未支持；不能因为 MarkItDown 理论可扩展就当作项目已经支持 |
| PDF 中嵌入图片 | PyMuPDF 提取图片文件，Vision LLM 可选生成描述 | 有思路，但当前图片位置处理不适合数学教材 |

它处理一份大 PDF 的实际步骤如下：

    1. 对整个文件做 SHA256
    2. SQLite 查询该 hash 是否已成功入库；相同文件直接跳过
    3. MarkItDown 把整份 PDF 转成一段文本
    4. PyMuPDF 遍历每页，导出嵌入图片
    5. 图片写入 data/images/<collection>/<fileHash>/
    6. 在文本中加入 [IMAGE: imageId] 占位符
    7. 将完整文本交给后续 Chunker

其中有两个优点：

- **按文件哈希增量处理**：同一文件再次上传不会重复建向量；
- **图片有独立 ID 和页码元数据**：后续可以尝试把图片描述合并到文本检索链路。

但对于 HP 教材，当前实现有四个不能忽略的问题：

1. 它没有 OCR，扫描教材、公式图片、复杂表格会丢失内容；
2. `MarkItDown.convert()` 按整份文件处理，缺少“页 → 章 → 节”的显式中间结构，大教材的失败重试、局部重建和质量抽查不够细；
3. 代码把每张图片的 `[IMAGE: ...]` 占位符都追加到**整份文本末尾**，而不是放在原本附近的段落。图形题、几何图、教材例题图会失去上下文；
4. 资料更新只依赖整个文件 hash。文件变一个字会全量重建；但 HP 还需要业务层 `documentVersion`、授权状态、教材适用范围和原子发布。

所以它值得迁移的不是 `PdfLoader` 原样代码，而是这条责任链：

    原始文件
      → 可追溯解析结果
      → 可重跑的分块
      → 可验证索引
      → 用 hash 防止重复处理

HP 应该把 Loader 抽象成：

    SourceParser
      ├─ PdfTextParser            // 有文字层 PDF
      ├─ PdfOcrLayoutParser       // 扫描 PDF：OCR + 版面 + 公式/表格
      ├─ DocxParser               // Word
      └─ MarkdownHtmlParser       // 已授权电子资料

每个 Parser 统一产出 `ParsedDocument`，其中至少包含 `blockId、text、pageOrAnchor、headingPath、contentType、image/formula/table reference`。后续按结构分块，而不是先扁平化成一大段字符串。

### 12.2 它的 Chunk 是怎么切的？

项目真正启用的是 `LangChain` 提供的 `RecursiveCharacterTextSplitter`，配置为：

    chunk_size: 1000
    chunk_overlap: 200
    splitter: recursive

这里的 1000 和 200 是**字符数**，不是 token 数，不是句子数，也不是语义单位。

递归切分时，Splitter 按以下优先级不断尝试：

    双换行
    → 单换行
    → 英文句号 ". "
    → 英文感叹号 "! "
    → 英文问号 "? "
    → 英文分号 "; "
    → 英文逗号 ", "
    → 空格
    → 单字符硬切

“递归”不是模型理解语义，而是：先优先保留较大的结构边界；一个块仍超长时，再逐级使用更细的分隔符，最后才强制按字符切。`overlap=200` 表示相邻块刻意重复大约 200 个字符，降低关键信息刚好被切到边界两侧的风险。

例如一节资料为：

    标题：分数除法

    定义……
    方法……
    例题……
    易错提醒……

理想情况下它会先按段落切；若“例题 + 解题过程”超过 1000 字，则会继续按标点或字符拆成两段，后一段带有前一段末尾约 200 个字符。

分块后的 `DocumentChunker` 会：

- 继承原始文档元数据；
- 添加 `chunk_index`、`source_ref`；
- 根据 `documentId + chunkIndex + 文本 hash` 产生一个初始稳定 ID；
- 从正文中识别 `[IMAGE: id]` 占位符，写入该 Chunk 的 `image_refs`。

随后 `VectorUpserter` 又用 `sourcePath hash + chunkIndex + content hash` 生成一次向量库 ID。最后 BM25 的 ID 对齐到向量库 ID。这个设计体现了幂等思路，但对学习者来说容易混淆：**同一个 Chunk 出现两套 ID 规则**。

HP 的改进应是：在业务层只生成一次 `chunkId`，这个 ID 同时用于 MySQL、VikingDB、BM25 结果、Trace 和 Evidence；不要由不同存储适配器重新发明 ID。

还有一个代码事实：配置注释写了 `semantic`、`fixed_length` 等 Splitter 选择，但 Factory 当前只注册了 `recursive`。因此这个项目没有真正的语义分块实现；“可插拔”是接口预留，不能理解成这三种算法已经具备。

### 12.3 分块之后它还做了什么？

它没有直接把原始 Chunk 向量化，而是加了三个 Transform：

    原始 Chunk
      → ChunkRefiner
      → MetadataEnricher
      → ImageCaptioner
      → Dense / Sparse Encoding

#### A. ChunkRefiner

先用规则去掉 HTML、注释、异常空格、部分英文页眉页脚；然后可以并发调用 LLM，把文本“清理得更连贯”。配置默认允许 LLM，每批最多 5 个并发调用，失败会退回规则清理。

优点是有降级设计，LLM 不可用不会导致整份资料入库失败。

风险是提示词要求模型不要输出任何 Markdown 标题、列表或格式。对通用技术文档可能合理，但教材标题层级、例题编号、列表式步骤本身就是重要语义；先扁平化、再让模型清洗，反而可能损失教学结构。

**HP 结论：** 先由解析器保留 `chapterPath / sectionTitle / exampleNo` 等结构，Refiner 只能清洗正文噪声，不能删除结构字段；对教材不把 LLM Refine 作为首期必经步骤。

#### B. MetadataEnricher

它从每个 Chunk 提取 `title、summary、tags`。规则实现重点偏英文：Markdown 标题、首句、英文首字母大写词、camelCase、snake_case；也可以让 LLM 通过一段文本格式返回标题/摘要/标签。

**实际用途核查（2026-10-15）：** 这些字段写入 `chunk.metadata`，正文不变，随后随记录保存；DenseEncoder 和 SparseEncoder 都只读取 `chunk.text`，未把生成标题、摘要和标签拼进向量输入或 BM25 分词文本。因此不能将此步骤描述为已经提高 dense/BM25 召回。

结果接口返回标题；`get_document_summary(doc_id, collection?)` 是面向 MCP 调用方的资料概览工具，返回标题、摘要、标签、来源路径与 Chunk 数。它按 ID 查文档片段，标题/标签主要取首片，摘要使用第一个带 `metadata.summary` 的片段，缺失时截取首片正文。工具执行时不调用 LLM，也不综合全文；局部摘要未必代表整个文档，不能直接当作可靠全文总结。[工具实现](../../别人的项目/MODULAR-RAG-MCP-SERVER/src/mcp_server/tools/get_document_summary.py:317)

标签在 HybridSearch 中有筛选分支，但 Chroma 适配将列表转换为逗号字符串，筛选又按集合处理；类型兼容需要单独验证。字段“被存储”不等于筛选已经可靠，更不等于向量相关性提高。

对中文教材，这套默认规则并不可靠，尤其无法稳定产出“学科、年级、教材版本、章、节、定义/方法/例题/易错点”等真正有价值的元数据。

**HP 结论：** 这些字段的主来源应该是资料录入和结构解析，而非让 LLM 猜。只服务问答召回、没有资料浏览需求时，逐片 LLM 标题/摘要生成缺少收益依据，当前本地 PoC 不采用。后续如需 `pedagogicalSummary` 或 `retrievalHints`，先确定是概览、筛选、增强向量、摘要索引还是重排输入，再决定是否生成、校验并保存模型/提示词版本；必须有对应评测，不能仅因参考项目有这一层就照搬。

#### C. ImageCaptioner

它把可关联的图片交给 Vision LLM 生成文字描述，希望实现“搜文字也能搜到图”。这个方向有价值，但当前图片锚点错误，Caption 可能附着不到真正相关的 Chunk。

**HP 结论：** 数学图形、表格和公式优先做“图像—页—段落/例题”的版面关联；没有关联，就不要把泛化 Caption 当作可信教材证据。

补充成本口径：当两个文本模块及视觉模块全部启用且无重试时，N 个 Chunk 与 I 张需描述的唯一图片通常产生约 `2N + I` 次生成请求，不是每篇文档总共三次。两个文本阶段默认各并发5，图片阶段并发3，阶段之间依次执行；会增加离线入库时间与 token 成本，不能把它们默认视为免费的检索优化。

### 12.4 LangChain、jieba、BM25、Chroma、RRF 分别在这里做什么？

#### LangChain：这里只使用了一个小组件

README 写了 LangChain，但依赖中实际只有 `langchain-text-splitters`。项目没有使用 LangChain 的 Chain、Agent、Retriever、LCEL，也没有 LangGraph。

它只借用了 `RecursiveCharacterTextSplitter`，等价于“拿一个成熟的文本切割工具”。这是合理的轻量使用方式，不代表项目是 LangChain 编排项目。

对 HP，可复用这个思想：首期完全可以只使用 `langchain-text-splitters`，不必因为需要分块就引入全套 LangChain。

#### jieba：给中文文本切词

中文没有天然空格，BM25 需要“词”来计算词频。项目在两个地方使用 jieba：

    入库：SparseEncoder
      Chunk → jieba.lcut() → 过滤标点和长度 < 2 的词 → 词频表

    查询：QueryProcessor
      Query → jieba.lcut() → 去停用词 → 查询关键词

例如：

    “分数除法为什么要把除数变成倒数”
    → [“分数”, “除法”, “为什么”, “要”, “把”, “除数”, “变成”, “倒数”]
    → 去掉“为什么、要、把”等停用词
    → [“分数”, “除法”, “除数”, “变成”, “倒数”]

这可以支持最基本的中文 BM25。但该项目存在一个实现不一致：查询侧默认允许 1 个字的词，入库 `SparseEncoder` 默认丢掉长度小于 2 的词；同一个词在两侧未必都存在。数学里 `x、y、π、角、边` 等单字符符号/术语尤其容易受影响。

**HP 结论：** jieba 可以用于早期文本 BM25 实验，但要维护教育词典、数学符号规则、教材术语同义词，并保证索引和查询共用同一套 Analyzer。教学资料检索不能只靠分词；它只是 Sparse 路的一环。

#### BM25：稀疏关键词召回

项目没有采用 `rank_bm25` 等现成库，而是自己构建倒排索引：

    term
      → idf / 这个词出现在哪些 Chunk
      → 每个 Chunk 中出现次数 tf
      → Chunk 长度 doc_length

查询时，BM25 为每个命中的 Chunk 累加词项分数。默认参数是 `k1=1.5`、`b=0.75`：

- `k1` 控制“一个词重复出现”的收益何时饱和；
- `b` 控制“长 Chunk 不能只因为包含更多词就天然占优”的长度归一化强度。

它适合“分数除法、倒数、单位 1、平方根”这种教材原文中可能准确出现的术语；不擅长“为什么要翻过来”这类口语化表述。

#### Chroma：本地优先的向量数据库

Chroma 不是 Embedding 模型，也不是大模型。它是保存和查询向量的数据库：每条记录可以理解成：

    id          = Chunk 的唯一标识
    embedding   = 该 Chunk 的向量
    document    = Chunk 正文
    metadata    = 标题、来源、chunk_index 等过滤字段

该项目用 `chromadb.PersistentClient` 把数据持久化到 `data/db/chroma`，每个 Collection 类似一个知识库命名空间，例如 `knowledge_hub`、`textbook_math`。它自己负责调用 Embedding API，随后把向量、正文和元数据传给 Chroma；查询时输入向量，Chroma 用余弦距离找最相似的 Top K。

Chroma 官方的 Collection 就是存储和检索的基本单位，也支持将 Embedding、文本和 Metadata 分开传入，并在查询时使用 Metadata Filter。[Chroma Collection 文档](https://docs.trychroma.com/docs/collections/manage-collections) [Chroma Query 文档](https://docs.trychroma.com/docs/querying-collections/query-and-get)

项目层面**没有自己建 `document`、`chunk` 两张关系表**。Chroma 内部有自己的持久化实现和文件，应用代码不应该依赖其内部 SQLite/HNSW 文件格式；把它当作一个“拥有 Collection 和 Record 的独立数据库”即可。

#### RRF：只融合“排名”，不直接相加分数

RRF（Reciprocal Rank Fusion，倒数排名融合）不是数据库或模型，而是一个排序算法，用于合并 Dense 和 BM25 两个候选列表。

    RRF_score(d) = Σ 1 / (k + rank(d))

项目 `k=60`。假设：

| Chunk | Dense 名次 | BM25 名次 |
| --- | ---: | ---: |
| A | 1 | 未出现 |
| B | 2 | 1 |
| C | 未出现 | 2 |

则 B 的分数约为：

    1 / (60 + 2) + 1 / (60 + 1)

它同时在两条路径靠前，所以比“只在其中一路第一”的候选更容易排前。这样不需要把余弦相似度和 BM25 原始分数硬凑到同一个量纲。

HP 可以参考 RRF 的思想，但要先比较 VikingDB 原生 Hybrid 与应用层 RRF 的效果。数据证明没有收益时，不要为了技术名词再增加一段处理。

### 12.5 它在本地到底存了什么？有哪些“库和表”？

可以把它的本地数据结构分成四类，而不是误以为所有内容都在 Chroma：

| 层 | 路径/数据库 | 核心数据 | 是否有用户自己维护的表 |
| --- | --- | --- | --- |
| 向量库 | `data/db/chroma` | Chunk 向量、正文、Metadata、Collection | 没有。通过 Chroma API 操作 Record，不依赖内部表 |
| 稀疏索引 | `data/db/bm25/<collection>/<collection>_bm25.json` | term → IDF → posting list | 没有 SQL 表，是一个 JSON 倒排索引文件 |
| 入库状态 | `data/db/ingestion_history.db` | 文件 hash、路径、成功/失败、集合、错误、时间 | 有一张 `ingestion_history` 表 |
| 图片索引 | `data/db/image_index.db` + `data/images/...` | 图片文件和图片 ID 到路径的映射 | 有一张 `image_index` 表 |
| 可观测日志 | `logs/traces.jsonl`、`logs/eval_history.jsonl` | 每次入库、查询、评测的 JSON 记录 | 没有表，是追加写入的日志 |

两张 SQLite 表的结构如下：

| 表 | 主键 | 字段 | 为什么存在 |
| --- | --- | --- | --- |
| `ingestion_history` | `file_hash` | `file_path、status、collection、error_msg、processed_at、updated_at` | 相同 SHA256 且上次成功的文件跳过；失败文件仍可重试 |
| `image_index` | `image_id` | `file_path、collection、doc_hash、page_num、created_at` | 检索结果出现图片 ID 后，找到本地文件并返回给 MCP Client |

BM25 JSON 内部大致是：

    {
      "metadata": {
        "num_docs": 100,
        "avg_doc_length": 180,
        "collection": "textbook_math"
      },
      "index": {
        "倒数": {
          "idf": 2.1,
          "df": 5,
          "postings": [
            {"chunk_id": "xxx", "tf": 2, "doc_length": 160}
          ]
        }
      }
    }

这里有一个值得学习、但不能照搬的点：`DocumentManager` 会尝试在 Chroma、BM25、图片索引、文件入库历史四处一起删除一个文档，并把部分失败返回给调用者。这是“跨存储生命周期管理”的意识。

但它没有跨库事务：Chroma 删除成功、BM25 删除失败时，系统只能记录部分失败，不能自动保证一致。HP 必须把 MySQL 的 `documentVersion/publishStatus` 作为权威状态，使用可重试的异步同步任务更新 VikingDB、缓存和对象存储。

项目还有两个存储设计问题值得避开：

1. Chroma Adapter 为兼容早期 Metadata 限制，会把 List 转成逗号字符串；`tags` 一类多值字段失去标准数组语义，复杂过滤不可靠；
2. 本地 Chunk 初始 ID 和向量库 ID 由不同模块生成，关联排查会变复杂。

### 12.6 它有哪些 Reranker？我该参考哪个？

Reranker 的输入不是“先向量化再比较”，而是每次直接读取一对：

    (Query, Candidate Chunk) → 相关性分数

所以它比 Dense Retriever 更精细，但不能对数十万 Chunk 全量运行，通常只重排召回的 Top 20～50。

项目提供三种状态：

| 方案 | 当前项目实现 | 优点 | 缺点 | 对 HP 的建议 |
| --- | --- | --- | --- | --- |
| None | 默认关闭 | 零额外成本和延迟 | 候选顺序只靠 Hybrid | 作为所有实验的基线 |
| Cross-Encoder | `sentence_transformers.CrossEncoder` 对每个 `(query, passage)` 批量 `predict` | 语义匹配更细、结果稳定、无需提示词 JSON 解析 | 要下载/部署模型；耗 GPU/CPU；候选越多越慢 | 值得作为第一候选，但要选中文/多语模型并实测 |
| LLM Reranker | 将 Query 和所有候选放进 Prompt，让 LLM 输出 0～3 的 JSON 分数 | 能利用复杂任务语义，改 Prompt 快 | 最慢、最贵、受 token 限制、结果可能不稳定且 JSON 可能解析失败 | 不建议 HP 第一版在线使用；适合离线标注、疑难样本分析或低频高价值场景 |

项目默认配置的 Cross-Encoder 是 `cross-encoder/ms-marco-MiniLM-L-6-v2`。该模型卡标记为 English，因此不应直接拿来给中文教材/数学讲解做重排。[模型卡](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2)

对于 HP 的中文教材 PoC，更合理的起点是选择一个明确支持中文或多语的 Cross-Encoder，例如 `BAAI/bge-reranker-v2-m3`，再在自己的 Golden Set 上和“不重排”对比。该模型卡说明它直接为 `query + passage` 输出相关度，支持多语场景，也给出了本地部署方式；但“模型被推荐”不等于“它一定比其他模型更适合 HP”。[BAAI 模型卡](https://huggingface.co/BAAI/bge-reranker-v2-m3)

推荐的验证顺序：

    Hybrid 不重排
    → Hybrid + 中文/多语 Cross-Encoder（Top 30 → Top 5）
    → 观察 Recall@5、MRR、P95、成本和错误样例
    → 只有实测显示仍有价值，再试 LLM Rerank

项目里 Cross-Encoder 的 `timeout=10` 只是保存成了属性，实际 `model.predict()` 没有被真正超时中断；`sentence-transformers` 也不在运行时依赖清单中。这进一步说明它是“接口已经搭好”，不是可直接作为生产能力背书的实现。

### 12.7 它没有 FastAPI，Python 是怎么启动的？

对，当前代码没有 FastAPI、Uvicorn、Flask 或 Django，也没有 LangGraph。它不是 HTTP Web 服务，而是三种本地运行形态：

| 目的 | 实际入口 | 运行方式 | 说明 |
| --- | --- | --- | --- |
| 离线入库 | `scripts/ingest.py` | `python scripts/ingest.py --path <PDF或目录> --collection <名称>` | 同步 CLI，递归发现 PDF，逐份执行 Pipeline |
| 本地检索调试 | `scripts/query.py` | `python scripts/query.py --query "..." --collection <名称> --verbose` | CLI，可打印 Dense、BM25、RRF、重排中间结果 |
| 可视化管理 | `scripts/start_dashboard.py` | `python scripts/start_dashboard.py --port 8501` | 启动 Streamlit Web UI |
| MCP 调用 | `src/mcp_server/server.py` | `python -m src.mcp_server.server` | stdio：从标准输入读 JSON-RPC、向标准输出写结果，供 MCP Client 拉起 |

它之所以不需要 FastAPI，是因为：

- 入库和调试是命令行任务；
- Dashboard 自带 Streamlit Web Server；
- MCP 的 stdio transport 由 MCP Client 启动子进程并通过标准输入输出通信，不通过 HTTP 端口。

还有一个真实代码问题：`pyproject.toml` 中安装命令 `mcp-server` 指向根目录 `main.py`，而这个 `main.py` 仍是旧占位入口，只会加载配置并提示“Phase E”。真正可启动的 MCP 实现在 `src/mcp_server/server.py`。因此如果想亲自运行，应优先使用 `python -m src.mcp_server.server`，并把这个入口不一致当作该仓库需要修复的问题。

对 HP 的最终启发是：

    参考项目适合：
    本地学习、CLI 调试、Demo Dashboard、MCP 集成

    HP / RunHub 真正实现适合：
    FastAPI 提供内部 HTTP API
    + Worker 承担耗时入库/OCR/Embedding
    + RabbitMQ 负责耐久异步任务
    + Streamlit 不是生产管理后台的必要依赖
    + MCP 仅是建立在同一 Retriever 之上的可选 Adapter

FastAPI 不是“比这个项目高级”，而是当 HP 需要被 Java 后端、小程序、Agent Runtime 和异步 Worker 稳定调用时，HTTP API 与任务系统更匹配；该项目选择 CLI + stdio 是因为它的目标就是本地学习和 MCP 工具服务。

### 12.8 这部分应该怎样迁移到 HP：最终判断

| 模块 | 是否参考 | HP 的正确落点 |
| --- | --- | --- |
| 文件 hash 去重和阶段 Trace | 是 | 入库任务版本、幂等键、可重试状态 |
| MarkItDown/PDF Loader | 只参考接口分层 | 建多格式 Parser；扫描教材必须 OCR + 版面/公式 |
| 1000/200 递归字符切分 | 仅作 Baseline | 结构化章节分块作为正式策略 |
| LLM Chunk Refine | 谨慎 | 首期默认关闭；不得破坏教材结构 |
| jieba + 自研本地 BM25 JSON | 只作概念学习 | 复用 Elasticsearch 作为 BM25 分支；统一中文/数学 Analyzer |
| Chroma | 可用于个人小 Demo | HP 用 Elasticsearch + 独立 VikingDB 教学资料 Collection |
| RRF | 是 | 与原生 Hybrid 进行 A/B 评测后决定 |
| Cross-Encoder | 是 | 选中文/多语模型，TopN 小范围重排后实测 |
| LLM Reranker | 后置 | 只用于低频高价值场景或离线实验 |
| CLI + Streamlit + stdio MCP | 只作开发体验 | FastAPI + Worker + 内部 Tool；MCP 可选 |

这一版补充不改变 06 中已经收敛的产品边界：教材、教参和已授权辅导资料进入教学文档 RAG；题库继续使用独立检索与推荐；教学资料 RAG 只提供可解释的教材上下文。

## 13. 本轮补充：这份参考实现与 HP 的最终边界

### 13.1 教材入库不能照搬“PDF 转纯文本”

本项目适合学习最短入库链路，但 HP 资料还可能是 DOCX、扫描 PDF、数学公式、表格和几何图。正式入口应是多格式 SourceParser：

    文件分类与文字层质量检测
    → 原生 PDF/DOCX 解析，或扫描件 OCR 回退
    → 保留标题、段落、表格、公式、图片及页内锚点的 Block
    → 按章节和内容单元分块

已有文字层的 PDF 不应先 OCR；DOCX 不应先转 PDF 再 OCR。公式要保留原件，必要时补数学 OCR/LaTeX 检索副本；表格要保留行列关系；图形保留原图、坐标及视觉 caption，caption 只帮助召回，不能替代图。教师端展示教材版本、册别、章节，不展示会随文件载体变化的页码。

MinerU 是更值得补充研究的解析候选：公开能力覆盖 PDF、图片、DOCX 等转 Markdown/JSON，并包含扫描 OCR、公式、表格处理。[MinerU](https://github.com/opendatalab/mineru) 是否采用仍需在真实教材样本上验证质量、授权、成本和部署边界。

### 13.2 Chunk 不应是“整本书交给 LLM 切分”

本项目递归字符切分可作为 Baseline；正式教材以确定性结构为主：

    Block → 标题层级 → 定义/方法/例题/易错点/总结等内容单元
    → 子 Chunk 向量化 → 关联节/课时父 Chunk

子 Chunk 是召回粒度，父 Chunk 用于在命中后补充章节上下文。超长内容才在自然段或句子边界有限递归切分。LLM 只应局部辅助处理复杂版面、模糊边界、摘要/检索提示和 OCR 低置信度标记；它的输出要版本化，不能覆盖解析原文。

### 13.3 检索算法可迁移，系统形态不可照搬

两边的检索骨架都是：

    Query → Dense + BM25 → RRF → 可选 Reranker

区别在前后两端。该项目直接处理通用原始 Query；HP 要先由产品动作或 Agent Tool 查询真实题目/批改数据，再判断是否需要教学资料 RAG，构造 Question Retrieval Profile 或动态 Student Error Query，并按教材版本、册别、学段、学科作硬过滤。候选返回后仍要经过 Evidence Gate 和 Context Pack，才交给模型生成。

所以并不是它的技术栈“不适合 HP”：Dense、BM25、RRF、重排、Trace、Golden Set 都值得复用。不能照搬的是其单 PDF、固定字符 Chunk、本地 Chroma 与 JSON BM25、CLI 主入口、无领域 Query Builder/版本过滤/资料生命周期的实现。

Chroma 适合本地学习和单机 Demo；VikingDB 适合 HP 复用既有托管基础，并为教学资料新建独立 Collection；Milvus 适合明确需要云厂商无关、自主部署或更深检索控制时再引入。三者不是“谁更准确”的排名，效果主要由解析、分块、模型、过滤、融合、重排和评测决定。HP 首版的关键词/BM25 分支应复用 Elasticsearch，VikingDB 专注 dense 向量分支，再在服务层 RRF 融合；不要把 VikingDB 的 sparse vector 支持未经验证地直接等同于 BM25。Milvus 支持 dense/sparse 多向量与混合检索；Chroma 则以 Collection 存放 documents、embeddings、metadata 并提供查询/过滤。[Milvus](https://milvus.io/docs/multi-vector-search.md) [Chroma](https://docs.trychroma.com/docs/collections/manage-collections)

RAG-only 项目没有 LangGraph 完全合理：入库与检索是确定性 Pipeline。HP 的 RAG 执行面也不必上 LangGraph；只有上层对话 Agent 需要会话状态、多 Tool 循环、确认写操作、等待异步任务时，才值得评估。

### 13.4 下一批参考资料

继续看项目的优先级应是：

1. **MinerU**：补复杂教材解析；
2. **RAGFlow**：学习 layout 分块、索引、检索调试和知识库管理；其文档明确说明 layout-based chunk 和 embedding/full-text 索引配置。[RAGFlow](https://github.com/infiniflow/ragflow)；
3. **LangSmith/Ragas**：学习如何在 Golden Set 上评估检索和生成，而非只凭单次效果印象。[LangSmith](https://docs.langchain.com/langsmith/evaluate-rag-tutorial) [Ragas](https://docs.ragas.io/en/v0.2.2/concepts/metrics/available_metrics/)

对 HP 而言，先把“资料怎样可靠进入系统”学透，比再找一个同类聊天壳项目更有收益。
