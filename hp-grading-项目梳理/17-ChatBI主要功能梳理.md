# ChatBI 项目主要功能梳理

> 梳理范围：`hp/chatbi` 当前仓库代码；更新时间：2026-10-12。本文描述代码中能核实的功能，不代表所有接口均已在生产环境启用，也不代表个人负责范围。

## 一句话定位

ChatBI 是慧批体系中的**作业与学情分析服务**：接收作业定标、学生提交和批改结果，按题目、学生、班级、学校及区域汇总统计，生成教师和学生可看的分析数据、周报与部分 AI 建议，并提供看板、导出和补算接口。

代码里的“ChatBI”主要指结构化统计和报告服务。当前没有查到让用户用自然语言提问、自动生成 SQL 查询或 Agent 自主调用工具的业务入口。

## 主要功能总览

| 功能 | 面向谁 | 主要产出 |
| --- | --- | --- |
| 单次作业分析 | 教师、学生 | 题目正确情况、学生完成情况、作业总览、学情状态 |
| 知识点与学科素养分析 | 教师、学生 | 知识点掌握情况、薄弱项、学科素养分布 |
| 作业 AI 建议 | 教师、学生 | 教学建议、学习建议；结合已计算的统计结果生成 |
| 班级周报 | 教师 | 按班级、学科、时间段汇总作业、学生、知识点及教学建议 |
| 学生周报 | 学生、家长、教师 | 分学科与总体表现、前后周变化、班级排名、学习建议 |
| 分数统计与排名 | 教师、学生 | 得分分布、优秀/及格等分层、排名、与上次作业的分数变化 |
| 作文作业分析 | 教师 | 成绩和字数分布、评分维度统计、AI 总结及报告查询 |
| 学校与区域看板 | 管理者 | 使用情况、作业量、提交情况、班级/教师/学校统计与趋势 |
| 报告与推荐练习册 | 教师、学生 | 周报 PDF、知识点推荐题练习册、学校看板 Excel 导出 |
| 异步统计与补算 | 运维/内部系统 | 批改事件触发分析、定时汇总、聚合数据、手动重算 |

## 1. 单次作业分析

批改结果到达后，服务取得作业、学生作业、题目定标及批改记录，计算**作业总览、逐题统计、逐学生统计**。总览包含应交/已交人数、题目数、作答记录正确与错误数量及比例；逐题包含题号、正确/错误数量与比例；逐学生包含提交状态、正确与错误记录、得分和个人分析。教师和学生分别通过学情接口读取对应视角。部分有分数的作业还计算总分、平均得分和得分率。

主分析任务在代码中限定于普通作业 `HW`、周测 `WT`、答题卡 `ANSWER_CARD` 和 `QA`；不能把该接口描述成覆盖所有作业类型。学生错题统计使用的是已经产生的批改记录，这里的“正确率”是**学生作答正确情况的业务指标**，不是定标或批改算法的评测准确率。

代码入口：[单次作业分析接口](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/controller/HwAnalysisController.java)、[统计任务](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/task/impl/HwAnalysisTaskImpl.java)、[教师/学生学情组装](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/manager/impl/HwAnalysisManagerImpl.java)。

## 2. 知识点、学科素养和薄弱项

服务利用题目定标关联的知识点/学科素养标签，把逐题批改结果归集到知识点和素养维度，形成教师侧分布和学生侧掌握情况。作业学情、班级周报及学生周报会复用这些结构化结果。还有按学生与作业范围查询薄弱知识点的接口，供其他系统使用。

学生周报任务也有“当周薄弱知识点推送”：它按知识点掌握情况排序，并对达到代码中筛选条件的学生发送到上游集成接口；这与用户随时查询薄弱点是两条不同路径。

代码入口：[作业分析任务](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/task/impl/HwAnalysisTaskImpl.java)、[薄弱知识点查询](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/manager/impl/WeakKnowledgePointManagerImpl.java)、[学生周报任务](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/task/impl/StudentWeekAnalysisTaskImpl.java)。

## 3. 教师与学生 AI 建议

系统先完成统计，再把知识点、学科素养、作业/周报数据组织成提示词，通过消息队列异步请求大模型。代码按四类处理：**单次作业教师建议、单次作业学生建议、班级周报教师建议、学生周报学习建议**。生成结果回写到已保存的分析记录，供报告接口读取。单次作业的建议生成还有作业类型、标签覆盖情况等触发条件，因此不是每份作业都必然生成 AI 建议。

LLM 调用封装在服务内，并记录模型调用相关信息；大模型负责文字建议，基础计数、排名、得分率等由业务代码计算。周报建议按预期 JSON 结构解析，失败时有一次重试；这只能说明代码设计了有限重试，不能推断线上建议永不失败。

代码入口：[建议消息消费者](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/mq/AdviceMessageListener.java)、[模型调用封装](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/utils/LLMUtil.java)。

## 4. 班级周报

按**班级、学科、日期范围**汇总该时段内的作业和学生数据，生成完成/提交情况、正确情况、分数表现、知识点与学科素养分析，并按学生表现形成关注信息。报告接口提供班级周报总览、作业明细与报告详情；AI 进一步生成作业、周测、知识点和重点学生等教学建议。

周报任务处理既有分析记录时会保留已有建议字段，然后异步生成新建议。定时任务的 handler 使用上一个自然周的时间范围；实际触发时间由外部调度配置决定。

代码入口：[班级周报接口](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/controller/ClassWeekAnalysisController.java)、[周报汇总任务](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/task/impl/ClassWeekAnalysisTaskImpl.java)、[周报调度入口](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/schedule/WeekAnalysisServiceSchedule.java)。

## 5. 学生周报

按**学生、学科、日期范围**汇总该生作业，既生成单学科周报，也生成多学科总体数据。报告包含提交与异常情况、做题正确情况、得分与知识点掌握、学科素养、学习建议，并与上周进行正确率、掌握率、评级和班级排名等比较。代码针对作文、听写/默写等作业类型有单独的数据组装逻辑；不同作业类型的统计口径并非完全一致。

班级排名依赖对应班级周报数据。周报中“优秀、良好、需提升”的评级依据总体正确率阈值由代码计算，建议文字由大模型生成。

代码入口：[学生周报接口](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/controller/StudentWeekAnalysisController.java)、[周报汇总任务](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/task/impl/StudentWeekAnalysisTaskImpl.java)、[周报展示与比较](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/manager/impl/StudentWeekAnalysisManagerImpl.java)。

## 6. 周测、答题卡的分数分布与排名

得分型作业有共享的分数分析服务：统计完成批改学生的得分分布、分数档位、平均得分、学生排名和高错误率题目。服务还会找到上一次相关作业，将得分按满分折算后比较，输出进步和退步学生。普通分析接口与答题卡专用接口复用同一实现。

这里的排名和分数统计基于已经完成的学生作业，不能理解为给未交作业自动打零分；与上一次作业比较也受上游找到的历史作业数据影响。

代码入口：[普通分数接口](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/controller/HwAnalysisController.java)、[答题卡分数接口](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/controller/AnswerCardAnalysisController.java)、[分数分析实现](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/manager/impl/ScoreAnalysisManagerImpl.java)。

## 7. 作文作业分析

该服务读取**其他批改系统已经生成的作文批改结果**和评分标准，在班级/作业层面计算成绩分布、字数分布、评分维度统计及提交、平均分、最高/最低分等总览，再让大模型根据汇总数据生成文字总结。接口可以查询分析结果、PDF 列表并接收 PDF 生成回调；分析结果存入 MongoDB。

这部分功能是**作文批改后的统计与报告**，不是 ChatBI 自己识别作文、给作文打分。作文分析任务中自动触发 PDF 生成的调用目前被注释；代码存在独立 PDF 生成方法和查询/回调路径，不宜表述为“每次作文分析都会自动产出 PDF”。

代码入口：[作文分析接口](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/controller/EssayAnalysisController.java)、[作文统计任务](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/task/impl/EssayAnalysisTaskImpl.java)、[结果查询与回调](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/manager/impl/EssayAnalysisManagerImpl.java)。

## 8. 学校与区域管理看板

**学校看板**提供学校总览、作业列表、班级/教师使用情况、班级/教师排行、日期范围统计及每日使用趋势。总览包含班级、教师、学生数量，以及作业量、提交量和批改记录等指标。班级与教师榜单的实现主要按**作业使用量**排序；不能写成“教学质量排名”或“教师教学效果评估”。看板支持班级、教师数据的 Excel 导出。

**区域看板**聚合下属学校数据，提供区域总览、学校排行、学校统计列表和日趋势。学校排行支持按作业量、提交作业量、提交率等指标切换。

代码入口：[学校看板接口](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/controller/SchoolBoardController.java)、[学校看板实现](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/manager/impl/SchoolAnalysisManagerImpl.java)、[区域看板接口](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/controller/DistrictBoardController.java)、[区域看板实现](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/manager/impl/DistrictAnalysisManagerImpl.java)。

## 9. 报告生成与知识点推荐练习册

PDF 任务接口支持**学生周报 PDF**和**推荐题练习册 PDF**。ChatBI 保存任务、提供报告内容、提交外部渲染服务，并在回调后保存文件名供查询下载；PDF 版式渲染发生在外部服务。推荐练习册路径会把用户给出的知识点名称映射到知识点 ID，再通过上游题目标签接口取推荐题，组织成渲染内容。

因此，ChatBI 在这里承担的是**数据准备、任务流转和文件查询**；题库召回与 PDF 渲染的完整算法不在当前仓库内。学校看板还有独立 Excel 导出接口。

代码入口：[PDF 任务接口](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/controller/PdfGenerateController.java)、[PDF 流程实现](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/manager/impl/PdfGenerateManagerImpl.java)、[推荐练习册内容组装](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/manager/impl/RecommendQuestionBookManagerImpl.java)。

## 10. 事件驱动计算、定时汇总与补算

批改结果通过 MQ 到达后，消费者按作业类型触发普通作业或作文分析，并更新作业明细数据；定标/批改处理阶段的消息还会写入对应的聚合记录。每日任务更新班级、教师日统计，周任务计算上周班级和学生周报，学校任务更新学校统计。管理接口提供按日期、批次或作业重算与刷新能力，便于补齐历史数据。

定标聚合、批改聚合会联合任务和学校、班级、教师、学生等业务信息，形成可分页查询的统计记录。MQ 消费者中存在捕获异常后确认消息的代码，所以此处仅能说“具备异步触发与补算接口”，不能据此承诺消息失败会自动可靠重试。

代码入口：[批改消息消费者](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/mq/GradingMessageListener.java)、[处理阶段消费者](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/mq/ProcessStageMessageListener.java)、[聚合任务](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/task/impl/HwAggregationTaskImpl.java)、[日统计调度](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/schedule/DayAnalysisSchedule.java)、[周统计调度](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/schedule/WeekAnalysisServiceSchedule.java)、[学校统计调度](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/schedule/SchoolAnalysisSchedule.java)、[补算接口](../../hp/chatbi/chatbi-service/src/main/java/com/hp/chatbi/controller/UtilController.java)。

## 典型数据链路

```text
HP-Grading 等上游系统：作业 / 题目定标 / 学生提交 / 批改结果
        ↓ 批改完成消息、查询接口
ChatBI：单次作业统计 + 知识点/素养归集 + 分数/作文分析
        ↓ 汇总任务
班级周报 / 学生周报 / 学校与区域统计
        ↓ 建议消息
大模型生成教师或学生建议 → 回写分析结果
        ↓ 查询、导出
前端报告 / 学校看板 / Excel / 外部 PDF 渲染
```

## 面试中可直接使用的项目概述

> ChatBI 是慧批的学情分析服务。它接收作业和批改结果，先在服务端统计逐题、逐学生、知识点和分数表现，再按班级、学生和学校等维度汇总成周报和管理看板。教师与学生的文字建议由大模型基于统计数据异步生成；周报 PDF、推荐练习册和 Excel 导出则走独立的报告流程。批改消息、定时任务和补算接口负责让分析结果持续更新。具体个人负责的功能和上线效果，需要再用项目任务记录与线上数据确认。

## 事实边界

- 本文只确认仓库中存在的接口和实现；实际启用情况、线上规模、性能和准确率需要运行环境或业务数据佐证。
- 作业分析中的“正确率”表示学生作答正确比例；**不能当作 OCR、定标、批改或 AI 建议的评测准确率**。
- 项目与 HP-Grading、定标/批改服务、题目标签服务和外部 PDF 渲染服务有集成关系。ChatBI 主要承担分析、聚合、建议编排与报告数据准备。
- 仓库代码只能证明功能存在，无法自动证明功能的个人归属；整理简历时需按实际参与范围表述。
