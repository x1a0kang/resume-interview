# 02｜HP-Grading 后端梳理

## 1. 定位与工程结构

`hp-grading` 是 Java 8、Spring Boot 2.3.12 的 Maven 多模块服务：

```text
hp-grading
├── hp-grading-api      DTO / VO / 枚举 / 服务接口（对内契约）
└── hp-grading-service  Spring Boot 应用（业务实现与运行入口）
```

服务侧遵循 Controller → Service → Manager → Repository/DAO 的分层，并把异步流程下沉到 `task`、`mq`、`schedule`：

```text
controller/     HTTP API、身份上下文、参数转换
service/        用例级校验与接口实现
manager/        领域编排、聚合结果、业务读写
repository/dao/ MyBatis PO、MySQL 访问
mongo/          文档型结果、扩展字段、审计日志
task/           向算法投递、回调后续处理、重试与通知
mq/             算法/题目任务消息监听
integration/    外部服务适配
es/ viking/     搜索与向量检索
prompt/         LLM 提示词
```

## 2. 主要业务域

| 业务域 | 代码落点 | 已验证能力 |
| --- | --- | --- |
| 作业定标 | `HomeworkLabeling*`、`LabelingQuestion*`、`HomeworkLabelingTask` | 上传、查询、分页结果、题目/空/答案/分数编辑、删除、分享、答题卡输入/回调 |
| 学生批改 | `ReviewTaskService`、`ReviewManager`、`RecognizeTask`、`GradingTask` | 提交学生图、创建批改任务/图片/记录、查询任务/单题/批量结果、修改结果后重批、按作业/题目重批 |
| 作文批改 | `Essay*`、`EssayGradingTask` | 系统/教师评分标准、作文题解析、学生作文识别、作文评分、PDF 辅助、结果查询/调分 |
| 答题卡 | `AnswerCardParsingTask`、`AnswerCardGradingTask` | 答题卡识别/批改和专属结果查询 |
| 题目资产 | `Question*`、`KnowledgePoint*`、`TeachingVersion*`、`XKW*` | 题目、教材版本/章节、知识点、题型、题模、标签、学科网题库、题目导入/结构化/推荐 |
| 质量运营 | `Feedback*`、`ErrorReason*`、`Mail*`、`NotifyTask` | 用户反馈、错因树/记录、邮件/飞书通知、失败任务告警 |

## 3. 对外接口轮廓

当前 REST 控制器覆盖的代表性接口：

| 路由前缀 | 代表操作 | 说明 |
| --- | --- | --- |
| `/labeling` | `/upload`、`/queryByPage`、`/result/queryByPage`、`/result/update`、`/blankAnswer/update`、`/question/updateScoreAndAnswer` | 教师定标全流程与人工修订 |
| `/question` | 定标题目/普通题查询、生成题查询 | 给业务端提供题目及生成内容 |
| `/essay` | 评分标准、作文 PDF、作文结果、调分 | 作文专用业务面 |
| `/pdf` | 生成与批量查询 | PDF 生成记录/结果 |
| `/knowledgePoint` | 导入、知识点树 | 题目知识体系 |
| `/feedback` | 反馈保存/查询 | 质量闭环 |
| `/util`、`/algo/data` | 算法数据、回调、重启、数据迁移、LLM/向量库辅助 | 运维与内部辅助接口；不应作为简历核心功能 |

注意：`ReviewController` 当前为空壳；学生批改相关“对内服务接口”已在 `ReviewTaskService`/`ReviewManager` 中完整存在，可能由其他服务、RPC 或尚未提交的入口对接。简历叙述应写“实现批改业务编排/结果服务”，不应据此断言某个 HTTP endpoint 已对外开放。

## 4. 任务状态和数据模型

### 4.1 关系型主数据（MySQL）

从 PO 与 SQL 迁移可识别的核心表对象：

```text
homework_labeling        定标作业
labeling_image           教师定标图片
labeling_question        定标题目
review_task              学生批改任务
review_image             学生提交图片
review_record            题目级批改处理/状态
algo_request_record      算法请求、参数、状态、版本
question / question_tag / question_type / question_model
knowledge_point / teaching_version / teaching_version_chapter
error_reason / error_reason_record / feedback / pdf_generate
```

### 4.2 文档型/扩展数据（MongoDB）

Mongo repository 体现了将大 JSON、复杂评分结果或日志从业务主表剥离的设计：

```text
review_result、essay_review_result、essay_question_criteria、essay_system_criteria、essay_teacher_criteria
algo_request_log、algo_cache_data、llm_request_record、out_service_request_log
question_v2、question_tag_v2、xkw_question、feedback_extend
```

### 4.3 数据生命周期

1. 上传时生成定标或批改任务及关联图片记录。
2. 后端组装算法输入，持久化 `algo_request_record` 后发送 MQ。
3. 算法回调由 `request_id` 找回业务类型和原始参数，按类型调用相应 `Task`。
4. Task 保存结构化题目、答案、识别或批改结果，推进定标/批改/记录状态。
5. 前端按作业、图片、题目、blank、批改任务或记录查询；教师修订后可触发重批。

## 5. 异步编排：后端的核心价值

`AlgoOutputMessageListener` 是普通算法回调的中枢，消费者并发度为 4。它的职责不是只“收消息”，而是：

1. 解析通用回调并识别算法状态；不可处理失败会通知并确认消息。
2. 查询 `algo_request_record` 恢复业务类型和版本。
3. 执行版本乱序保护：旧回调不覆盖新版本。
4. 记录算法排队/处理/回调耗时监控指标。
5. 分派到领域 Task 并手动 ACK。

回调映射如下：

| 算法业务类型 | 后端接收处理 |
| --- | --- |
| OCR、PDF 题目解析、答案解析、解题、定标 | `HomeworkLabelingTask` 的阶段回调 |
| 学生作答识别 | `RecognizeTask.algoRecognizeOutput` |
| 答题卡解析 | `AnswerCardParsingTask.algoRecognizeOutput` |
| 普通/单题批改 | `GradingTask` 的批改结果回调 |
| 单题 OCR/解析/解题/定标/人工填空 OCR | `QuestionLabelingTask` 的阶段回调 |
| 作文解析、识别、评分 | `EssayGradingTask` 的专属回调 |

辅助可靠性机制包括 `ReviewRetryTask`、`NotifyTask`、XXL-Job 调度、请求日志和幂等/版本校验。该层是面试中可重点讲述的“长耗时 AI 工作流工程化”部分。

## 6. 基础设施与部署

- Nacos：服务发现与配置中心；本地/开发/测试/生产 profile 分离。
- MySQL + MyBatis-Plus + Druid：业务主数据。
- MongoDB：复杂 JSON 结果和扩展文档。
- Redis：缓存及相关集成。
- RabbitMQ：算法任务输入/输出和内部业务事件；消费者显式 ACK。
- Elasticsearch + VikingDB：题目搜索、相似题/去重等能力。
- OSS/TOS：教师与学生图像/文件对象存储。
- Spring Actuator + Prometheus + Datadog 相关配置：健康检查与指标；管理端口配置为 9101，业务端口配置为 9001。
- Docker、GitLab CI/CD、Kubernetes StatefulSet：容器化部署；仓库部署清单显示默认可配置多副本。

## 7. 可用于后续简历的真实技术亮点（暂不写成成果）

- 构建以 `request_id + version` 驱动的异步 AI 任务编排与回调防乱序机制。
- 将“作业 → 题目 → blank → 学生解答 → 逐空评分”建模为可编辑、可追踪、可重试的数据闭环。
- 结合关系库与 MongoDB，承载强一致业务状态与高结构复杂度的算法输出。
- 把算法端长耗时处理接入消息队列、监控、失败告警、人工纠正与重批流程。
- 支持普通题、答题卡、单题和作文等差异化工作流，而非仅单一 OCR 调用。
