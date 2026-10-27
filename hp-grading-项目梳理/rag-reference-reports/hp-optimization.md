# HP 教学资源 RAG：参考与优化建议

> 架构口径更新（2026-10-23）：以 [Agent 架构确认基线](../agent-architecture-handoff.md) 为准。前端只访问 Java；Java 保存业务问答；Python 使用 LangChain `create_agent`（底层 LangGraph）及 PostgreSQL checkpointer。同步滚动摘要保存在 checkpoint，不另建摘要表。本文描述确认方案，不据此新增上线或个人成果声明。


> 审阅日期：2026-10-14。依据用户提供的本地源码与 06 方案。静态分析，未运行参考项目或模型；建议不代表 HP 已上线能力。

你的教育场景设计已覆盖查询改写、结构教材分块、Evidence Gate 和真实评测。优先补工程协议，不需要因为参考项目不同而整体换栈。

当前架构按 §21–23 收敛为 MySQL 主数据 / Java 业务会话 / MongoDB Trace / PostgreSQL checkpoint / ES BM25 / VikingDB Dense / RabbitMQ Worker；应清理 §17.5 与 §18.3 的少量历史示例；首期资料为授权 PPT / Word 教案 / 教辅，不要求取得教材 PDF。

HTML：[阅读入口](index.html) · [MODULAR-RAG](modular-rag.html) · [PaiSmart](paismart.html) · [HP 优化](hp-optimization.html)

## P0：统一架构口径，消除互相冲突的章节

**方案现状：** 最新 §8、§9、§21–23 已统一 ES BM25 + VikingDB Dense，首期资料改为授权 PPTX / DOCX / 教辅。仍可收口的是 §17.5 将 VikingDB 写为 BM25 / Hybrid、§18.3 保留 teaching_resource_chunk_hybrid / sparse_vector，以及 §17 的历史 SQL checkpoint 讨论。

**借鉴来源：** MODULAR 的显式 provider 契约；PaiSmart 把检索实现集中在 HybridSearchService。参考它们的单一实现入口，不跟随其基础设施换选型。

**具体补法：** 以 §21–23 的最新拆分为本报告基线：MySQL 主数据、Java 业务会话 / MongoDB Trace / PostgreSQL checkpoint、ES 关键词、VikingDB 独立教学资料 Dense collection。sparse 保留为备选；PostgreSQL checkpoint 已于 2026-10-23 确认，集中维护当前决策表。资料来源身份与教材适配分别保存，首期不以教材 PDF 为前提。

**验收方式：** 文档中每个流程图与当前决策表一致；Retriever 明确 keyword_backend / vector_backend；两边各有独立连通、过滤和回源验收。

**取舍与边界：** 这是文档收敛建议，本轮未修改 06 原方案。VikingDB 内置 Hybrid 若以后实测更合适，再单独决策迁移。

## P0：将原生 Office 解析与内容质检做成独立门禁

**方案现状：** §23–24 已检查 18 份 PPTX / 6 份 DOCX，明确 OMML 保真、跨页例题、表格角色、纯图片首页与已知顶点错误。当前是样本检查与设计，未完成生产 Parser 和召回实验。

**借鉴来源：** 两参考均提供 parser / transform 组件分层；PaiSmart 有并发解析闸门和任务状态。它们没有现成的 PPT 跨页教学单元和 Word 教学表格角色解析，不能直接替代 HP Parser。

**具体补法：** 建立 OOXML 原生解析契约：OMML 树→原结构 / 可校验 LaTeX，shape 与关系文件→图资产，Word row / cell→教学角色；每个 Block 与 TeachingUnit 保存 parse_integrity、content_review_status。分别设 PARSE_INCOMPLETE 与 CONTENT_QUARANTINED，依赖缺失、原文错误、源文件未附听力等不混为一类。审核修正版另建版本并记录 reviewer / supersedes。

**验收方式：** 用方案中专题 1 第 6–8 张、三视图“如图”例题、多列二次函数教案、错误顶点和缺听力样例做固定回归：条件 / 图 / 答案能一起取回；错误与缺素材单元不进入可用索引或 Pack，回放能分清源文问题与解析问题。

**取舍与边界：** 这是补充可执行状态与回归样例，保留方案已有原生解析 / 按需 OCR 思路。首期不全量 LLM 纠错，不要求取得教材 PDF。

## P0：把多存储 READY 发布做成一个明确协议

**方案现状：** §18.3 已设计完整新版本后原子切换，但 ES 与 VikingDB 是两个系统，分别写成功不等于原子可见。

**借鉴来源：** PaiSmart KnowledgeIndexManager 的新物理索引 + alias；MODULAR 多存储顺序写入暴露的部分成功风险。

**具体补法：** 新增 index_generation / publish_manifest：记录 version_id、pipeline_version、ES generation、Viking generation、预期 Chunk 数及对账结果。后台先完整构建和抽检，MySQL 事务切 active generation；每次查询读取一次 manifest 快照，两路与 canonical 回源都使用这组版本约束。旧版本在读请求排空后异步回收。

**验收方式：** 故障注入覆盖 ES 成功 / Viking 失败、发布前宕机、发布后查询未结束等情况；未完成版本不进入 Evidence Pack。对账不只数 Chunk，还核对 ID / hash 与权限 / 版本元数据。

**取舍与边界：** 不声称跨库 ACID；用逻辑发布与补偿修复实现一致可见。下架另设强制 deny 标记，使旧 manifest 和缓存立即失效。

## P0：给入库任务补 Outbox、租约与处理版本幂等

**方案现状：** 已有 kb_ingestion_job、RabbitMQ + Worker、hash 去重与幂等方向，任务登记、消息投递、认领和卡死恢复协议仍需细化。

**借鉴来源：** PaiSmart FileProcessingOutboxService / VectorizationLeaseService / RecoveryJob；MODULAR should_skip 仅按文件 hash 的不足。

**具体补法：** 任务与 outbox 同事务写入；派发按退避重试；worker 用 claim_token / lease_until 认领与心跳。幂等键采用 document_version_id + pipeline_version + stage，Chunk 写入使用稳定业务 ID。记录 parser / chunker / embedding / retrieval_text 版本；模型变化重新向量化，解析变化重新生成对应中间产物。消息传对象 key，不保存短期预签名 URL。

**验收方式：** 重复消息、发送后未标记、worker 中途终止、租约过期、旧 worker 回写均有测试；旧 claim_token 不能写完成 / 发布状态，索引写入也限制在该 generation 内。非重试错误进入死信，运维可按阶段恢复。

**取舍与边界：** Kafka 无需引入。RabbitMQ 做至少一次投递即可；本地文件去重与消息幂等是不同问题。优先在新版本空间写入，避免照搬先删旧数据。

## P0：用一个总 deadline 约束整个教学请求

**方案现状：** §22 已要求区分超时和依赖故障，但 Query Builder、多意图召回、重排、上下文扩展与生成的预算分配没有统一协议。

**借鉴来源：** PaiSmart RequestDeadline 与保留最终回答时间；HybridSearchService 共用召回等待期限。

**具体补法：** RetrievalRequest 传 deadline / remaining_budget；阶段 timeout 取配置与剩余预算的较小值。为最终生成保留时间；Rerank 预算不足可跳过并标记 DEGRADED。先并行发 ES BM25 与查询 Embedding，Embedding 成功再发 Viking Dense，避免 BM25 被模型网络等待拖住。底层 HTTP 也配置超时与并发隔离。

**验收方式：** 故障注入下测总时延与未取消请求数；依赖超时后仍能识别成功分支；不把单路失败当作完全无资料。生成、重排、每路召回均记录耗时和状态。

**取舍与边界：** future.cancel 或外层 timeout 不保证远端请求停止，需要连接 / 读取超时与容量上限。具体预算由目标 P95 和真实语料决定。

## P0：把 Evidence Gate 从一个阈值拆成可解释判定

**方案现状：** §9 已有 evidenceLevel、integrityStatus、错误隔离、缺少教材原始证据和降级；尚未给出不同排序模式的分数口径与 Gate 判定协议。

**借鉴来源：** PaiSmart 的 rawScore / mode / thresholdDroppedInTopK；它按双路 / 单路调整 RRF 阈值，但不能照搬数值。

**具体补法：** 分别保存 dense_score、bm25_score、rrf_score、rerank_score、score_type。先做候选级 Gate，再对扩展后的完整 Pack 检查，避免 §9.1 先 Gate 后扩展时未验证新补条件；输出 PASS / PARTIAL / REJECT 与 reason_codes。完整、正确、来源可支持该结论、版本适配与相关性分别判定；阈值按模式和模型用正负样例校准。

**验收方式：** 给出“接受证据中的正确率”和“应接受证据被拒绝的比例”；双路、单路、跳过重排分别统计。RRF 分数归一化不可被命名为 confidence_probability。无依据讲解不得声称来自教材。

**取舍与边界：** 相关性与证据充分性不同。第一版先规则做结构 / 版本 / 授权校验，疑难事实支持关系用人工或离线 Judge，避免全量再加一次在线 LLM。

## P0：所有回源、缓存与降级路径都继承授权约束

**方案现状：** 最新 §7.3、§10、§24.2 已明确 AllowedResourceSet、两路预过滤、回源 / 扩展 / 缓存复核和撤销失效。下一步是将这些要求变成可重放的授权快照与否定测试，而不是再次增加权限原则。

**借鉴来源：** PaiSmart 同时在 BM25 / kNN 内预过滤；ParentContextExpander 的文件级回源假设与无权限 search 兼容入口是应避免的边界。

**具体补法：** 可信 AuthContext 在服务端生成，不允许 Agent 修改 school_id、角色和许可范围。AllowedResourceSet 固化 license / permission_version、用途、角色与期限；两路、回源与资产读取校验同一快照并检查最新撤销状态。缓存 key 在已有字段上加 index_generation / retrieval_text_version；Trace、草案导出与 Model Gateway 留下权限决策摘要。

**验收方式：** 跨学校、跨角色、跨教材、已下架版本、缓存命中和父块扩展都有否定用例，返回正文 / 资产也必须授权；任何超时降级不放宽 scope。内部 FILTERED 状态不对外泄露无权限资料的标题或存在性。

**取舍与边界：** 从“不返回越权结果”推进为“每条证据可验证 scope”。不能把 PaiSmart 的 public / orgTag 逻辑直接当作 HP 资料授权。

## P1：统一检索文本版本，让三条路径看到同一份表示

**方案现状：** §24.2 已提出 sourceContent / retrievalText / structuralMetadata / assetRefs；需要从数据字段落成唯一生成组件。

**借鉴来源：** PaiSmart ContextualChunkText.compose，把原文和 chunkContext 分离，Embedding / BM25 / Rerank 复用表示约定。

**具体补法：** 新增 RetrievalTextBuilder：规则拼版本、章节、内容类型、公式文字化和原文；保存 retrieval_text_hash / version。Embedding 与 ES 都索引它，Rerank 使用同版本文本；sourceContent 独立只读。LLM 补充说明保存为独立字段，记录 prompt_version 与来源 Block IDs，不能覆盖原文。

**验收方式：** 对相同 Chunk 检查三路表示版本一致；对 LLM 关闭 / 开启做消融。重建可按表示版本定位受影响 Chunk，能够回放原始证据。

**取舍与边界：** 你已经采用了比参考项目更适合教材的四层模型；补法是工程契约，不是再增加一种分块算法。

## P1：给关系扩展加原子单元、去重和 token 装包规则

**方案现状：** §24.2 已明确完整例题、父子扩展、角色 / 授权复核与 token 预算；§24.3–24.4 给出 PPT 跨页和 Word 表格实例。下一步细化预算计算、合并键与扩展过程的质量状态。

**借鉴来源：** PaiSmart parentKey 去重、单命中与总字符上限；保留命中子 Chunk 的证据定位。

**具体补法：** 先按 version_id + parentUnitId / assetId 合并；以 token 预算代替纯字符预算。装包优先级为必要条件与题干 → 图 / 公式 → 解法 → 方法补充 → 邻接说明。不可拆的例题超预算时，明确减少命中或请求针对性解释，不能静默裁掉条件；命中子 Chunk 与阅读扩展分别记录。

**验收方式：** 例题完整率、图表关联完整率、重复 token 比例与截断原因可统计；同一父单元多次命中只装一次，不跨版本拼接，不跨权限扩展。

**取舍与边界：** HP 不应把关系扩展降级为前后各一块；字符预算可作为兜底，主要预算应按实际模型 tokenizer 计算。

## P1：多 Query 要按意图归组，控制重复票数和班级覆盖

**方案现状：** 最新 §9.2–9.4 已规定受控改写、Question Retrieval Profile、学生错因与关联题号；还需规定作业多 Query 融合如何避免同义改写反复抬高同一 Chunk。

**借鉴来源：** MODULAR 的 rank-based RRF 适合单 Query 双路；PaiSmart 的候选窗口 / 重排上限可以作为预算机制。两项目并未直接解决 HP 的批量题目覆盖。

**具体补法：** QueryIntent 带 intent_id、question_ids、query_origin、必要业务上下文 hash。先对语义重复需求归组，组内融合 BM25 / Dense，组间按显式权重或配额分配；每道关键错题保留覆盖需求。Rerank 回看关联原题和标准解析，不使用不可靠知识点标签。规定 Query 数、候选总数、并行度与最大重排批量。

**验收方式：** 增加逐题 evidence_coverage 与 duplicated_intent_ratio；同义改写数量增加不能无界提高证据分数。检索画像缓存随标准解析 / 题目版本失效，学生错误查询保持当前学生范围。

**取舍与边界：** 分组融合是本报告提出的 HP 领域建议，不是参考项目已有能力。先验证双路基线，再用消融决定是否加权。

## P1：用阶段标签诊断失败，用隔离测试集决定上线

**方案现状：** §11、§21.2、§24.6 已有 Golden Set、公式保真、表格角色、跨页完整率、已知错误拦截等指标；缺的是可复现的 case schema、配置快照和结果诊断协议。

**借鉴来源：** PaiSmart EvalCase / RagEvalCaseRunner 的阶段结果、人审抽样；MODULAR Golden Set 空标注是反例。

**具体补法：** case 保存 source_version、可接受资料小节 / TeachingUnit、必需 Block / asset、角色、用途、should_retrieve、expected_degradation 与人工答案要点。按课件 / 教案文档家族划分调参与留出集，防止同一例题改写泄漏。运行绑定各组件版本与 index_generation。加入缺图、错顶点、缺听力素材、教师活动不能给学生等真实负例。

**验收方式：** 分别统计未召回、精排丢失、Gate 拒绝、扩展丢条件、生成误用；报告只出现可复现运行的指标。先用代码评测 ID / scope / completeness，再对教学表达做校准过的人审 / Judge。

**取舍与边界：** 30～50 条是首个验证集的起步规模，不足以证明全学段稳定。先复核真实失败再扩展指标，避免把指标目录全部搬进项目。

## P1：隐藏引用仍要保留陈述到证据的可追溯关系

**方案现状：** 最新 §2.6 已规定自然呈现、按许可保留署名、定位到实际资料且教材页码为 secondaryReference；应进一步区分命中证据与最终回答使用证据。

**借鉴来源：** PaiSmart 的 reference mapping 持久化与事后 CitationVerification；HP 不需要复制其引用角标 UI。

**具体补法：** Evidence Pack 内给稳定 evidence_id；草案保存 claim_span → evidence_ids 与 support_status。检查 ID、版本、来源允许支持的结论，再抽样检查事实支持。引用按 license 署名规则渲染，定位返回 slide / shape 或 Word table / row / cell。无教材原始证据返回 NO_PRIMARY_TEXTBOOK_EVIDENCE，不能由配套资料推导教材原文。

**验收方式：** 能从讲评中的具体结论追到 sourceContent / Unit / 文档版本；核查失败不得标为已通过。保存草案版本与 Trace 关系，历史引用不指向重建后的另一份正文。

**取舍与边界：** 不能用异步“疑似”标签代替输出前的 Gate；全量在线 LLM 核查成本与延迟需先评估，首版可抽样。

## P2：将冲突处理落实为权威等级与版本关系

**方案现状：** §2、§9.5、§24.5 已区分来源权威与正确性，并发现具体顶点答案错误要求隔离。下一步定义内容错误、解析错误、版本差异和合法多解的不同治理路径。

**借鉴来源：** PaiSmart conflict 模块包含候选发现、键值比较、可选 LLM 确认。该机制更偏企业事实冲突，不直接等同数学教学冲突。

**具体补法：** 明确 supersedes、effective_from、source_authority 与 evidenceLevel；不同解法不自动判冲突。源文答案错误走 quarantine / 人工修正版；OMML 结构解析错误走 parser 修复后重建；适配差异走版本配置。检索高分和出版社来源均不能覆盖数学正确性或缺失条件。

**验收方式：** 构造“等价解法 / 适用条件不同 / 真正矛盾 / 旧版已替代”样例；只有需要拦截的冲突进入隔离，对合法多解保留教学选择。

**取舍与边界：** 这是扩展方向，优先级低于解析、检索和发布闭环。首期少量教材可先人工治理，暂不建全库 LLM 两两比对。

## 建议实施顺序

1. 统一当前技术决策表与组件 schema。
2. 小语料跑通 canonical、双路检索、Outbox / lease 与 manifest 发布。
3. 固定分层 Golden Set 与留出集，分别验证结构分块、查询改写、Rerank 和扩展。
4. 先接一个确定性讲评 Workflow，再将稳定 Retriever 包装为 Agent Tool。

指标分别覆盖授权 / 版本、例题完整性、检索排序、无证据降级、教学一致性和运行成本。每个指标关联具体上线决策。参考 [Langfuse 指标选择指南](https://langfuse.com/academy/evaluate/choosing-what-to-evaluate)。

RunHub 可以验证通用检索与工程机制；赛事文章不能证明数学教材解析、公式关系和教学表达质量。PPT / Word 教辅的原生结构、公式、跨页与资料错误样例仍需单独评测。

所有建议的源码位置与摘录见 HTML 源码抽屉与 evidence-index.json。原始 06 方案未修改。
