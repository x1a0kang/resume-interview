# 06｜HP 教学资源 RAG：产品与技术方案

> 架构口径更新（2026-10-23）：以 [Agent 架构确认基线](agent-architecture-handoff.md) 为准。前端只访问 Java；Java 保存业务问答；Python 使用 LangChain `create_agent`（底层 LangGraph）及 PostgreSQL checkpointer。同步滚动摘要保存在 checkpoint，不另建摘要表。本文描述确认方案，不据此新增上线或个人成果声明。

> 文档类型：产品方案 + 技术方案。  
> 状态：已上线项目的方案整理，后续优化继续讨论。
> 最后更新：2026-10-20。
> 事实更新（2026-10-20 本人确认）：公司 Agent 与 RAG 均已上线，并向 100 多所学校开放；RAG 切分、Embedding、混合召回与重排由本人实际开发，模型选型和设计与算法工程师共同讨论。本文后续优化与独立本地 PoC 仍须单独标识，不以全篇方案推定线上实现。原“未上线”总括表述失效。
> 当前资料路线：出版社配套教辅、教学 PPT、Word 教案和作业设计；不以取得教材 PDF 为前提。学科网合作采购允许提供生成结果，由用户确认；本次未读取采购合同或逐份核验资源授权。

本轮调整把产品依据从“教材正文知识库”改为“与学校教材体系对齐的授权教学资源库”。教材版本仍用于适用性路由，但资料的来源身份、内容权威性和使用权限分别记录。下载资料的实查结论见 [RAG资料评估.md](../rag/RAG资料评估.md)。

**实施状态补充（2026-10-16）：** 独立本地 PoC `E:/project/rag-chroma-poc/` 当前为 0.5.3，已统一用 MarkItDown 0.1.8 读取单文件并输出 Markdown；每张表调用 Qwen3.7 Flash 做二分类，最多 4 个线程并发处理，按原表顺序收集结果后切片；表格预算 1024 token，并记录逐表模型调用耗时。普通正文仍用 LangChain 递归切分。尚未接入 Embedding、Chroma 检索与回答评测。本文 MySQL/ES/VikingDB、治理与发布链路仍是 HP 目标架构，不是该 PoC 的启动要求。父子 Chunk、相邻片段扩展和标题路径增强均为后续候选，当前状态与面试口径统一见第 24 节。

## 1. 产品定义

HP 的文档 RAG 检索**授权教辅中的方法讲解、课件中的重难点与易错说明、教案中的教学活动和讲解顺序**，为班级讲评、学生讲解和教师备课提供资料支持。它不管理题目主数据，也不承诺复现教材原文。

```text
HP Domain Tools
  → 当前作业题、学生作答、标准答案、批改结果、得分与班级统计
Question Bank / Recommendation
  → 原题匹配、相似题、完整练习及推荐排序
Teaching Document RAG
  → 授权 PPT / DOCX / 教辅中的教学解释与教学设计
LLM / Agent
  → 组合业务事实、资料证据和可推荐题，生成可编辑的教学成果
```

资料按授权集合使用：学科网合作内容属于合作私域，可在合同覆盖的产品、学校及用户范围内提供生成结果；学校或教师上传的资料保留所属租户权限；只有明确允许平台范围使用的内容才进入平台授权集合。私域表示访问边界，不表示平台取得内容所有权，也不自动表示所有学校均可访问。

学校、教师和学生的题目、作答等私有业务数据不进入跨校共享库。老师布置的题目即使落库，也不自动进入公共推荐题库。

## 2. 资料来源、用途与教材的区别

### 2.1 当前主资料是教学资源，教材正文作为后续可选来源

| 资料 | 能补充什么 | 证据边界 |
| --- | --- | --- |
| 出版社配套教辅或 PPT | 方法、重难点、例题讲解、专题归纳 | 确认出版社及具体资源来源后，标为出版社配套资源；不自动等于教材原文 |
| 学科网合作采购教案 | 教学目标、学情假设、活动、提问、讲解顺序 | 用户已确认可提供生成结果；适用人群与资源范围按合作约定落地 |
| 学科网合作采购课件 | 知识说明、方法归纳、易错误区、图文例题 | 同时校验公式、跨页关系与题解质量 |
| 分层作业设计 | 分层策略、评价建议、练习、答案与解析 | 教学设计与具体题目分流，不把整份作业作为纯解释文档 |
| 教材或官方教师用书 | 教材原文、编排顺序、官方教学说明 | 当前未取得可用于该产品的正文授权，不纳入首期 |

获取渠道和内容类型是不同维度：从出版社官网下载的 PPT 仍是 `COURSEWARE`，从学科网采购的 Word 教案仍是 `LESSON_PLAN`。文件标题带“人教版”只说明宣称适配该教材体系，不证明由人教社编写或授权，更不证明符合某一修订版的完整内容。

### 2.2 能替代教材的哪些功能，不能替代哪些功能

| 维度 | 教材正文 | 当前教辅、PPT、教案 |
| --- | --- | --- |
| 概念、规则 | 有对应版本的正式表达及条件 | 常有概括，需校验条件和正确性 |
| 讲评与纠错 | 有基础例题，针对错因的总结未必充分 | 方法归纳和易错点更直接适配讲评 |
| 教师备课 | 正文展示学习顺序，教学活动未必展开 | 教案有目标、时间安排、师生活动和设计意图 |
| 覆盖范围 | 对应整册内容及连续章节 | 可能是单课时或跨册专题，缺失内容应明确 |
| 来源定位 | 授权正文可支持教材章节及原文定位 | 只能定位到本资料；引用的教材页码属于待核验二手信息 |
| 质量与权威性 | 可核验的对应教材版本具有正式表述意义 | 出版社配套资源与个人教案应分级，不能以下载渠道替代审核 |
| 解析结构 | 页、目录、图文布局 | PPT 跨页展开，Word 多列表格、公式、教学角色更常见 |
| 使用权 | 取决于实际授权 | 同样取决于实际授权，文件格式不改变权限 |

因此首期适合“基于资料解释方法、总结易错点、组织教学活动”，不适合“逐字返回课本定义、保证课本页码、声明教材采用某种解法”。没有教材证据时，说明“所用教案/课件采用此思路”，不能说“教材就是这样讲的”。

### 2.3 解释性内容与题目内容分别处理

```text
同一份 PPT / DOCX
  ├─ 方法、概念、易错点、教学活动 → Document RAG
  ├─ 例题题干 + 图 + 解法 + 方法反思 → 完整的文档例题单元
  └─ 可独立练习题 + 答案解析 → 题库导入候选，另行审题与授权
```

把例题保留在文档中是为了理解讲解。将其用于练习分发或正式推荐是另一项用途，必须检查题目完整性和相应许可。合作私域题目不会因为抽取成功就变成公共题目；需要入库时仍继承合作/学校范围。已有题库中的题目只维护一份主数据，文档通过关联 ID 引用。

### 2.4 当前题目的答案和评分规则

```text
当前题目
  → 题库精确匹配
      ├─ 命中同一道原题 → 读取该题已有答案/评分细则作为强参考
      └─ 未命中 → LLM 根据当前题目生成答案、解析和评分规则
  → 一致性与可解性校验 → 教师修改确认 → 按 version 保存
```

相似题只能辅助理解题型，不能把其采分点直接当作当前题评分标准。教辅 RAG 可补充概念和方法，但其题解属于资料证据，不等于官方评分依据。中高考题、答案、评分细则仍由结构化 Question Retriever 获取，并检查来源和展示许可。

### 2.5 例题来源

| 用途 | 来源 |
| --- | --- |
| 说明命中的资料方法 | 与课件/教案正文关联的完整例题单元 |
| 推荐正式练习 | 权限校验后的题库与推荐接口 |
| 临时说明简单概念 | 模型生成示例，校验后明确为生成示例 |

模型生成示例和从私域文件抽出的题目均不自动进入公共题库。

### 2.6 资料位置与内部证据

一般结果仍默认自然呈现，引用展示服从授权及署名要求；若某来源要求署名，需在输出保留，不能被“默认不展示引用”的产品偏好覆盖。定位入口改为“相关资料在哪里讲过”。

```text
documentId / documentVersion / sourceType / sourceOrigin / licenseId
alignedEditionId / curriculumRevision / schoolSystem / volume / academicYear
sectionPath / sectionTitle / chunkId / contentHash
sourceLocator / retrievalScore / 实际送入模型的片段
```

PPT 保留 `slideIndex + shapeId`，Word 保留标题路径、段落 ID 或 `tableId/rowId/cellId`；图、公式和说明有独立关联 ID。原文件索引只在该 `documentVersion` 内稳定，不当作跨版本身份。PDF 页序及页内坐标可以作为内部定位信息，教师端不承诺教材页码。教案提到“教材第 69 页”时，记为 `secondaryReference`，不可冒充系统核验过的教材原文。

### 2.7 教材版本仍用于适用性路由

沿用“地域默认 + 学校覆盖”：`schoolId + regionCode + subject + grade + semester + academicYear` 解析学校教材配置。学校明确配置优先，其次区县/城市、省级默认，无法确定时请教师选择，不让模型猜测。

`editionId` 表示学校教材体系，文档使用 `alignedEditionId` 表示审核过的适配体系，另存 `curriculumRevision`、五四/六三学制、册次与学年。教材体系相同不表示同一修订版；“2026—2027 学年”不表示版权年份或修订年份。

召回前同时应用授权过滤和适用性过滤。未确认版本的跨册专题资料不能猜填“人教版九上”；如确实通用于多个版本，登记审核后的 `editionCompatibility` 并由服务端按任务纳入。精准版本任务不放宽，普通概念解释可使用明确审核的通用资料，并在输出标明适配程度。不能因没搜到内容而扩大租户或合作许可范围。

## 3. 哪些场景真正需要 RAG

### 3.1 判断标准

生成需要外部教学解释或教学设计时调用 RAG；需要分数、作答和班级事实时调用 Domain Tools；找题时调用 Question Retriever。用户不需要知道 RAG 或资料库的存在。固定入口按 Workflow 调用，自由对话由 Agent 按教学意图调用。用户指定某份资料时只收窄可用集合。

### 3.2 P0：班级智能讲评

```text
教师点击“生成智能讲评”
  → Domain Tools 查询当前题、得分、错误分布及典型作答
  → RAG 检索授权资料的方法、易错点及教学顺序
  → Recommendation 获取允许该班级使用的完整例题/练习
  → LLM 生成可编辑草案
```

教案中的“学生容易混淆”是该资料的教学判断，实际班级错误率和典型作答必须来自 HP。教案中的课后反思也不作为当前班级的真实观察。

### 3.3 P0：学生当前错题的教学讲解

只看答案和分数使用现有批改结果；点击“智能讲解”、问“为什么错”“换一种讲法”“总结方法”时，系统尝试检索可向学生使用的解释性单元，与本人错误结合生成分步说明。教师教案中的课堂管理、学情假设、教学反思等单元默认只用于教师任务。

“用课本的方法讲”先按学校教材体系检索适配资料，回答准确标明证据来自教案/课件；“课本原文怎么定义”“课本有没有这个例题”必须有授权教材证据才可正面定位，否则说明当前只有配套教学资料。需要新练习时调用推荐题接口。

### 3.4 P1：教师备课与专题复习

支持“结合这次作业准备 20 分钟复习课”“总结二次函数的易错点”“参考已采购教案调整讲解顺序”。RAG 提供方法、活动和教学设计；新增练习由题库获取。当前样本中的英语教案可支持活动设计，但未附完整听力音频或脚本，不可补造教材听力答案。

### 3.5 P1：资料定位问答

返回资料名、真实类型、适配体系、资料小节和幻灯片/Word 原文件锚点，按许可展示必要内容。指定教材定位而无正文证据时返回 `NO_PRIMARY_TEXTBOOK_EVIDENCE`，可以展示配套资料位置，但不能把二手课本引用包装成核验结果。

### 3.6 与推荐题组合

推荐服务返回完整题目，RAG 返回教学说明，LLM 解释方法联系与练习目的。推荐排序本身不由文档 RAG 完成。

## 4. 哪些能力不属于文档 RAG

- 查询作业、作答、分数、批改状态和班级统计；
- 为当前题目生成并定版答案、解析、评分规则；
- 原题精确匹配、相似题召回、推荐排序；
- 统计历年题型、题量与分值；
- 修改答案、分数或触发重批；
- 将私有或合作资料题目自动推荐给其他学校。

这些分别由 Domain Tool、求解 Workflow、Question Retriever、SQL 分析和既有 Java 页面完成。第一阶段不开放正式业务写 Tool；需要基于资料解释结果时才追加 Document RAG。

## 5. 产品入口设计

| 入口 | 用户获得什么 | 后端组合 |
| --- | --- | --- |
| 班级结果页“生成智能讲评” | 根据真实错误分布生成讲评草案 | Domain + RAG + Recommendation |
| 单题详情页“智能讲解” | 当前错误、方法及易错提醒 | Domain + 学生可用资料 RAG |
| “相关资料在哪里讲过” | 定位教案/课件的实际位置 | RAG + 资料权限 |
| 教师教学助手 | 备课、复习、修改讲评 | Agent 按需组合 Tools |
| 内容运营后台 | 来源登记、授权关联、质检、更新和下架 | 确定性入库 Workflow |

班级入口携带 `schoolId/classId/assignmentId`；学生入口携带 `studentId/reviewTaskId/questionId/blankId`。第一次生成使用固定 Workflow，后续“缩短到 10 分钟”“换一组练习”等动态修改再进入对话 Agent。

来源归属与引用详情可以收起，但不得伪称教材原文。聊天工具白名单由角色和页面上下文确定；模型只提出检索意图，服务端控制资料范围。

## 6. 在线调用与路由

```text
actionCode + 页面上下文 → 固定 Workflow
自由文本 + AuthContext + 页面上下文 → 当前角色 Agent
  ├─ 业务事实 → Domain Tools
  ├─ 教学解释 / 备课 → Document Retriever
  └─ 练习与题目 → Question Retriever / Recommendation
```

检索 Observation 区分命中、证据不足、上下文不完整、授权拒绝、依赖故障、超时和缺少教材原始证据，不能把系统错误都表述为“没有资料”。`internalEvidenceTrace` 保存实际证据及出处；用户定位请求只展示其被允许访问的信息。

## 7. 数据域与授权边界

### 7.1 内容类型、来源渠道、范围分别建模

```text
sourceType: COURSEWARE / LESSON_PLAN / ASSIGNMENT_DESIGN / SUPPLEMENT
            TEXTBOOK / TEACHER_GUIDE（后续明确授权时启用）
sourceOrigin: PUBLISHER_SITE / XKW_PARTNER / SCHOOL_UPLOAD / INTERNAL_ORIGINAL
knowledgeScope: PARTNER_PRIVATE / SCHOOL_PRIVATE / PLATFORM_LICENSED
```

`sourceType` 不能决定谁有权访问；`sourceOrigin` 不能代替作者与权利人；`knowledgeScope` 不能代替具体合同。每份资料和版本关联 `licenseId`，记录允许的产品、租户/学校、角色、用途、期限，以及署名、摘录、导出和原文件访问规则。Chunk 继承权限，必要时进一步收窄 audience。

### 7.2 已知授权事实与缺失信息

用户已确认**学科网合作采购明确允许提供生成结果**。本方案以此继续设计合作私域 RAG，不要求再次确认该事项。本次没有读取合同，具体资源清单、服务对象和加工部署条件由运营按已有合作约定登记；不把“生成结果许可”推导为原文件转发、教材复制、模型训练或无范围限制的跨校使用。

出版社官网下载资料未提供具体下载页及条款，本次只确认内容可用于技术评估，尚不将其标记为产品范围已授权。教材正文当前无适用授权，首期排除。授权不足的资源可登记和检查，是否允许后续模型加工须按真实权利依据决定。

“教材禁止商用”应准确写为“当前未取得教材正文用于本产品的授权”，不写成一律无法授权或不存在合法电子教材。教辅、PPT、Word 也受作品权利约束。著作权法第二十四条的教学例外有范围限制，第二十六、二十九条要求按许可使用；不能仅凭产品面向教育就认定可向所有客户提供作品。依据：[现行著作权法](https://www.ncac.gov.cn/xxfb/flfg/flfg_532/202103/t20210309_50530.html)。

学科网公开普通用户协议限制个人商业使用及私自向第三方提供资源；搜索可见版本标注更新于 2021-11-23，直接访问此次返回 403，因此不能据此判定当前合作采购合同条款。合作资料按用户确认的专项许可及实际合同管理。依据：[学科网用户注册协议](https://tsso.xkw.com/user/agreement)。

### 7.3 授权随全链路执行

```text
AuthContext → AllowedResourceSet（产品、租户、角色、用途、有效期）
  → ES 与向量分支均先过滤 → 候选权威库复核 → Rerank
  → 父子/邻接扩展再次校验 → Model Gateway → 输出用途校验
```

不能先全库 TopK 再过滤：可能泄漏内容，也可能挤掉有权访问的候选。缓存键包含授权集合/权限版本、租户、角色、用途、资料版本和查询哈希；命中缓存及继续会话也要复核权限。草案、文件产物、检索日志和 checkpoint 中的资料片段同样受访问与保留规则控制。

### 7.4 题库与业务数据

题目只有在来源、授权、完整性和答案质检通过后，才允许 `recommendable=true`，并保留授权范围。老师当前作业题默认 `retrievalScope=CURRENT_TASK_ONLY`，不向跨校推荐开放。

## 8. 离线入库与成本控制

```text
PPTX / DOCX / 已授权教辅
  → 来源、资源 ID、下载页、作者、授权集合登记 + 文件 hash
  → 原生 OOXML 解析（图片区域按需 OCR/视觉识别）
  → 保留公式、表格、图片、形状/单元格与阅读关系
  → 资料结构、内容角色和适配版本审核
  → 数学/题解质检；缺图、缺答案、错误单元隔离
  → 教学单元分块；具体练习题另走题库候选流程
  → MySQL canonical chunk + ES 文本索引 + 独立 VikingDB dense 索引
  → 数量、权限、版本、完整性校验 → 完整版本原子切换 READY
```

已有文字层不先 OCR，数学 OMML 保留结构并转换为可校验公式表达，不能简单串联文字。当前本地 PoC 使用 MarkItDown 将指定的 PPTX、DOCX 等文件统一转成 Markdown，再识别表格块并切片；按主题合并跨页例题、恢复教学关系及父子检索属于后续优化，不能作为当前已实现能力，具体见 23、24 节。

首期选择九年级数学“二次函数/圆”的少量资料，优先解析与审核质量，再扩量。文件/内容哈希去重限定在授权域内，不因内容相同合并不同私域的访问权限。只索引当前可用版本，资料更新按版本差异重算，视频音频和大规模图片向量暂不建设。

主数据对象为 `kb_document`、`kb_document_version`、`kb_chunk`、`kb_ingestion_job`、`kb_license` 与 `kb_license_resource`。`rag_query_trace` 记录查询、实际过滤、最终证据与成本，敏感原文按许可和保留期保存。

## 9. 检索、Query Builder 与 Evidence Pack

### 9.1 统一链路

```text
用户任务 + 可选当前题/标准解析/本人作答/批改事实
  → Query Builder 输出受控检索语句
  → 服务端授权域 + 学科/学制/年级/适配版本/资料有效状态过滤
  → ES BM25 + 独立 VikingDB dense 召回
  → RRF 去重融合 → 可选 Reranker → Evidence Gate
  → 完整教学单元扩展 → Context Pack → LLM
```

关键词与向量分支采用后文 22 节已收敛的 ES + VikingDB 方案。VikingDB sparse 能力可作为后续对照，不在首版未经验证替代 ES。切换语料不需要更换向量数据库。

### 9.2 为什么数学题需要构造教学查询

原题的数字和公式经常缺少教学语义。优先使用题目已有标准解析，加上真实批改错因，再构造针对方法的查询，避免只按数字相似检索。

```text
题目：求 y = 2x² - 8x + 5 的对称轴和顶点
标准解析：配方为 2(x - 2)² - 3
学生错误：提取系数后配方时没有同步处理常数项
检索意图：二次函数一般式转顶点式的配方法；提取二次项系数后的易错步骤
可能证据：二次函数教案中的配方活动；专题 1/2 的方法与易错误区
```

这只是当前资料上的设计示例，尚未运行召回实验，不代表已取得命中率。不是所有错因都一定有资料覆盖；错误参考答案单元须在入库质检中排除。

### 9.3 Query Builder 按需输入

独立问答只需要问题和必要会话背景；单题解释按需附题干和标准解析；学生纠错再附本人作答和批改事实；教师作业备课可附多题但无需先完成批改。Agent 决定调用哪些业务工具，后台组装 `QueryBuildRequest`。不要为每种任务再加一个前置分类模型。

```json
{
  "userRequest": "结合这次作业准备二次函数讲评",
  "questionContexts": [
    {"questionId": "q1", "stem": "...", "standardExplanation": "...", "reviewFacts": "..."}
  ],
  "conversationSummary": "只讲配方和顶点，时长 10 分钟"
}
```

LLM 可输出 `searchQueries` 及其关联的输入题号；不得虚构题号、章节和学生错误，也不得决定租户、许可或版本过滤。`sourceScope` 由后台按任务和角色指定。简单概念问答可以原样查询，无需强制改写为多条。

### 9.4 先建立无额外模型的基线

先用“问题 + 标准解析关键段”检索。对公式多、语义弱或输入过长的情况再试 LLM Query Rewriting。题目级共用查询可以按答案解析版本缓存为 `Question Retrieval Profile`，学生错因查询按本人批改结果动态生成，两者不混用。

Prompt 的核心约束是“只生成检索意图，不给最终教学结论；只使用已有上下文，不输出权限过滤字段”。使用 JSON Schema 校验数量、长度、关联题号；超时或非法输出回退到原始问题与已有解析，并单独记录构造失败。

### 9.5 内部证据契约

```json
{
  "businessFacts": ["HP 工具返回的班级事实"],
  "documentEvidence": [{
    "documentId": "...",
    "documentVersion": 1,
    "chunkId": "...",
    "sourceType": "COURSEWARE",
    "sourceOrigin": "XKW_PARTNER",
    "licenseId": "...",
    "alignedEditionId": "...",
    "sectionTitle": "方法归纳",
    "sourceLocator": {"slideIndices": [6, 7, 8]},
    "content": "通过质检的有限文本",
    "evidenceLevel": "SUPPLEMENTARY",
    "integrityStatus": "COMPLETE"
  }],
  "recommendedQuestionIds": ["按题库权限返回的 ID"]
}
```

`evidenceLevel` 描述来源可支持的结论，不能用渠道或检索高分替代正确性校验。出版社配套资源、个人教案和教材原文身份分别核验。遇到冲突先检查条件与来源，隔离错误或无法核验的单元，不让模型自行声称某个权威来源裁决。

### 9.6 证据不足与降级

- 未覆盖主题：基于当前题与已有解析提供一般讲解，标明未找到资料支持；
- 版本不符：拒绝伪称适配，要求选择版本或使用服务端审核过的通用集合；
- 缺图、缺条件、缺答案：拒绝用不完整例题作为结论依据，改取完整方法单元；
- 教材定位：无授权正文则说明仅有配套资料，二手页码不当成已核验定位；
- 授权过滤：保持资料范围，不允许 Agent 换学校或改角色规避；
- 系统故障：与正常无证据分别记录及呈现。

### 9.7 第一版不用不可靠的题目知识点标签

检索词来自问题、标准解析、真实错因和资料固有标题；不依赖当前低准确度知识点预测结果，也不用其 ID 做章节硬过滤或 RAG 触发条件。

### 9.8 在真实资料上验证查询构造

对照“原题干”“题干 + 标准解析”“受约束 Query Rewriting”三组，人工标注可接受的教学单元。测主题命中、Recall@K、MRR、错误版本召回、无证据降级、成本和教师可用性，不把语言更流畅当作召回提升。

### 9.9 题目级检索画像与学生动态查询

题目定版后可根据题干和标准解析生成共用的 `Question Retrieval Profile`，包含方法说明、必要前提与基础检索语句。缓存身份绑定 `questionId + answerExplanationVersion + queryBuilderVersion`；资料检索结果另绑定授权集合与索引版本。老师调整解析后重新生成画像，不沿用旧解法的查询。

学生请求解释错因时，动态查询只增加其本人真实错误，例如“配方时提取二次项系数后常数项处理错误”。不能把某位学生的作答或错误放入所有用户共享的题目级画像。画像是查询辅助，不是最终教学证据；生成仍以实际召回且通过质检的资料为依据。

### 9.10 统一 Query Builder 输入、输出与校验

统一接口不要求所有请求都有作业或学生批改结果。业务对象按任务附加，权限和版本条件由服务端单独构造，不能接受模型覆盖。

```text
QueryBuildRequest
  userRequest（必需）
  conversationSummary（可选，带当前用户/会话权限）
  questionContexts[]（可选）
    questionId / stem / standardExplanation / explanationVersion
    studentAnswer / reviewFacts（仅学生纠错等必要场景）
  taskContext（可选：时长、关注方法等）

RetrievalPolicy（服务端可信值，与模型输出分离）
  authContext / allowedResourceSet / role / purpose / permissionVersion
  subject / schoolSystem / grade / alignedEdition / revision / activeVersions

QueryBuildResult
  searchQueries[]
    query / relatedQuestionIds[]
  missingContext[]
```

独立问答“点在圆内如何判断”可以输出一条原始问题，`relatedQuestionIds=[]`；作业讲评可按每题方法输出几条关联查询，不能凭空增加题号。缺必要图片、题干或解析时记录 `missingContext` 并按产品流程补取或询问，不凭空完成图形理解。模型超时、JSON 非法属于构造失败；授权拒绝、依赖故障和正常无证据属于其他阶段，分别观测。

Prompt 示例：

```text
你负责为授权教学资源库构造检索语句，不负责给出最终教学答案。
根据用户请求及实际提供的上下文生成少量简洁查询。
优先保留标准解析中的方法、条件和用户明确关注的内容。
学生错因只可来自已提供的本人作答和批改事实。
独立问答不要求附题号；只引用输入存在的 questionId。
不要猜教材章节、课本页码、听力材料或图片条件。
不要输出学校、角色、许可、授权范围或教材版本过滤字段。
仅输出符合 QueryBuildResult JSON Schema 的对象。
```

应用层校验查询数量、长度、重复与关联题号，异常时回退原始问句和已有解析；记录 Prompt/模型/构造版本用于对照评测。Query Builder、Retriever 与 Context Builder 分别保留 trace，使效果差时可以定位是查询、召回、完整性还是生成的问题。

## 10. 安全与质量治理

- 授权范围、期限与资料状态在召回前执行，并在上下文组装及生成输出复核；
- 外部资料属于不可信数据，文档内指令不能调用工具或修改策略；
- 发现内容错误保留原文件，隔离错误单元；人工修正版另建审核版本，不让 LLM 覆盖原文；
- 教案学情和教学反思标为来源观点，不冒充当前班级数据；
- 资料下架、授权到期后立即停止检索，同时使相关缓存失效，并治理草案、产物和 trace 中的副本；
- 日志、观测系统、Embedding/LLM 服务的原文处理方式与保留期服从实际合作约定，不能因“只返回生成结果”而省略加工范围管理；
- 不把资料题解当作当前题官方评分规则，不自动修改正式批改数据；
- 原文件下载、较长摘录、题目分发、产物导出分别校验，不以生成许可替代。

## 11. 评测与成功指标

| 环节 | 指标 |
| --- | --- |
| 解析 | 原生公式保真、表格角色保留、图文关联、跨页例题完整率 |
| 内容 | 已知错误拦截、来源/适配字段审核、教学设计与题目分流准确率 |
| 检索 | Recall@K、MRR/NDCG、错误版本/学制召回、跨租户与跨角色泄漏 |
| 证据 | 完整单元取回率、原始资料定位准确率、无教材证据正确降级 |
| 生成 | 证据支持度、数学正确性、虚构教材原文/页码率、教师评分 |
| 产品 | 草案采纳率、编辑时长、学生讲解任务完成率 |
| 性能 | P95、token/cost、缓存命中及授权失效正确性 |

所有线上效果均待实现验证。先以当前样本构造人工评审的评测集，Expected Output 不能仅由模型生成后直接当真值。按任务、主题、文档类型、图文依赖、权限和失败情况分层，比较固定长度基线与教学单元策略。可将测试与版本、Trace 关联，便于检查单条退化；参考 [Langfuse 数据集指南](https://langfuse.com/academy/datasets)。本轮不创建在线数据集。

## 12. MVP 范围

1. 使用九年级数学二次函数/圆的少量授权 PPT 和教案，先做合作私域教学库；教材正文不作为启动条件。
2. 先跑通 PPTX/DOCX 原生解析、公式/图文关系、跨页分块和错误隔离。
3. 服务端落实授权集合与角色过滤，使用 MySQL + ES BM25 + 独立 VikingDB dense + RRF，保存内部证据。
4. 主链路为教师班级讲评和备课；通过质检且允许学生用途的知识单元再开放学生讲解。
5. 分层作业只先导入设计策略；具体练习经独立题库流程和相应用途许可后再开放。
6. 保留来源身份与必要署名，资料定位展示实际教案/PPT 位置；无教材正文时不承诺课本原文定位。

本轮样本评估证明资料具有候选内容价值和可解析结构，尚未证明在线召回、教学正确率或商业使用覆盖每一份文件。实际样本分级与待处理问题见配套评估文档。

## 13. RAG 触发机制与实现架构

### 13.1 谁决定是否调用 RAG

RAG 的触发遵循已经确定的双入口规则，不再增加独立意图路由：

| 请求类型 | 决策方式 | 示例 |
| --- | --- | --- |
| 产品任务按钮 | 按钮携带 `actionCode`，直接执行预定义 Workflow | 点击“智能讲解”后固定查询题目、答案解析和批改详情，再检索教学资料 |
| 任意自由文本 | 直接进入当前角色 Agent，由模型按问题提出 Tool Call | “帮我根据最近情况准备复习课” |
| Tool 执行 | Policy Guard 校验角色、资源、参数和预算 | 学生只能读取本人已批改题目，家长只能读取绑定孩子 |

模型只能看到当前角色和页面上下文允许使用的工具定义。它可以请求 Domain、RAG、推荐或产物 Tool，但不能直接连接数据库、ES 或 VikingDB，也不能自行修改 `schoolId`、`studentId` 和教材版本等权限字段。

一次开放对话的执行流程：

```text
1. 接收 userMessage + pageContext + threadId
2. AuthContext 校验身份和业务数据域
3. ContextBuilder 补全班级、作业、学科、年级和学期
4. TextbookEditionResolver 解析学校教材体系，ResourcePolicyResolver 解析本轮授权集合
5. ToolPolicy 根据角色和页面上下文生成本轮允许的 Tool Set
6. 模型返回文本或结构化 Tool Call
7. Tool Executor 校验参数、权限、超时、幂等和预算
8. 执行 Domain Tool / Document Retriever / Question Retriever
9. 将标准化 Observation 放回模型上下文
10. 循环直至得到最终回答，或达到轮数/成本限制
11. 保存会话、工具轨迹、模型用量和内部 Evidence Pack
```

按钮 Workflow 在 Agent Graph 之外执行；自由文本进入 Agent 后，即使只是查分或要练习题，也不再经过另一个分类模型。Agent 直接选择 Domain Tool 或 Question Tool，拿到 observation 后回答。

### 13.2 文本 RAG 与题目 RAG 的命名

产品讨论时可以统称为两类检索增强：

```text
文本 RAG
  → 授权 PPT、教案、教辅中的解释性内容
  → Document Retriever

题目检索增强（可简称题目 RAG）
  → 真题、第三方练习和公开推荐题
  → Question Retriever / Recommendation
```

但工程实现不能把两者做成相同的数据结构：

- 文本 RAG 返回 `document chunks`；
- 题目检索返回结构化 `question objects`；
- 两者最终合并为统一 `ContextPack` 交给模型；
- 题目继续以 MongoDB 为详情主存，复用 ES 和 VikingDB，不在文档知识库重复存储。

### 13.3 推荐的服务边界

不建议把 Agent Runtime 继续堆进当前 `hp-grading-service`。新增独立服务：

```text
小程序 / Web
  → hp-ai-assistant-service
       ├─ Agent API / SSE
       ├─ AuthContext Adapter
       ├─ Context Builder
       ├─ Tool Policy
       ├─ Agent Tool Loop
       ├─ Tool Registry / Policy Guard
       ├─ Textbook Edition Resolver
       ├─ Document Retrieval Orchestrator
       ├─ Model Gateway
       └─ Trace / Metrics / Evaluation Hooks
            │
            ├─ HP Domain Tools → hp-grading-service
            ├─ Analysis Tools → chatbi-service
            ├─ Question Tools → 现有题库/推荐服务
            └─ Document RAG → Metadata DB + Vector Retriever + Object Storage
```

原 `hp-grading-service` 继续负责批改、作业、题目和正式业务写操作，`chatbi-service` 继续负责作业、学生、班级、教师、学校和区域的确定性分析。Python Assistant 服务通过内部 HTTP/RPC Facade 调用两类 Java 领域能力。修改答案、分数、批改结果和重批不封装成第一版 Agent Tool，Agent 只用文字引导现有页面；保存讲评草案和生成文件作为 Agent 新产物由 Assistant 服务管理。

### 13.4 新服务同时承载 Agent 与 RAG

`hp-ai-assistant-service` 不是只为 RAG 建立的检索服务，而是完整 AI 应用层：

```text
在线部分
  → Agent Runtime、多轮状态、Tool Calling、Policy Guard
  → 文档 RAG 与题目工具编排
  → 流式响应、Trace 和评测埋点

离线部分
  → 资料解析、分块、Embedding 和索引构建
  → 版本切换、失败重试和删除同步
```

第一阶段放在同一个 Python 仓库，拆成 `api` 与 `worker` 两个进程/部署单元。在线请求不执行耗时 OCR 和批量向量化，离线 worker 不承载用户对话。

### 13.5 技术路线比较与当前结论

RAG 文档库通常不是一个数据库，而是多类存储协作：

```text
原文件：S3 / MinIO / TOS
资料、版本和业务状态：关系数据库
模型输入输出、对话、工具轨迹和运行快照：文档数据库
全文/稀疏检索：BM25
语义检索：Vector Database
```

| 方案 | 优点 | 局限 | 适合场景 |
| --- | --- | --- | --- |
| PostgreSQL + pgvector | 组件少、事务和过滤方便 | 中文全文和复杂 Hybrid 需要额外配置 | 低成本 MVP、中小语料 |
| Elasticsearch/OpenSearch | BM25、中文搜索、过滤和聚合成熟，也支持向量 | 集群运维较重 | 搜索能力很重、已有搜索团队 |
| Milvus | 向量原生，支持 dense、BM25 sparse、Hybrid、RRF 和过滤 | 需要独立服务，不能替代业务数据库 | 可复现的专业向量检索实现 |
| VikingDB | HP 已接入，支持 dense/sparse、BM25、Hybrid 和过滤，托管运维 | 依赖火山引擎账号、权限和费用 | HP 真实生产方案 |
| Qdrant | API 清晰，dense/sparse、过滤和 RRF 体验好 | 传统全文检索不以替代专业搜索引擎为目标 | 中小型向量检索、快速落地 |

HP 真实落地目标已经收敛为：

```text
Python 3.12
FastAPI + Pydantic v2
LangGraph
LangChain Core/Integrations（模型、Tool 和 Retriever 适配）

MySQL：资料元数据、版本、canonical chunk、入库任务、教材映射、session 和草案
MongoDB：可选 tool/RAG trace 和现有模型调用日志
PostgreSQL：Python Agent checkpoint（含滚动摘要）
Java：业务会话与用户问题、最终回答
Elasticsearch：新教学文档 BM25 索引
VikingDB：新建教学文档 collection，执行 dense 召回；Retriever 融合两路
Redis：缓存、限流和短期幂等
RabbitMQ + Worker：解析、OCR、Embedding、索引和删除任务
S3/MinIO/TOS：原文件和解析中间产物
OpenTelemetry + Langfuse：Trace、token、latency、cost 和评测关联
pytest + 自定义 Evaluation Harness（按需接入 Ragas）
```

RunHub 的真实实现一期优先复用现有 Supabase PostgreSQL：使用 pgvector 做语义召回，使用 PostgreSQL 关键词/全文检索做文本召回，再用 RRF 融合。两边通过统一的 `DocumentRetriever`、数据结构、Trace 和评测协议保持一致。RunHub 不应只为展示技术栈引入 Milvus，HP 也没有必要替换已经具备所需能力的 MySQL、MongoDB 和 VikingDB。

选择 Python 不是因为 Java 无法实现，而是 Agent/RAG 的文档解析、Embedding、Reranker、评测和编排生态以 Python 为第一支持语言。LangGraph 第一版负责 Agent/Workflow 分支、对话状态、Tool Loop、流式输出和失败恢复；HP Java 服务继续负责业务一致性、最终资源鉴权和现有正式写操作。

第一版不同时引入 LangGraph、LlamaIndex 和 Haystack。只选择 LangGraph 作为编排框架，检索与分块逻辑保持独立模块。

### 13.6 HP 数据库与基础设施分工

| 组件 | 职责 |
| --- | --- |
| MySQL | 资料身份/版本、canonical chunk、入库任务、教材映射、`ai_session`、讲评/学习计划草案和文件产物元数据 |
| MongoDB | 可选 `ai_tool_execution`、`rag_query_trace` 和模型调用日志；业务问答由 Java 管理，checkpoint 使用 PostgreSQL |
| Elasticsearch | 独立教学文档索引，执行 BM25 与相同的授权/适配过滤；不混用题目索引 |
| VikingDB | 现有题目 collection 继续查重/语义召回；新教学文档 collection 做 dense 召回；与独立 ES 文本索引融合 |
| Redis | 检索缓存、限流和幂等键；不作为永久主存 |
| RabbitMQ | Worker broker；解析、OCR、Embedding、索引和删除任务 |
| S3/MinIO/TOS | 原文件和解析中间产物 |
| Langfuse/OpenTelemetry | 模型、检索、工具、token、latency 和 cost 观测 |
| HP 原有 Mongo/ES/VikingDB 题库能力 | 继续承载完整题目、结构化检索和相似召回，由 Question Tools 调用 |

关系数据库对象：

```text
ai_session / teaching_plan_draft / learning_plan_draft / ai_artifact
kb_document / kb_document_version / kb_chunk
kb_license / kb_license_resource
kb_ingestion_job / kb_ingestion_job_stage
region_textbook_mapping / school_textbook_override
```

MongoDB collection：

```text
ai_turn / ai_tool_execution / rag_query_trace
# checkpoint 独立由 PostgreSQL saver 管理，不放在 MongoDB collection 中
现有 llm_request_record
```

VikingDB 教学文档 collection 字段：

```text
chunk_id / content
dense_vector（首版）；sparse_vector（后续对照，不与 ES BM25 重复设为必需）
source_type / source_origin / knowledge_scope / license_id / audience
subject / stage / school_system / grade / academic_year
aligned_edition_id / curriculum_revision / volume / chapter_path / section_title
permission_version / source_locator
document_version / content_hash / status
```

保留当前资料版本的 slide/paragraph/table 内部锚点，不承诺教材页码。MySQL 中的 canonical chunk 是权威正文，VikingDB 是可重建的检索索引。MongoDB 中的 Agent trace 只描述 AI 执行过程，不能替代已有 HP Java 业务功能自身的权限、事务和审计。

### 13.7 文档入库 Pipeline

```text
内容运营登记来源、授权集合和适配关系
  → 上传原文件到对象存储
  → MySQL 创建 document version 和 ingestion job
  → Celery/RabbitMQ 触发解析
  → PPTX/DOCX 原生解析；PDF/扫描件作为后续按需适配
  → 公式/图文/跨页关系质检，错误或缺失单元隔离
  → 识别章节层级并按语义单元分块
  → MySQL 保存 canonical chunk
  → 生成 dense embedding
  → ES 写入正文/BM25 索引；VikingDB 写入 dense 向量和相同权限过滤字段
  → 校验数量、授权/角色过滤、版本和索引状态
  → 原子切换文档版本为 READY
```

任一步失败都记录阶段，支持从失败阶段幂等重试。新版本完全就绪后再切换，避免检索到不完整的资料版本。

### 13.8 BM25 与在线 Hybrid Retrieval

#### 13.8.1 BM25 是什么

BM25（Best Matching 25）是经典的关键词相关性排序算法。它不理解深层语义，而是回答：查询中的词在某个文档里出现得是否足够重要。

简化公式：

```text
score(D,Q) = Σ IDF(q) × [tf(q,D) × (k1 + 1)]
                         / [tf(q,D) + k1 × (1 - b + b × |D| / avgdl)]
```

- `tf`：查询词在当前文档中的出现次数，但次数越多收益会逐渐饱和；
- `IDF`：词越稀有，区分能力越强，权重越高；
- `|D| / avgdl`：对超长文档做长度归一化；
- `k1`：控制词频饱和速度，常见默认约为 1.2；
- `b`：控制长度归一化程度，常见默认约为 0.75。

例如查询“人教版六年级上册分数除法”，BM25 会重视“人教版”“六年级上册”“分数除法”等精确词。Dense Embedding 更擅长找到“除以一个数等于乘这个数的倒数”这类语义相近但用词不同的内容。

因此两者组合：

```text
BM25：保证专有名词、版本、公式名称和原文关键词不丢
Dense Retrieval：召回表达不同但含义相近的内容
RRF：按两路结果的排名融合，避免直接比较不同量纲的分数
Reranker：对少量候选做更精细的相关性判断
```

中文关键词检索必须验证分词或字符匹配质量。ES 教学文档索引需要配置和验证适合教学资料的 analyzer；RunHub 一期应对 PostgreSQL `tsvector`、`pg_trgm` 或应用层中文分词方案做小规模对比，不能把默认英文全文检索配置直接用于中文正文。文本召回质量会直接影响 Hybrid Retrieval 结果。

#### 13.8.2 在线检索流程

```text
用户问题 + 当前题目摘要
  → 授权集合/角色/适配版本/subject/grade/sourceType 硬过滤
  → ES BM25 召回 TopN
  → 独立 VikingDB dense vector 召回 TopN
  → RRF 合并、去重
  → 可选 Reranker
  → Context Builder 按 token budget 组装 TopK
```

题目链路保持独立：

```text
Question Retriever
  → HP 现有 ES/VikingDB 召回 questionId
  → MongoDB 补全题干、答案和解析
  → Recommendation 排序
  → 将选中的 question objects 放入 ContextPack
```

检索结果不足时可以给出一般性说明，但不能声称内容来自当前教材版本。


### 13.9 当前代码能够复用和需要重构的部分

可以直接复用的能力：

- MongoDB 题目详情和 ES 题目索引；
- VikingDB 题干向量检索；
- 学科网实时/本地推荐链路；
- RabbitMQ、对象存储、Prometheus 和 XXL-Job；
- 现有作业、批改、题目、班级和学生查询逻辑。

不能直接视为 Agent Runtime 的部分：

- 当前 `LLMUtil` 只构造单个 user message 并执行一次 Chat Completion；
- 没有 system policy、会话历史、Tool Schema、Tool Call 循环和结构化输出校验；
- 每次调用重新创建 Ark client 和连接池，应改为应用级单例；
- 当前请求日志直接保存完整 input/output，新 Agent trace 必须做学生信息脱敏、字段级开关和保存期限控制；
- 当前 VikingDB Repository 继续服务题目去重和相似召回；文档 RAG 新建独立 VikingDB collection 和 `VikingDocumentRetriever`，不复用题目 Repository；
- 当前 ES Repository 继续服务题库；教学文档另建索引与 Repository，复用 ES 基础设施；
- 当前仓库没有形成 Agent/RAG Evaluation Harness，需要补充 fixture、mock tool、record/replay 和状态断言。

### 13.10 推荐实施顺序

```text
阶段 1：确定合作授权域、资料质量和教材适配路由
阶段 2：完成授权 PPT/教案入库与 Document Retriever
阶段 3：用固定 Workflow 做“教师班级智能讲评”
阶段 4：把 Domain、Document、Question 三类能力封装为只读 Tools
阶段 5：加入对话 Agent、多轮修改和会话状态
阶段 6：加入文件产物版本、评测集、灰度与成本治理
```

先做固定讲评 Workflow 可以独立验证 RAG 质量，避免检索问题、提示词问题和 Agent 规划问题同时出现，导致无法定位效果差的原因。检索稳定后再开放模型动态选择工具。

## 14. 向量检索选型：VikingDB、pgvector 与 Milvus

### 14.1 先理解向量数据库在做什么

Embedding 模型可以把一段文本转换成一组数字。例如：

```text
文本：除以一个不等于零的数，等于乘这个数的倒数
向量：[0.018, -0.274, 0.661, ...]
```

这组数字不是人工定义的知识点编号，而是模型对文本语义的数学表示。含义相近的文本，其向量在高维空间中的距离通常更近。

向量检索系统保存这些向量，并在收到新的查询向量后，快速找出距离最近的若干条记录。Milvus 和 VikingDB 是独立向量数据库/服务；pgvector 则把向量类型和近邻索引能力扩展到 PostgreSQL 中。

### 14.2 共同能力与主要区别

| 对比项 | PostgreSQL + pgvector | Milvus | VikingDB |
| --- | --- | --- | --- |
| 产品形态 | 关系数据库扩展，向量与业务 metadata 可以同库事务管理 | 开源向量数据库；可自建或购买托管服务 | 火山引擎商业云服务 |
| 稠密向量检索 | 支持精确检索、HNSW、IVFFlat | 支持 | 支持 |
| 文本/稀疏检索 | 组合 PostgreSQL 全文检索或字符相似；需单独验证中文处理 | 支持 sparse vector 和内置 BM25 | 支持 sparse vector、关键词检索和 BM25 |
| 混合检索 | 分别查询文本和向量结果，再用 RRF/加权融合 | 支持 dense + sparse 多路召回 | 支持 dense + sparse 混合检索 |
| 元数据过滤 | 直接使用 SQL、索引和 RLS/业务条件 | 支持标量字段过滤 | 支持标量索引和过滤 |
| 运维与适用规模 | 组件最少，适合已使用 PostgreSQL、首期语料和流量有限的项目 | 独立部署与运维，适合向量检索成为明确规模瓶颈 | 托管运维，适合已经采购火山引擎能力的 HP |

不能说 VikingDB 只能做向量检索，也不能说使用 Milvus 就天然比 VikingDB 准。最终效果主要取决于：

```text
文档解析质量
→ 分块策略
→ Embedding 模型
→ BM25 分词
→ 元数据过滤
→ dense/sparse 融合
→ Reranker
→ 上下文组装
```

数据库只是执行检索的基础设施。

### 14.3 对 HP 和 RunHub 的选型判断

如果这是原公司真实上线决策，HP 已经购买并使用 VikingDB，而且当前版本已经满足 BM25、混合检索、过滤、容量和成本要求，那么最合理的方案通常是：

```text
保留现有题目 VikingDB collection
+
新建完全隔离的教学文档 collection/index
```

没有充分收益时，不应仅为了“技术更新”再维护一套 Milvus。

RunHub 已经使用 Supabase PostgreSQL，首期资料规模预计是文章与赛事官方资料，而不是千万级通用知识库。最符合项目的方案是先复用 PostgreSQL：

- pgvector 保存 embedding 并使用 HNSW/精确检索完成 dense 召回；
- PostgreSQL 关键词/全文检索完成文本召回；
- Python Retriever 执行 metadata 过滤、RRF 融合和可选 Reranker；
- 用评测集验证 Recall@K、MRR、引用准确率和 P95，再判断是否存在独立向量库的真实需求。

Milvus 仍是合格的替代方案，但只有当数据规模、并发、向量索引调优或稀疏检索能力出现已测量瓶颈时再引入。为了简历展示而多维护一个数据库，与本项目“功能贴合、不过度设计”的目标冲突。

因此推荐采用统一接口、两个适配器的设计：

```text
DocumentRetriever
  ├─ PgVectorDocumentRetriever    # RunHub 一期真实实现
  └─ VikingDocumentRetriever      # HP 生产环境的合理映射
```

两边保持一致的是数据模型、过滤字段、Hybrid Retrieval 流程、评测方法和 Agent 调用协议；不同的只是底层向量数据库适配器。这比宣称 HP 为了 RAG 替换了已有 VikingDB 更合理、更符合事实。

参考：[Supabase Hybrid Search](https://supabase.com/docs/guides/ai/hybrid-search)、[pgvector](https://github.com/pgvector/pgvector)、[Milvus 官方概览](https://milvus.io/docs/overview.md)、[VikingDB 检索类型](https://www.volcengine.com/docs/84313/1580544?lang=zh)、[VikingDB BM25](https://www.volcengine.com/docs/84313/1791139?lang=zh)

## 15. 一份 Word 教案进入 RAG 后，各类存储保存什么

以当前“26.2.3 二次函数一般式的图象和性质”教案说明存储职责。以下 ID、授权字段与状态是设计示例，不表示该文件已核验来源、完成入库或上线。

### 15.1 对象存储

保存原始 DOCX、OOXML/Block 解析产物、公式与图片、人工审核记录。原文件保持不变，解析升级可重放；访问使用授权校验后的短期地址，不向用户自动开放原文件下载。

```text
source/<license-set>/<document-id>/v1.docx
parsed/<document-id>/v1/blocks.json
assets/<document-id>/v1/<asset-id>
```

### 15.2 关系数据库

HP 使用 MySQL，RunHub 使用已有 PostgreSQL；关系职责一致。

```json
{
  "document_id": "doc_quadratic_lesson",
  "title": "26.2.3 二次函数一般式的图象和性质 教学设计",
  "source_type": "LESSON_PLAN",
  "source_origin": "PENDING_VERIFICATION",
  "subject": "MATH",
  "grade": 9,
  "aligned_edition_id": "PEP",
  "curriculum_revision": null,
  "license_id": null,
  "status": "PENDING_REVIEW"
}
```

目标设计中，`kb_document_version` 记录文件哈希、原文件 URI、Parser/Chunker 版本；`kb_chunk` 保存原始内容、经过审核的公式表示、教学角色、标题/表格关系与来源锚点。仅在实际采用父子检索时增加父关联。错误单元隔离、`QUARANTINED` 和审核修正版属于后续治理设计，当前本地 PoC 只输出读取提示，没有自动审核与隔离能力。

授权集合登记到 `kb_license/kb_license_resource`，文档通过资源清单关联，范围不能由文件名推断。教学适配关系存于 `alignedEditionId + curriculumRevision + schoolSystem + volume`，地域与学校教材映射仍独立维护。

`kb_ingestion_job` 保存阶段、重试和错误码，Worker 不依靠队列消息作为任务事实。全部解析、质量与授权检查通过后，才将完整版本切换为 `READY`。

### 15.3 ES 与 VikingDB

ES 保存可检索文本与关键词索引；VikingDB 保存 dense 向量与必要副本。两路都复制授权过滤与适配字段，以便召回前限制范围。MySQL canonical chunk 是权威内容，检索索引可重建。

```text
chunk_id / document_version_id / content / content_hash
license_id / allowed_resource_set / audience / permission_version
subject / grade / aligned_edition_id / school_system / status
```

多租户授权用可过滤的授权集合或关系映射实现，不能简单写一个 schoolId 就当成合作许可。检索候选仍回权威库复核，包括扩展父单元。

### 15.4 Redis

保存短期缓存、限流与幂等。检索缓存键包含授权集合及权限版本、角色、用途、适配版本、资料版本、查询哈希；权限或资料下架时失效。不得只用 `rag:query_hash:result` 在不同学校间复用私域证据。

### 15.5 RabbitMQ

消息携带 job/documentVersion ID，Worker 执行解析、质检、向量化或删除同步，阶段状态写回 MySQL。授权撤回时先阻止在线使用，再异步清理索引。

### 15.6 HP 原有数据与 AI 运行数据

现有 MySQL 保存作业、分数等业务事实，MongoDB 保存题目详情，ES/VikingDB 题目索引继续原职责。新 AI 服务通过 Tools 读取。MongoDB/观测系统保存脱敏工具 trace 与检索过程；PostgreSQL 保存 Agent checkpoint；Java 保存业务问答，资料正文保留按许可与 TTL 控制；会话和产物元数据存 MySQL。

### 15.7 一次查询

教师要求“结合这次作业讲清二次函数配方”。系统读取当前题、标准解析和错误分布，确定教材适配与可用授权集合，检索方法与易错单元，验证公式和单元完整性，再生成草案。内容来自教案或课件时使用相应归因，不能称为教材原文；实际错误率仍由业务系统提供。

## 16. LangChain 与 LangGraph：分别是什么、为什么用、怎么用

### 16.1 先看不用框架时要自己写什么

一个能调用工具的 Agent 至少需要循环处理：

```text
把用户消息和工具说明发给模型
→ 模型决定回答，或者请求调用工具
→ 程序校验工具名称、参数和权限
→ 程序执行工具
→ 把工具结果作为 observation 发回模型
→ 模型可能继续调用工具，也可能给出最终回答
```

再加入多轮会话、流式输出、重试、暂停确认、恢复和 trace 后，手写代码会迅速变复杂。LangChain 和 LangGraph帮助解决的是这部分工程问题，不负责替代业务设计。

### 16.2 LangChain 是“LLM 应用组件与统一接口层”

LangChain 提供常用抽象和适配器：

```text
Chat Model：用相近接口调用不同模型
Prompt：组织 system/user 等消息
Tool：把 Python 函数声明成模型可请求的工具
Structured Output：要求模型输出 Pydantic/JSON 结构
Document：统一表示正文和 metadata
Embedding：调用不同向量模型
Vector Store / Retriever：连接 Milvus、PGVector 等检索系统
Agent：提供现成的模型—工具循环
```

它像一盒标准化零件。没有 LangChain 也能直接调用每个厂商的 SDK，但更换模型、向量库和工具协议时，需要自己维护更多适配代码。

最小工具示意：

```python
from langchain.tools import tool

@tool
def retrieve_teaching_documents(query: str) -> list[dict]:
    """在当前用户可用资料范围内检索教学讲解。"""
    # trusted_context 由服务端注入，不属于模型可修改的 Tool 参数。
    policy = resource_policy.resolve(trusted_context)
    return document_retriever.search(query=query, policy=policy)
```

`@tool` 会把函数名称、说明和参数结构转换成模型能够理解的 Tool Schema。模型只能“请求调用”，真正执行函数的是我们的应用。

### 16.3 LangGraph 是“带状态、可分支、可暂停恢复的执行引擎”

LangGraph 把流程表达为图，核心只有三个概念：

- `State`：整次执行共享的数据；
- `Node`：读取 State、执行一步并更新 State 的 Python 函数；
- `Edge`：决定下一步进入哪个 Node。

HP Assistant 的状态可以包含：

```python
class AssistantState(TypedDict):
    messages: list
    auth_context: dict
    page_context: dict
    active_goal: str | None
    known_constraints: dict
    textbook_edition: str | None
    business_facts: list[dict]
    document_evidence: list[dict]
    recommended_questions: list[dict]
    artifact_request: dict | None
```

对应 Graph：

```text
START
  → build_auth_context
  → agent_model
       ├─ 调用 Domain/RAG/Recommendation/Artifact Tool
       │    → policy_guard → execute_tool → append_observation → agent_model
       ├─ 信息不足 → 生成追问 → 保存 checkpoint → END
       └─ 信息充分且无需继续调用 → 生成回答/草案 → 保存 checkpoint → END
```

按钮触发的固定摘要、周报或文件生成 Workflow 位于该 Graph 之外；若用户从结果页继续追问，再携带报告/产物引用进入同一个 Agent 会话。

简化代码形态：

```python
from langgraph.graph import StateGraph, START, END

graph = StateGraph(AssistantState)
graph.add_node("build_auth_context", build_auth_context)
graph.add_node("agent", call_agent_model)
graph.add_node("tools", execute_allowed_tool)

graph.add_edge(START, "build_auth_context")
graph.add_edge("build_auth_context", "agent")
graph.add_conditional_edges("agent", continue_to_tools_or_end)
graph.add_edge("tools", "agent")

assistant_graph = graph.compile(checkpointer=mongodb_checkpointer)
```

这段代码只是说明结构；真正实现时还要加入 Tool Registry、Policy Guard、错误节点、超时和 trace。

### 16.4 为什么 HP 不只使用 LangChain 的现成 Agent

简单问答可以直接使用 LangChain `create_agent(model, tools)`。它适合快速建立模型—工具循环。

HP 的流程还包含：

- 根据教师、学生和学校限制数据域；
- 先确定教材版本再允许检索；
- 班级讲评必须同时查询真实批改数据、教学资料片段和推荐题；
- 报告、学习计划等开放请求缺少时间范围或学科时，需要把当前目标和已知约束写入 Graph State/checkpoint，下一轮从同一会话继续；
- 用户在追问中可能修改时间、学科或目标，Agent 需要基于完整会话状态重新规划，不需要额外维护路由枚举；
- DOC/PDF 文件生成可能运行较久，需要保存任务状态并在完成后返回产物版本；
- 工具失败需要走确定性的补偿或重试路径。

因此推荐：

```text
LangChain：模型、Tool、Document、Retriever、Structured Output 等标准零件
LangGraph：维护模型—工具循环、会话 checkpoint、长任务状态和可恢复执行
自研代码：权限、业务规则、文件版本、幂等、领域工具与检索策略
```

不能把权限和业务规则交给 LangGraph 或大模型自行决定。

### 16.5 我们实际采用 LangChain 的哪些部分

第一阶段保持克制，只使用：

```text
langchain-core：Message、Document、Runnable、Tool Schema
模型 provider package：统一模型调用与 Structured Output
向量库 integration：HP 接 VikingDB 自研适配器；RunHub 一期接 pgvector/PostgreSQL 检索适配器
LangGraph：StateGraph、checkpoint 和 streaming；`interrupt` 仅作为未来高风险写操作的预留能力
```

文档解析、分块规则、教材版本路由、检索过滤、RRF/Reranker 策略、权限和审计都保留为自己的业务模块，不堆进不可理解的长 Chain。

### 16.6 推荐的学习和实现顺序

```text
第 1 步：不用 Agent，只用 LangChain Model 接口完成一次普通模型调用。
第 2 步：定义一个只读 @tool，理解“模型请求工具、应用执行工具”。
第 3 步：使用 LangChain Agent 跑通最小 Tool Calling 循环。
第 4 步：通过 `DocumentRetriever` 调用目标向量库，跑通一次教学资料 Hybrid Retrieval。
第 5 步：用 LangGraph 把路由、检索、回答画成 State/Node/Edge。
第 6 步：HP 使用 PostgreSQL checkpointer 和同步摘要，实现同一 thread_id 的多轮状态；RunHub 按自身方案验证实现。
第 7 步：加入文件产物异步生成、版本管理和状态查询。
第 8 步：最后再加入失败重试、trace 和 Evaluation Harness。
```

LangChain 的高层 Agent 本身建立在 LangGraph 之上。简单场景可以先用 LangChain Agent；HP 需要把确定性 Workflow、Agent Tool 循环、跨轮意图续接、持久化和失败恢复放在同一执行图中，因此直接使用 LangGraph 更容易表达这些边界。Human-in-the-loop 是框架提供的能力，但不属于当前只读 Tool 方案的一期需求。

参考：[LangChain 概览](https://docs.langchain.com/oss/python/langchain/overview)、[LangChain Tools](https://docs.langchain.com/oss/python/langchain/tools)、[LangGraph 概览](https://docs.langchain.com/oss/python/langgraph/overview)、[LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)、[LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

## 17. 关系型业务表清单、数据量与 PostgreSQL/MySQL 判断

以下数量都是容量规划示例，不是 HP 已上线数据。真实数量应使用“资料数、平均分块数、日会话量、平均工具调用数和保留天数”计算。

### 17.1 教学资料业务表

| 表 | 一行代表什么 | 主要内容 | 预计数据量 | 增长特点 | MySQL 能否代替 |
| --- | --- | --- | --- | --- | --- |
| `kb_document` | 一份逻辑资料 | 标题、资料类型、来源渠道、适配体系、授权集合、当前版本 | 首期几十到几百；长期数百到数千 | 很慢 | 完全可以 |
| `kb_license / kb_license_resource` | 许可及其覆盖的资源关系 | 产品、租户/学校、角色、用途、期限、署名/导出规则、权限版本 | 按合同与资源清单增长 | 随采购/撤回更新 | 完全可以 |
| `kb_document_version` | 一份资料的一个导入版本 | 原文件 URI、文件哈希、解析器版本、Embedding 模型、状态、发布时间 | 通常是 document 的 1～5 倍；长期数千到数万 | 资料更新时增长 | 完全可以 |
| `kb_chunk` | 一个可检索正文片段的权威副本 | 章节路径、小节标题、正文、顺序、内容哈希、token 数 | 首期一万到三十万；长期十万到千万 | 文档量 × 每份文档分块数，是资料侧最大表 | 可以；正文用 `TEXT/LONGTEXT`，按 version/document 建索引 |
| `kb_ingestion_job` | 一次入库或重建任务 | 当前阶段、状态、重试次数、错误码、开始/结束时间 | 首期几百到几千；长期数万到百万 | 每次导入、升级和重试都会产生 | 完全可以 |
| `kb_ingestion_job_stage`（可选） | 入库任务的一个阶段执行记录 | OCR、解析、分块、Embedding、索引等阶段的输入输出摘要和耗时 | 通常为 job 的 5～10 倍 | 用于排障，可按保留期清理 | 完全可以 |

`kb_chunk` 数量计算示例：

```text
300 份教学资料（容量示例，不是本轮 24 份短文件）
× 假设平均每份 800 个 chunk
= 240,000 个 chunk
```

假设每个 chunk 平均约 800 个中文字符，正文原始量约为 1.92 亿字符；加上索引、行开销和版本后会更大，但对 MySQL/PostgreSQL 都不是不可接受的规模。向量不放在该表，而放在 VikingDB，因此关系数据库不会承担高维向量索引。

### 17.2 教材适用范围表

| 表 | 一行代表什么 | 主要内容 | 预计数据量 | MySQL 能否代替 |
| --- | --- | --- | --- | --- |
| `region_textbook_mapping` | 一个地区在某学段、学科、年级、学期使用哪个教材版本 | province/city/district、stage、subject、grade、semester、edition_id、生效时间 | 几百到几万 | 完全可以 |
| `school_textbook_override` | 某学校相对地区默认值的覆盖配置 | school_id、stage、subject、grade、semester、edition_id、生效时间 | 学校数 × 开通学科/年级；通常几千到几十万 | 完全可以 |

读取优先级：

```text
学校覆盖配置
→ 区县/城市配置
→ 省级默认配置
→ 没有配置则不声称使用某一教材版本
```

### 17.3 Agent 业务表

| 表 | 一行代表什么 | 主要内容 | 预计数据量 | 增长与治理 | MySQL 能否代替 |
| --- | --- | --- | --- | --- | --- |
| `ai_session` | 一次对话会话 | user、school、role、业务入口、状态、创建/结束时间；会话摘要随 checkpoint 保存 | 日会话量 × 保留天数；例如 5,000/日 × 180 天约 90 万 | 中等；按时间归档 | 完全可以 |
| `ai_turn` | 会话中的一轮消息 | session_id、role、脱敏内容或内容引用、token、模型、时间 | session × 平均 6～15 轮；百万到千万级 | 大表；按月分区、设置保留期 | 完全可以 |
| `ai_tool_execution` | 一次工具调用 | tool_name、参数摘要、权限结果、幂等键、状态、错误码、耗时 | 每轮 0～5 次；可能达到千万级 | 大表；敏感字段脱敏，冷热分层 | 完全可以 |
| `teaching_plan_draft` | 一份尚未正式保存的讲评/备课草案 | owner、关联作业、版本、正文、状态、expected_version | 通常少于 session；万到百万级 | 只保留必要历史版本 | 完全可以 |
| `rag_query_audit` | 一次 RAG 查询的审计摘要 | query_hash、过滤条件、返回 chunk_id、模型版本、耗时、trace_id | 接近 RAG 调用次数；百万级以上 | PostgreSQL/MySQL 只存摘要，详细 trace 交给观测系统并设置保留期 | 完全可以 |

不要默认把完整学生原始作答、完整模型输入输出和全部 Evidence 正文永久写入这些表。应保存 ID、哈希、必要摘要和脱敏字段，降低隐私与容量风险。

### 17.4 LangGraph 框架管理的 checkpoint 表

Checkpoint 不是一轮聊天记录，而是 Graph 每执行一步后的状态快照。例如一次讲评流程经过 10 个节点，可能产生多个 checkpoint 和 node writes。

生产中使用官方 `PostgresSaver` 时，表由框架初始化和管理，主要保存：

```text
checkpoint：某个 thread 在某一步的序列化 State
checkpoint_blob：较大的状态字段
checkpoint_write：各 Node 的中间写入结果
checkpoint_migration：框架表结构版本
```

预计数量通常是：

```text
会话数 × 每次 Graph 执行次数 × 每次执行节点数
```

它可能比 `ai_session` 增长快得多。例如 90 万会话、每会话两次 Graph 执行、每次 8 个步骤，理论上可产生约 1,440 万个步骤级记录。因此必须设置会话结束后的压缩、归档或 TTL，不能无限保存。

当前方案已经选定 PostgreSQL checkpointer，业务历史继续由 Java 管理；不迁移 HP 既有业务主数据。Postgres saver 的 schema 初始化与迁移按锁定版本验证。

参考：[LangGraph Checkpointer Integrations](https://docs.langchain.com/oss/python/integrations/checkpointers/index)、[LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

### 17.5 最终替代结论

MySQL 可以替代 PostgreSQL 保存全部 RAG/Agent 业务表，包括资料、版本、chunk、任务、教材映射、会话、消息、工具审计和草案。

MySQL 不能替代：

```text
对象存储：原始 PPTX/DOCX/PDF、公式/图片与解析产物
Elasticsearch：教学文档 BM25 索引
VikingDB：dense 向量召回；与 ES 在 Retriever 层融合
RabbitMQ：异步任务消息
Redis：缓存、限流和短期幂等状态
```

因此 PostgreSQL 不是 RAG 原理要求，而是新 Python AI 服务的工程选择。HP 既有业务继续使用 MySQL/MongoDB；Python Agent 状态已选定 PostgreSQL checkpointer。RunHub 的业务存储按自身方案维护。

## 18. HP 当前 VikingDB 的真实作用与 RAG 扩展方式

### 18.1 当前已经实现的作用：题目近重复判断

当前代码中的 `QuestionDeduplicationVikingRepositoryImpl` 绑定了专门的题目去重 collection 和 index。

写入字段：

```text
question_id
edu_stage
subject
question_body
question_stem
```

查询方式：

```text
输入题干文本
→ 按 subject 使用 partition
→ searchByText
→ denseWeight = 0.5
→ limit = 5
→ 返回 questionId、题目内容和 similarity score
```

业务判断：

```text
score > 0.95
→ 认为命中重复/近重复题目
→ 复用已有 questionId 或更新已有题目
```

在题目结构化流程里，命中重复题后直接关联已有题目，不再调用大模型重新结构化；在学科网题目导入流程里，先查重，再决定更新已有 MongoDB 题目还是创建新题，并把新题写入 VikingDB。

当前实现的核心定位因此是：

```text
题干语义索引
+
题目导入/结构化前的近重复过滤
```

项目文档还把它规划为推荐题的语义候选召回和近重复过滤，但应与上述已经存在的代码事实分开表述。

### 18.2 当前实现的局限

- Repository 和 PO 都是题目专用结构；
- collection/index 是题目去重专用；
- 只返回 Top 5，参数写死；
- subject 作为 partition，其他检索过滤较少；
- 相似度阈值 `0.95` 是业务常量，缺少按学科和题型评测后的阈值配置；
- 当前部分导入代码会把题干、答案和解析拼接后查重，而推荐设计要求只使用清洗题干，两者需要进一步统一；
- 没有教材版本、册次、章节、资料类型、文档版本和有效状态字段；
- 没有完整的 BM25 + dense 候选融合、Reranker 和 RAG Evaluation。

因此新增 RAG 可以复用 VikingDB 产品和账号基础设施，但不能直接复用当前题目 collection、PO 和 Repository。

### 18.3 用于教学文档 RAG 的正确扩展

新建独立资源：

```text
collection: teaching_resource_chunk
index: teaching_resource_chunk_dense
```

示例字段：

```text
chunk_id / document_id / document_version_id
content
dense_vector（首版）；sparse_vector（后续对照）
source_type / source_origin / knowledge_scope / license_id / audience
subject / stage / school_system / grade / academic_year
aligned_edition_id / curriculum_revision / volume / chapter_path / section_title
permission_version / source_locator
content_hash / status
```

入库：

```text
原文件进入对象存储
→ worker 原生解析、按需图片识别、完整性/正确性质检、分块
→ MySQL/PostgreSQL 保存 canonical chunk 和任务状态
→ Embedding
→ 写入独立 ES 文本索引与 VikingDB 文档 dense collection
→ 全量校验成功后把文档版本切换为 READY
```

在线检索：

```text
用户问题 + 当前题目摘要
→ TextbookEditionResolver 确定学校教材体系，授权解析器确定 AllowedResourceSet
→ DocumentRetriever 生成检索请求
→ ES/VikingDB 按授权集合、角色、subject、grade、适配版本、status 做硬过滤
→ ES BM25 关键词召回 + VikingDB dense 语义召回
→ 融合候选
→ 可选 Reranker
→ 返回 TopK DocumentChunk
→ Context Builder 组装 Internal Evidence Pack
→ 大模型生成回答
```

下架和更新：

```text
先构建完整新版本
→ 校验 chunk 数量和检索可用性
→ 原子切换 active version
→ 查询过滤立即排除旧版本，并使权限/资料相关缓存失效
→ 异步删除旧索引数据
```

新的 Python AI 服务建议直接使用当前 VikingDB Python SDK/V2 API，并在应用层实现 `VikingDocumentRetriever`。不要让 Agent 直接持有 AK/SK 或直接拼接数据库请求；Agent 只能调用受控的 `retrieve_teaching_documents` Tool。

## 19. Retriever 是不是“召回器”

大方向正确，但更标准的中文叫“检索器”。

“召回”通常描述搜索系统的第一阶段：从大量数据中快速找出一批可能相关的候选。例如从 24 万个教学资料 chunk 中找出 50 个候选。

“Retriever”是执行检索的应用组件，范围通常比单纯的向量召回更大：

```text
接收 query 和业务过滤条件
→ Query 改写/标准化
→ 生成 query embedding
→ 调用 BM25 和 dense search
→ 应用 edition/grade/status 等过滤
→ 合并去重
→ 返回统一 DocumentChunk
```

Reranker 可以放在 Retriever 内部，也可以作为它后面的独立组件。为了便于评测和替换，HP 建议分开：

```text
Retriever：Top 50 粗召回
Reranker：把 50 个候选精排成 Top 8
Context Builder：根据 token budget 选出真正送给模型的片段
```

Retriever 不是向量数据库本身：

```text
VikingDB = 存储并执行底层搜索的基础设施
VikingDocumentRetriever = 封装查询构造、过滤、融合、错误处理和返回格式的应用代码
```

同一个 Retriever 接口可以有不同实现：

```python
class DocumentRetriever(Protocol):
    async def retrieve(self, request: RetrievalRequest) -> list[DocumentChunk]:
        ...

class VikingDocumentRetriever(DocumentRetriever):
    ...

class MilvusDocumentRetriever(DocumentRetriever):
    ...
```

对应 HP 的三类数据来源：

```text
DocumentRetriever：检索授权 PPT、教案、教辅正文
QuestionRetriever：从公开题库召回结构化题目
Domain Tool：按 ID 精确查询当前作业、批改结果和班级统计；它不是 Retriever
```

所以面试表达可以说：

> Retriever 是检索抽象，召回是它负责的核心阶段之一。我们把 VikingDB 封装在 `VikingDocumentRetriever` 后面，使 Agent 不依赖具体向量库，同时把粗召回、精排和上下文组装分层评测。

## 20. 业务历史、Trace 与 PostgreSQL checkpoint 的职责

### 20.1 当前确认结论（2026-10-23）

前端只调用 Java，再由 Java 转发 Python。Java 拥有业务会话和用户可见问答，保存用户问题与模型最终回答。Python 使用 LangChain `create_agent`（底层 LangGraph）与 PostgreSQL checkpointer 保存 Agent state；MongoDB 继续保存既有题目详情、模型调用日志以及按需求保留的工具/RAG Trace，不承担本方案 checkpoint。

| 数据 | 所有者与用途 |
| --- | --- |
| 会话、业务消息 | Java：鉴权、列表、历史展示、审计；字段、物理存储及落库时机待定 |
| messages、工具消息、中间状态、滚动摘要 | Python：PostgreSQL checkpoint，用于跨轮上下文和执行状态恢复 |
| 工具/RAG Trace | 观测或现有日志系统，按脱敏与保留策略保存，不能代替业务历史 |
| 教学文档与检索索引 | 原 MySQL canonical 文档、ES BM25、VikingDB dense 继续各自职责 |

### 20.2 摘要与 RAG 上下文

使用 `SummarizationMiddleware` 在下一轮模型调用前同步检查，达到阈值先压缩旧消息、保留近期窗口，再生成回答。通过 SSE 经 Java 提示压缩状态。middleware 更新 state，checkpointer 持久化摘要后的消息状态，不另建摘要表；安装 middleware 本身不等于数据库持久化已生效。

后续从同一 thread 的 checkpoint 继续，不默认把 Java 完整历史重新拼回 prompt。再次摘要按当前旧摘要与待压缩消息滚动推进。RAG Evidence 是按本轮问题、角色和许可检索的知识证据，不等于会话记忆；摘要不替代授权检查或 canonical 原文。需要原始对话细节时按需查 Java 历史，重建 Agent state 要显式实现。

### 20.3 标识、并发与一致性

推荐 `thread_id = conversation_id`，每轮新建 run_id，业务消息各有 message_id；原 turn_id 与 run_id 的关系需在接口中明确。同一会话多实例并发须共享协调，具体锁/队列及排队或拒绝策略待定。Java 消息落库与 Python checkpoint 不是自动的跨库原子事务，须设计幂等、状态与补偿；断线、取消、摘要失败及最终回答落库失败分别处理。

### 20.4 实现边界

摘要阈值 60%/70% 只是讨论示例；trigger、keep、token_counter、trim_tokens_to_summarize、包版本、SSE 字段和 checkpoint schema 均需实现时核对。保留和双边删除策略待设计，不能把 checkpoint 默认设成更短 TTL 后又承诺聊天可以无限续接。任务重启调度、逐 token 重放、审核恢复和长期记忆仍需独立实现与证据。

详见 [05 第 16.5—16.6 节](05-HP多角色对话Agent产品文档.md) 和 [确认基线](agent-architecture-handoff.md)。

## 21. 当前技术选型结论与真实开发下一步

### 21.1 HP 目标架构已经基本收敛

```text
语言与 API：Python 3.12 + FastAPI + Pydantic v2
Agent 编排：LangChain create_agent（底层 LangGraph runtime，不手写图）
模型/Tool/Retriever 适配：LangChain Core/Integrations

MySQL：
  kb_document / kb_document_version / kb_chunk
  kb_license / kb_license_resource
  kb_ingestion_job / 教材版本映射
  ai_session / teaching_plan_draft
  learning_plan_draft / ai_artifact

MongoDB：
  ai_turn / ai_tool_execution / rag_query_trace

PostgreSQL：
  LangGraph checkpoint，含消息状态与滚动摘要
  现有 llm_request_record 继续保留

Elasticsearch：独立教学文档索引执行 BM25，与题目索引分离
VikingDB：
  现有题目 collection 继续题目查重/语义召回
  新建教学文档 collection 做 dense 召回，与 ES BM25 融合

对象存储：原文件和解析中间产物
Redis：缓存、限流、短期幂等
RabbitMQ + Worker：解析、OCR、分块、Embedding、建索引
OpenTelemetry/Langfuse：Trace、token、latency、cost 和评测关联
```

尚未完全确定，但不阻碍开始第一阶段的项目级参数：

- 文档解析器/OCR 的具体产品；
- Embedding 模型、维度和版本；
- Reranker 模型；
- ES/VikingDB 两路召回融合参数、TopN/TopK；
- 具体 TTL、分片键和脱敏规则。

这些不应靠讨论拍板，要在真实语料 PoC 和评测集上决定。

### 21.2 若以真实开发为目标，下一步不是先写对话 Agent

HP 无法连接原公司数据库和云权限，因此真正开发应在 RunHub 进行，但实现一套与 HP 相同的接口和工程机制。下一步分为两个连续动作：

#### 动作 A：RunHub 只读审阅结论（已完成）

```text
技术栈：Java 21 / Spring Boot 3.5.9 / Maven 多模块 / MyBatis
数据库：Supabase PostgreSQL
模块：common、identity、notification、race、zuicool、api
现有 AI 基础：文章抓取、正文清洗、图片 OCR、LLM Structured Output、确定性赛事更新 Workflow
现有业务基础：赛事搜索/详情、报名状态、评分、用户赛事、成绩、地图、提醒设计
```

关键差距：

- 当前 `source_article` 只保存来源身份、URL、标题、发布日期、`content_hash` 和处理状态；正文只在本轮内存上下文中使用，没有可用于 RAG 的长期、版本化正文存储；
- 当前依赖中未发现 pgvector、Redis、RabbitMQ、对象存储、Flyway/Liquibase 或 Agent 编排框架；不能在方案中把这些当成已经存在；
- 现有 Java LLM Workflow 是固定结构化处理链路，不等于具备对话会话、Tool Registry、Tool Loop、Retriever、citation 和 Evaluation Harness；
- 正文解析日志目前会输出完整文章文本，接入 RAG 前应改成长度、hash、来源和 trace 等摘要日志，避免扩大内容与隐私风险；
- 需要新增 Python AI 子项目、`knowledge_*` 数据迁移、pgvector/文本检索 PoC、Java Domain Facade、会话/trace 表和首个 Retriever API。

这说明“所有已同步文章正文进入 RAG”首先是数据产品改造：必须从抓取时就保存可版本化的 canonical 正文，而不是拿现有 `source_article` 直接建向量。

#### 动作 B：完成一个“可评测的 RAG 垂直切片”

首个切片只选少量真实资料，例如：

```text
10～20 篇已同步文章
+
2～5 份赛事官方规程/报名须知
```

按这个顺序实现：

```text
1. 定义 KnowledgeDocument / DocumentVersion / Chunk 领域模型。
2. 导入现有正文，完成清洗、分块、hash 去重和版本状态。
3. 写入 canonical chunk 和向量检索库。
4. 实现统一 DocumentRetriever API。
5. 跑通 keyword/full-text + dense + metadata filter + RRF；HP 首版以现有 Elasticsearch 承担关键词/BM25 分支、独立 VikingDB Collection 承担 dense 向量分支，再在 Retriever 服务层融合；RunHub 一期使用 PostgreSQL 文本检索。
6. 建立 30～50 条人工标注查询：每条标出应该命中的资料/章节。
7. 评估 Recall@K、MRR、过滤正确率、P95 和失败样例。
8. 检索稳定后，才把 Retriever 包装成 Agent Tool。
```

先做 Retriever 而不是 Agent，因为最终回答不好时，必须能区分：

```text
资料没导好
分块不对
检索没召回
Reranker 排错
上下文组装丢信息
还是模型生成错误
```

若一开始把所有问题包进对话 Agent，效果差时很难定位责任环节。

### 21.3 HP 与 RunHub 的一致性

两边不必强行使用相同云厂商，但必须共享抽象与评测协议：

```text
DocumentIngestionPipeline
DocumentRetriever
RetrievalRequest / DocumentChunk
ContextPack
Tool Schema
Trace Schema
Evaluation Dataset
```

RunHub 一期使用现有 Supabase PostgreSQL/pgvector，HP 架构映射为 MySQL/VikingDB。面试时可以诚实表达：两边复用各自已有基础设施，通过统一 `DocumentRetriever` 和评测协议保持工程方法一致；只有评测或容量证明 PostgreSQL 方案成为瓶颈时，RunHub 才演进到 Milvus 等独立向量库。

## 22. MODULAR-RAG-MCP-SERVER 参考项目吸收结论

已完成对 `E:\project\MODULAR-RAG-MCP-SERVER` 当前代码的分析，详细证据见 [10-MODULAR-RAG-MCP-SERVER参考项目分析.md](10-MODULAR-RAG-MCP-SERVER参考项目分析.md)。

对本方案产生的确定性结论如下：

1. 保留模块化接口、稳定 Chunk ID/内容哈希、幂等 Upsert、Dense + BM25、RRF、可选 Reranker、分阶段 Trace 和 Golden Set 评测思想；
2. 不采用其 Chroma + 本地 BM25 JSON 作为 HP 生产存储。HP 以 Elasticsearch 承担关键词/BM25 分支、独立 VikingDB 教学资料 Collection 承担 dense 向量分支，并以 MySQL 保存权威文档/版本/Chunk 主数据；
3. 不照搬固定 1000/200 字符分块，改为课件/教案章节和“定义/方法/例题/易错点”结构优先分块；
4. 不照搬 PDF 图片统一追加到文末的简化处理，数学 PPT/教案需要公式、图形、表格与附近正文的版面锚定；
5. MCP 只是 Retriever 的可选协议适配层，不是 RAG 核心。HP 内部主入口仍为 FastAPI/Domain Tool，确有多 Agent Host 复用需求时再加 MCP；
6. 参考项目的规则 QueryProcessor 不能解决 HP 题目召回，`question_retrieval_profile` 预生成与 `student_error_query` 动态生成仍是 HP 的领域核心；
7. 第一版仍不使用当前不可靠的知识点标签作为 Query、触发条件或硬过滤；
8. 查询状态必须区分正常无证据、部分降级、依赖故障、超时和 ACL 过滤，不能把检索异常伪装成“没有找到资料”；
9. 参考项目的 Golden Set 尚未填写正确 Chunk，不能作为效果证明。HP 必须先用真实教学资料构建有人工标注的评测集，再确定分块、Embedding、Hybrid 和 Reranker 参数。
10. 参考项目当前实际只支持可解析文字层的 PDF；Word、扫描 PDF OCR、数学公式/表格版面关联均未完成。HP 需要以 `SourceParser` 抽象支持 PPTX、DOCX，以及后续 PDF、OCR PDF 等输入，先保留章/节/图表结构，再生成 Chunk；
11. 参考项目当前真正实现的只有 `RecursiveCharacterTextSplitter`，默认固定 1000 字符、200 字符重叠；`semantic` 等配置没有对应实现。HP 可以把它作为 PoC Baseline，但正式方案采用教学资料结构优先分块；
12. 参考项目的默认 Cross-Encoder 为英文模型，且实际超时控制与依赖收口不完整。HP 只在 Golden Set 证明收益后，再引入中文/多语 Cross-Encoder 对 TopN 候选重排；LLM Rerank 不进入第一版高频在线链路。

该参考项目适合用来学习 RAG 基础算法和模块契约，也适合作为 HP PoC 的对照基线；它不改变本方案已经收敛的产品定义、知识源边界、VikingDB 选型和 Query Builder 方向。

## 23. PPT 与 Word 解析和检索的当前结论

### 23.1 原生解析优先，OCR 针对图片区域

本轮本地样本是 18 份 PPTX 和 6 份 DOCX，没有教材 PDF。它们均能读取 OOXML，不能由此推断图、公式和题解已完整解析。

| 载体 | 首选解析 | 必须保留 |
| --- | --- | --- |
| PPTX | presentation 顺序、slide XML、shape/group、关系文件与备注 | 形状位置、阅读次序、OMML、图片引用、跨页主题和例题 |
| DOCX | 正文、标题/样式、表格行列、关系文件与公式 | 教师活动/学生活动/设计意图等列角色、合并单元格、OMML 与图文关系 |
| 图片区域 | 保留原图，按需 OCR/视觉说明并复核 | 图中条件、字母标记、几何关系、与正文的关联及置信度 |
| 后续 PDF/扫描件 | 原生文字层或版面 OCR 按载体选择 | 页内坐标、目录、公式和图表关联 |

数学公式的 OMML 树包含分数、根号、上下标。直接串联 `m:t` 会把分数误抽成 `b2a`，把平方、根号等结构丢掉。公式应保存原始 XML 或等价结构，并转换为可校验 LaTeX/MathML；数学字母可另外规范化用于检索，但不能覆盖 sourceContent。

18 份 PPT 都有一张纯图片首页。抽出原图后可见至少专题 1 首页为知识思维导图，不能统一当作无用封面删除。图片区无文本时记为待视觉处理，不直接判定内容为空。Word/PPT 内图片数量也不等于有效教学图数量。

### 23.2 Parser 的验收标准

解析器输出 Block、公式/图资产及关系，而非仅返回 Markdown 大字符串。Block 携带文档版本、位置、角色、阅读顺序、适配元数据和完整性状态。原生解析与 OCR 产物分别保留，不让模型猜补无法读取的图或缺失听力内容。

先在本轮二次函数 Word、圆 Word、二次函数 PPT 与三视图 PPT 上验证公式/表格/跨页/图形链路。是否引入 MinerU 或其他工具由实际解析对比决定，不能用“支持 PPTX/DOCX”替代本语料验收，也不需要先将全部 Office 转 PDF。

### 23.3 检索基础设施保持已收敛方案

对象存储保存原文件和中间产物，MySQL 保存文档、版本、授权与 canonical chunk，独立 ES 教学文档索引执行 BM25，独立 VikingDB 文档 Collection 执行 dense 召回，服务端 RRF 融合后按需 Rerank。现有题目 Collection 与 Repository 保持题库职责。VikingDB sparse 分支作为后续可测替代，不能与当前 ES 分支混写成两套同时必需方案。

### 23.4 参考项目可复用什么

沿用 MODULAR-RAG-MCP-SERVER 的模块接口、幂等 Upsert、hash、检索融合与 Trace 思路；补齐其 PDF 单载体、固定分块、通用 Query、缺少合作授权与角色治理的局限。RAG Pipeline 仍可以是固定执行过程；对话 Agent 才需要工具循环和状态编排。

## 24. 教学资料 Chunk 专项设计

### 24.1 当前本地基线：取消强制 Parent，正文递归切片、表格模型分类后按行切片

当前基线（PoC 0.5.3）：调用方指定一个文件，MarkItDown 0.1.8 返回 `DocumentConverterResult(markdown, title)`；接口将原始字段放在 `markitdown_result`，并以顶层 `markdown` 提供全文。该 Markdown 字符串不会被 `markdown-it-py` 改写。读取层用 `markdown-it-py` 解析语法 token，只把识别出的顶层 Markdown 表格转换为内部 `TableBlock(header, rows, raw_markdown, table_type)`；其余标题、段落、列表等内容仍合并在 `TextBlock(text)` 中。`ReadResult.blocks` 是读取与切片之间的内部结构，解析接口不直接返回 `blocks`，只返回 `table_count`、调试用 `table_types`、全文及最终 chunks。[读取结构](../../rag-chroma-poc/app/reader.py:19) · [表格识别](../../rag-chroma-poc/app/reader.py:46)

普通 `TextBlock` 使用 LangChain `RecursiveCharacterTextSplitter`，以 `cl100k_base` 计算 token，默认预算 500、目标 overlap 75。每个 `TableBlock` 保留原始表格 Markdown，逐表请求 `qwen3.7-flash`，仅输出 `0/1`，请求参数显式关闭思考。`1` 表示关系型，默认首行为列标题，拆分后每片重复首行；`0` 表示非关系型（键值、未知或混合），按行切片，原首行只出现一次。表格固定上限 1024 token，不复用正文预算；整行优先，单行超过上限时才按单元格顺序调用 LangChain 递归切分并产生 warning。失败、超时、缺少 API Key 或输出不合规时降级为 0，保留内容并记录 warning。[分类器](../../rag-chroma-poc/app/table_classifier.py) · [表格切分](../../rag-chroma-poc/app/chunker.py)

关系型和非关系型首行处理不同，避免对键值或混合表盲目复制列名。单元格内的 `|`、反斜杠和换行会转义或转换为 `<br>`。若表格 Markdown 不完整、未被解析器识别，它会落入普通 `TextBlock` 路径，递归切分可能切坏表格排版，这是当前边界。[序列化规则](../../rag-chroma-poc/app/tables.py:9) · [详细规则](../rag/表格LLM分类与1024Token切片改造方案.md)

当前无强制 Parent 分组、无 `parent_id`、无自动标题路径或生成式元数据；表格结构分类是唯一的入库前 LLM 调用。表格 chunks 才会增加 `table_position=single/first/middle/last`；实际召回后的邻居扩展尚未实现。记录 ID 为 `<document_id>:000001`，按文件内输出顺序递增。

0.5.3 的34项本地测试覆盖分类请求 payload、思考关闭、0/1 严格解析、关系/非关系首行策略、固定 1024 token、失败降级、超长行兜底及表格并发和顺序稳定性。0.4.0 对 24 份资料得到的 259 个 Chunk、15 张表、179 张图片是旧切片统计，不能代表新分类结果。当前环境没有 API Key，尚未验证真实 DashScope 调用；检索效果也未评测。Embedding/Chroma、Rerank、总结与评测按后续三步实施。[本地分步方案](../rag/Chroma本地入库PoC设计方案.md) · [表格规则与示例](../rag/表格LLM分类与1024Token切片改造方案.md)

### 24.2 当前资料暴露的真实问题

| 样本或内容 | 后续应检查什么 | 不能由当前规则保证什么 |
| --- | --- | --- |
| 专题1 第6～8张：例1题干/配图、答案、方法与易错点分布在不同页 | 召回后是否同时具有题干条件与解答 | 幻灯片连续不等于已经识别例题关系；当前不强制合为父块 |
| 专题18 第6～8张：“如图”的条件在图片中，后页给解答 | 图片条件是否真正提取并关联 | 扩大文字上下文不能恢复未读取的尺寸和视图 |
| Word 教案的师生活动、评价与设计意图等表格列 | 行列角色、教学步骤与公式是否保真 | 递归切片不保证整张表或活动链完整进入同一片 |
| 英语分层作业：题目与答案在不同位置，部分任务引用缺失听力素材 | 题答配对与素材完整性 | 相邻扩展不一定找到远处答案，也不能补造音频与脚本 |
| 二次函数教案练习1（2）的顶点答案错误 | `y=-x²+2x-3` 应配方为 `-(x-1)²-2`，顶点为 `(1,-2)`；源文写 `(1,-4)` | 高检索分数、父子扩展或标题增强都不能证明原文正确 |

这些问题用于构建后续失败样本，不作为恢复强制 Parent 或引入 LLM 的充分理由。当前只输出读取提示，关键公式、缺图和原文错误仍需人工核对。

### 24.3 父子 Chunk：面试可讲的后续优化方向

**触发条件：** 评测发现“小片段命中了，但缺定义前提、公共题干或解答上下文”，且资料有可信结构或稳定相邻关系。父子模式将检索粒度与生成上下文粒度分开，不应作为所有文档的默认配置。

#### 24.3.1 固定父子关系如何实现

```text
入库：可信章节/较大正文块 → 有长度上限的父块 → 子块
      子块正文 + 向量 + parent_id → 向量索引
      parent_id + 父正文 + 文档版本/范围 → 普通文档存储

查询：检索/重排子块 → 按 parent_id 取父正文
      → 去重、校验版本与权限、限制上下文预算 → 回答模型
```

父正文通常不参加第一轮向量搜索，也不必生成向量。可保存于 MySQL、SQLite、MongoDB、键值存储或本地文件；父子是逻辑职责区分，不要求物理分库。若不想重复保存正文，可保存一份规范化全文，父块只记录其字符或字节范围，按需读取。范围必须对应固定文档版本，不能混用 tokenizer 位置、字符与字节偏移。

父块不必是一整章或整篇文档；长章节仍需按可理解的边界拆分并限长。父正文与子正文都完整保存时确有文字重复及维护成本，不能宣称零额外存储；只给子块建向量则不必额外为父块承担向量及其索引成本。[MongoDB 官方父子检索实现](https://www.mongodb.com/docs/atlas/ai-integrations/langchain/parent-document-retrieval/)

#### 24.3.2 动态相邻扩展是另一种实现

PaiSmart 已实现 small-to-big：入库保存顺序小块，命中后从 MySQL 取同文件前后相邻块，去掉 overlap 重复内容，动态拼成父上下文；不要求预存章节树。默认前后各取1片，单父上下文最多1500字符，总预算6000字符，命中覆盖同一父范围时复用，引用仍锚定原命中子片。它的 Parent 是检索时的较大上下文，和解析器里的流式 parent 缓冲不是同一概念。[实现代码](../../别人的项目/PaiSmart-main/src/main/java/com/yizhaoqi/smartpai/service/search/ParentContextExpander.java:17)

因此可以证明已有框架和项目实现这种模式，但不能据此宣称我们的 PoC 已使用它，或它在 HP 上已有收益。

#### 24.3.3 优点、代价与失败边界

| 方面 | 可能收益 | 代价与限制 |
| --- | --- | --- |
| 检索与生成粒度 | 小块减少主题混杂；大上下文可补定义、条件、步骤 | 父块本身不会自动提高子块召回率；噪声增多也可能降低回答质量 |
| 存储 | 父块无需额外向量；也可全文加范围引用 | 完整父正文与子正文重复；多版本与父子关联需要维护 |
| 模型上下文 | 扩展比只给小片更可能完整 | 单父块与全部证据都要限长，还要预留问题、历史及输出预算；去重很重要 |
| 边界 | 可信章节或邻接关系便于确定扩展范围 | 子块在父块首尾时，所需内容可能在父块外；可试父块 overlap/邻居窗口，但不能保证补齐 |
| 文档结构 | 有可靠层级时容易建立关系 | 结构不明确时硬分 Parent，可能只增加复杂度、隔断本可合并的文字 |
| 工程与治理 | 能明确记录取回范围、追溯证据 | 多一次正文读取，增加时延；扩展内容仍需检查权限、版本及教学角色 |

先重排子块、再按需扩展，是一种可测方案；不必把所有初始候选都扩成父块。只有通过对照验证，才能决定扩展大小、数量和时机。

### 24.4 标题路径：与父子检索独立的轻量增强

可靠标题可组成 `二次函数 > 图象与性质 > 顶点坐标`，单独保存在未来的 `metadata.heading_path`。它不要求保存父正文，也不要求父子检索。Word 原生 Heading、Markdown 标题等可作为依据；PPT 文本字号或短句不能自动证明章节层级，跨多个小节的 Chunk 也不能冒用其中某个局部标题。

**建议候选：可靠且简短的标题路径与正文一起生成文档向量，同时单独保留正文与结构字段。**

```text
存储正文：原始 Chunk 正文
metadata.heading_path：二次函数 > 图象与性质 > 顶点坐标
Embedding 输入：章节：<heading_path>\n正文：<Chunk 正文>
Rerank / 回答输入：显式拼接标题路径与正文
```

metadata 单独存在不会自动影响 dense 相似度；只在回答时拼标题也无法帮助初次召回。可靠路径参与 Embedding 可以消解短片段的主题歧义，但效果尚需比较。避免重复冗长目录、通用文件名和推断出来的错误层级；前缀计入模型输入预算。Query 使用相同 Embedding 模型，不要求用户问题带一条未知标题路径。变更文档向量输入后，应重新向量化受影响记录，不能将新旧输入策略混用后声称已完成公平对照。

LangChain `MarkdownHeaderTextSplitter` 能将标题提取为 metadata；是否拼入向量输入仍由应用决定。[官方文档](https://docs.langchain.com/oss/python/integrations/splitters/markdown_header_metadata_splitter)

标题路径增强尚未实现；当前普通文本metadata为`id、subject、grade、hash`，表格仅多`table_position`。没有`heading_path`或生成式元数据，也未增加模型调用。

### 24.5 LLM 元数据增强：必须对应明确用途

MODULAR 的 MetadataEnricher 按 Chunk 生成 `title、summary、tags`，不改正文；DenseEncoder 与 SparseEncoder 都以 `chunk.text` 为输入，因此这些生成字段没有自动参与向量表示或 BM25 分词。[Dense 输入](../../别人的项目/MODULAR-RAG-MCP-SERVER/src/ingestion/embedding/dense_encoder.py:116) · [Sparse 输入](../../别人的项目/MODULAR-RAG-MCP-SERVER/src/ingestion/embedding/sparse_encoder.py:119)

它们仍可用于结果标题、资料浏览与标签筛选。`get_document_summary(doc_id)` 是一个 MCP 工具：查出该文档的 Chunk，以首片信息确定标题/标签，摘要取第一个带 `summary` 的 Chunk；没有摘要就截取首片正文。此工具执行时不再调用 LLM，也没有综合全文生成摘要，因此不能把某个局部 Chunk 的摘要当作可靠全文摘要。[概览实现](../../别人的项目/MODULAR-RAG-MCP-SERVER/src/mcp_server/tools/get_document_summary.py:317)

标签筛选还要检查存储类型：参考项目的 Chroma 适配将列表变为逗号字符串，而筛选逻辑按集合比较，不能未经验证就声称该链路可靠。

对只需“问答召回”的本地 PoC，若标题/摘要只展示、无筛选需求，也没参与检索或重排，为每片调用 LLM 的成本缺少收益依据，直接跳过。真实标题优先复用原文，预览可以截正文；需要全文概览时，可按需生成并缓存。若将生成摘要用作检索，应显式接到增强向量、摘要独立索引或重排输入中，并验证错误摘要是否伤害检索，不能仅以“已增加 metadata”作为优化成果。

### 24.6 评测与实施顺序

当前先跑通读取/切片 → Embedding/Chroma → Dense/Rerank → 回答与评测。之后针对失败模式逐项比较，不一次叠加所有优化：

1. 原文递归切片基线。
2. 仅加可靠标题路径，比较正文向量与“路径+正文”向量。
3. 仅加相邻窗口或有界父块扩展，观察缺失前提、题干、答案是否补齐。
4. 只有仍存在明确问题时，再考虑生成式上下文、摘要索引或更复杂教学关系。

父块扩展主要评测上下文完整性、证据支持与回答正确率，不只看子块 Recall@K；标题向量增强则比较 Recall@K、MRR/nDCG、主题混淆。统一记录输入 token、上下文重复率、P95、模型与存储成本。查询、语料、模型、候选数等对照条件保持一致，同时记录预算限制下能提供多少证据。缺素材、错版本、权限拒绝、跨父块边界及原文错误均需反例，不能只挑有收益的问句。

### 24.7 面试时如实表述

“父子 Chunk 是后续可验证的优化方向。小片检索容易定位，但有时缺公共条件或答案；可以检索子片后取有界父块，或像 PaiSmart 那样动态补相邻片。父正文放普通存储，通常不做第一轮向量搜索。代价是正文重复、读取和 token 成本，父边界也不保证补足所有上下文，所以需要去重、限长并用失败样本验证。当前独立本地 PoC 采用原文递归切片，没有父子扩展；我不会把候选设计说成线上已实现，也不会在没有评测时宣称召回或准确率提升。”

完整追问见 [12 的 Q19-A～Q19-C](12-模拟面试官提问与回答.md)。本地 PoC 的 24 份读取验证与 HP 生产运行是不同证据，不能虚构上线、检索指标、用户规模或逐份授权合同审核。

### 24.8 表格按行切片：LLM 判断关系型与独立表格预算（PoC 0.5.3 已实现）

本地 PoC 0.5.3 已按该方案实现：读取层由 MarkItDown 将指定文件转成 Markdown，`markdown-it-py` 识别表格边界并提取行列；模型不重写或整理表格正文。每张表的 Markdown 作为一次分类请求输入，使用 DashScope OpenAI 兼容地址 `https://dashscope.aliyuncs.com/compatible-mode/v1` 和模型 `qwen3.7-flash`，请求显式传 `enable_thinking=false`，只接受单个数字 `1`（关系型）或 `0`（非关系型）。模型地址、模型名和 `DASHSCOPE_API_KEY` 由环境变量配置，仓库不保存密钥。异常、超时、缺少 Key 或输出不合规降级为 `0`，在解析响应 warning 中说明，读取与切片继续完成。

29.1.1 圆的有关概念文档曾出现“教学过程表被判为 0”：表1是键值信息，判0合理；表2有固定四列表头（教学环节、教学内容与教师活动、学生活动、设计意图）和6行同构数据，按本方案应判1；表3是单行总结，判0合理。旧提示词把“教学流程”直接列为非关系型，且规定不确定时输出0，造成判断偏向0。0.5.3 已改为优先依据稳定列结构判断，并加入教学过程表输出1、键值表输出0的对照示例。此修正目前有提示词回归测试，真实分类仍需在加载0.5.3并配置 API Key 的服务进程里验证。

切片规则收敛如下：

- 所有表格只按行累积，表格 chunk 最大预算固定为 1024 token，与普通正文的 400–600 token 预算分开。达到预算就结束当前表片，不跨表补长度；较短尾片允许保留。
- `type=1` 时，把 Markdown 表格第一行视为列标题。每个表格 chunk 都重复这行标题，再加入当前片段的数据行。重复的标题行也计入 1024 token。
- `type=0` 时，按原顺序逐行切，不重复列名。原表第一行仍须在首次输出中保留，避免丢失内容；后续片段不附加它。
- 不按列拆分。若单独一行超过 1024 token，才对该行的超长单元格调用已有 LangChain 递归切分器作为兜底，并按顺序输出；该异常路径可能跨片破坏行内关系，响应 warning 应可见。
- 不增加键值对推断、行背景补充、父子 Chunk 或邻片检索；分类仅决定是否重复第一行标题。

classifier 位于 `TableBlock` 进入 `make_chunks` 前，避免 Markdown 表格进入普通 `TextBlock` 递归切分。分类只在文件处理时发生，不在查询时发生；当前用最多 4 个 Python `ThreadPoolExecutor` 工作线程并发执行逐表网络请求，不做持久缓存。分类是 I/O 密集型任务，线程池可让多个请求等待模型响应的时间重叠；并发上限用于控制对供应商的请求压力。Future 按文档表格顺序收集，因此 `table_types`、warning 与切片顺序保持稳定。分类结果在 PoC 响应 `table_types` 中提供类型、状态和 `duration_ms`，服务日志也逐表记录耗时与分类结果，不写入 Chroma metadata。表格预算为内部常量 `1024`，响应提供 `table_chunk_tokens`。真实模型调用需要运行环境设置 `DASHSCOPE_API_KEY`；如果缺失，接口会逐表 warning 并退化为非关系型策略。

当前实现已通过 mock 与离线单测验证请求格式、失败降级、首行策略和长度约束；由于执行环境未配置 DashScope API Key，仍需在有 Key 的本机实际解析 24 份资料，抽查每表分类、关系表重复首行、非关系表首行只出现一次、超长行兜底、内容顺序和 warning。只有随后用检索问题集对比召回与回答结果，才能判断模型分类与更大表格预算是否改善效果。






