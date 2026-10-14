# MODULAR-RAG-MCP-SERVER：检索、重排与评测源码研究

研究日期：2026-10-14。依据本地 `D:/project/rag-github/MODULAR-RAG-MCP-SERVER` 源码与配置；未调用模型云服务，未运行需要 API Key 或模型下载的链路。默认配置包含占位 endpoint/API key，因此“配置默认选用”不等于“已成功调用”。未找到根目录及本研究相关目录的 AGENTS.md。

## 1. 最重要的结论

1. 本项目的主要角色是为外部 MCP 客户端提供知识检索工具。内部实现 Dense + 自写 BM25 + RRF；可开启 Cross-Encoder 或 LLM 重排。默认配置关闭重排。
2. 没有我们此前讨论的“LLM 从整份作业归纳主题、生成多个 Query 并保留题号映射”的 Query Builder。这里的 QueryProcessor 是 jieba 分词、停用词过滤、过滤条件解析等规则处理。
3. 不含父子文档检索、兄弟单元补充或向上逐层扩展；`source_ref` 表示来源文档，并不代表实现了教学章节树。
4. 返回检索片段、引用及可能的原图；服务内部不生成最终自然语言回答，也不运行判断证据是否足够并再次检索的 Agent 循环。外部 Agent 可以再次调用 MCP 工具，但这由客户端实现。
5. 默认 MCP 查询：两路各最多 20 个 → 去重融合最多 10 个 → 默认关闭重排，只截取前 5 个。默认 `scripts/query.py` 则请求融合 10 个，不与 MCP 返回行为完全一致。
6. 未实现相关性阈值或证据充分性检查。非空结果不意味着内容能回答问题。
7. 评测框架有实现，但附带 Golden Set 的 5 条问题没有任何正确 Chunk/Source 标注，不能用来证明真实检索效果。评测默认关闭。

## 2. 从一次 MCP 查询追踪调用链

```text
外部 MCP 客户端/Agent
  → query_knowledge_hub(query, top_k=5, collection="default")
  → 初始化 Embedding、ChromaStore、BM25Indexer、QueryProcessor、HybridSearch
  → QueryProcessor：jieba 分词、去停用词、提取 key:value 过滤条件
  → 两路并行
      Dense：原始 query → Embedding → Chroma 向量查询（最多 20）
      Sparse：关键词 → 本地 JSON 倒排索引 BM25（最多 20）
              → 根据 Chunk ID 从 Chroma 取正文和元数据
  → RRF：按名次融合、同 Chunk ID 去重，最多 10
  → Rerank：默认禁用，保留原顺序前 5
  → ResponseBuilder：Markdown 片段 + 引用 JSON + MCP ImageContent
  → 外部客户端自行决定如何回答、是否再次调用
```

证据：[MCP 组件初始化](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/mcp_server/tools/query_knowledge_hub.py:164)、[异步调用检索/重排及响应构建](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/mcp_server/tools/query_knowledge_hub.py:273)、[MCP 注册的三个工具](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/mcp_server/protocol_handler.py:192)。

真正存在两路线程并行：`ThreadPoolExecutor(max_workers=2)` 先提交 Dense，再提交 Sparse，随后按字典顺序调用 `future.result(timeout=30)`。顺序收集不会让已提交任务变成串行。不过线程池退出会等待任务，不能把这个 30 秒理解成严格的全链路时间上限。证据：[线程池实现](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/hybrid_search.py:447)。

## 3. QueryProcessor 做什么

- `process()` 规范化空白、解析过滤语法、分词、移除停用词；返回 `ProcessedQuery(original_query, keywords, filters)`。
- 中文和混合中英文使用 `jieba.lcut()`。
- 关键词默认最短 1 字，最多 20 个；按出现顺序去重，并非 TF-IDF 排序或 LLM 挑选关键词。
- `collection:docs`、`type:pdf`、`source:xxx`、`tag:a,b` 等可转成元数据过滤。
- Dense 仍收到 `processed_query.original_query`，不是去掉过滤表达式的纯查询；Sparse 收到去掉过滤表达式后抽取的关键词。
- `ProcessedQuery.expanded_terms` 是预留字段，未接入同义词扩展或查询改写。

证据：[process](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/query_processor.py:117)、[分词](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/query_processor.py:210)、[关键词筛选](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/query_processor.py:239)、[默认上限](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/query_processor.py:90)、[两路输入](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/hybrid_search.py:451)、[预留字段](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/types.py:241)。

与 HP 方案的差别：HP 的 Query Builder 要处理用户意图、题目解析、多查询以及查询与题目的关联；本项目这一步只接受一条检索字符串。外部 Agent 可能已经生成这个字符串，但本地服务不会替它做作业级分析。

## 4. Dense、数据库与分数

`DenseRetriever` 使用入库时所用的 Embedding 客户端，把 query 转向量后调用 `vector_store.query()`。默认配置选 `openai / text-embedding-ada-002 / 1536`；provider 实际类为 `OpenAIEmbedding`，还实现 Azure 与 Ollama provider。配置提供的 Azure endpoint 会触发 OpenAIEmbedding 的 Azure 兼容地址构造，因此不能只看 provider=openai 就断言流量发往 OpenAI 公共 API。

证据：[默认 Embedding 配置](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/config/settings.yaml:21)、[Dense Embed → Query](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/dense_retriever.py:138)、[Embedding provider 注册](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/embedding/embedding_factory.py:112)、[Azure 兼容 endpoint](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/embedding/openai_embedding.py:81)。

实际内置向量数据库实现是 **Chroma**；配置注释虽然列出 qdrant/pinecone，但 Factory 内置注册只有 ChromaStore。使用 `chromadb.PersistentClient` 本地持久化，collection 配置 `hnsw:space=cosine`。Chroma 既保存向量，也保存 Chunk 正文和元数据，因此 BM25 命中后从 Chroma 回表，不是从 MySQL 取原文。

证据：[内置注册](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/vector_store/__init__.py:12)、[PersistentClient 与 cosine](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/vector_store/chroma_store.py:110)、[Sparse 回表](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/sparse_retriever.py:171)。

ChromaStore 读取 cosine distance，再计算 `score = max(0, 1 - distance/2)`。如果 distance=1-cosine，则这里的 score 等价于 `(1+cosine)/2`：正交向量为 0.5。因此屏幕上显示的 0.5 不应直接解释为原始余弦相似度 0.5，也不是相关概率。

证据：[分数转换](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/vector_store/chroma_store.py:260)。

## 5. BM25 的算法和存储

不是 Elasticsearch，也没有调用向量数据库的内置混合检索。项目自己实现 `BM25Indexer`：

1. 入库 `SparseEncoder` 用 jieba 分词，默认转换为小写，计算词频、文档长度等统计。
2. `BM25Indexer` 建立词 → Chunk ID/词频/长度的倒排项，保存本地 JSON。
3. query 关键词转换为小写，遍历匹配词的倒排列表，为每个命中 Chunk 累加 BM25 得分。
4. 排序取 Top N，再到 Chroma 取原文与元数据。

默认参数 `k1=1.5, b=0.75`，公式：

```text
IDF = ln((N - df + 0.5) / (df + 0.5))
score = Σ IDF * tf*(k1+1) / [tf + k1*(1-b+b*length/avg_length)]
```

这里的 IDF 没加外层 `1+`，当词出现在超过一半 Chunk 中时，可以为负。该实现也未过滤负分，只按总分排序。SparseRetriever 原样传递负数，RetrievalResult 只校验数字类型，没有执行非负或 `[0,1]` 限制。因此频繁词命中不会因为负数就全部被丢弃；不过候选排序会受负 IDF 影响。所以不能把它与所有 BM25 实现的分值直接互换。证据：[候选构建](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/sparse_retriever.py:275)、[分数校验](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/types.py:299)。

MCP 以 `data/db/bm25/{collection}` 创建 Indexer；Indexer 进一步使用 `{collection}_bm25.json` 文件。SparseRetriever 每次查询重新从磁盘加载索引，以读取其他进程新写入的数据。

证据：[SparseEncoder 分词与小写](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/embedding/sparse_encoder.py:134)、[默认参数](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/bm25_indexer.py:71)、[查询计分](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/bm25_indexer.py:256)、[IDF/长度归一化](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/bm25_indexer.py:436)、[JSON 文件路径](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/bm25_indexer.py:507)、[每次重载](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/sparse_retriever.py:222)。

## 6. RRF、N/K 和阈值

| 入口或参数 | 默认值 | 实际解释 |
| --- | --- | --- |
| retrieval.dense_top_k | 20 | Dense 路上限 |
| retrieval.sparse_top_k | 20 | BM25 路上限 |
| retrieval.fusion_top_k | 10 | 只有未显式传 top_k 时才作为融合上限 |
| retrieval.rrf_k | 60 | RRF 平滑常数；与返回片段个数 K 无关 |
| MCP top_k | 5 | 最终上限，工具允许最大 20 |
| MCP ToolConfig.enable_rerank | true | 使初次融合请求 top_k*2，即默认 10 |
| settings.rerank.enabled/provider | false / none | 实际默认不运行任何重排模型 |
| settings.rerank.top_k | 5 | Core 单独调用且未传 top_k 才采用；MCP 显式传最终 top_k |
| scripts/query.py --top-k | 10 | 查询脚本直接请求融合 10，未实现 MCP 的 *2 行为 |

证据：[配置](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/config/settings.yaml:60)、[MCP ToolConfig](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/mcp_server/tools/query_knowledge_hub.py:82)、[*2 与禁用截取](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/mcp_server/tools/query_knowledge_hub.py:337)、[脚本默认值](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/scripts/query.py:80)、[脚本检索调用](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/scripts/query.py:183)。

RRF 用 `Σ 1/(60+rank)`，按 `chunk_id` 聚合两路，保留第一次出现的正文及 metadata；最后按 RRF 分数降序，分数相同时按 chunk_id 排序。支持加权 `fuse_with_weights()`，但默认 HybridSearch 使用等权 `fuse()`。

例：A 在 Dense 第1、BM25 第5，分数 `1/61+1/65≈0.03178`；B 只在 Dense 第1，分数 `1/61≈0.01639`。两路原始分数无需比较。

只有一路有结果时，HybridSearch 直接返回该路 Top K，不计算 RRF，因此 response 的 `score` 可能是 Chroma 转换分数、BM25 分数、RRF 分数或重排分数。不能对返回的统一 score 设置一个固定相关性门槛。

证据：[RRF 算法](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/fusion.py:133)、[同分排序](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/fusion.py:167)、[单路直返/等权调用](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/hybrid_search.py:615)。

链路没有 Dense 最低分、BM25 最低分、Reranker 最低分、证据覆盖度或主题一致性门槛：只是 Top K。两路之一失败时降级使用另一路；这处理可用性，不能替代相关性校验。

过滤条件：Dense 传到存储；Sparse 只传 collection 选择索引，其余条件在融合并截断后统一过滤。可能过滤后不足 K，且本来相关的低位候选在融合截断时已丢失。作为 HP 权限过滤参考时需要设计所有召回路径上的严格过滤及必要的候选补取。

证据：[Dense filters](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/dense_retriever.py:150)、[Sparse 只传 collection](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/hybrid_search.py:557)、[融合后过滤](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/hybrid_search.py:292)。

## 7. 重排：实现存在，默认关闭

| Backend | 实现 | 模型选择与执行方式 |
| --- | --- | --- |
| none | NoneReranker | 返回原顺序；默认配置选此项 |
| cross_encoder | CrossEncoderReranker | 从 `rerank.model` 读取名称；`sentence_transformers.CrossEncoder(model_name)` 本地加载，`model.predict([(query, chunk_text), ...])` 批量打分 |
| llm | LLMReranker | `LLMFactory.create(settings)`，复用全局 llm 模型；把所有候选与 query 放一个 Prompt，请模型输出 passage_id、score、reasoning，解析 JSON 并排序 |

CrossEncoder 配置写有 `cross-encoder/ms-marco-MiniLM-L-6-v2`，但默认不加载、不运行；这不是项目已验证适用于中文教材的证据。需要注意，配置名与 [Hugging Face 官方模型卡的 `cross-encoder/ms-marco-MiniLM-L6-v2`](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2) 不同，多了 `L` 与 `6` 之间的连字符。原样启用可能加载失败并静默降级；先校正配置或提供有效本地模型路径。启用时模型首次加载可能下载权重，研究没有触发。实际 pair scorer 代码使用候选完整 text，最终由 CoreReranker 截取 Top K。

LLM 配置默认 `openai/gpt-4o`，具体 provider 类支持 OpenAI、Azure、DeepSeek、Ollama。`LLMReranker` 默认 Prompt 定义 0–3 分，并说明语义、回答性、完整性等；实现只校验 score 是数字，未把 0 分结果筛掉，也没有完整校验必须返回所有候选。不要把重排自动理解成“过滤了不相关内容”。

初始化或执行失败会降级原排名。代码有 timeout 配置字段，但 CrossEncoder `self.timeout` 与 CoreReranker timeout 未用于中断 `predict()`，不能把注释里的超时承诺当作严格实现。

证据：[Factory 注册两种实现](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/reranker/reranker_factory.py:78)、[模型加载](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/reranker/cross_encoder_reranker.py:94)、[predict](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/reranker/cross_encoder_reranker.py:221)、[LLM prompt/调用](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/reranker/llm_reranker.py:86)、[提示词](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/config/prompts/rerank.txt:5)、[LLM provider 注册](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/llm/__init__.py:23)、[Core fallback](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/reranker.py:328)。

## 8. 返回给 Agent 的实际内容

ResponseBuilder 默认 Markdown 最多展示 5 个结果，各正文片段最多 300 字符；引用里的 `text_snippet` 默认最多 200 字符。JSON 引用没有完整 Chunk 正文。因此 top_k=20 不会让外部 Agent 在 Markdown 中得到 20 个完整 Chunk。内部 trace 记录完整 text 不等于 MCP 已把完整 text 交给客户端。

`MultimodalAssembler` 根据 metadata 的 `images` 或正文 `[IMAGE: id]` 取关联原图，返回 MCP ImageContent；这是“文字命中后带回原图”的链路。`get_document_summary` 优先用 metadata.summary，否则用首 Chunk 提取并截断预览；不是在线 LLM 阅读完整文档的摘要工具。

这里有真实持久化与读取间的接口缺口：ChromaStore `_sanitize_metadata()` 将 list/tuple 转为逗号连接字符串，dict 转为 Python `str(dict)`，并不是 JSON 序列化。查询/按 ID 回表后，ChromaStore、DenseRetriever、SparseRetriever 都没有把这些字符串还原成 list/dict；而 MultimodalAssembler 仅在 `images` 为 list、`image_captions` 为 dict 时处理结构化信息。原图 metadata 中的路径、页码、caption 因而不能按原设计完整往返。正文保留 `[IMAGE: id]` 时仍可回退解析图片 ID，再用约定路径查图，但此回退是否成功取决于正文占位符及文件位置是否保留。不能把直接传入 Python metadata 的 mock/unit test 视为真实 Chroma 往返验证。

证据：[metadata 字符串化](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/vector_store/chroma_store.py:379)、[Dense 原样保留 metadata](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/dense_retriever.py:217)、[Sparse 原样保留 metadata](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/query_engine/sparse_retriever.py:272)、[真实 list/dict 检查](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/response/multimodal_assembler.py:181)、[占位符及路径回退](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/response/multimodal_assembler.py:202)。

证据：[响应默认上限](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/response/response_builder.py:118)、[截取正文](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/response/response_builder.py:278)、[JSON 引用与 metadata](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/response/response_builder.py:71)、[引用上限](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/response/citation_generator.py:67)、[图片关联读取](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/response/multimodal_assembler.py:161)、[summary 提取](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/mcp_server/tools/get_document_summary.py:422)。

## 9. 评测实现与证据边界

实现支持 CustomEvaluator（Hit Rate、MRR）、RagasEvaluator（faithfulness、answer_relevancy、context_precision）、CompositeEvaluator；配置注释提到 deepeval，但没有内置 deepeval evaluator 注册。

默认 `evaluation.enabled=false`，EvaluatorFactory 返回 NoneEvaluator。若只改 enabled=true 并保留默认 custom/metrics（hit_rate、mrr、faithfulness），CustomEvaluator 因不支持 faithfulness 抛错；需要把 custom 指标列表限定为 hit_rate、mrr，或选适用后端。

Golden Set 只有 5 个示范问题：每个 expected_chunk_ids=[]、expected_sources=[]，仅有 reference_answer。已直接解析 JSON 核实。CustomEvaluator 缺少真实标注时直接返回 0；这既不能证明检索失败，也不能证明成功。

EvalRunner 将非空 expected_chunk_ids 转成 `{ids: ...}` 后传 evaluator；expected_sources 和 reference_answer 虽然加载到了 dataclass，本路径没有传给 evaluator。Ragas 选用的是 ContextPrecisionWithoutReference，不使用 reference_answer 判准确性。

CLI `scripts/evaluate.py` 没有给 EvalRunner 传 reranker 或 answer_generator，甚至配置启用重排时也不会在 CLI 评测中调用。未传生成器/答案时，所谓 generated_answer 仅拼接前 5 个 Chunk 文本；这不能评价最终 Agent 生成质量。

Dashboard 评测会根据配置创建 reranker，也允许用户输入实际答案；但答案框默认用 Golden Set 的 reference_answer 填充。如果不替换为实际系统答案，测到的是参考答案在检索上下文下的表现。应使用真实用户查询、真实标注和实际端到端答案。

证据：[Evaluator Factory](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/evaluator/evaluator_factory.py:101)、[Custom 支持范围](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/evaluator/custom_evaluator.py:21)、[空标注返回 0](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/evaluator/custom_evaluator.py:142)、[Golden Set](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/tests/fixtures/golden_test_set.json:4)、[EvalRunner 真值构建](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/observability/evaluation/eval_runner.py:288)、[默认答案拼接](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/observability/evaluation/eval_runner.py:346)、[CLI Runner 初始化](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/scripts/evaluate.py:141)、[Ragas 指标选择](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/observability/evaluation/ragas_evaluator.py:163)、[Dashboard 答案默认值](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/observability/dashboard/pages/evaluation_panel.py:111)、[Dashboard 传 reranker/答案](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/observability/dashboard/pages/evaluation_panel.py:236)。

## 10. 对 HP 方案可学习和需要补齐的部分

可直接学习模块边界：Embedding provider、Dense/Sparse Retriever、RRF Fusion、CoreReranker fallback、Trace、MCP 响应装配。学习时推荐按上面的调用链读真实源码，不把 README/配置注释里的 provider 清单视为全部已实现。

教材项目需要另行实现：作业 Query Builder 与题号关联、教材章/节/教学单元树、父子或兄弟上下文扩展、每路严格权限/版本过滤、相关性阈值与证据充分性判断、可用的完整证据返回、有最大次数的二次查询，以及真实教材标注与最终回答评测。

项目的模块化检索框架可参考；该本地快照不足以证明中文教材的公式、几何图、例题讲解已经达到可用效果。
