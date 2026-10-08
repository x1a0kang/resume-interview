# HP 图片 AI 工作流与 MQ 架构优化

> 审查基线：2026-09-07 代码；Eval 专项更新：2026-09-08。  
> 适用范围：`hp-grading`（Java）与 `x_edu_ai`（Python）。  
> 文档定位：本目录中当前项目架构、图片建标、答案识别、批改和大模型工程优化的唯一主文档。文中的问题是代码审查与实验建议，不等同于已确认的线上事故。

## 1. 结论先行

当前 `Java + RabbitMQ + Python Worker + 对象存储` 的方向合理，适合 OCR、VLM、解题、批改这类耗时长、耗时波动大、需要削峰和异步恢复的任务。没有必要仅因为“模型服务通常用 FastAPI”就把它改成 Java 长连接等待 Python；HTTP/gRPC 适合同步接入和短调用，MQ 适合异步任务，两者不是替代关系。

当前工作流分阶段也有充分理由：前端能显示进度；研发能定位是 OCR、题目合并、答案识别还是评分出错；失败可以只重试局部；不同阶段可以使用不同模型并按页或按题并行。但是需要区分三件事：

1. **业务阶段**：用户和研发需要看见的检查点，如 OCR、题目解析、答案解析、解题、识别、评分。
2. **模型调用**：阶段内部为完成某个判断而调用一次 LLM/VLM，不应天然等同于一个业务阶段。
3. **跨服务往返**：Java 投递 MQ、Python 回调、Java 再组装下一阶段。它是一种编排实现，不是实现进度反馈的唯一方法。

因此，建议不是“一把出”，也不是永远保留每次 Java↔Python 往返，而是：

- 保留可观测、可检查、可恢复的语义阶段；
- 用实验删除没有信息增益的模型调用；
- 优先删除无计算价值的独立 `labeling` 往返；
- 短期继续由 Java 维护业务状态，并完善阶段事件；
- 中期让 Python 的持久化工作流负责算法 DAG，持续向 Java 上报进度和最终结果；
- 对小而简单的试卷提供 fast path，对复杂材料保留完整分阶段路径；
- 不以“强模型”作为质量保证，必须用同一测试集比较一步式、当前分步式和优化分步式。

## 2. 第一性原理：系统到底要保证什么

上传一组图片后，系统不是只需要“得到一个像答案的文本”，而是要构造一份可长期复用、可与学生图片对齐、可计算分数、可追溯证据的结构化资产。

| 不变量 | 含义 | 失败后果 |
| --- | --- | --- |
| 身份一致 | 作业、教师、学生、模板、页、题、空必须属于正确上下文 | 批错学生或串题 |
| 几何一致 | 坐标明确属于哪张原图、哪个尺寸和哪个变换版本 | 框错位置、答案归错空 |
| 语义一致 | 题干、选项、材料、图、答案、解析关系正确 | 题库本身错误 |
| 证据可追溯 | 原图、OCR 原文、规范化文本、模型判断和最终分数能互相追踪 | 无法解释和申诉 |
| 不确定性诚实 | 缺失、冲突和低置信度不能伪装成正确 | 静默错判，风险最高 |
| 可恢复 | 超时、重试、重复消息、进程退出不会丢任务或重复记分 | 卡单或重复副作用 |
| 可评测 | 每个阶段和最终业务结果都有离线基准与线上指标 | 无法证明优化有效 |

分阶段是否合理，应看它是否保护了这些不变量；某个模型调用是否合理，应看它是否提供了独立信息增益，而不是看函数名有多少个。

## 3. 当前系统的真实边界与时序

### 3.1 Java 和 Python 的职责

```text
前端/业务调用方
    |
    v
hp-grading (Java)
    - 鉴权、参数和业务关系校验
    - 创建 labeling/review/job/page/request 记录
    - 持久化状态、题库、批改结果
    - 向前端或下游发布阶段变化
    |
    | RabbitMQ：任务消息（应主要传元数据和对象引用）
    v
x_edu_ai (Python workers)
    - 图像预处理、OCR、版面分析
    - 题目/答案结构化、解题
    - 学生答案识别、配准与批改
    - 输出结构化结果、证据、质量与成本信息
    |
    | RabbitMQ：结果/进度事件
    v
hp-grading (Java) -> 状态机/数据库/前端
```

Java 本身已经是接入层和 job 创建者，不必额外增加一个只做 HTTP→MQ 转发的服务。只有出现多个调用方统一鉴权、限流、租户配额、模型路由或多协议适配时，独立 AI Gateway 才有明显价值。

### 3.2 为什么当前会多次 Java↔Python

建标链路当前大致是：

```text
上传与建任务
 -> 每页 OCR
 -> 汇总全部页
 -> stem_parsing
 -> answer_parsing
 -> solving
 -> labeling
 -> Java 入库题目
```

批改链路当前大致是：

```text
上传学生图片与建任务
 -> recognizing
 -> grading
 -> Java 入库分数、批注并通知
```

每次回调后 Java 更新状态再投递下一任务，带来的收益是真实的：

- 前端不会在数分钟内完全无反馈；
- 失败阶段明确，可展示“识别失败”而不是笼统失败；
- 可以查看 OCR、题目结构、识别文本和评分各自的中间产物；
- 局部重试不会总是重跑前面成功的昂贵阶段；
- 算法结果在业务库中形成检查点，便于人工修正和恢复。

但前端要的是**进度事件**，不必要求每个内部步骤都由 Java 重新发起。当前代码已有 `process_stage_routing_key`，说明产品也采用了阶段通知思路；下一步应把它统一为明确的进度契约，而不是继续用跨服务回调数量表达进度。

## 4. 教师图片建标：逐步拆解

### 4.1 上传、建任务和页级绑定（Java）

目标是建立不可歧义的业务上下文，而不是直接做 AI 推理。

1. 校验用户、来源、学科、年级、模板类型和上传文件。
2. 图片/PDF 存入对象存储，数据库保存稳定对象 key，而不是长期依赖临时签名 URL。
3. PDF 切页或按上传顺序建立 `labeling_image`，保存 `image_id`、`image_index`、宽高、旋转和原始文件哈希。
4. 创建总任务及每页 OCR 请求记录，生成 `request_id`、`trace_id`、`schema_version`。
5. 通过 outbox 可靠投递；仅当 broker confirm 成功后标记已发布。
6. 多页 OCR 可以并行，但汇总阶段必须等待全部必需页进入终态。

应补的校验：页码唯一且连续；同一任务中的图片属于同一模板；文件类型、像素、字节数和页数不超过限制；重复上传可按哈希幂等处理。

### 4.2 OCR 阶段不是“一次 OCR API”

当前 OCR 是一条级联系统。面试时可以按下列顺序解释：

1. **输入准备**：检查 task、图片引用、页 ID、旋转信息、调试目录和引擎配置。
2. **下载与标准化**：受控下载图片、解码、记录原始宽高；长边压到约定上限（代码中可见 2048 级别处理），所有缩放都形成变换矩阵。
3. **跳过策略**：根据调用来源和参数决定是否跳过矫正或去手写；两个能力必须使用独立开关。
4. **文档矫正**：调用 Quark 或相应视觉能力处理旋转、透视和卷曲，保存矫正图及原图→矫正图映射。
5. **是否含手写判断**：VLM 做二分类或轻量检测，避免所有图片都执行破坏性去手写。
6. **去手写**：需要时调用去手写能力，保留矫正但未去手写的版本，绝不覆盖原图。
7. **透背/阴影抑制**：降低背面文字和光照对 OCR 的干扰，同时做内容保真质量门。
8. **主 OCR**：TextIn 等 OCR 输出文字、公式、表格/图形类别和多边形坐标。
9. **阅读顺序修复**：处理双栏、题号与正文分离、跨行公式、页眉页脚和脚注顺序。
10. **统一 segment**：把供应商格式转换成稳定 `segment_id/type/text/polygon/page_id`。
11. **公式与特殊区域补识别**：对主 OCR 低质量的公式或局部裁剪调用 VLM/备用 OCR；表格和插图建立类型与父子关系。
12. **异常检测与降级**：当 segment 数、覆盖率、乱码率、空白率或置信度异常时，触发备用 Quark OCR，而不是仅以“结果是否为空”判断。
13. **去噪与重排**：过滤页眉水印等噪声，重新排序并保留每次删除/合并的 trace。
14. **坐标还原**：把矫正图/缩放图坐标通过矩阵还原到约定坐标系，并输出原始尺寸、处理尺寸和 `transform_version`。
15. **产物与指标**：输出处理图引用、segments、质量分、耗时、供应商、模型/prompt/预处理版本和调试 artifact 引用。

这里可能发生多次模型/API 调用，但它们主要解决图像质量、文字识别和坐标问题。优化重点不是粗暴合成一次 VLM，而是：规则先判是否需要某项处理；主路径低成本；异常才升级；所有破坏性处理都有质量比较和原图回退。

当前值得追查的实现点：`skip_rectification` 与 `has_handwriting_remover` 疑似被绑定；去手写只在“结果为空”时回退，无法发现局部文字被擦除。应增加字符/公式/连通域覆盖变化和 OCR 差异门禁。

### 4.3 stem parsing：从 OCR 块变成题目树

OCR 只知道“页面哪里有什么”，stem parsing 才决定“这些内容属于哪一道题”。其内部可拆为：

1. **输入归一**：加载每页处理图和 OCR segments；按页序排序；统一坐标；为页、segment 生成稳定短 ID。
2. **Stage 0：页内元素识别**：逐页 VLM 将 segment 归为材料、标题、大题、小题、选项、说明、图形等，并判断图片与文本关系。页面之间可并行。
3. **元素清洗**：规则消除明显重复、非法引用、孤立小块，合并被 OCR 拆碎的同行/公式。
4. **Stage 1：初始题目组装**：LLM 在一页或一个批次的元素上建立 `question -> stem/options/material/figure/blank` 结构。
5. **跨页连续性**：判断材料是否延续、上一页题目是否在下一页续写、题号是否重启；不能仅按每页独立结果拼接。
6. **题号提取与校验**：规则提取显式题号，检查重复、跳号和层级；LLM 只处理模糊情况。
7. **Stage 2：逐题裁剪复核**：按初始题目区域裁图，VLM 复核题干是否漏行、串入下一题、漏选项或漏图。
8. **Stage 3：空结构生成**：下划线、括号、方框、答题区先由规则/CV 检测；语义空或复杂题型再调用 LLM/VLM。
9. **类型与分值归一**：统一客观题、主观题、复合题、听力、连线、作图等枚举；分值缺失要标未知，不能臆造。
10. **题目位置生成**：题框通常来自相关 segment 多边形的并集、间距和版面边界，不是模型凭空生成坐标。
11. **空位置精修**：用线段、括号轮廓、文字基线等经典 CV 在局部 ROI 中找精确 blank polygon。
12. **特殊题后处理**：阅读材料共享、跨页题、作文大区域、图文题和多小问建立稳定父子关系。
13. **ID/坐标恢复**：把临时短 ID 映射回业务 ID，把坐标还原到原图或明确的标准图坐标。
14. **结构校验**：所有引用 ID 存在；同一 segment 不被不合理地归给多题；题框覆盖其必要元素；输出 schema 可被 Java 验证。

这几级调用并非每级都必须永久保留。应做消融实验：去掉逐题复核、仅对低置信题复核、规则空检测后不再调模型、把页内元素与初始组装合并。判断依据是题目边界 F1、跨页正确率、空召回、人工修改量、P95 和成本，而不是主观感觉。

### 4.4 answer parsing：从答案页抽取“教师给出的答案”

它和解题的事实来源不同：answer parsing 应忠实提取图片里的答案/解析，solving 才是在缺失时推导答案。

普通路径：

1. 输入 `question_list` 与答案页 OCR segments，保留页和 segment 稳定 ID。
2. 简化题目结构，只发送匹配所需的题号、题干摘要、blank ID，减少 token。
3. 建立 prompt，要求模型把答案、解析以及来源 segment ID 绑定到题/空。
4. 一次 LLM 调用完成抽取与匹配；对返回 JSON 做 schema、ID 和完整性校验。
5. 把短 ID 映射回原 ID；未匹配项保持空并附原因，不能自动猜到相邻题。

大输入分片路径已在代码中明确：**答案图片超过 5 页或总 blank 超过 200 个**时进入 split。

1. 用正则和版面规则寻找“1.”、“答案：”等 anchor 候选。
2. LLM 只负责把模糊 anchor 与 question ID 对应，减少全量上下文。
3. 按 anchor、页区间、题数和空数切成有界 chunk。
4. 并行调用各 chunk 的答案解析。
5. 按原题顺序合并，检查重复匹配、跨 chunk 遗漏与 ID 冲突。

可优化点：题号明确时用规则 `(题号, 小问号)` 直接匹配，LLM 只处理无题号、错序或跨页；输出应包含 `source_segment_ids` 和 `match_confidence`，从而能区分“原卷没有答案”和“系统没有匹配到”。

### 4.5 solving：仅为缺失项生成参考解

solving 不是再识别一次答案页，而是根据题干和图形推理。当前设计中已经存在“答案和解析完整则跳过模型”的合理优化。完整过程为：

1. 加载题目、关联图片、旋转和裁剪信息，为每题构造 `Record/BlankInfo`。
2. 教师明确指定的答案优先；其次使用 answer parsing 的参考答案；仅对缺失答案或解析求解。
3. 如果所需答案和解析均完整，或特殊作图题满足跳过条件，则直接复用，不调用模型。
4. 按学科、年级、题型、文本复杂度和是否依赖图片分流：听力、作文、连线/作图、几何、图文题、简单文本题、复杂推理题走不同路径。
5. 简单文本题选轻量模型；难题、图形题或首轮失败升级强模型/VLM。
6. 只裁剪并附加该题必要的材料、图和选项，避免整套卷重复发送。
7. 按题并发提交，但受全局并发、供应商限流、任务 deadline 和内存预算约束。
8. 单题调用先查版本化缓存，再调用主模型；超时或可恢复错误才走备用模型。
9. 结构化返回失败时先确定性修复；仅在内容正确但格式异常时使用 reformat 模型，不能无限“JSON 修复”。
10. 合并题级结果，严格区分 `specified/parsed/generated` 来源，生成答案不能覆盖教师答案。
11. 对化学式、比例、拼音、多答案、LaTeX 和特殊题型做确定性归一，同时保留原始模型文本。
12. 输出解答、解析、图示描述、来源、置信度、模型版本、token、耗时和错误信息。

当前默认等待上限可达到约 905 秒量级，说明仅有单次 RPC timeout 不够。需要 job deadline、每题 deadline、并发预算、剩余时间检查和部分成功策略。

### 4.6 labeling：当前是可删除的独立算法阶段

当前 Python `labeling` 实现基本是校验后原样返回 `question_list`，没有新增模型判断或图像处理。因此：

- 它没有独立算法信息增益；
- 却新增一次 MQ 发布、排队、序列化、回调、状态和失败面；
- 仓库本地日志抽样中也表现为近乎即时，和真正耗时的 stem/solving 明显不同。

建议删除独立 Python `labeling` 任务。solving 成功后 Java 进入“保存/发布题库”业务状态即可；前端仍可显示“正在保存题库”，但不需要为了显示状态调用一次空算法。

### 4.7 Java 最终入库

1. 校验结果 schema、任务版本和 request 状态。
2. 通过状态机条件更新，只允许一次 `PROCESSING -> SUCCEEDED/PARTIAL_SUCCESS/FAILED`。
3. 在一个受控事务中写题、空、位置、答案、解析和来源映射。
4. 使用 outbox 发布完成事件；重复回调不重复创建题或发送通知。
5. 低置信或部分失败进入人工复核，而不是全部失败或静默补全。

## 5. 学生图片批改：逐步拆解

### 5.1 提交与业务校验（Java）

1. 校验调用者是否有权批改该任务，模板是否处于可用版本。
2. 校验每张学生图的 `image_index/page_no` 唯一、页数与模板关系合理。
3. 校验所有图片指向同一个 `labeling_id`，不能在遍历中让最后一张图片覆盖前面的值。
4. 显式建立模板页与学生页配对，而不是分别查询两个无排序列表。
5. 创建 review task、review image、recognize request 和进度状态后可靠投递。

推荐消息直接携带：

```json
{
  "page_pair_list": [
    {
      "image_index": 1,
      "template_image_id": "...",
      "template_image_ref": "...",
      "student_image_id": "...",
      "student_image_ref": "...",
      "question_ids": ["..."]
    }
  ]
}
```

Python 当前用 `zip(template_image_list, student_image_list)` 配对，列表不等长会被静默截断，顺序不稳定会整页错配。这是最高优先级正确性问题。

### 5.2 recognizing：先回答“学生写了什么、写在哪里”

recognizing 不是单纯 OCR，而是模板结构、视觉语义和几何位置的融合：

1. 校验并按显式 page pair 读取模板图和学生图，记录原始宽高与页 ID。
2. 对学生图做方向/透视矫正，拒绝极端宽高比或明显错误页。
3. 按铅笔/钢笔、灰度和透背情况增强，但保留 immutable original 和变换矩阵。
4. 从建标结果取本页题、空和区域，为模型生成稳定短 ID。
5. 为每页构造最小必要 prompt 和题目裁剪，避免把全卷问题重复发送。
6. **语义分支 A**：判断题/空是否有作答；当前存在独立 VLM 调用。
7. **语义分支 B**：VLM 提取答案文本和所属题/空；校验返回数量和 ID，必要时备用模型降级。
8. **几何分支 A**：Quark/手写 OCR 输出学生笔迹文本及 polygon。
9. **几何分支 B**：将模板题框和空框配准到学生图，处理平移、缩放、旋转和局部形变。
10. **路由分支**：规则先把明显位于某题/空区域的 OCR segment 分配过去。
11. 对边界重叠、跨行、批注、涂改等模糊 segment，LLM/VLM 只做 keep/drop 和 blank mapping。
12. 合并 VLM 的语义文本与 OCR 的精确位置，不能让一侧静默覆盖另一侧；冲突要输出原因。
13. 多页并行完成后，检查错页、漏页、重复页和题目覆盖情况。
14. 保留 `raw_solution_text`；参考答案只用于生成 `normalized_solution_text`，并记录 `normalization_trace`，避免答案泄漏式纠正。
15. 将模板 question/blank polygon 映射到学生图，生成 `solution_list`、`solution_segment_list` 和逐题识别结果。
16. 处理图应由 Python 上传对象存储并返回 artifact ref，不应把整页 Base64 塞入 MQ 让 Java 再解码上传。

`has_answer` 和答案提取可能合成一次结构化 VLM 调用，因为答案提取本身可返回 `has_answer`。但必须比较空白页误报率、漏答率、成本和 P95；若独立二分类模型更轻且能显著减少昂贵提取调用，保留两步反而更快。

### 5.3 grading：再回答“依据什么标准得多少分”

1. 输入题库参考答案、解析、分值/评分规则、`solution_list`、证据 segments 和必要图片。
2. 拆分作文与普通题；对 prompt 使用短 ID，保留还原表。
3. 为每题构造最小 payload 和图像 crop，题级任务可并行。
4. **未作答规则**：识别结果明确为空时直接零分/未答，不调用大模型。
5. **确定性客观题**：选择、判断、固定数值等先做规范化后精确或容差比较；评语可异步或模板化。
6. **多参考答案/步骤题**：构造允许的解法组合、关键步骤和部分分规则。
7. 根据题型和证据决定文本 LLM 还是 VLM；只有答案包含图形、作图、连线或空间布局时才附图。
8. 调用主模型，做 schema、分值范围、总分一致性、引用步骤和 ID 校验；可恢复错误才走备用模型。
9. 必要的 recheck 应是独立验证者或规则校验，不能只是同一 prompt 重问后盲目采纳第二次。
10. 合并模型结果与确定性规则，生成 correctness、score、score_level、comment 和逐步得分。
11. 作图、连线、作文等进入专用子评分器；普通主观题保留证据到结论的映射。
12. 将评分步骤绑定到学生图 segments，支持前端框选与解释。
13. 对“有作答但模型漏返回”的题标记 `UNKNOWN/REVIEW_REQUIRED/PARTIAL_SUCCESS`，绝不能默认正确、满分、五星。
14. 清理 LaTeX 和展示文本，按原题序还原 ID，输出 token、耗时、模型和 prompt 版本。

recognizing 与 grading 分开的核心不是“多调用一次显得专业”，而是把**观察事实**和**依据标准做判断**分开。这样同一份识别结果可以重评、换 rubric、人工修正；同时避免参考答案过早进入识别 prompt，降低模型把学生错误答案纠正成标准答案的风险。

可以跳过或合并 grading 的情形：确定性客观题直接规则评分；简单题采用 `image-to-grade` 快路径。但即使一次调用直接输出答案和分数，也应在 schema 中分别保存 observed answer、evidence、judgment 和 confidence，逻辑边界不能消失。

### 5.4 特殊支线

**答题卡**：VLM/CV 找到题号、卡号、选项框和涂写；规则优先按 `(chapter_no, card_no)` 与题库匹配，只有错序、污损或题号模糊时使用 LLM。选择涂卡应优先用几何/像素规则，模型负责异常解释。

**作文**：先解析作文题目、体裁、字数和 rubric，再识别学生作文正文，最后按维度评分。作文 prompt 文件很大，必须拆分静态 rubric、动态题目和作文正文，记录各维 token；评分需有标定样本、维度一致性、超长截断策略和人工抽检。

## 6. “一次强模型一把出”为什么不天然更快、更准

### 6.1 总耗时模型

端到端耗时可以近似写成：

```text
T_total = Σ关键路径串行阶段(
    T_queue + T_download/serialize + T_preprocess
  + T_prompt_prefill + T_output_decode + T_retry
) + max(可并行分支) + T_database
```

分步会增加固定开销：更多 MQ 排队、状态写入、图片下载、序列化、重复上下文、模型 prefill、失败状态和契约维护。如果 5 个模型调用严格串行，且每次都重发整套试卷和长约束，整体当然可能更慢、更贵。

但一步式并不自动消除主要耗时：

- 多页高清图片会产生大量视觉 token；
- 一个超长 prompt 仍有高 prefill/TTFT；
- 一次输出整套题、坐标、答案和解析会产生很长 decode 时间；
- JSON 越大越容易截断、漏字段或 ID 串位；
- 一处失败要重跑全部，重试放大更严重；
- 失去按页/按题并行和简单题使用小模型的机会；
- 模型既看参考答案又认学生答案时，任务间会发生信息污染。

所以真正的比较是：

```text
一步式：固定往返少，但单次上下文/输出大、耦合强、失败重跑大
分步式：固定往返多，但可并行、可路由、可跳过、可局部重试
```

强模型提高能力上限，不会自动保证坐标精度、schema 完整、业务 ID 一致、可复现性或评分公平。生产质量来自任务分解、约束、验证器、证据链和评测。

### 6.2 当前代码的耗时信号

对仓库内本地日志做过粗粒度抽样，得到 OCR 中位约 6.75 秒、stem parsing 中位约 74 秒、solving 中位约 122 秒、recognizing 中位约 53 秒，而 `labeling` 中位约 0.01 秒；长尾可显著更高。这只能证明“耗时波动与阶段差异确实存在”，不能作为生产指标，因为日志混合了不同代码版本、缓存、调试运行，部分 `request_id` 为空，且配对方法是近似的。

在简历或面试中不能把这些数字说成线上 P95。正确做法是从统一 trace 记录真实线上 `queue_wait/preprocess/model/retry/persist/end_to_end` 后再给结论。

### 6.3 prompt 长到底影响哪一段

仓库中 recognizing、grading、question-card、essay-grading 等 prompt 文件达到数万字符，说明约束复杂；但**文件大小不等于单请求 token**，一个文件往往含多个分支模板。需要逐请求记录：

- 图片数量、分辨率或视觉 token；
- 静态 prompt token、动态题目 token、历史/样例 token；
- cache hit 与 cached input token；
- time to first token（主要观察输入预填充和排队）；
- output token 与 decode duration；
- 模型 RPC、重试/备用模型和 JSON reformat 次数；
- 每页、每题和整 job 的 P50/P95/P99。

优化顺序：

1. 先删无用字段、重复规则和对当前题无关的上下文。
2. 静态规则置于稳定前缀，利用供应商 prompt/prefix cache。
3. 使用短稳定 ID，结果还原时严格查表。
4. 按题裁图，低分辨率先行，坐标/公式不确定才升级高清 crop。
5. 只要求模型输出不能由代码推导的字段，坐标并集、排序、分数加总交给程序。
6. 使用强 schema、枚举和最大输出长度；复杂任务分块并行。
7. 规则/轻模型作为默认路径，强模型只处理困难样本。
8. 有条件地合并 `has_answer + extract_answer`；不要把所有任务合成一个巨型调用。

## 7. OCR 和多模态大模型的坐标准确性

用户的判断**方向正确，但表述需要更精确**：

- 传统文档 OCR/版面模型通常直接为文字行、公式、表格、图形输出像素级 polygon/bbox，适合作为几何事实源。
- 通用 VLM 也能输出 bounding box 或 point，并非“不能定位”；Gemini 官方图像理解文档和 Qwen2.5-VL 技术报告都明确支持视觉定位。
- 通用 VLM 的坐标常为归一化或离散 token，重复运行稳定性、细线/小空框、旋转透视页和密集排版上的精度未必满足精细批改。
- OCR 本身得到的是低层 segment 坐标，不会天然知道最终“题目框”和“答题空框”。当前项目的最终坐标来自 OCR/VLM 元素语义、stem grouping、规则/CV、跨页处理以及模板→学生图配准的组合。

因此面试时应说：

> 我们没有假设 VLM 不能输出坐标，而是把 OCR/CV 作为高精度、可复现的几何底座，把 VLM 用于题目归属和语义关系；是否替换要通过同一数据集的定位与下游批改指标验证。

当前仓库的解析 benchmark 更偏文本相似度、segment 集合和空数量，尚不足以证明“OCR 一定比 VLM 准”。需要补 A/B：

| 维度 | 指标 |
| --- | --- |
| 题框/空框检测 | precision、recall、F1 |
| 区域重合 | mIoU、IoU@0.5、IoU@0.75 |
| 边界误差 | 左/上/右/下像素误差，按原图尺寸归一 |
| 中心定位 | center-distance / 对角线 |
| 稳定性 | 同图重复运行坐标方差 |
| 端到端 | 模板→学生页配准成功率、答案归空准确率 |
| 工程 | P50/P95、单页成本、失败/重试率 |

至少比较 OCR+规则/CV、VLM 直接 grounding、混合方案三组，并按印刷体/手写、公式、表格、旋转透视、低清、密集小空分层。

## 8. 推荐目标形态：保留阶段，解耦进度与编排

### 8.1 短期低风险形态

暂时保留 Java 发起各高层阶段，先完成：

- 删除空 `labeling` 算法往返；
- 明确成功状态白名单，失败/部分成功不得自动推进；
- 统一 stage event；
- 消息只传对象引用；
- 页显式配对；
- 结果 schema、幂等、outbox、retry/DLQ；
- 记录阶段内部耗时和 token，找到真正瓶颈后再合并调用。

这条路径不会一次性重写架构，也能保留前端阶段反馈。

### 8.2 中期目标形态

```text
Java 创建业务 job + outbox
   |
   v
Python durable workflow / orchestrator
   |- OCR：按页 fan-out / join
   |- stem parsing
   |- answer parsing 与 solving：可并行/条件执行后 join
   |- recognizing：按页 fan-out / join
   `- grading：按题 fan-out / join
   |
   +--> 持续发布 stage events
   `--> 发布 final result/artifact refs

Java 消费事件，维护业务状态、持久化结果、供前端查询/推送
```

Java 仍是业务真相源；Python 拥有算法 DAG、模型路由、内部并行和局部重试。所谓 durable workflow 不一定要立即引入新平台，也可以先用数据库状态机实现，但必须支持 checkpoint、幂等、超时和恢复。

### 8.3 统一进度事件

```json
{
  "event_id": "uuid",
  "job_id": "...",
  "request_id": "...",
  "trace_id": "...",
  "schema_version": "1.0",
  "pipeline_version": "...",
  "stage_code": "STEM_PARSING",
  "state": "STARTED|PROGRESS|SUCCEEDED|PARTIAL_SUCCESS|FAILED",
  "page_done": 2,
  "page_total": 5,
  "question_done": 8,
  "question_total": 20,
  "attempt": 1,
  "elapsed_ms": 73000,
  "error_code": null,
  "occurred_at": "ISO-8601"
}
```

前端优先显示真实的“2/5 页、8/20 题”，不要伪造精确百分比。若需要百分比，用历史数据为阶段设置权重，并允许长阶段显示子进度。ETA 只在样本足够且带置信区间时展示。

## 9. 统一优化清单

### 9.1 P0：结果正确性、安全与消息不丢

| 编号 | 问题与代码事实 | 落地方案 | 验收证据 |
| --- | --- | --- | --- |
| P0-01 | 模板页与学生页分别查询后按 `zip` 配对；无序或长度不同会错配/截断 | Java 构造显式 `page_pair_list`；Python 校验一一对应、页数和 question 归属 | 打乱查询顺序、缺页、重复页测试均不串页，异常明确失败 |
| P0-02 | recognize 回调对非 7/8/9 状态也可能继续 grading | 仅 SUCCESS/PARTIAL_SUCCESS 白名单推进；其他终态停止；未知枚举拒绝 | 对每个状态做参数化测试，失败绝不触发下游 |
| P0-03 | grading 对“有作答但模型漏结果”存在默认正确/满分/五星的 fail-open | 改为 UNKNOWN/REVIEW_REQUIRED，分数不凭空生成 | 模型少返回一题时进入复核且不会得满分 |
| P0-04 | recognizing 把整页处理图 Base64 放入 MQ，Java 解码再上传 | Python 上传 artifact；MQ 只传 object key、尺寸、hash、过期策略 | 消息大小有上限；大图任务不触发 broker 大消息风险 |
| P0-05 | 提交 DTO 与业务关系校验不足，遍历图片时 `labelingId` 可被最后一项覆盖 | Bean Validation + ownership + all-same labeling + 页/题关系校验 | 跨模板混图、越权、重复页、空列表均被拒绝 |
| P0-06 | 去手写等破坏性预处理缺少局部内容损失检测 | immutable original、多视图、变换矩阵、OCR/连通域质量门和回退 | 构造擦除公式/标点样本，能检测并回退 |
| P0-07 | 仓库本地配置出现明文密钥 | 先轮换，再迁 Secret/Vault/受控配置；CI secret scan | 旧密钥失效，仓库和日志无有效凭证 |
| P0-08 | Java 结果消费者异常后仍可能在 `finally` ACK | 成功落库后 ACK；临时错误延迟重试；不可重试进 DLQ | DB 故障不丢结果，非法消息进入 DLQ且可重放 |
| P0-09 | DB 建任务与 MQ 发布存在双写空窗 | transactional outbox + publisher confirm + mandatory returns | broker 不可用、错路由、提交后崩溃均可恢复 |

### 9.2 P1：模型工程、恢复和性能

| 编号 | 优化项 | 关键要求 |
| --- | --- | --- |
| P1-01 | 原始识别与参考答案感知归一分离 | 保存 raw/normalized/trace，评分读取哪个版本必须明确 |
| P1-02 | 逐阶段不确定性传播 | OCR、配准、答案匹配、评分都有 confidence/reason；低置信进入复核 |
| P1-03 | Python 管算法 DAG，Java 管业务状态 | 迁移期间兼容现有阶段回调；进度事件不依赖 Java 重新发起每个内部步骤 |
| P1-04 | 强 schema 和契约 | JSON Schema/AsyncAPI 或 Protobuf；枚举、ID、分值范围、版本由 CI 契约测试 |
| P1-05 | deadline/并发/熔断 | job、stage、question 三级预算；剩余时间不足时部分成功；供应商级限流与熔断 |
| P1-06 | benchmark 变发布门禁 | overall + 学科/题型/图像质量切片；质量、P95、成本、失败率与基线比较 |
| P1-07 | prompt injection 防御 | OCR/学生文本始终作为不可信数据；固定系统规则、字段隔离、工具白名单、输出校验 |
| P1-08 | 图片下载安全 | 域名/协议白名单、超时、流式字节上限、MIME/魔数、像素和解压炸弹限制 |
| P1-09 | 全链路版本 | model、prompt、preprocess、OCR vendor、schema、cache key、pipeline 均可追溯 |
| P1-10 | Retry/Delay/DLQ 统一 | 主队列+指数退避延迟队列+DLQ；attempt 上限；DLQ 查询/重放/告警 |
| P1-11 | 数据库幂等 | request/event 唯一键、条件状态迁移、通知幂等；Redis 只作性能优化 |
| P1-12 | 按资源拆 worker | OCR/视觉、轻量解析、LLM/作文独立队列与 Deployment，可独立扩缩容/发布 |
| P1-13 | 控制 prefetch 和本地积压 | 当前高 prefetch 与无界本地队列需按 P95、内存和 HPA 压测调整 |
| P1-14 | 优雅终止 | 先 not-ready、停拉新任务、等待在途、超时释放未 ACK 消息；grace period 对齐任务上限 |
| P1-15 | 缓存键完整 | 多模态缓存必须包含实际图片内容/稳定 hash、prompt、response schema 和模型版本，不能只看文本 |

### 9.3 P2：可维护性、可观测性和隐私

| 编号 | 优化项 | 验收方向 |
| --- | --- | --- |
| P2-01 | 拆分超大算法模块 | 按 pipeline/adapter/validator/artifact 划分，仍保留端到端测试 |
| P2-02 | 契约、属性与故障注入测试 | 乱序、重复、缺页、超时、模型漏字段、进程中断、DB/MQ 故障可复现 |
| P2-03 | 日志最小化 | 生产仅记 ID、状态、大小、hash、耗时；不打印作文、答案、签名 URL 或整消息 |
| P2-04 | 统一健康检查 | ready 表示 consumer 真正连接；heartbeat 反映主循环；两类 Deployment 语义一致 |
| P2-05 | 端到端 trace 与 SLO | queue age/depth、unacked、stage latency、retry、DLQ、callback failure、质量漂移 |
| P2-06 | 学生数据生命周期 | 调试 artifact 加密、最小权限、访问审计和 TTL；数据集脱敏并有授权边界 |

## 10. Eval：从零散回放升级为发布质量系统

### 10.1 现状定性：有评测代码，不等于有评测体系

用户反馈的三个问题成立：修改不是每次都经过规范评测；测试集陈旧且规模小；执行依赖人工。代码审查还发现以下更具体的问题：

1. `assets/benchmark/samples.csv` 是默认回归输入，共 72 条非空 JSONL 记录；另外四个学科文件共 114 条，但默认脚本没有使用它们，文件之间是否重叠也没有 manifest 说明。
2. 所有默认样本都从 `desc` 推导为“整份全对”或“整份全错”，各 36 条；没有部分正确、漏答、涂改、答案写错位置、开放题多解等真实分布。
3. `replay_pipeline.py` 在运行当前算法后复制当前预测，再把 correctness/星级覆盖成全对或全错，生成 `.anno.json`。这不是独立人工标注的逐题真值，无法可靠评估学生答案文本、blank 归属、坐标和评分理由。
4. `regression_test.sh` 只执行 `bench_grading.py` 和 `bench_cost.py`，没有执行仓库已经存在的 `bench_parsing.py`；OCR、answer parsing、solving、recognizing 也没有独立门禁。
5. benchmark 只生成报告，没有接收 baseline 和准入阈值；没有样本时只是 warning 并 return，也可能以成功状态结束。因此“Job 跑完”不等于“质量通过”。
6. GitLab CI 的顺序是 `build -> deploy -> test`，回归只在 Web 手动触发、`dev` 环境、标准服务开启时运行。它是部署后检查，不是部署前阻断，更不能保护生产发布。
7. parsing benchmark 在无法匹配时会逐轮降低相似度阈值直到下限，这会让评测标准随输出改变，不能作为稳定 release gate。
8. 当前样本依赖业务 ID、开发环境接口和缓存数据，缺少不可变快照；上游数据变化、权限、缓存命中都可能让两次运行不可比。
9. 模型具有随机性，但当前主要跑单 trial；没有固定或记录 seed/temperature、缓存策略、模型快照，也没有置信区间和显著性判断。
10. 报告主要按年级+学科、blank type 汇总，缺少图像质量、版式、题型难度、跨页、手写类型、模型降级等关键切片。

所以当前成熟度应表述为：**具备端到端 replay、基础批改准确率和成本统计的雏形，但尚未形成可信 ground truth、持续评测、统计比较和发布门禁。**

### 10.2 主流工程范式及其对本项目的含义

公开的一线模型团队工程文档体现出相近范式：

- OpenAI 建议 eval-driven development、任务专项评测、从日志挖样本、自动化执行、每次变更持续评测，并用人类反馈校准自动评分；数据要覆盖典型、边缘和对抗场景。
- Anthropic 区分 capability eval 与 regression eval，组合代码、模型和人工 grader；由于模型非确定性，同一任务应有多个 trial；离线评测、生产监控、A/B 和人工复核共同覆盖风险。
- Google 的 judge model 文档要求用带人工评分的数据校准自动裁判，并查看 balanced accuracy、F1 和混淆矩阵，不能默认 LLM judge 自己就是标准答案。
- Microsoft 将部署前受控/合成数据评测与部署后真实会话/trace 评测分开，分别用于发布验证和生产质量监控。

映射到本项目就是：**阶段级 deterministic grader 为主，主观解题/评分才使用经教师校准的 LLM judge；离线 golden set 保护发布，线上真实流量持续产生新 case；每次变更都有可追溯实验，而不是临上线手工抽几题。**

### 10.3 评测目标：不是只问“准确率多少”

评测必须回答六类问题：

| 目标 | 要回答的问题 |
| --- | --- |
| 正确性 | 文字、题目结构、答案归属、分数是否正确？ |
| 完整性 | 是否漏页、漏题、漏空、漏模型返回？ |
| 安全性 | 是否串模板/串学生、把缺失当满分、泄露参考答案或越权？ |
| 稳定性 | 同一个输入多次执行是否稳定，失败是否可恢复？ |
| 性能成本 | P95/P99、token、调用数、每页/每题成本是否在预算内？ |
| 业务效果 | 教师需要改多少题、花多久修正、用户是否需要重传或申诉？ |

不能用一个加权总分隐藏 P0 错误。安全不变量先做 hard gate，之后才比较平均质量。

### 10.4 数据集不是一个文件，而是多套用途不同的 suite

| Suite | 数据来源和用途 | 执行频率 | 特点 |
| --- | --- | --- | --- |
| Contract/Smoke | 历史 P0/P1 故障、协议边界、最小题型 | 每个 MR/提交 | 20～50 个快速、确定性 case；几分钟内完成 |
| Golden Regression | 教师双审后的真实生产样本 | 每个候选版本、Prompt/模型变更 | 保护已经做对的能力，准入率应接近 100% |
| Capability/Challenge | 当前做不好的难例、长尾和新题型 | 每日/每周 | 用于爬坡，不要求一开始高通过率，不直接和回归集混算 |
| End-to-End Job | 完整教师卷+答案页+多名学生作业 | 发布前 | 从上传快照跑到最终题库/分数，测错误传播和业务结果 |
| Judge Calibration | 教师独立评分与仲裁结果 | judge/rubric 变更时 | 只用于校准 LLM judge，不参与 prompt 调优 |
| Rolling Production | 脱敏随机流量、投诉、人工修正、低置信任务 | 每日采样、周期标注 | 监控分布漂移并补充新失败模式 |
| Robustness/Safety | 错页、缺页、重复页、恶意文字、超大图、超时和故障注入 | 发布前/定期 | 验证 fail-closed、资源限制、幂等和恢复 |

**Regression 与 capability 必须分开。** 已修复的典型问题进入 regression，保证不复发；尚未解决的困难样本进入 capability，观察提升。把二者混在一个总分里，会出现“新增大量简单题后总分上升，但旧问题回归”的假象。

### 10.5 数据从哪里来

推荐组合而不是单一来源：

1. **真实随机样本**：按生产业务分布随机抽取，估计真实平均水平。
2. **失败挖掘**：用户投诉、教师改分/改题、重传、人工复核、低置信、模型 fallback、超时和 schema 失败自动进入候选池。
3. **分层补齐**：对生产中少见但高风险的跨页、密集小空、透视、低清、公式、图表、连线、作文等过采样。
4. **合成扰动**：在有真值的原图上生成旋转、模糊、压缩、阴影、裁边、透背、噪点和页序扰动，用于鲁棒性测试；合成数据不能替代真实数据。
5. **规则生成负例**：缺页、重复页、模板/学生错配、非法 ID、模型漏返回、重复 MQ 消息和恶意 OCR 文本。

报告同时给两组结果：

- **production-weighted micro 指标**：按真实流量权重回答“总体用户体验怎样”；
- **slice macro/最差切片指标**：各学科、题型和图像条件分别汇总，回答“是否牺牲了少数关键场景”。

### 10.6 覆盖矩阵：这个项目必须有哪些样本

| 维度 | 最少覆盖内容 |
| --- | --- |
| 学段/学科 | 小学/初中/高中；语数英、物理、化学及真实上线科目 |
| 题型 | 选择、判断、填空、计算、证明、阅读、完形、翻译、听力占位、连线、作图、实验、作文 |
| 答案状态 | 全对、全错、部分对、漏答、多答、涂改、答案写错区域、过程对结果错、结果对过程错 |
| 题目结构 | 单页、多页、跨页材料、嵌套小问、共享材料、双栏、表格、图文、无题号/跳号 |
| 图像条件 | 高清、低清、旋转、透视、阴影、透背、裁边、折痕、压缩、反光、铅笔浅字、红笔批注 |
| 版面几何 | 密集小空、下划线、括号、方框、大答题区、坐标图、公式、表格和插图 |
| 工作流异常 | 缺页、重复页、乱序、错模板、学生图数量不一致、模型超时/漏字段、缓存 miss/hit、重复消息 |
| 安全隐私 | OCR prompt injection、超大文件、伪造 MIME/URL、越权对象引用、日志敏感字段 |

每个 case 使用多标签，而不是只写一个 `desc`。这样才能定位某次改动到底伤害了“高中数学公式+透视”还是普遍退化。

### 10.7 真值结构与标注规范

一条完整端到端样本至少保存：

```json
{
  "case_id": "immutable-id",
  "dataset_version": "2026.09.v1",
  "split": "regression|capability|judge_calibration",
  "artifact_refs": {
    "teacher_original_pages": [],
    "answer_pages": [],
    "student_original_pages": []
  },
  "metadata": {
    "subject": "math",
    "grade": "junior_3",
    "question_types": [],
    "image_conditions": [],
    "risk_tags": []
  },
  "ground_truth": {
    "ocr_segments": [],
    "question_tree": [],
    "teacher_answers": [],
    "student_observations": [],
    "grading_items": []
  },
  "annotation": {
    "guideline_version": "...",
    "annotator_ids": [],
    "adjudicator_id": "...",
    "agreement": {},
    "updated_at": "ISO-8601"
  }
}
```

标注原则：

1. 原图和标注不可被被测 pipeline 覆盖，所有坐标明确坐标系和图像 hash。
2. 客观题可由一名标注者+规则校验+抽检；结构解析、开放题和作文至少两名教师独立标注，分歧由第三人仲裁。
3. 分类统计 Cohen's kappa/一致率；星级/等级可用 weighted kappa；连续分数报告 MAE 和教师间差异，先建立“人类一致性上限”。
4. 标注规范明确等价答案、单位、近似值、步骤分、多个合法解、空白、涂改、无法判断和需复核。
5. LLM 可以预标但不能直接成为 gold；教师必须确认。LLM judge 必须在独立校准集上与教师比较。
6. 数据脱敏、最小权限、访问审计和 TTL；训练集、prompt 开发集、judge 校准集、最终 holdout 严格隔离。

### 10.8 每个阶段怎么评

#### OCR 与预处理

- 文本 CER/WER，公式规范化 exact match/符号错误率；
- segment 检测 precision/recall/F1，reading-order accuracy；
- bbox/polygon mIoU、IoU@0.5/0.75、边界与中心误差；
- 去手写后的印刷内容保留率、公式/标点擦除率；
- 矫正成功率和原图→处理图坐标还原误差；
- 单页耗时、供应商失败率、fallback 率和成本。

#### Stem parsing

- 题目数量 precision/recall/F1，题干归一化字符 F1；
- 材料、题、选项、图、小问父子关系准确率；
- blank 数量、blank 类型和 ID 匹配 F1；
- 跨页连续、双栏阅读顺序、图文绑定准确率；
- question/blank polygon IoU；
- 结构 schema 成功率、人工改题数和修正时间。

现有 `stem/segment/blank` 加权均值可作为诊断项，但不能继续在失败时自动降低匹配阈值。匹配算法与阈值必须固定并版本化。

#### Answer parsing

- 教师答案抽取 exact/equivalence accuracy；
- answer→question/blank 的 precision/recall/F1；
- 解析文本与 `source_segment_ids` 的证据覆盖率；
- “原卷无答案”和“系统漏匹配”的区分准确率；
- 跨页、错序、多答案和超过 5 页/200 blanks 分片路径的合并正确率。

#### Solving

- 最终答案 exact/equivalence accuracy；
- 多空、多解、单位、数值容差和公式规范化正确率；
- 教师答案保留率必须为 100%，模型不得覆盖 specified answer；
- 解题过程按 rubric 检查关键步骤、事实错误和自相矛盾；
- 已有答案时的 skip 率、简单题轻模型路由准确率、fallback 收益；
- 题级 P95、超时率、token 和成本。

#### Recognizing

- `has_answer` 混淆矩阵，尤其漏答和把空白认成作答；
- `raw_solution_text` 的字符/公式/语义准确率；
- answer→blank 路由 precision/recall/F1；
- 学生笔迹 polygon IoU 与模板→学生配准成功率；
- 参考答案感知规范化的错误纠正率，即把学生错答改成标准答案的比例；
- 错页、缺页和不等长 page pair 检出率必须为 100%。

#### Grading

- correctness confusion matrix，不只报告 accuracy；
- **错误答案召回率**与“错判为对”的 false-positive rate 单独作为关键门禁；
- 正确答案召回率，避免过度严格；
- 分数 MAE、分数分布偏差、等级 weighted kappa；
- 部分分、步骤分和多个参考解的一致性；
- 评语是否引用真实学生作答、是否与分数矛盾；
- 有作答但模型漏结果率必须单列，默认满分事件必须为 0；
- 与两名教师及仲裁结果的 agreement，并按题型切片。

#### 端到端与系统工程

- job 完成率、partial success、静默失败率和人工复核率；
- 全卷 exact success：页、题、空、答案和分数是否全部满足不变量；
- 教师平均修改题数、改分数、修正时长、学生申诉/重传率；
- 页串位、学生串位、越权、重复记分、漏消息事件必须为 0；
- E2E 与 stage P50/P95/P99、queue wait、TTFT、decode、重试、token、人民币成本；
- 故障注入后的恢复时间、重复计算范围和幂等结果。

### 10.9 Grader 选择：能用代码判的，不先用 LLM

| 任务 | 首选 grader | 原因 |
| --- | --- | --- |
| schema、ID、页数、分值范围、坐标 | 代码/规则 | 快、稳定、能阻断 |
| 客观题等价答案 | 符号归一+领域规则 | 避免 judge 随机性 |
| bbox、分割、配准 | 几何指标 | 有明确数值真值 |
| 开放题解答完整性 | 教师 rubric + LLM judge | 允许多种合法表达 |
| 作文质量/评语 | 多维 rubric、教师校准的 judge | 主观但可分维度约束 |
| 候选模型质量比较 | 盲测 pairwise + 教师抽检 | LLM 更擅长比较而非无锚点打分 |

LLM judge 的约束：不得使用与被测模型完全相同的输出作为真值；A/B 顺序随机并隐藏模型名；每个维度单独 rubric；允许输出 `UNKNOWN`；记录 judge 模型/prompt；在教师校准集上报告 balanced accuracy、F1、混淆矩阵和偏差；达不到约定一致性就不能用于自动 gate。

### 10.10 样本规模与统计：100 题能守底线，但证明不了小幅提升

样本规模由要检测的退化幅度和独立样本单位决定。若准确率约 90%，把每个样本粗略视作独立，则 100 个样本的 95% 置信区间半宽约为 5.9 个百分点；要把半宽压到约 2 个百分点需要约 865 个独立样本，约 1 个百分点需要约 3458 个。实际同一份作业内各 blank 相关，有效样本量会更低。

因此：

- 旧的 72/约 100 条可以先变成固定 smoke/regression，守住明显回归；
- 不应声称它能判断 1%～2% 的小幅提升；
- 新旧版本必须在**同一批 case 上配对比较**，用 paired bootstrap 给差值置信区间；正确/错误二分类可补 McNemar 检验；
- 报告 case/job 级 bootstrap，避免把同卷大量 blank 当成完全独立而虚高显著性；
- 对不稳定 LLM case 做多 trial。用户每次只得到一次结果的批改产品重点看 pass@1 和 pass^k/多次一致率，不用“多试几次总有一次对”的 pass@k 掩盖不稳定。

具体样本量应在首轮标注后根据基线、方差、目标退化界限和教师标注成本做 power analysis，而不是拍脑袋定成“1000 题”。

### 10.11 发布门禁：先评测，再部署

推荐流水线：

```text
MR/Prompt/模型配置变更
 -> unit + contract + schema + smoke
 -> 构建候选镜像（固定 digest）
 -> 阶段级离线 eval
 -> 完整 E2E golden eval
 -> 比较 champion vs challenger
 -> quality/cost/latency gate
 -> 部署 dev shadow
 -> canary + 线上护栏
 -> 扩量或自动回滚
```

门禁分三类：

1. **Hard invariant**：页/学生错配、越权、缺失结果默认满分、schema 不合法、题目/空 ID 串位、敏感信息泄漏，出现一次就阻断。
2. **Non-inferiority**：整体和关键切片相对 champion 的质量差值下界不得超过团队设定的容忍区间；关键切片不能靠其他简单样本抵消。
3. **Budget**：P95/P99、timeout、fallback、单 job 成本和调用量不得越过预算；质量显著提升时可走有审批的例外流程。

门槛值应在可靠 baseline 后由产品、算法和业务共同冻结，不能在看到 candidate 结果后临时调低。报告必须让脚本以非零退出码阻断 CI；无样本、样本缺失、grader 异常也必须 fail closed。

变更影响矩阵：

| 变更 | 必跑 suite |
| --- | --- |
| OCR/预处理 | OCR + parsing + recognize + E2E |
| stem prompt/规则 | parsing + answer parsing + solving + E2E |
| answer parsing | answer parsing + solving + grading + E2E |
| solving/model | solving + grading + E2E |
| recognizing | recognize + grading + E2E |
| grading rubric/prompt | grading + judge calibration + E2E |
| 模型版本/全局 RPC/cache | 所有 stage + E2E + latency/cost |
| MQ/编排/schema | contract + fault injection + E2E |

### 10.12 基线与实验记录

每次 eval run 必须生成不可变 manifest：

```text
run_id / commit_sha / image_digest
pipeline_version / schema_version / dataset_version
model provider + exact snapshot / temperature / seed
prompt hash / preprocess version / OCR vendor version
cache policy and hit rate / concurrency / environment
per-case output + stage trace + grader version
quality metrics + confidence intervals
latency/token/cost/failure metrics
gate decision + approver + artifact location
```

champion 与 challenger 使用同一数据、同一机器/限流条件和同一缓存策略。需要测真实成本时两边都冷缓存；需要测生产体验时再分别报告预热缓存结果，不能让一边命中旧缓存、一边冷启动。

### 10.13 用 Eval 回答“一步式还是分步式”

建立四组候选：

| 方案 | 描述 | 目的 |
| --- | --- | --- |
| A 当前基线 | 当前分阶段与当前 prompt | 建立真实质量、耗时、成本基线 |
| B 一步式基线 | 强 VLM 一次输出题目/答案或识别/评分 | 验证“一把出”而非口头争论 |
| C 优化分步 | 规则先行、短 prompt、按页/题并行、难例升级、删除空阶段 | 推荐生产候选 |
| D fast path | 小页数、版式简单、客观题为主时减少复核/模型调用 | 降低简单任务等待时间 |

同一套 case 同时统计阶段质量、最终业务质量、人工修正、长尾、成本、schema/漏题/错配和故障重跑范围。合并调用的准入标准是：质量不退化，长尾或成本有明确收益，错误仍可定位，失败不会扩大重跑范围。只降低调用次数但增加总 token、输出截断或人工修改，不算优化。

### 10.14 线上持续评测闭环

离线通过不代表结束。生产侧应形成：

```text
真实任务/教师修正/投诉/低置信/异常
 -> 脱敏与风险打标
 -> 抽样进入待标注池
 -> 教师标注和仲裁
 -> capability 或 regression suite
 -> 修复与离线回归
 -> shadow/canary
 -> 监控与再次回流
```

线上不一定有即时 ground truth，所以分开监控：

- 即时代理指标：schema failure、unknown、人工复核、fallback、重试、页不匹配、耗时和成本；
- 延迟业务真值：教师改题/改分、学生申诉、重新上传、人工抽检 agreement；
- 分布漂移：学科/题型/页数、图片清晰度、手写类型、OCR 置信度、模型路由比例；
- 大版本在无用户影响的 shadow 中与 champion 对比，通过后小流量 canary，关键错误或 SLO 越界自动回滚。

数据集维护要有明确 owner。每个线上 P0/P1 都必须先固化为可复现 case 再关闭；定期淘汰重复、失效和泄漏样本，保留固定 hidden holdout，避免团队围绕公开 regression 反复调 prompt 导致过拟合。

### 10.15 分阶段落地计划

**第一阶段：两周内建立最低发布底线**

1. 冻结现有 72 条和其他可用样本，去重并生成 manifest；不再从当前预测生成真值。
2. 教师复核 correctness/score，补部分正确和高风险历史 case。
3. 修复脚本：无样本/异常失败；输出机器可读 metrics；固定阈值；非零退出阻断。
4. 将 test 移到 deploy 前，所有生产候选强制运行；先接 smoke 和现有 grading/cost。
5. 加入 P0 hard invariants：错页、漏结果满分、非法 ID、越权、重复结果。

**第二阶段：建立阶段级可诊断 Eval**

1. 定义统一 case schema、坐标系和标注规范。
2. 补 OCR、parsing、answer parsing、solving、recognizing、grading 独立 grader。
3. 从真实修改/投诉中标注第一版 golden set；增加关键 slice dashboard。
4. champion/challenger 配对运行，报告置信区间、性能和成本。

**第三阶段：生产闭环和模型迭代能力**

1. trace、教师修正和低置信任务自动进入候选池。
2. 建 judge calibration suite，教师定期复核 LLM judge。
3. shadow/canary/rollback 与质量监控打通。
4. 根据 power analysis 扩大独立样本量，维护 regression、capability 和 hidden holdout。

面试中必须诚实区分：“项目当时做到 replay 和基础准确率/成本报告”与“我基于复盘设计或后来落地了 release gate”。只有真正修改代码、补标数据并接入 CI 后，后者才能写成已完成成果。

## 11. 面试官会如何挑战这个项目

### 11.1 架构与 MQ

1. 为什么不用 Java 同步调用 FastAPI？什么请求适合同步？
2. 为什么不需要单独 HTTP→MQ 转发服务？何时才需要 AI Gateway？
3. DB 已提交但 MQ 没发出去如何处理？结果消息落库失败为何不能 ACK？
4. MQ 至少一次投递下如何防止重复创建题、重复记分和重复通知？
5. 毒消息如何退避、进入 DLQ、人工重放？
6. 为什么 RabbitMQ 足够，何时 Kafka 的可回放事件流更合适？
7. 一个 Pod 为什么不应预取过多长任务？如何用 queue age 和 P95 扩容？

### 11.2 图像与 OCR

1. 原图、矫正图、去手写图、OCR 坐标分别属于哪个坐标系？如何还原？
2. 如何证明去手写没有擦掉印刷公式、标点和下划线？
3. OCR 和 VLM 坐标谁更准？测试集和 mIoU 数据在哪里？
4. 双栏、跨页材料、题目续写、图文题如何建立结构？
5. OCR 供应商切换后如何保证 segment schema 和回归质量？

### 11.3 模型工作流

1. stem parsing 为什么要多级模型？去掉其中一级会怎样？
2. answer parsing 和 solving 为什么不能合并？教师答案与生成答案如何标来源？
3. recognizing 为什么要语义与几何两条分支？冲突由谁裁决？
4. 为什么识别与评分要拆开？如何防止参考答案污染识别？
5. 强模型一步式是否更快？输入 token、输出 token、并行和重试如何计算？
6. prompt 为什么这么长？哪部分是静态规则、动态题目、图片 token？是否命中缓存？
7. 模型漏字段、JSON 截断、超时、限流、主备答案冲突怎么处理？
8. 哪些题完全不需要 LLM？规则优先能省多少成本且不降质量？

### 11.4 评分可信度与评测

1. 模型没有返回某题，为什么绝不能默认满分？
2. 客观题、步骤题、作图题、作文分别怎样评分和校准？
3. 如何衡量人工老师一致率、误判率、漏判率和分数偏差？
4. 上线前 release gate 是什么？线上漂移如何检测？
5. 低置信题如何进入人工复核，复核结果如何回流评测集？
6. prompt/model/preprocess 版本变化后，历史结果如何重放与解释？

### 11.5 建议的回答骨架

> 我们把阶段边界和模型调用边界分开设计。阶段边界服务于进度、检查点、证据和局部恢复；模型调用是否拆分则由信息增益、质量、P95 和成本实验决定。当前 OCR/CV 负责稳定几何，VLM 负责语义分组；答案识别保存观察事实，评分单独读取 rubric，避免参考答案污染。MQ 适合分钟级任务，但必须配套 outbox、confirm、幂等、retry/DLQ 和统一进度事件。我们还会以一步式强模型作为基线，而不是假设它一定好或坏。

## 12. 推荐实施顺序与每项证据

### 第一阶段：先阻止静默错结果

1. 页显式配对与缺页校验。
2. 回调成功状态白名单。
3. 删除评分默认满分 fail-open。
4. 提交身份/所有权/模板一致性校验。
5. 去手写质量门和 immutable original。

### 第二阶段：确保任务和证据不丢

1. 轮换明文密钥，完成日志脱敏。
2. 修复 ACK；建立 retry、DLQ 和重放。
3. outbox + publisher confirm + returns。
4. 业务幂等和版本化消息契约。
5. Base64 改对象存储 artifact ref。

### 第三阶段：形成模型工程闭环

1. 统一 trace、阶段耗时、token、重试、模型/prompt/preprocess 版本。
2. 坐标、题目结构、答案识别、评分四类 benchmark。
3. current vs one-shot vs optimized-staged vs fast-path 实验。
4. 规则优先、难例升级、结构化输出和不确定性复核。
5. release gate、shadow/canary 和回滚策略。

### 第四阶段：减少编排与资源耦合

1. 删除空 labeling 阶段和无信息增益调用。
2. 完善 progress event，让前端进度不再依赖跨服务往返数量。
3. Python 工作流接管内部 DAG；Java 保留业务状态和最终入库。
4. 按 OCR/视觉、轻量解析、LLM/作文拆 worker，压测 prefetch、并发和优雅终止。

每一项修改都要留下：问题样例；修改前后代码/设计；自动化测试；同一数据集质量对比；P50/P95/P99；成本；故障演练；监控面板或日志检索证据。没有这些证据，就只能说“做过”，很难在面试中证明“做对了”。

## 13. 代码证据索引

- Java 建标阶段投递：`hp-grading-service/.../HomeworkLabelingTaskImpl.java` 中 OCR、stem parsing、answer parsing、solving、labeling 的连续任务与回调。
- Java 识别回调和状态推进：`hp-grading-service/.../RecognizeTaskImpl.java`。
- Java 评分结果和阶段事件：`hp-grading-service/.../GradingTaskImpl.java`。
- 提交参数和模板关系：`ReviewTaskSubmitDTO.java`、`ReviewManagerImpl.java`。
- 页面查询顺序：`LabelingImageRepositoryImpl.java`、`ReviewImageRepositoryImpl.java`。
- OCR 主流程：`x_edu_ai/libs/ocr/api.py`。
- stem parsing：`x_edu_ai/libs/stem_parsing/api.py` 及相关实现。
- 答案解析分片阈值：`x_edu_ai/libs/answer_parsing/api.py`，`len(image_list) > 5 or blank_count > 200`。
- solving 路由、跳过与 timeout：`x_edu_ai/libs/solving/solver.py`、`utils.py`。
- no-op labeling：`x_edu_ai/libs/labeling/api.py`。
- 页配对、识别与 Base64 回传：`x_edu_ai/libs/recognizing/api.py`。
- 评分缺失结果补偿：`x_edu_ai/libs/grading/impl.py`。
- 多模态缓存键：`x_edu_ai/libs/common/rpc_ops.py`。
- 现有效果脚本：`x_edu_ai/regression_test.sh`、`x_edu_ai/regression-job.yaml.template`、`x_edu_ai/benchmark/bench_parsing.py`、`bench_grading.py`、`bench_cost.py`。
- CI 执行顺序与触发条件：`x_edu_ai/.gitlab-ci.yml`。
- 默认样本与其他学科样本：`x_edu_ai/assets/benchmark/*.csv`（内容实际为逐行 JSON）。

外部工程参考：

- [Gemini API：Image understanding](https://ai.google.dev/gemini-api/docs/image-understanding?authuser=4)：支持归一化 bounding box 输出。
- [Qwen2.5-VL Technical Report](https://arxiv.org/abs/2502.13923)：描述 bounding box/point 视觉定位能力。
- [OpenAI：Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)：eval-driven development、真实任务分布、持续评测与人工校准。
- [Anthropic：Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)：capability/regression 分离、多 trial、多类 grader、生产监控与人工评测组合。
- [Google Cloud：Evaluate a judge model](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/evaluate-judge-model)：用人工评分校准 judge，并检查 balanced accuracy、F1 和混淆矩阵。
- [Microsoft Foundry：Run evaluations](https://learn.microsoft.com/en-ie/azure/foundry/how-to/evaluate-generative-ai-app?view=foundry)：部署前受控评测与部署后真实 trace 评测。

## 14. 逐项核对表

| 编号 | 负责人 | 决策 | 方案/PR | 离线结果 | 性能结果 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| P0-01 |  |  |  |  |  | 待核对 |
| P0-02 |  |  |  |  |  | 待核对 |
| P0-03 |  |  |  |  |  | 待核对 |
| P0-04 |  |  |  |  |  | 待核对 |
| P0-05 |  |  |  |  |  | 待核对 |
| P0-06 |  |  |  |  |  | 待核对 |
| P0-07 |  |  |  |  |  | 待核对 |
| P0-08 |  |  |  |  |  | 待核对 |
| P0-09 |  |  |  |  |  | 待核对 |
| EVAL-01 冻结、去重并版本化现有数据 |  |  |  |  |  | 待核对 |
| EVAL-02 制定标注规范并建立独立人工真值 |  |  |  |  |  | 待核对 |
| EVAL-03 设计统一 case schema 与不可变 artifact |  |  |  |  |  | 待核对 |
| EVAL-04 补齐六个阶段及 E2E grader |  |  |  |  |  | 待核对 |
| EVAL-05 区分 smoke/regression/capability/holdout |  |  |  |  |  | 待核对 |
| EVAL-06 增加配对比较、置信区间与多 trial |  |  |  |  |  | 待核对 |
| EVAL-07 把质量门禁移动到 deploy 前并 fail closed |  |  |  |  |  | 待核对 |
| EVAL-08 建立变更影响矩阵和必跑 suite |  |  |  |  |  | 待核对 |
| EVAL-09 建立教师校准的 LLM judge |  |  |  |  |  | 待核对 |
| EVAL-10 建立线上失败挖掘、shadow/canary/回流 |  |  |  |  |  | 待核对 |
| EVAL-11 数据脱敏、权限、审计和生命周期 |  |  |  |  |  | 待核对 |
