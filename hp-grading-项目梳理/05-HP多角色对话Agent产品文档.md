# 05｜HP 多角色对话 Agent 产品文档

> 架构口径更新（2026-10-23）：以 [Agent 架构确认基线](agent-architecture-handoff.md) 为准。前端只访问 Java；Java 保存业务问答；Python 使用 LangChain `create_agent`（底层 LangGraph）及 PostgreSQL checkpointer。同步滚动摘要保存在 checkpoint，不另建摘要表。本文描述确认方案，不据此新增上线或个人成果声明。

> 文档类型：产品方案 / PRD 草案。  
> 状态：已上线项目的产品与技术整理，含后续演进讨论；当前 Agent 技术选型、会话/turn/checkpoint 设计与流式链路见第 16.4—16.8 节。
> 最后更新：2026-10-20。
> 事实与方案更新（2026-10-20 本人确认）：Agent 与 RAG 均已上线并向 100 多所学校开放；本文记录的是项目整理及确认的目标技术方案。Agent 使用 LangChain 的 `create_agent`，由其底层 LangGraph runtime 执行；应用不手写 `StateGraph` 节点和边，配置 PostgreSQL checkpointer。Java `SseEmitter` 流式链路仍按第 16.6 节执行。不能把本文中的候选方案或未来能力表述成已经上线。

## 1. 产品定义

产品暂定名为**慧批智能助手**。教师端显示“教学助手”，学生与家长端显示“学习助手”；底层共用 Agent Runtime，但按角色提供不同的入口、工具、数据范围和表达方式。

它不是把现有页面查询搬进聊天框，而是解决以下页面难以自然完成的问题：

1. 跨多次作业、多个题目和多个维度综合分析；
2. 用户用自然语言提出目标，系统通过追问逐步明确范围；
3. 根据用户反馈持续调整解释、讲评和学习计划；
4. 生成可继续修改的教学或学习成果；
5. 在一次会话里组合查询、分析、解释和后续行动。

一个场景至少满足上述两项，才进入 Agent 核心能力。单纯“查分数”“查某题详情”“查批改进度”仍以现有页面为主，只作为对话过程中的支撑工具。

## 2. 核心用户价值

| 角色 | 现有问题 | Agent 的核心价值 |
| --- | --- | --- |
| 教师 | 批改结果分散在作业、题目和学生维度；备讲评需要人工归纳 | 把一段时间或一次作业的真实数据转成可追问、可修改的讲评与干预方案 |
| 学生 | 能看到答案和批改详情，但不会因此自动理解错因或形成订正计划 | 通过连续对话完成诊断、启发式讲解、订正和巩固 |
| 家长 | 能看到结果，但难以理解趋势、问题优先级和家庭可执行动作 | 将一段时间的学习事实翻译成克制、可操作的家庭辅导建议 |

## 3. 角色场景地图

第一版只保留两条入口规则：产品定义的任务按钮直接进入确定性 Workflow；所有自由文本统一进入当前登录角色的 Agent。取消独立意图分类模型和前置文本路由，避免在 Agent 之外再维护一套意图、槽位和跨轮状态。

### 3.1 教师：教学决策协作 Agent

教师端不再把“课堂临场调整”和“课后分层跟进”列为核心需求。保留三个存在开放目标、动态取数和反复修改的场景，共用一个教学决策 Agent。

| 场景 | 典型请求 | 为什么不能只做固定 Workflow | Agent 的动态决策 | 最终产物 |
| --- | --- | --- | --- | --- |
| 学情驱动的备课与作业设计 | “结合六年级二班最近几次作业，帮我准备下周分数除法的复习课。课堂 40 分钟，基础比较差，不要安排太多计算。” | 教师的教学目标、课时、范围、学生基础和侧重点组合不固定；取哪些历史作业、是否补充教材证据、是否需要题目资源会随请求变化 | 澄清教学目标；选择班级和时间范围；查询历史表现；判断证据是否充分；按需检索资料或题目；生成方案并根据教师反馈反复修改 | 结构化备课方案、作业草案；可保存到业务系统并按需导出 |
| 批改后的讲评方案共创 | “这次作业只留 20 分钟讲评。不要逐题讲，帮我找出最值得讲的两个问题，并说明为什么。” | “取本次批改结果→聚合→生成总结”本身只是 Workflow；真正不固定的是教师如何选择教学目标、排除哪些错误、是否参考历史表现，以及如何根据反馈改变讲评策略 | 根据目标选择本次或历史数据；调用题目、学生、错因和知识点工具；验证某个问题是偶发还是持续；提出讲评取舍；接受“压缩时间、换重点、补证据”等修改 | 讲评目标、顺序、重点题、典型错误、时间分配；在小程序中预览并按需导出 DOC/PDF |
| 开放式教学诊断与复盘 | “最近两个班应用题正确率都下降了，是题目变难了，还是某个知识点没掌握？” | 问题通常先有假设但没有固定分析口径；需要根据初步结果继续拆分班级、作业、题型、知识点和时间范围 | 先澄清比较口径；动态调用聚合工具；根据 observation 继续下钻或提出数据不足；区分事实、推断和待验证项；直到形成可以解释的结论或明确无法判断 | 带数据依据的诊断结论、待验证问题和教学复盘草案 |

教师 Agent 的核心不是“自动写一份教案”，而是与教师共同完成一个无法一次性定义清楚的教学决策。固定取数、统计、文档渲染和保存仍由确定性工具完成。

### 3.2 学生：个性化答疑与讲题 Agent

学生端只保留一个主产品场景，不再把“整份作业复盘、引导式订正、变式推荐、学习计划”拆成多个看似独立但重叠的 Agent 功能。推荐题继续使用现有推荐接口和按钮，不作为聊天卖点。

个性化答疑 Agent 内部包含以下连续能力：

1. 带入当前题目、学生作答、标准答案、解析、知识点和批改结果；
2. 判断学生是在问题意、概念、某一步推导、错误原因还是完整解法；
3. 信息不足时询问学生原来的思路，而不是直接猜测错因；
4. 根据学生反馈在提示、举例、图形化解释、完整讲解之间切换；
5. 学生说“还是不懂”时，改变解释路径，而不是重复原答案；
6. 在适当时让学生复述关键步骤或回答一个很短的检查问题，判断是否可以结束；
7. 若需要同类题，调用现有推荐题能力并以操作卡展示，不要求学生通过聊天完成本来已有按钮的操作。

这个场景必须使用 Agent，因为后续动作取决于学生每一轮的新回答，无法在开始时确定完整步骤。这里的“订正”和“理解检查”是答疑过程的一部分，不再作为独立产品功能。

### 3.3 家长：学习报告分析与学习计划 Agent

家长端有两个核心 Agent 场景。分数、正确率、班级平均、题目难度和知识点错因仍由确定性工具计算；Agent 负责从不完整的自然语言中确定分析目标、补齐条件、选择工具、解释结果并支持连续修改。

#### 3.3.1 分析孩子的学习报告

家长的请求不一定天然带有固定周期和学科，例如：

> “孩子最近学习怎么样？”

Agent 不应直接假设“最近”等于一周，也不应默认分析全部学科后输出一份很长的报告。它需要结合入口上下文和已知身份，判断还缺少哪些关键条件，并使用快捷选项降低家长的输入成本：

```text
Agent：您想看哪个时间范围？
[最近一周] [最近一个月] [本学期] [自定义]

Agent：想先看哪些内容？
[全部学科] [数学] [语文] [英语]
```

如果家长从“查看孩子周报”按钮进入，则默认带入本周和全部学科，可以直接生成第一版结果，不重复追问；之后仍允许家长说：

- “改成最近三周，只看数学。”
- “排除上周没完成的那次作业再分析。”
- “为什么分数提高了，应用题正确率反而下降？”
- “和班级平均相比，主要差在哪些知识点？”
- “具体是哪几道题导致这个判断？”

此时 Agent 根据新问题重新选择统计、作业、题目、知识点、错因和题目难度工具，直到证据充分或明确说明无法判断。

学习报告建议包含：

- 分析对象、时间范围、学科和纳入的作业数量；
- 分数与正确率变化；
- 与孩子自身历史及班级整体指标的对比；
- 主要知识点、错因和代表题目；
- 已有改善、持续问题和数据不足项；
- 可以继续追问的方向，以及“基于本报告制定计划”的入口。

#### 3.3.2 制定孩子的学习计划

在周末、法定假期或寒暑假前，Agent 结合孩子近期真实作业表现、学校已有任务和家庭时间约束，与家长共同制定一份可以执行并允许反复修改的学习计划。

```text
家长点击“生成本周末学习计划”
→ 自动带入孩子身份和本周作业范围
→ Agent 查询各学科表现、题目难度、知识点和错因
→ 将孩子自身变化与允许展示的班级整体数据进行比较
→ 判断优先内容及证据是否充分
→ 只询问当前计划真正缺少的条件，例如可用时间和希望安排的学科
→ 生成计划草案
→ 家长提出“周六没时间”“数学控制在 30 分钟”“先完成学校作业”等修改
→ Agent 重新安排并在家长确认后结束
```

假期计划还要动态处理假期长度、休息日、各学科比例、复习与预习边界。例如：

> “国庆七天，前三天外出，只安排数学和英语；每天最多 40 分钟，不要提前学新课。”

计划建议包含：

- 计划周期、每天预计时长和休息安排；
- 优先学科、知识点和选择依据；
- 回看哪些已批改题目；
- 是否调用现有推荐题能力补充少量练习；
- 家长需要参与的环节和可以直接使用的提问方式；
- 数据不足、题目过少或结论不稳定时的说明。

如果产品只是“读取本周数据→套模板→生成周末计划”，它仍然是 Workflow。Agent 的必要性来自动态取数、按需追问、多目标取舍、自然语言修改以及判断何时可以结束。

#### 3.3.3 其他可支持的分析

只要工具和权限允许，同一个 Agent 还可以回答单次作业、某学科、某知识点、某类错因和指定题目的问题。这些属于通用分析能力，不需要分别包装成新的产品模块。

“这次变化需要担心吗”具有合理语义，但没有搜索日志、客服记录或用户访谈时，不能认定它是家长的高频原话，因此不作为核心入口文案，只作为 Agent 应理解的自由提问。

Agent 只能陈述数据支持的学习表现；不能根据错题自行推断“粗心、懒惰、态度差”等人格、心理或家庭原因。家长主动补充的家庭情况可以作为本次计划约束，但必须与系统事实区分记录。

### 3.4 Agent 场景中的 RAG 接入点

Agent 统一编排业务工具、文档 RAG 和题目服务，但不是每个对话都要调用 RAG：

| Agent 场景 | Domain Tools | 文档 RAG | 题库/推荐服务 | RAG 的具体作用 |
| --- | --- | --- | --- | --- |
| 学情驱动的备课与作业设计 | 查询班级历史表现和已有任务 | 检索当前教材定义、方法和教参教学顺序 | 提供公开且可推荐的练习题 | 让备课方案与实际教材体系一致 |
| 批改后的讲评方案共创 | 查询本次及历史批改结果 | 检索教材方法、教参重难点和第三方方法总结 | 提供课堂例题和巩固练习 | 把批改统计转成有教材依据的讲评内容 |
| 开放式教学诊断与复盘 | 负责主要分析和统计 | 仅在教师继续询问“教材如何处理、接下来怎样讲”时调用 | 仅在需要补充练习时调用 | 不参与正确率下降等事实判断，只补充教学处理建议 |
| 学生个性化答疑 | 查询当前题目、本人作答和批改结果 | 学生要求课本方法、教材定义或换教材思路时调用 | 学生需要同类题时调用 | 根据指定教材改变讲解路径 |
| 家长学习报告分析 | 查询孩子表现和允许展示的统计 | 通常不调用 | 通常不调用 | 报告是业务事实分析，不应为了使用 RAG 检索教材 |
| 家长学习计划 | 查询孩子表现、学校任务和时间约束 | 仅在计划需要说明当前教材复习顺序时调用 | 按需提供少量公开练习 | RAG 是可选补充，不是计划生成的前置条件 |

教材版本由服务端根据学校地域、学科、年级、学期和学年解析后作为检索硬过滤条件。RAG 默认不向用户展示引用；用户明确询问课本位置时，只返回教材版本、册次和章节。

## 4. 按钮、Workflow 与 Agent 的关系

### 4.1 两条入口规则

- **任务按钮：** 按钮由产品预先绑定 `actionCode` 和页面上下文，例如 `homeworkId`、`classId`、`studentId`，服务端校验后直接执行对应 Workflow，不调用 Agent。
- **自由文本：** 无论用户表达的是报告、答疑、备课、计划、能力询问还是超范围请求，都直接进入 `Agent(role=当前登录角色)`，由 Agent 理解目标、补充条件、选择 Tool 和判断结束。

“打开聊天页”“围绕结果继续问”只是导航按钮，不代表一个固定任务；进入聊天页后的文字仍统一交给 Agent。

### 4.2 正确架构：按钮执行固定流程，自由文本统一由 Agent 编排

```text
用户入口
├─ 明确任务按钮
│  → 服务端预定义 actionCode + 页面上下文
│  → 确定性 Workflow
│  → 结果页
│  └─ 用户继续追问时进入 Agent
│
└─ 任意自由文本
   → 根据登录身份选择 AgentProfile 与 Tool Set
   → Agent 获取 observation 并判断下一步
      ├─ 信息不足：继续查工具或向用户追问
      ├─ 需要生成内容：形成草案并允许继续修改
      ├─ 命中已有业务写操作：给出文字操作指引
      └─ 目标完成：总结、生成产物并结束
```

其中：

- Agent 决定“为了当前目标，下一步做什么”；
- Tool 负责一次可验证的查询或操作；
- Workflow 负责按钮触发的固定流程以及 Agent Tool 内部的确定性子流程；
- 修改分数、答案和重批不开放 Agent Tool；文件与草案等新产物只能通过受控产物 Tool 创建。

### 4.3 不建议做成无边界的单 Agent

底层可以共用一套 Agent Runtime，但应按教师、学生、家长配置不同的目标说明、工具白名单、数据域和结束条件。教师 Agent 不能调用家长/学生身份下的工具，学生答疑 Agent 也不能获得修改标准答案或查看班级数据的能力。

因此，更准确的产品表述是：

> 一套角色感知的智能助手平台：产品任务按钮执行固定 Workflow，其他自然语言统一进入当前角色 Agent，由 Agent 基于会话历史和当前请求动态编排受控业务 Tool。

## 5. 不作为核心场景

以下能力可以支持，但不作为 Agent 的主卖点：

- 查询某道题为什么扣分；
- 查询某份作业是否批完；
- 查询当前得分、答案、解析或排名；
- 用一句指令直接修改答案或分数；
- 把固定报表换成聊天方式展示。

原因是它们在详情页、状态页或报表中通常更快。只有当这些查询成为跨作业分析、持续辅导或多步行动的一部分时，对话才产生额外价值。

固定周报/月报本身属于报表能力；从模糊问题确定报告范围、围绕报告连续下钻、解释矛盾指标和据此制定计划，才属于 Agent 能力。

## 6. 产品交互

### 6.1 入口

不只提供一个空白聊天框，而是提供角色化、上下文化入口：

| 位置 | 推荐入口文案 | 自动带入的上下文 |
| --- | --- | --- |
| 教师工作台 | “和教学助手一起备讲评” | 当前班级、学科、最近已批完作业 |
| 作业分析页 | “围绕这次作业继续分析” | 作业、班级、题目与统计范围 |
| 教师小程序讲课页面 | “和教学助手准备本次讲评” | 当前作业、班级、聚合统计和当前查看题目 |
| 教师备课/作业布置页 | “根据班级学情设计教学与作业” | 当前班级、学科、教学进度和历史作业 |
| 教师学情分析页 | “继续追问变化原因” | 当前班级、学科、时间范围和当前筛选条件 |
| 学生作业结果/题目详情页 | “问问学习助手” | 当前学生、题目、作答、批改结果和解析 |
| 学生首页 | “向学习助手提问” | 当前学生身份；先从已经批改的作业和题目中选择上下文 |
| 家长首页/孩子档案 | “生成周末/假期学习计划” | 已绑定孩子、各学科近期作业和历史表现 |
| 家长周报/月报 | “围绕这份报告继续问” | 当前孩子、报告时间范围、学科和统计口径 |
| 家长作业通知/结果页 | “围绕这次作业继续问” | 当前孩子、题目批改详情、班级整体指标和历史参照范围 |

### 6.2 角色化对话首页

教师：`一起准备讲评`、`根据学情设计备课方案`、`分析最近教学变化`。  
学生：`这一步为什么错`、`换一种方式讲`、`先提示我不要给答案`。  
家长：`分析孩子最近的学习`、`生成本周末学习计划`、`生成假期学习计划`。

对话首页不能只有一个空输入框。它至少包括：

1. 一句话角色说明，告诉用户助手服务谁；
2. 3 个核心能力卡片，说明可以完成什么任务；
3. 结合当前身份、最近作业和时间节点生成的推荐问题；
4. 最近使用过的班级、孩子、作业或题目上下文；
5. 输入框中的角色化占位文案。

用户不需要知道底层有哪些 Tool，也不应直接看到 `queryHomeworkResult` 等技术名称。产品应把工具翻译成用户能力：

| 角色 | 用户可见的能力说明 |
| --- | --- |
| 教师 | “我可以分析您有权限的班级和作业，与您一起准备备课、讲评和教学复盘。” |
| 学生 | “我可以结合你已经批改的题目和作答，回答具体哪里不懂，并根据你的反馈换一种讲法。” |
| 家长 | “我可以分析已绑定孩子的作业和学习变化，也可以一起制定周末或假期学习计划。” |

### 6.3 两种启动路径

#### 明确任务按钮进入 Workflow

按钮向服务端传递一个可信任务信封：

```json
{
  "role": "PARENT",
  "actionCode": "GENERATE_WEEKLY_LEARNING_REPORT",
  "sourcePage": "WEEKLY_REPORT",
  "studentId": "已绑定孩子 ID",
  "defaultTimeRange": "THIS_WEEK",
  "defaultSubjects": ["ALL"]
}
```

服务端只接受预先登记且当前角色有权执行的 `actionCode`。它直接启动报告 Workflow，不调用 Agent。Workflow 生成结果后，页面可以提供“围绕这份报告继续问”；该按钮只负责打开对话并绑定报告 ID、统计口径和筛选条件，用户真正输入文字时才进入 Agent。

#### 直接进入聊天框

用户的任意自由文本直接进入当前角色 Agent，不经过独立意图模型：

1. 根据登录身份展示对应能力卡片，教师、学生和家长看到不同内容；
2. 展示 3—5 条可直接点击的完整示例问题，而不是只写“请输入您的问题”；
3. 输入框上方展示可选上下文，例如班级、孩子、最近作业或已批改题目；
4. 用户只说“帮我分析一下”时，Agent 先确认分析对象、时间和学科；
5. 能从身份和页面上下文确定的信息自动补全，只询问真正影响结果的缺失项；
6. 用户问“你能做什么”或明显不知道如何开始时，重新展示能力卡片，并推荐一个最贴近当前数据的任务；
7. 超出能力范围时，明确说明限制，并给出 1—3 个当前可以完成的替代任务。

示例问题建议使用“对象 + 范围 + 目标”的自然表达，但不要求用户学习固定句式：

- 教师：“分析六年级二班最近三次数学作业，帮我准备明天的讲评。”
- 学生：“结合我这道题的作答，告诉我第二步为什么错，先不要直接给答案。”
- 家长：“看看孩子最近一个月的数学学习情况，重点说说反复出错的知识点。”

### 6.4 多轮澄清规则

- 不为了体现对话而机械追问；已有上下文可以确定时直接执行。
- 一轮最多询问 1—2 个高影响条件，并优先提供可点击选项。
- “最近”没有明确范围时必须澄清，或明确展示系统采用的默认范围并允许一键修改。
- 多个孩子、班级、学科或作业可能匹配时，必须让用户选择，不能自行猜测。
- 每次范围发生变化，都要在回复中重新标明分析对象、时间、学科和纳入数据量。
- 用户中途改变目标时保留仍然有效的上下文，重新规划剩余步骤。

### 6.5 回复结构

回答不应只有大段文字，建议由四部分组成：

```text
结论摘要
→ 数据依据（作业、题目、时间范围）
→ 可操作建议或下一步
→ 推荐追问 / 保存、生成、继续订正等动作
```

教师和家长可查看所使用的业务数据范围；默认不展示 RAG 来源。用户明确询问课本位置时，只返回教材版本、册次和章节。学生端使用适龄表达，默认先提示后答案。任何结论都应标明分析范围与数据不足。

### 6.6 教学方案与讲评文件

“讲课平台”不是独立系统，只是小程序中面向教师的一个讲课页面。Agent 可以从该页面进入并自动带入当前作业，不假设页面已经存在讲评顺序、重点题等保存能力。

这里的“结构化”是新增的后台草案数据格式，不是教师目前能配置的功能。备课或讲评内容先在对话中按标题、环节、题目、讲解重点和时间等字段展示；教师明确要求生成文件或点击“生成文件”后，才创建 DOC/PDF 产物。

大模型不直接生成二进制文件，也不直接操作对象存储。推荐流程：

```text
Agent 生成 TeachingPlanDraft 草案数据
→ 教师预览并继续修改
→ 教师明确确认生成 DOC/PDF
→ Artifact Render Service 按模板生成 DOC/PDF
→ 上传 OSS/TOS
→ 数据库保存文件记录、业务关联和版本
→ 前端收到生成完成状态并展示限时下载按钮
```

`generate_teaching_plan_file` 只负责生成文件，不负责执行下载。真正的下载是浏览器/小程序根据已授权 URL 完成的前端操作，不是 Agent Tool。这样可以保证格式稳定、便于审计和版本管理，也避免每轮对话都生成无用文件。对象存储负责保存最终文件，不负责保存 Agent 的思考或会话状态。

它也不需要在所有教师对话中始终暴露给模型。只有当前会话已经存在可生成的草案，并且教师用自然语言明确要求“生成 PDF/DOC”时，才把该 Tool 加入本轮候选；如果教师点击页面上的“生成文件”按钮，前端直接调用同一个 Artifact Application Service，完全绕过模型。无论哪种入口，下载动作都由文件完成后的前端按钮执行。

用户已经导出文件后又要求修改内容时，不覆盖对象存储中的旧文件，也不直接编辑 DOC/PDF 二进制内容。系统修改数据库中作为唯一内容源的 `TeachingPlanDraft`，形成同一个逻辑文档的新版本，再重新渲染一个新文件：

```text
teachingPlanId=P100，draftVersion=1
→ 导出 artifactVersion=1，文件 P100/v1.pdf
→ 教师继续对话并要求修改
→ 生成 draftVersion=2，parentVersion=1
→ 导出 artifactVersion=2，文件 P100/v2.pdf
→ 页面默认下载最新版，旧版本按保留策略用于审计或回退
```

因此产品语言可以说“修改这份讲评文件”，但技术实现是“修改同一份讲评方案的内容版本，并生成新的文件版本”。这样能避免 CDN/签名 URL 缓存、下载中的旧文件被覆盖、并发编辑和无法回退等问题。建议至少保存 `teachingPlanId`、`draftVersion`、`parentVersion`、`contentSnapshot`、`objectKey`、`createdBy` 和 `createdAt`。

## 7. 角色权限与数据边界

- 教师只能访问有权限的学校、班级、作业和学生；涉及单个学生的信息只用于明确教学目的。
- 学生只能访问本人作业、结果和学习记录。
- 家长只能访问上游账号体系中已经明确绑定并授权的孩子；登录身份 ID 和家长—孩子关系是现有产品能力。
- 学生不能获得教师工具、班级汇总、其他学生结果或标准答案修改能力；家长不能获得教师工具或标准答案修改能力。
- 家长可以查看本人孩子的题目和批改详情，也可以使用班级平均分、班级平均正确率、题目难度等班级整体指标。
- 家长不能查看其他学生的姓名、作答、分数或任何可反推个体身份的数据；默认不提供个人排名和学生横向名单。
- 输出不得把分数波动直接解释为学习态度、心理状态或家庭原因。

## 8. 异常与降级

| 情况 | 产品行为 |
| --- | --- |
| 批改尚未完成 | 说明缺少哪些结果，可先分析已完成部分或建议稍后再试 |
| 时间范围内作业太少 | 明确样本不足，不输出趋势性判断 |
| 知识点/错因标签缺失 | 使用题目与批改事实做有限总结，并标记依据不足 |
| 学生要求直接给未作答题答案 | 先确认是订正还是进行中作业；默认采用分级提示 |
| 家长未绑定孩子 | 引导完成绑定，不允许通过姓名搜索孩子 |
| 数据之间冲突 | 展示冲突、停止强结论，并提供查看原始记录或联系教师入口 |

## 9. 第一版优先级

### P0：三角色首发闭环

- 教师：教学决策 Agent，优先落地批改后讲评共创；
- 学生：个性化答疑与讲题 Agent；
- 家长：学习报告分析 Agent + 周末/假期个性化学习计划 Agent；
- 公共能力：角色鉴权、上下文选择、证据范围、会话历史和数据不足提示。

### P1：从分析走向行动

- 教师学情驱动的备课/作业设计、开放式教学诊断与复盘；
- 学生答疑中的多模态题目输入、图形化解释和适龄教学策略；
- 家长跨学科问询、关注项跟进和家校沟通清单；
- 接入教学资源 RAG，为讲评和辅导提供指定版本的教材、教参和辅导方法上下文。

### P2：受控业务操作

- 答案、解析、分数修改草案；
- 教师确认后的提交与单题重批；
- 批改异常诊断和运营人工分流。

P2 有工程价值，但不是用户高频使用 Agent 的首要理由。

## 10. 成功指标

### 教师

- 讲评草案完成率、保存/复制率、二次修改率；
- 从进入助手到形成可用讲评的时长；
- 教师对问题归纳和建议可用性的评价。

### 学生

- 有效答疑完成率、“仍未理解”率和主动追问率；
- 同一问题重复更换讲法后的理解反馈；
- 无依据回答率、直接泄露答案率和平均答疑轮数。

### 家长

- 周末/假期计划生成完成率、确认率和二次修改率；
- 周报/月报后的有效追问率，以及从追问进入计划生成的比例；
- 计划时长、学科和家庭约束的满足率；
- “看不懂结果”“不知道怎么安排”等反馈下降情况。

### 安全与质量

- 越权访问、未确认写入、其他学生数据泄露：目标均为 0；
- 业务事实引用正确率、无依据强结论率、低数据量误判率；
- 首次响应时延、完整任务时延和人工转接率。

## 11. 产品依赖与待确认问题

已有可复用基础：作业、题目、blank、答案、解析、分数、批改任务、知识点、错因，以及教师/学生/班级外部查询能力。

已确认的产品基础：

1. 用户登录后已有明确身份 ID；
2. 已存在家长账号以及家长—孩子绑定关系；
3. 可以根据身份 ID 获取不同时间的多次作业历史；
4. 教师数据关联路径为“教师 → 班级 → 已布置作业 → 学生 → 学生提交 → 批改结果”；
5. 所谓“讲课平台”是教师小程序中的一个讲课页面，已经支持按题目聚合查看作业、学生、错因和知识点，目前没有讲评方案的结构化保存能力；
6. 教师导出格式可以按 DOC 或 PDF 设计；
7. 学生答疑只针对系统中已经批改的题目，不支持拍照或输入新题；
8. 家长可以查看本人孩子的题目批改详情、题目难度和知识点错因；
9. 家长可以查看班级平均分、班级平均正确率等整体指标，但不能查看其他学生个体数据。

仍需进一步确认：第一版的首要商业目标与首发角色是什么，这将决定教师、学生和家长能力是同期上线还是分阶段上线。

技术 Runtime、领域工具、确认状态机和 Evaluation Harness 将在核心产品场景确认后继续细化。RAG 的产品与技术方案独立维护在 [06-HP教学资源RAG产品与技术方案.md](06-HP教学资源RAG产品与技术方案.md)。

## 12. Agent Tool 需求与现有代码匹配

### 12.1 Tool 设计原则

Tool 是提供给 Agent 调用的稳定业务能力，不等同于把现有 Controller 原样注册给大模型。

1. Tool 输入必须使用业务 ID 和明确筛选条件，不能允许模型拼接 SQL；
2. 身份、角色、家长—孩子绑定、教师—班级关系由 Runtime 注入和 Policy Guard 校验，不允许模型自行声明权限；
3. 分数、正确率、平均值和趋势由确定性代码计算，大模型只解释结果；
4. 班级分析优先返回聚合指标和少量授权样本，不能把全班所有原始作答直接塞入上下文；
5. 保存讲评/学习计划、生成文件等 Agent 产物操作必须使用明确业务对象和幂等控制；修改答案、分数和批改结果继续使用现有页面，不作为第一版 Agent Tool；
6. Tool 返回统一包含 `scope`、`data`、`evidence`、`dataQuality` 和 `nextCursor` 等信息，使 Agent 能判断证据范围和数据是否充分。

身份鉴权、会话存储、Tool 白名单、最大调用次数、是否结束等属于 Agent Runtime/Harness，不作为模型可以自由调用的业务 Tool。

### 12.2 产品场景要求的 Tool 清单

以下 17 项是产品能力盘点，用来检查数据和工程缺口，不代表必须注册成 17 个独立 Tool，更不代表每次模型调用都要暴露全部能力。相邻能力会在 12.5 中合并成更少的高层 Tool。

| 编号  | Tool 建议名                      | 主要角色     | 主要用途                            | 关键输入                                          | 核心输出                                          |
| --- | ----------------------------- | -------- | ------------------------------- | --------------------------------------------- | --------------------------------------------- |
| R01 | `list_accessible_contexts`    | 全部       | 为直接聊天提供可选班级、孩子、作业和已批改题目         | 上下文类型；当前身份由服务端注入                              | 有权限的对象列表及最近使用项                                |
| R02 | `search_homeworks`            | 全部       | 按角色、时间、学科、班级、学生和状态查询作业          | 时间范围、学科、classId/studentId、状态                  | 作业列表、提交/批改状态和关联 ID                            |
| R03 | `get_homework_detail`         | 教师、家长    | 查询作业名称、学科、班级、教师、时间、定标信息         | homeworkId                                    | 作业基本信息与 labelingId                            |
| R04 | `get_class_homework_analysis` | 教师       | 为讲评、备课和开放诊断提供一个或多个作业的班级分析       | classId；homeworkId/homeworkIds 或时间范围；学科与筛选条件  | 每次作业的平均得分率/正确率、题目/知识点/错因聚合、难度、样本量、可选数值差值和数据质量 |
| R05 | 趋势解释能力（合并到 R04，不注册独立 Tool）    | 教师       | 基于 R04 返回的多次作业分析判断改善、下降、偶发或证据不足 | R04 的 homeworkAnalyses[] 与教师问题                | 由模型生成的变化解释、依据和不确定性                            |
| R06 | `get_student_learning_report` | 家长       | 生成任意时间和学科范围的孩子学习报告              | studentId、时间范围、学科、排除条件                        | 分数/正确率趋势、知识点、错因、代表题目                          |
| R07 | `get_class_benchmark`         | 教师、家长    | 比较孩子或一次作业与班级整体表现                | classId、homeworkIds、题目/知识点范围                  | 班级平均分、平均正确率、样本量和统计口径                          |
| R08 | `get_question_context`        | 全部       | 获取题目事实，供讲评、答疑和报告下钻              | labelingQuestionId/questionId                 | 题干、blank、答案、解析、分数、知识点、难度                      |
| R09 | `get_student_question_review` | 学生、家长、教师 | 获取指定学生已批改题目的作答和批改详情             | studentId、studentHwId/reviewTaskId、questionId | 学生作答、逐空结果、评分、点评和图片                            |
| R10 | `get_error_reason_summary`    | 教师、家长    | 按作业、学生、知识点、题目和时间聚合错因            | 范围、分组维度                                       | 错因数量、比例、关联题目和证据 ID                            |
| R11 | `get_representative_answers`  | 教师       | 为讲评挑选典型错误作答                     | homeworkId、questionId、错误类型、数量                 | 经授权的典型作答及选择依据                                 |
| R12 | `list_pending_homeworks`      | 家长       | 制定周末/假期计划时优先纳入学校已有任务            | studentId、计划周期、学科                             | 未完成/待订正作业及截止时间                                |
| R13 | `recommend_questions`         | 全部       | 按题目或知识点补充少量练习                   | 原题/知识点、年级、难度、数量、排除项                           | 推荐题和来源信息                                      |
| R14 | `save_teaching_plan`          | 教师       | 保存 Agent 共创的备课或讲评草案             | planDraft、关联班级/作业、版本                          | planId、version、保存状态                           |
| R15 | `generate_teaching_plan_file` | 教师       | 将已确认草案渲染为新的 DOC/PDF 文件版本        | planId、version、格式、idempotencyKey              | artifactId、异步任务状态和完成后的下载信息                    |
| R16 | `save_learning_plan`          | 家长       | 保存或更新周末/假期学习计划                  | studentId、planDraft、周期、version                | planId、version、任务列表                           |
| R17 | `search_teaching_resources`   | 教师、学生、家长 | 按需补充带引用的教学解释和资料                 | 查询、年级、学科、教材版本、ACL                             | 证据片段和 citation；依赖后续 RAG                       |

P0 应优先覆盖 R01—R10、R14—R16 所代表的产品能力，但实现时需要按场景合并，不逐项机械创建 Tool；R11—R13 按需接入，R17 属于 RAG 阶段。

### 12.3 当前 HP 与 ChatBI 代码可以提供的能力清单

| 编号 | 现有能力 | 主要代码依据 | 当前可提供的数据 | 结论 |
| --- | --- | --- | --- | --- |
| E01 | 登录身份上下文 | `BaseController#getUserId/getUserType` | 请求头中的 userId、userType | 可复用，但只有身份头，不等于完整数据域鉴权 |
| E02 | 教师基本信息 | `TeacherIntegration#batchTeacher` | 教师、学校、学科等 | 可直接封装批量基础信息查询 |
| E03 | 学生基本信息 | `StudentIntegration#batchQueryStudent` | 学生、班级、学号等 | 可直接封装；必须先校验调用者数据域 |
| E04 | 班级基本信息 | `ClassIntegration#batchQueryClassBase*` | 班级、学校、年级、学段 | 可直接封装基础信息；现接口不能按 teacherId 查询任教班级 |
| E05 | 作业基本信息 | `HwIntegration#findHwByHwId/batchFindHwList` | 作业、班级、教师、学科、时间、labelingId | 单作业可直接复用；批量接口只有 ID/时间条件，缺少角色化过滤 |
| E06 | 学生作业提交 | `HwIntegration#findStudentHwByHwId/batchHwStudentInfos/batchStudentHwByTaskIds` | studentId、studentHwId、reviewTaskId、状态、提交/批改时间 | 可以从作业串到学生提交和批改任务 |
| E07 | 学生题目快照和图片 | `HwIntegration#getReviewQuestionSnapshot/getStudentHwAnswerImages` | 指定学生作业的题目快照和作答图片 | 可作为题目答疑上下文来源之一 |
| E08 | 批改任务与结果 | `ReviewTaskService`、`ReviewManager`、`ReviewFeignController` | 总分、题目/blank 正确性、得分、作答文本、答案、解析、点评、错因 | 查询能力完整，适合封装批量和单题 Tool |
| E09 | 定标题目详情 | `LabelingQuestionService/Manager`、`QuestionFeignController` | 题干、blank、答案、解析、分数、图片位置 | 可直接封装，但建议与标签合并成一个 Agent Tool |
| E10 | 题目标签和难度 | `QuestionTagService`、`QuestionTagFeignController`、`QuestionTagDTO` | knowledgePointIds、知识点路径、difficultyValue | 可直接批量查询 |
| E11 | 知识点体系 | `KnowledgePointService/Manager` | 知识点树、节点和子节点 | 可直接查询知识点名称和层级 |
| E12 | 错因体系与记录 | `ErrorReasonService`、`ErrorReasonRecordService` | 错因树；按 user/学科/时间/reviewTask/question 查询记录 | 原始查询可复用，聚合统计需新增 |
| E13 | 推荐题 | `QuestionRecommendService/Manager`、`QuestionGenerateFeignController` | 按原题或知识点推荐题目，包含题干、答案和解析 | 可以接入，但不是学生 Agent 的独立产品场景 |
| E14 | PDF 生成记录 | `PDFGenerateService/Manager/Task` | 题目练习 PDF、作文报告、生成状态和 pdfUrl | 基础设施可复用，但不能直接生成通用讲评 DOC/PDF |
| E15 | 对象存储 | `TOSUtil`、`OSSUtil`、`FileController` | 字节上传、URL 转存、签名访问 URL | 可复用到 Agent 文件产物 |
| E16 | 单次大模型调用与日志 | `LLMUtil`、`LLMRequestRecordMongoRepository` | 单轮文本/图片请求、token 与请求记录 | 不是 Agent Runtime；没有 Tool Calling 和多轮会话 |
| E17 | 周报相关枚举 | `PDFBizTypeEnum.STUDENT_WEEK_ANALYSIS_REPORT`、`LlmBizEnum.WEEKLY_REPORT_*` | 表明系统曾为学生周报/PDF和建议预留业务类型 | 当前仓库未发现完整周报查询与聚合链路，不能视为现成 Tool |
| E18 | 答案、分数、批改结果修改与重批 | `HomeworkLabelingService#updateBlankAnswer/updateQuestionScoreAndAnswer`、`ReviewTaskService#updateReviewResult`、`ReviewFeignController`、`EssayService#updateResultScore` | 修改定标答案/分数、学生批改结果、作文分数，以及单题或批量重批 | 现有产品已经有对应操作入口；第一版保留原页面执行，不封装成 Agent Tool |
| E19 | 单次作业题目与学生分析 | ChatBI `HwAnalysisController/Manager` | 题目正确率、常错题、分数分布、学生提交与错题情况、知识点掌握等 | 应作为班级分析 Tool 的主要确定性数据源 |
| E20 | 学生周报与学习状态 | ChatBI `StudentWeekAnalysisController/Manager`、`StudentWeekReportDTO` | 正确率/得分率及变化、排名、知识点、作业列表、学科素养和建议 | 可直接支撑家长学习报告；任意时间范围需增加统一查询 Facade |
| E21 | 班级周报与教学分析 | ChatBI `ClassWeekAnalysisController/Manager`、`ClassWeekReportDTO` | 班级作业量、正确率、薄弱知识点、作业详情与教学建议 | 可直接支撑教师周讲评和多作业分析 |
| E22 | 教师/学校/区域分析 | ChatBI `SchoolBoardController/Manager`、`DistrictBoardController/Manager` | 教师、班级、学校排名与趋势，区域概览和日使用趋势 | 可作为管理视角扩展，不默认暴露给普通教师/家长 |
| E23 | 分析建议与报表产物 | ChatBI Advice MQ Listener、`PdfGenerateController`、作文/周报相关服务 | 异步大模型建议、版本校验、PDF/Excel 生成与查询 | 可复用现有异步产物基础，统一到 Agent 草案版本模型 |

### 12.4 需求 Tool 与现有代码匹配矩阵

状态定义：

- **A｜可直接封装**：现有接口已能返回主要数据，只需增加 Agent Schema、鉴权和错误码；
- **B｜需要聚合封装**：底层数据存在，但要新增面向 Agent 的聚合 Service/Facade；
- **C｜依赖上游接口**：业务系统已存在该关系或数据，但当前 HP 仓库没有合适的集成接口；
- **D｜需要新建**：当前没有对应持久化或执行能力；
- **E｜RAG 阶段**：由独立 RAG 能力提供。

| 产品 Tool | 匹配状态 | 可复用能力 | 主要缺口 |
| --- | --- | --- | --- |
| R01 `list_accessible_contexts` | C | E01—E04 | 缺教师—班级、家长—孩子、学生—历史作业的角色化查询接口；不能用学校全部班级代替教师班级 |
| R02 `search_homeworks` | C/B | E05、E06 | 现有 `BatchHwReqDTO` 只有 hwIds/startTime/endTime，缺 teacherId/classId/studentId/subject/status 和服务端权限过滤 |
| R03 `get_homework_detail` | A | E05 | 增加调用者对作业的访问校验和稳定 Tool Schema |
| R04 `get_class_homework_analysis` | A/B+C | E19、E21，必要时补充 E05—E12 | 单作业和按周分析已有明确实现；需增加统一 Facade 支持任意作业集合/时间范围，并补角色化历史作业查询 |
| R05 趋势解释能力 | 合并 | R04 | 不新增 Tool；模型读取 R04 的多作业结果后解释变化，避免与 R04 职责重叠 |
| R06 `get_student_learning_report` | A/B+C | E20，必要时补充 E05—E12 | 现有学生周报可直接复用；需扩展为任意时间和学科范围，并接入家长—孩子权限关系 |
| R07 `get_class_benchmark` | A/B | E19—E21 | ChatBI 已有班级平均正确率、分数分布等确定性聚合；只需统一口径、样本量和权限输出 |
| R08 `get_question_context` | B | E09—E12 | 数据已经存在，需要合并题目、答案解析、知识点、难度和错因，避免 Agent 连续调用多个细粒度接口 |
| R09 `get_student_question_review` | B | E06—E09 | 单题结果和快照存在，需要校验学生本人/绑定家长/任课教师关系并统一输出 |
| R10 `get_error_reason_summary` | A/B | E12、E19—E21 | ChatBI 已有题目/知识点分析，HP 有错因记录；需要统一错因分类和跨作业时间范围聚合 |
| R11 `get_representative_answers` | B | E06—E10 | 需定义典型样本选择规则、数量限制、教师权限和返回脱敏策略 |
| R12 `list_pending_homeworks` | C | E05、E06 | 当前集成以“按作业查学生提交”为主，缺按 studentId 查询待完成任务的上游接口 |
| R13 `recommend_questions` | A | E13 | 增加角色权限、数量上限、去重和来源说明即可接入 |
| R14 `save_teaching_plan` | D | 无 | 需新增讲评/备课草案、版本和业务关联模型 |
| R15 `generate_teaching_plan_file` | B+D | E14、E15 | 可复用异步记录和对象存储，但需新增通用 DOC/PDF 模板渲染、版本管理与 Agent 草案关联；实际下载由前端完成 |
| R16 `save_learning_plan` | D | 无 | 需新增计划、每日任务、关联题目、状态和版本模型；是否同步学生端待产品确认 |
| R17 `search_teaching_resources` | E | ES/VikingDB 基础设施可借鉴 | 需要独立教学资源知识库、ACL、混合检索、rerank 和 citation，不复用现有题目去重集合 |

### 12.5 第一阶段最终 Tool Catalog

不要先把所有现有接口注册成几十个细粒度 Tool。17 项产品能力不等于 17 个模型可见 Tool。第一阶段最终确认以下 10 个高层 Tool：

```text
1. search_homeworks
2. get_class_homework_analysis
3. get_question_context
4. get_student_question_context
5. get_student_learning_report
6. get_representative_answers
7. recommend_questions
8. save_teaching_plan
9. generate_teaching_plan_file
10. save_learning_plan
```

#### 为什么删除 `get_class_learning_trend`

趋势不是新的数据资源，而是对一个时间范围内多次作业分析结果的解释。如果 `get_class_homework_analysis` 已经支持 `homeworkId/homeworkIds/timeRange` 三种范围，并返回按作业排列的统计序列，再建立 `get_class_learning_trend` 只会造成职责重叠，让模型难以判断应该调用哪一个。

合并后的链路为：

```text
教师 ID（AuthContext）
→ 上游教师—班级关系校验
→ Agent Tool Facade 按 homeworkId/homeworkIds/timeRange 统一查询
→ 单次作业优先复用 ChatBI HwAnalysis
→ 周期分析优先复用 ChatBI ClassWeekAnalysis
→ ChatBI 尚未覆盖的明细再通过 HP Review/QuestionTag/ErrorReason 补齐
→ 由确定性服务统一得分率、正确率、知识点/错因比例、难度和样本量口径
→ 按时间返回 homeworkAnalyses[]、必要数值差值和 dataQuality
→ 模型结合教师问题判断持续改善、持续薄弱、偶发变化或证据不足
```

原先仅审查 HP 时，会误以为所有统计都要从批改明细重新聚合。纳入 ChatBI 后，单作业分析、学生周报和班级周报已有可复用实现；真正缺少的是面向 Agent 的统一查询 Facade、任意时间范围适配，以及教师—班级、家长—孩子的服务端权限校验。

输出不能只给“平均分变化”。不同作业总分和难度可能不同，至少应返回：

```text
每次作业：提交人数、有效样本量、平均得分率、平均正确率、题目难度分布
知识点序列：每个知识点在各次作业中的题目数、作答人数、正确率
错因序列：主要错因的数量和占比变化
数据质量：作业过少、样本不足、知识点标签缺失、不同作业难度不可比
```

担心的不是模型看不懂前后差异，而是不能让模型从全量学生原始记录中自行算平均分、正确率和比例。确定性代码负责基础指标与必要的数值差值，模型负责结合难度、样本量和知识点分布解释变化。若时间范围内只有一份有效作业，返回 `INSUFFICIENT_HISTORY`，模型只能做单作业总结，不能虚构趋势。

合并逻辑如下：

- `list_accessible_contexts` 更适合作为 Context Builder 和前端选择器的能力。系统在进入会话时预加载最近班级、孩子、作业和已批改题目，不必让模型先调用一个 Tool 才知道用户能访问什么；
- `get_homework_detail` 可并入 `search_homeworks` 或班级分析结果，只有当完整作业元数据经常被单独查询时再拆出；
- `get_student_question_review` 与学生/家长所需的题目事实合并为 `get_student_question_context`，一次返回题干、标准答案、解析、学生作答和逐空批改结果；
- `get_class_benchmark`、`get_error_reason_summary` 先作为班级分析和学生报告中的可选统计模块，不必立即成为独立 Tool；
- `list_pending_homeworks` 在上游查询能力补齐后，可并入 `get_student_learning_report` 的计划输入数据；
- `search_teaching_resources` 在 RAG 上线时作为第 11 个 Tool 独立加入，避免把知识检索和业务数据查询混在一起。

底层 E05—E13 继续作为这些 Tool 的领域服务和数据来源，不直接全部暴露给模型。这样可以控制 Tool 数量、减少模型规划难度，并将权限、聚合口径和数据裁剪固定在服务端。

### 12.6 Tool 数量与动态暴露策略

企业落地没有“必须少于多少个”的硬阈值。17 个 Tool 对能力强的模型并非绝对过多，但如果名称相近、职责重叠、参数复杂，17 个已经足以明显增加选错 Tool、漏调 Tool 和参数填错的概率。判断数量是否合适应看以下四点：

1. 每个 Tool 是否对应一个清楚且互斥的业务动作；
2. 模型完成高频任务是否通常只需要 1—3 次 Tool 调用；
3. 相似 Tool 是否会让模型难以区分；
4. Schema 总长度、返回数据量和调用链是否可控。

HP 不应在每次推理时暴露完整 Tool Catalog，而应使用三级筛选：

```text
系统全部 Tool
∩ 当前角色允许的 Tool
∩ 当前角色与页面上下文允许的 Tool
= 本次模型调用可见的 Tool Set
```

建议第一阶段的角色默认集合：

| 角色 | 默认可见 Tool | 数量 |
| --- | --- | --- |
| 教师 | `search_homeworks`、`get_class_homework_analysis`、`get_question_context`、`get_representative_answers`、`recommend_questions`、`save_teaching_plan`、`generate_teaching_plan_file` | 7 |
| 学生 | `get_student_question_context`；只有答疑后明确需要巩固时再开放 `recommend_questions` | 1—2 |
| 家长 | `search_homeworks`、`get_student_learning_report`、`get_student_question_context`、`recommend_questions`、`save_learning_plan` | 5 |

这里的“可见”是指模型本轮可以选择调用，不是指前端向用户展示内部 Tool 名称。产品界面仍然展示“分析本周学习”“讲解这道题”“制定周末计划”等用户语言。

从调用协议看，每一次允许模型做 Tool Calling 的模型推理，都必须明确当前可用 Tool 的定义和参数 Schema。普通模型 API 通常随每次请求传入；少数平台可以通过会话 ID 或预注册配置引用已有定义，但 HP 后端仍要记录本轮允许使用的 Tool Set。一轮用户对话也可能包含多次模型推理：先决定调用 Tool，拿到 observation 后再判断是否继续调用或生成答案。

用户身份在登录和建会话时已经确定，因此不需要每轮让模型重新判断身份。Runtime 在会话建立时形成角色白名单，并在每次 Tool 真正执行前重新校验权限。后一个校验不能省略，因为家长绑定、教师任课关系、作业归属和账号状态可能在会话期间变化。

### 12.7 AuthContext 与 Tool 入参规则

Tool 是否需要多个 ID，与“多少种角色会使用它”没有直接关系。关键是：完成这个业务动作，需要用户明确选择哪些目标资源。

Runtime 应在服务端注入以下上下文，不能交给模型填写：

```text
AuthContext
├── actorId            当前登录账号 ID
├── actorRole          teacher / student / parent
├── tenantId/schoolId  组织与学校范围
├── boundChildIds      家长绑定的孩子范围
├── classScope         教师可访问的班级范围
└── permissionSet      当前角色的操作权限
```

模型只提供目标资源和业务筛选条件，例如 `classId`、`homeworkId`、`questionId`、时间范围和学科。具体规则是：

- 学生查询自己的批改题目时，Tool 不接受可改变主体的 `studentId`，服务端强制使用当前学生身份；
- 家长只有一个绑定孩子时可省略 `studentId`；绑定多个孩子时，由家长选择目标孩子，服务端再校验该 ID 是否属于 `boundChildIds`；
- 教师查询班级或学生时可以传 `classId`、`studentId`，但这些都是“目标资源”，不是调用者身份，Policy Guard 必须验证其属于教师的数据域；
- 同一个 Tool 被多个角色使用时，可以保持同一 Schema，由服务端按角色执行不同权限判断。只有当业务语义、输出内容或合规规则差异很大时，才应拆成不同 Tool。

例如 `get_student_question_context` 的模型参数可以是：

```json
{
  "studentId": "可选，仅家长多孩子或教师指定学生时使用",
  "studentHwId": "目标学生作业 ID",
  "questionId": "目标题目 ID"
}
```

模型不能传 `parentId`、`teacherId` 或“我是管理员”等权限声明。Tool Executor 会将模型参数与可信 `AuthContext` 合并，再进行资源级鉴权。

### 12.8 为什么现有 Controller 不应原样注册成 Tool

现有接口当然可以复用，但“作为 Tool 的底层实现”与“将接口原样交给模型”是两件事。HP 应在 Controller/Service 上方增加一层 `AgentToolFacade`：

```text
LLM
  → Agent Tool Schema
  → Tool Executor / Policy Guard
  → AgentToolFacade（鉴权、编排、聚合、裁剪、口径）
  → 现有 Controller 对应的 Service / Integration
  → MySQL、MongoDB、Redis、上游服务
```

不能直接暴露的主要原因如下：

1. **接口鉴权不等于资源鉴权。** 当前 `BaseController` 能读取 `userId/userType`，但一个接受 `studentId` 或 `hwId` 的接口，不一定会证明该家长绑定了这个学生、该教师任教这个班级。模型参数不能成为权限依据；
2. **现有接口通常过细。** 完成一次学生单题答疑，底层可能要分别查询学生作业、题目快照、批改结果、标准答案、知识点和难度。让模型自己串六个接口会增加延迟、失败点和规划错误；高层 Tool 应由确定性代码一次编排完成；
3. **返回 DTO 面向内部系统，不面向模型。** 其中可能有无关字段、历史字段、内部状态码、大图 URL 或全班原始作答。直接返回既浪费 Token，也可能泄露超出当前任务的数据；
4. **统计口径必须固定。** 每次作业的正确率、平均得分率、错因比例和必要数值差值应由服务端代码计算，并返回样本量、时间范围、难度和缺失数据；模型负责解释变化，不拿全量学生原始记录自行统计；
5. **参数需要边界。** Agent Tool 要限制最大时间范围、最大题数、分页大小、可选枚举和超时，避免模型发起无界批量查询；
6. **错误必须可推理。** Tool 应把底层异常统一为 `FORBIDDEN`、`NOT_FOUND`、`DATA_INCOMPLETE`、`VERSION_CONFLICT` 等稳定结果，让 Agent 知道应该追问、换条件还是结束；
7. **写操作需要额外协议。** 保存计划、修改内容和导出文件需要草案确认、`expectedVersion`、`idempotencyKey`、审计记录和异步状态，这些通常不是原 Controller 单接口天然具备的；
8. **需要统一治理。** Tool 层承担 Trace、审计、限流、超时、重试、熔断、敏感字段裁剪和指标监控，不能把这些判断散落在 Prompt 中。

以学生单题答疑为例，模型只看见一个高层 Tool：

```java
@AgentTool("get_student_question_context")
public StudentQuestionContext execute(Input input, AuthContext auth) {
    policyGuard.checkQuestionAccess(auth, input);
    StudentHomework homework = hwIntegration.findStudentHomework(input);
    ReviewResult review = reviewTaskService.getQuestionResult(homework, input.getQuestionId());
    QuestionDetail question = labelingQuestionService.getQuestion(input.getQuestionId());
    QuestionTag tag = questionTagService.getTag(input.getQuestionId());
    return assembler.toSafeAgentContext(homework, review, question, tag);
}
```

这层并不复制原有业务逻辑，而是复用现有 Service/Integration，补上 Agent 所需的授权、跨接口编排、稳定 Schema 和数据裁剪。

如果某个现有接口已经同时满足“资源级鉴权、稳定且紧凑的 Schema、参数有界、错误明确、读写幂等、语义正好对应一个用户任务”，它可以近似一对一封装成 Tool。例如单作业详情和推荐题接口比较接近这种情况，但仍建议经过 Tool Executor，而不是把 Controller URL 和内部 DTO 直接交给模型。

### 12.9 精简入口与基于会话历史的续接

#### 12.9.1 取消独立意图路由

第一版不再建设 Entry Router、廉价意图模型、意图枚举、`PendingRoute` 或独立槽位提取流程。入口只有两个确定分支：

```text
前端任务按钮
→ 校验登录态、角色、actionCode 和页面资源
→ 直接执行服务端绑定的确定性 Workflow

任意自由文本
→ 校验登录态并确定 TEACHER / STUDENT / PARENT AgentProfile
→ 使用 conversationId 调用同一个 Agent Runtime
→ Agent 理解目标、调用 Tool、追问或结束
```

这样不会在 Agent Graph 外再维护一份意图状态。模型理解用户目标本来就是 Agent 的职责；第一版为了省一次模型调用而增加分类器、槽位状态和转交协议，工程收益不足。

#### 12.9.2 Workflow 结果如何衔接 Agent

直接走 Workflow 不代表失去对话能力。Workflow 产出应保存 `artifactId/reportId`、输入范围、统计口径和证据 ID。用户在结果页点击“继续追问”时，以这些数据创建 Agent 会话：

```text
周报按钮
→ LearningReportWorkflow
→ reportId=R1001
→ 页面展示固定报告
→ 家长问“改成最近三周，只看数学”
→ Agent Session(reportId=R1001, role=PARENT)
→ Agent 重新选择查询范围并生成新分析
```

这样固定流程保持确定性，开放追问才使用 Agent。

#### 12.9.3 缺少信息时如何续接

自由文本一旦进入 Agent，后续追问不退出当前会话，也不转交给另一个分类器。Python 从同一 thread 的 checkpoint 恢复摘要后的消息状态，结合本轮页面上下文和登录身份构造模型输入：

```text
checkpoint_messages（摘要后的 Agent state）
auth_context（每次请求从可信登录态重新构造）
page_context（每次请求按需加载）
active_goal（可以从最近消息提取；重要任务约束可单独结构化保存）
known_constraints（按业务需要持久化）
last_tool_observations（只有后续需要复用时才保存引用或摘要）
current_draft_ref（存在可修改产物时保存）
```

例如：

```text
家长：分析一下孩子最近的学习
→ Agent 根据上下文发现时间和学科不明确
→ Agent：您更想看最近一周、一个月还是本学期？需要限定学科吗？
→ 助手追问作为普通消息落库，本轮结束

家长：最近一个月，只看数学
→ 使用同一个 conversationId 发起新请求
→ 以新 turn_id 发起请求；Python 以同一 thread_id 恢复 checkpoint，仅追加本轮新输入
→ Agent 调用 get_student_learning_report
→ 根据 observation 回答；必要时继续追问
```

追问句由 Agent 生成。前端仍可把常用回答显示成快捷选项，但它们只是对 Agent 文本的结构化交互优化，不形成独立槽位路由系统。用户改变目标时，Agent 直接根据最新消息更新 `activeGoal`。

普通的用户追问不视为挂起中的任务：模型已经生成追问并结束本轮，用户补充信息后作为新请求进入，依赖同一 thread 恢复的 Agent state 继续理解上下文；这一交互本身不要求 checkpoint。本项目仍决定配置 PostgreSQL checkpoint，以持久化 Agent thread 状态并支持后续恢复能力；后台续跑任务的发现、调度与聊天消息仍分别建模。

#### 12.9.4 一套 Runtime，三个角色配置

`ParentAgent`、`TeacherAgent`、`StudentAgent` 不是三个独立系统。更准确的表达是同一个 Agent 执行框架使用不同 `AgentProfile`：

```text
Agent(role=TEACHER)  → 教师 Prompt + 教师 Tool Set + 教师数据域
Agent(role=STUDENT)  → 学生 Prompt + 学生 Tool Set + 学生数据域
Agent(role=PARENT)   → 家长 Prompt + 家长 Tool Set + 家长数据域
```

之所以写 `Agent(role=PARENT)`，只是为了明确它不能看到教师 Tool、其他学生数据，并使用适合家长的表达方式，不表示需要额外部署一个“家长 Agent 服务”。

### 12.10 模型调用、会话保存与 Prompt Cache：概念澄清

这里不应包装成三个独立的“高级架构能力”。对 HP 来说，核心事实很简单：模型本身没有可靠的业务记忆，Java 保存业务问答，Python 在下一次模型调用时从 PostgreSQL checkpoint 恢复 Agent state。这是同一条多轮对话链路的两个环节。

#### 12.10.1 模型调用与后端会话保存是同一条链路

绝大多数模型推理都只根据本次输入生成本次输出。即使模型平台提供 conversation/thread/previous-response ID，本质上也是平台替应用保存或引用部分历史，并不意味着模型拥有永久记忆。

HP 的实现可以直接理解为：

```text
用户发送消息
→ Java 登记本轮用户消息，转发当前输入和可信业务上下文
→ Python 按稳定 thread_id 恢复 checkpoint；达到阈值时先同步摘要
→ 选择本轮允许使用的 Tool Schema
→ 裁剪并组装模型输入
→ 调用模型
→ 执行 Tool，必要时再次调用模型
→ Java 保存用户问题和最终回答；Python 由 checkpointer 保存含工具消息/摘要的 Agent state
```

后端通常需要保存：

```text
sessionId
用户与助手消息
当前角色
当前孩子/班级/作业/题目
Tool 调用记录与必要结果摘要
当前报告或计划草案
```

“Agent Runtime”不是一种神秘的新技术，只是对执行 Agent 循环的后端代码的统称。除了会话保存，它还负责：选择 Tool、执行 Tool、把 observation 交回模型、限制最大调用次数、处理错误和判断本轮是否结束。本方案由 Python create_agent 承担 Agent 循环，Java 保持前端唯一入口。

#### 12.10.2 Tool Schema 是否每次传递

对于普通无状态模型 API，本次希望模型调用哪些 Tool，就在本次请求中提供哪些 Tool 的名称、说明和参数 Schema。后端可以根据登录角色、页面上下文和 Agent 当前状态每轮组装。

如果模型平台提供服务端会话或已注册工具能力，传输形式可能有所不同，但应用层仍应明确记录“本轮模型被允许使用哪些 Tool”。平台的会话功能不能代替 HP 自己的身份、资源权限和业务审计。

#### 12.10.3 Prompt Cache 通常是模型服务商的优化

Prompt Cache 指模型服务商复用相同输入前缀的内部计算。它不是 HP 在 Redis 里缓存一段模型回答，也不是后端自己实现模型的 KV Cache。

```text
经常相同的前缀：System Prompt + 安全规则 + Tool Schema
每轮变化的内容：会话消息 + Tool observation
```

不同模型平台可能是：

- 自动识别相同前缀并缓存，HP 不需要额外开发；
- 要求请求中传一个缓存配置或缓存标识，HP 只需按平台文档接入；
- 完全不支持，此时正常发送 Prompt 即可。

HP 后端能做的主要是让 System Prompt、Tool 顺序和 Tool 描述保持稳定，并观察平台返回的 cached tokens、耗时和费用指标。缓存真正如何存储和复用由模型服务商完成。

Prompt Cache 不保存完整会话、不自动记住 Tool 结果、不替代数据库和鉴权。同一个 Prompt 命中缓存后，模型仍然会生成新的回答。因此它只是可选的成本/延迟优化，不作为 HP Agent 的核心产品能力，也不应当作为简历中的主要技术亮点。

### 12.11 鉴权究竟放在 Tool 里面还是 Tool 调用之前

“调用 Tool 之前鉴权”指的是：**模型已经生成 Tool Call 和参数，但在任何业务查询或修改真正发生之前进行鉴权。** 它不是要求在模型选择 Tool 之前就知道所有资源 ID。

推荐执行顺序：

```text
1. 用户请求进入 Runtime，校验登录凭证
2. 模型输出 Tool Call(name, arguments)
3. Tool Executor 校验 Tool 是否在当前角色白名单
4. 校验参数 Schema、数量、时间范围和枚举
5. Runtime 注入可信 AuthContext
6. Policy Guard 根据 AuthContext + 目标资源 ID 做资源级鉴权
7. 鉴权通过后才调用 AgentToolFacade/领域 Service
8. 对返回结果做字段裁剪和隐私检查
9. 记录审计与 Trace，再把 observation 交给模型
```

工程上，第 3—6 步可以写在统一的 Tool Executor 拦截器中，也可以把第 6 步放在每个 Tool Handler 的第一行。两种说法并不冲突。推荐采用两层防御：

- Tool Executor 统一检查登录态、角色白名单、参数边界和通用策略；
- Tool/领域 Service 再检查具体资源归属，防止该 Service 被其他入口调用时绕过权限。

不要先查询完数据再鉴权。对于写操作，还应在最终提交瞬间再次检查权限和版本，防止“预览时有权限、确认时权限已经变化”的竞态问题。

### 12.12 两个客户端与三种角色的会话模型

HP 实际有教师端和学生端两个客户端；学生端登录时再选择学生或家长角色。客户端数量与权限角色数量是两个维度：

```text
clientType = TEACHER_APP / STUDENT_APP
actorRole = TEACHER / STUDENT / PARENT
```

Agent Session 应记录本次选择的角色。学生端切换“学生/家长”时，应重新签发或刷新包含角色、绑定关系版本和数据范围的会话凭证，不能只改前端变量。

如果系统当前约定“家长解绑唯一孩子后立即退出登录”，Agent 也必须同步失效：

1. 新的用户消息不再进入原 Agent Session；
2. 尚未开始的 Tool Call 返回 `AUTH_CONTEXT_EXPIRED`；
3. 正在执行的查询在返回敏感数据前重新检查绑定关系，失效则丢弃结果；
4. 尚未保存的 Agent 草案、待执行的导出任务和临时下载权限立即失效；
5. 如果存在尚未完成的异步业务任务，在返回敏感结果或提交正式变更前再次鉴权，无法通过则停止；
6. 前端回到登录或角色选择页。

不能因为 Agent 在解绑前已经开始思考，就允许它继续访问孩子数据。模型会话历史也不能作为权限依据。可通过 `authVersion/bindingVersion`、短时访问令牌、解绑事件清理 Session 缓存等方式实现及时失效。

### 12.13 是否给 Agent 提供写 Tool：第一版产品决策

#### 12.13.1 结论

第一版不向 Agent 开放修改标准答案、解析、题目分数、学生批改结果和触发重批等核心业务写 Tool。原因不是技术上做不到，而是这些操作已经有明确按钮和编辑页面，对话没有带来足够新增价值，却显著增加了误操作、越权、确认和审计成本。

第一版采用：

```text
Agent 负责理解和分析
→ 发现用户想修改正式数据
→ 用文字说明应前往的现有页面和操作入口
→ 用户自行进入现有编辑页面
→ 在结构化表单中核对并提交
→ 现有业务流程负责保存和重批
→ 用户可返回 Agent 刷新分析结果
```

例如教师说“第三题标准答案不对，改成 3/4 并重新批改”，Agent 可以说明自己不能修改正式批改数据，并提示教师前往该作业的题目详情/定标编辑页面，使用已有的修改答案和重批功能。第一版不生成跳转链接或操作卡，避免为低频便利额外开发页面路由、参数传递和安全校验。

#### 12.13.2 为什么现阶段不值得做

1. **已有页面更高效。** 修改答案、分数和批改结果需要查看题目图片、blank、旧值和影响范围，结构化页面比聊天确认更直观；
2. **新增价值不足。** 如果 Agent 最后仍要让用户逐项核对，节省的操作步骤有限；
3. **错误成本高。** 修改标准答案或题目分数可能触发全班重批，风险远高于查询和生成讲评；
4. **工程成本高。** 安全落地需要 ChangeSet、影响预览、一次性确认、乐观锁、幂等、审计、补偿和异步状态；
5. **会扩大第一版范围。** 当前更应该验证教师分析、学生答疑、家长报告和学习计划是否真正有使用价值。

只有以后出现明确证据，例如教师经常需要跨多题批量修改、现有页面操作明显低效，才重新评估“Agent 生成修改草案 + 页面确认提交”。即使到那时，模型也只负责准备修改建议，最终提交仍应通过确定性业务接口完成。

#### 12.13.3 第一版保留哪些产物操作

以下操作虽然会写入数据或对象存储，但写入的是 Agent 自己生成的产物，与修改正式批改数据的风险不同，可以保留：

| 操作 | 是否保留 | 原因与处理 |
| --- | --- | --- |
| 保存讲评/备课草案 | 保留 | 只保存教师个人草案；使用 planId、version 和 ownerId |
| 生成 DOC/PDF | 保留 | 用户明确要求后异步生成新文件版本，使用 idempotencyKey；完成后由前端提供下载按钮 |
| 保存家长学习计划 | 保留 | 先保存家长侧草案；如果以后发布到学生任务列表，再单独设计发布确认 |
| 修改标准答案/解析/题目分数 | 不作为 Agent Tool | 文字引导用户使用现有定标编辑页面，不做自动跳转 |
| 修改学生批改结果/作文分数 | 不作为 Agent Tool | 文字引导用户使用现有批改详情页面，不做自动跳转 |
| 单题或批量重批 | 不作为 Agent Tool | 由现有修改页面或重批按钮触发 |

读取 Tool 与这些低风险产物操作仍需身份认证、资源级鉴权、参数边界、审计、限流和超时。导出还需要幂等和对象存储访问控制，但不必为了第一版引入完整的 ChangeSet/confirmationToken 体系。

当前代码中的答案、分数、批改结果修改与重批能力继续作为现有产品功能保留，是代码能力盘点的一部分，不计入第一版 Agent Tool Catalog。

#### 12.13.4 未来若重新开放核心写 Tool 的最低要求

本节仅作为技术知识储备，不属于第一版范围。未来如果有真实产品需求，至少需要：

```text
修改草案 ChangeSet
修改前后快照
影响学生/题目范围
用户在结构化页面显式确认
expectedVersion 防止覆盖并发修改
idempotencyKey 防止重复提交
提交瞬间重新鉴权
requestId 串联数据库、MQ、算法回调与审计
异步重批状态和失败补偿
```

这说明“写 Tool 比读 Tool 复杂”是正确的工程知识，但不意味着 HP 为了证明 Agent 能力就必须实现它。合理的产品取舍本身比堆叠高风险 Tool 更重要。

### 12.14 Tool 阶段收敛结论与下一步

产品与 Tool 讨论已经达到可以进入技术设计的程度，当前确定项如下：

1. 产品任务按钮携带服务端预定义 `actionCode`，直接进入 Workflow；任何自由文本统一进入当前角色 Agent；
2. 第一版不建设独立意图模型、Pattern 路由、`PendingRoute` 和专用分类模型；普通跨轮目标与约束由会话消息历史承接，确需稳定复用的业务约束再结构化保存；
3. Agent 使用高层、角色化、带资源鉴权和聚合口径的读取 Tool，不原样暴露现有 Controller；
4. 教师、学生、家长按登录角色获得不同 Tool Set，每次 Tool 执行前校验资源权限；
5. 修改答案、分数、批改结果和重批不做 Agent Tool，也不开发跳转，只用文字引导现有功能；
6. 保存讲评/学习计划和生成 DOC/PDF 作为 Agent 新创造的产物能力保留；
7. 用户修改已生成内容时，修改逻辑文档草案并生成新文件版本，不覆盖旧对象；
8. RAG 作为后续独立的教学资源检索 Tool 接入，不混入业务统计 Tool。

下一阶段按以下顺序设计：

```text
服务边界：原 Java 领域服务与新增 Python AI 服务如何协作
→ 请求链路：按钮 Workflow、Agent Loop、会话历史与任务状态如何协作
→ 会话模型：消息、摘要、页面上下文和保留周期
→ Tool Registry/Executor/Facade：接口、鉴权、超时和错误协议
→ 文件产物：草案、版本、异步渲染和对象存储
→ 数据存储：MySQL、MongoDB、Redis 各自职责
→ 可观测性：Trace、Prompt/Tool 日志、Token、延迟和失败率
→ Evaluation Harness：Tool 选择、跨轮追问、权限和最终结果评测
```

基于当前代码盘点，Agent 第一阶段不需要为了“技术先进”新增数据库。现有组件基本可以承担：

| 现有技术 | 初步职责 |
| --- | --- |
| Python / FastAPI / LangChain `create_agent`（底层 LangGraph） | Agent Loop、会话上下文、Tool Executor、RAG 编排、流式输出和 AI 层权限预检；PostgreSQL checkpointer 持久化 Agent 线程状态 |
| Java / Spring Boot（原 HP） | Domain Facade、业务聚合、权威数据访问与最终资源鉴权 |
| MySQL | 会话/产物元数据、讲评和计划版本、任务状态、幂等记录 |
| MongoDB | 保留原有题目详情、模型调用日志和可选 Trace；不承载本方案 checkpoint |
| PostgreSQL | Python Agent checkpoint，包含摘要后的消息状态；框架管理基础设施表 |
| Redis | 活跃会话缓存、短期页面上下文、分布式锁、限流和临时状态 |
| RabbitMQ | DOC/PDF 异步生成和其他长任务通知 |
| OSS/TOS | 版本化文件产物与限时下载地址 |
| Prometheus | 模型调用、Agent/Workflow、Tool、Token、延迟和错误指标 |

需要新增的是 Agent 应用层代码与数据模型，而不是新的数据库品类。RAG 阶段再单独评估现有 Elasticsearch 和 VikingDB 是否满足教学资源的混合检索、ACL、版本和引用要求，并使用独立 Index/Collection。

## 13. Agent 与 RAG 的服务边界和语言选型

### 13.1 综合结论：同一个独立 Python AI 应用层

结合本文的多角色 Agent 和 RAG 文档中已经确定的资料解析、Hybrid Retrieval 与评测需求，推荐新增独立的 `hp-ai-assistant-service`，在同一个 Python 仓库中同时承载在线 Agent 与教学文档 RAG；原 Java HP 继续作为业务事实和批改 Workflow 的领域服务，ChatBI 继续作为确定性学情分析服务。

这修正了此前“新增独立 Java Agent 服务”的单独判断。只看 Agent Tool Calling，Java 完全可以完成；但把完整 RAG 需求纳入后，若在线 Agent 使用 Java、RAG 又使用 Python，会形成额外的 Java Agent → Python RAG 网络层，并重复模型网关、会话、Trace、Schema 和错误协议。Agent 本来就需要把 Domain Tools、Document Retriever 和 Question Retriever 组合进同一份 ContextPack，同一个 Python AI 应用层更简单。

### 13.2 推荐部署形态

```text
教师端 / 学生端
→ HP Java API Gateway
   ├── 登录态、角色和请求校验
   ├── 对话接口：创建 SseEmitter 并立即返回
   └── 有界后台线程池：调用 Python AI API 并读取其模型流
       ├── 下游 SSE 可写时，通过 SseEmitter 推送文本
       ├── 下游断开时，记录发送异常并继续读取上游流
       └── 模型完成后，保存完整问答

后台线程 → hp-ai-assistant-api（Python / FastAPI）
   ├── LangChain create_agent / AgentProfile + PostgreSQL checkpointer
   ├── Tool Registry / Policy Guard / Context Builder
   ├── Model Gateway / Document Retriever / Reranker
   ├── Teaching Plan / Artifact API / Trace / Evaluation Hooks
   └── HP Domain Facade API、ChatBI、题库和教学资料索引

同一 Python 仓库中的 ingestion-worker
→ PDF/Word/图片解析、OCR、分块、Embedding、索引、版本切换
```

Java API 对前端持有 SSE 连接；Java 后台线程单独消费 Python 返回的模型流。`emitter.send` 因客户端断开而失败时，异常不得终止上游流的读取，也不得取消 Python 请求；线程继续收齐模型输出并保存最终问答。Python `api` 与 `ingestion-worker` 共用代码仓库和数据模型，但作为两个进程/部署单元运行；在线 API 不执行耗时的批量解析和向量化，ingestion worker 不承载用户对话。

### 13.3 原 Java 领域与分析服务继续负责什么

当前 `hp-grading` 仍是 Java 8、Spring Boot 2.3.12 的 Maven 多模块项目：

```text
hp-grading
├── hp-grading-api
└── hp-grading-service
```

HP-Grading 继续负责：

- 作业、班级、学生、题目和批改结果的权威数据；
- 单作业/跨作业聚合所需的底层批改事实；
- 教师—班级、家长—孩子等资源权限的最终校验；
- 修改答案、分数、批改结果和重批等现有功能；
- RabbitMQ 异步批改、版本、防倒灌和任务状态机。

ChatBI 继续负责：

- 单次作业题目与学生分析；
- 学生/班级周报和教师/学校/区域统计；
- 正确率、得分率、知识点、错因、排名等确定性聚合口径；
- 既有建议生成和 PDF/Excel 报表能力。

Python 服务不能直连 HP/ChatBI 的业务表后绕过领域规则，而应调用为 Agent 封装的只读 Facade API。`AuthContext` 随内部请求传递，Python 侧先做 Tool 白名单和参数校验，Java 领域侧仍做最终资源鉴权。

### 13.4 为什么这里选择 Python

市场上不存在所有公司统一的语言标准：Java 企业使用 Spring AI/LangChain4j 是正式路线，Python 也不是 Agent 的原理要求。HP 选择 Python 的理由是这次新增的是完整 AI 应用层，而不只是给一个 Java Controller 增加模型调用：

1. Agent 与 RAG 在线查询共享模型、上下文、Retriever、Reranker、Trace 和评测，放在同一语言和服务中更容易组合；
2. 文档解析、Embedding、Reranker、RAG Evaluation 和 Milvus/VikingDB SDK 通常优先提供 Python 用法；
3. LangChain `create_agent` 提供高层 Agent Loop，底层使用 LangGraph runtime；PostgreSQL saver 持久化 Agent state/checkpoint，应用层仍负责会话/turn 业务记录、任务触发、重试和幂等；
4. 原 Java 8/Spring Boot 2.3 栈过旧，不适合直接引入当前现代 Java Agent 框架；
5. Python 服务与原 HP 通过稳定 Facade API 解耦，不要求升级核心批改链路；
6. RunHub 可以真实实现同一套 Python Agent/RAG Harness，HP 与 RunHub 只替换 Domain Tool 和 Retriever Adapter。

如果公司只有 Agent、没有 RAG/文档处理，而且 Java 服务已经升级到 Java 17 和现代 Spring Boot，那么使用 Spring AI 的独立 Java 服务同样合理。这里选择 Python 是基于 HP 已确认的完整需求，不应表达成“企业 Agent 一定使用 Python”。

### 13.5 技术栈分层

建议技术栈与 RAG 文档保持一致：

```text
Python 3.12
FastAPI + Pydantic v2
LangChain `create_agent`（底层 LangGraph runtime）
PostgreSQL checkpoint integration（`langgraph-checkpoint-postgres`）
SQLAlchemy 2 + Alembic
Redis
RabbitMQ + Celery
S3 / MinIO / TOS
OpenTelemetry + Langfuse
pytest + 自定义 Evaluation Harness
```

存储和检索适配按落地环境区分：

| 环境 | 关系数据库 | 文档向量/Hybrid 检索 | 原因 |
| --- | --- | --- | --- |
| 原公司 HP 的合理演进 | Java 管理业务历史；Python 新增 PostgreSQL checkpoint，原 MySQL/MongoDB 继续既有职责 | 验证现有 VikingDB 后新建独立教学文档 Collection | 新增 PostgreSQL 承载 Agent 状态，不迁移原业务数据 |
| RunHub 可运行参考实现 | 复用现有 Supabase PostgreSQL | `pgvector + PostgreSQL keyword/全文检索 + RRF` | 资料规模尚小，减少新基础设施；先验证检索质量，再决定是否引入独立向量库 |

两边保持相同的 `DocumentRetriever`、Tool Schema、ContextPack、权限字段、Trace 和评测方法，底层通过 `VikingDocumentRetriever` 或 `PgVectorDocumentRetriever` 适配。Milvus 保留为未来数据规模或检索性能证明有需要时的替换实现，不作为 RunHub 一期必选组件。

### 13.6 面试中的准确表达

> HP 的核心批改系统是 Java 8/Spring Boot 2.3，继续负责业务事实、权限和可靠的异步批改 Workflow。新增能力包含多角色 Agent、教学文档解析、Embedding、Hybrid Retrieval、Reranker 和 Evaluation，因此新增独立 Python AI 应用层，在同一仓库中使用 FastAPI、LangChain `create_agent`（底层 LangGraph runtime）承载在线 Agent 和 RAG，并拆分 API 与 ingestion worker 两个部署单元。Agent 使用 PostgreSQL checkpointer；会话与单轮请求分别由 `conversation_id` 和 `turn_id` 标识，推荐 `thread_id = conversation_id`，见第 16.5 节。前端对话仍进入 Java API，由 Java Controller 创建并返回 `SseEmitter`，有界后台线程调用 Python AI API、读取模型流并转发给前端；下游断开时后台继续读取上游流并保存完整问答。checkpoint 提供持久化状态，但进程重启后的任务发现、重触发和幂等仍由应用层负责。Python Agent 通过受控 Facade 调用原 Java 领域服务，不直连业务库。RunHub 再真实实现相同接口和 Harness，一期复用 Supabase PostgreSQL/pgvector，对应 HP 侧的 MySQL/VikingDB；两边替换存储适配器而不改变 Agent、Retriever 和评测协议。

### 13.7 RunHub 真实代码交叉验证

已只读核对 `E:\run\runhub`：当前是 Java 21、Spring Boot 3.5.9、Maven 多模块、MyBatis 和 Supabase PostgreSQL，包含 `identity`、`race`、`zuicool`、`notification`、`common` 与 `api` 模块；`zuicool` 已有文章正文解析、OCR/LLM 结构化提取和确定性资讯更新 Workflow。这说明新的 Agent/RAG 不是从零构造业务，而是要复用现有赛事、用户赛事、评分和文章能力。

RunHub 的合理落地形态是：在同一个代码仓库中新增一个可独立部署的 Python AI 子项目，同时承载 Agent 与 RAG 的在线编排，并拆分 API/ingestion worker 进程；现有 Java 应用继续作为赛事与用户领域服务。Python 服务不直接绕过 Java 读取或修改赛事核心表，Domain Tool 通过受控内部 API 获取事实；AI 自有的知识文档、chunk、会话、trace 和产物元数据可以复用现有 PostgreSQL。这样既保留 Java 项目价值，又让 RunHub 真正积累 Python Agent/RAG 的实现经验。

这既符合 Agent/RAG 的主流 Python 工具链，也保留了 Java 业务系统的职责边界；不能把尚未在 HP 上实施的演进设计表述成已上线成果。

预约类开源项目的代码级对照、Agent/Workflow 边界和 HP 迁移清单见 [09-smart-appointment参考项目Agent分析与HP迁移.md](09-smart-appointment参考项目Agent分析与HP迁移.md)。该项目可作为 Tool Calling、槽位状态和 Retriever 的入门样本，但其前置分类器、全局内存会话和简单 FAISS RAG 不进入 HP 目标方案。

## 14. “直接套开源 Agent”与自研业务 Agent的边界

### 14.1 结论

“企业做 Agent 不必自己使用 LangChain/LangGraph 开发，直接套 Pi、Codex 等成熟 Agent”这句话只在部分场景成立：

- 企业内部 Coding Agent、运维助手、研究助手、通用办公 Agent和快速 PoC，可以优先复用成熟 Agent/Harness；
- 嵌入既有产品、面向外部用户、具有复杂领域权限和稳定数据口径的业务 Agent，通常仍要开发自己的业务应用层；
- 使用 Agent Runtime 不等于从零自研 Agent；无论采用框架还是应用层 Tool Loop，HP 仍需开发自己的 Context、Tool、权限、UI 和评测；
- 直接套 Pi/Codex 也不等于零开发。真正上线仍要补身份、会话、业务 Tool、鉴权、事件适配、审计和评测。

HP 属于第二类，不建议把 Coding Agent 改造成学生/家长/教师产品的核心 Runtime。

### 14.2 四个容易混淆的层次

```text
第一层：Model
  DeepSeek / Qwen / OpenAI / Claude 等，只负责生成和 Tool Call

第二层：Agent Runtime / Harness
  Model→Tool→Observation 循环、状态、事件、重试、暂停与恢复
  例：LangGraph、Pydantic AI、Pi Agent Core、托管 Agent API

第三层：业务 Agent 应用层
  身份、角色 Prompt、Context Builder、Domain Tool、权限、业务状态、评测
  例：HP 教师/学生/家长 Agent

第四层：产品入口
  小程序聊天页、按钮、SSE、文件下载、运营配置、反馈入口
```

Pi/Codex 更接近“第二层已经完成，并附带一套面向代码/文件/终端的第三、四层产品”；LangGraph主要提供第二层能力，让企业自己实现适合业务的第三、四层。

### 14.3 什么叫“套壳”

行业里“套壳”不是一个严谨架构术语，常指下列一种或多种做法：

1. **界面套壳**：保留现成 Agent 后端，只换 Logo、页面和聊天入口；
2. **Prompt 套壳**：增加一段行业 System Prompt，让通用 Agent 自称“教育助手”；
3. **Tool 套壳**：给现成 Agent 接 REST API、MCP Server 或插件，使其可以读取公司数据；
4. **Runtime 嵌入**：通过 SDK、CLI 子进程或独立服务调用现成 Agent，把事件转发到自己的产品；
5. **Fork 改造**：复制开源仓库，删除不需要的工具并增加自己的身份、会话和业务逻辑。

前三种通常很快，但产品边界较浅；后两种经常已经接近二次开发，维护成本不一定低于使用 Pydantic AI 或 LangChain Core 构建一个小而明确的领域 Agent。

### 14.4 以 Pi 套成 HP Agent，需要做什么

如果强行采用 Pi，大致链路是：

```text
HP 小程序
→ 自建 Java/Python Gateway
→ 将 userId、role、threadId 映射为 Pi session
→ 调 Pi Node/TypeScript Runtime
→ 禁用默认 Shell、文件写入等 Coding Tools
→ 注册 HP/ChatBI 的业务 Tool 或 MCP Server
→ 将 Pi 事件转换为小程序 SSE 协议
→ Tool 调用再次进行教师/学生/家长资源鉴权
→ 将消息、引用、文件和 Trace 同步到 HP 自己的数据库
→ 建立 HP 场景评测和上线治理
```

也就是说，Pi 可以省掉一部分 Tool Loop、上下文压缩和事件循环，但以下部分一个也省不掉：

```text
AuthContext
三角色 Tool 白名单
教师—班级、家长—孩子、学生—作业资源校验
HP/ChatBI Facade
业务会话与小程序历史展示
RAG Evidence/citation
DOC/PDF 产物
Trace、数据脱敏、Evaluation
```

而且 Pi 是 TypeScript Coding Agent，默认围绕工作目录、文件、Shell 和开发者单用户使用；HP 是 Python/Java、多租户、敏感学生数据和受限只读 Tool。两者的产品假设差异过大。

### 14.5 什么时候套现成 Agent 最合适

| 需求 | 推荐方案 | 原因 |
| --- | --- | --- |
| 公司内部代码开发、代码审查、仓库维护 | 直接采用 Codex/Pi 等 Coding Agent | 产品目标和工具假设一致 |
| 两周做内部知识助手 PoC | Dify、Pydantic AI、托管 Agent 平台或现成聊天 Harness | 先验证价值，减少基础设施开发 |
| 内部运维故障调查，用户是可信工程师 | 在沙箱和严格权限下扩展现成 Agent | 需要文件、日志、Shell、搜索等通用工具 |
| 面向家长/学生的学情与讲题助手 | 使用领域 Agent 应用层 + 框架 Runtime | 权限、事实口径、引用、产品交互均高度定制 |
| 明确参数的周报、入库、文档解析任务 | 确定性 Workflow | 没有必要引入 Agent 或套壳 |

### 14.6 LangChain 与 LangGraph 是否重复

它们不是必须同时完整使用；本方案使用 LangChain 高层 Agent API，并接受其底层 LangGraph runtime，但不手写图：

```text
LangChain Core
  模型客户端、Message、Tool Schema、Retriever 适配

LangGraph（由 create_agent 底层使用）
  State、节点/边、checkpoint、interrupt 编排 Runtime；HP 不手写 StateGraph
```

HP/RunHub 不需要为了技术标签引入完整 LangChain 生态。精简方案是：

```text
FastAPI + Pydantic
LangChain create_agent + PostgreSQL checkpointer
自研 HP/RunHub 的 Conversation Service、Domain Tool、权限、任务调度与 Evaluation
```

多轮对话本身不要求 checkpoint。用户补充信息时，以新的 `turn_id` 发起请求，并由 Python 恢复同一 thread 的 Agent state。项目选择 PostgreSQL checkpointer 是为了持久化 Agent 执行状态；它不会自动恢复重启前的后台任务。推荐 `thread_id = conversation_id`，同一聊天保持稳定；单轮执行另用 run_id。已确认的在线流式方案由 Java API 创建并返回 `SseEmitter`，将调用 Python AI 服务和消费模型流的工作放入 Java 有界后台线程池。前端断开时，捕获下游 `emitter.send` 异常但继续读取上游 Python 流，直至模型完成并保存最终回答；这仍不包含进程重启后的自动任务发现/重触发，也不补发断线期间错过的 token。

### 14.7 HP 的架构判断

HP 不应“从零造 Agent 框架”，也不应“给 Coding Agent 换个教育 Prompt”。正确做法位于两者之间：

```text
复用成熟框架负责 Runtime 通用能力
+
开发 HP 特有的领域 Agent 应用层
```

这意味着简历和面试中不能把“使用 LangGraph”当成核心亮点；真正的工程亮点是：

- 把确定性批改 Workflow 与开放式 Agent 控制面分开；
- 将 Controller 重构为少量高层 Domain Tool；
- 用 AuthContext 和领域 Facade 实现两层鉴权；
- 区分业务事实、教学资料 RAG 和模型解释；
- 建立会话历史、任务状态、上下文压缩、Trace、引用与 Evaluation Harness。

## 15. PoC、套壳边界与 Python Harness 参考

### 15.1 PoC 是什么

PoC 是 **Proof of Concept（概念验证）**。它不是一个可上线的完整产品，而是用最小成本回答一个关键问题：

> 这个方案在技术上和业务上，是否真的可行？

以 HP 家长学情 Agent 为例，一个 PoC 可以只包含：

```text
1 个角色：家长
1 个入口：纯文本对话
2～3 个只读 Tool：孩子作业列表、作业分析、知识点分析
一小批脱敏或 Mock 数据
20～50 条代表性测试问题
```

PoC 重点验证：模型会不会选对 Tool、能否正确补问范围、是否只使用授权孩子的数据、是否能基于 Tool 结果给出可靠报告。它不要求完整小程序页面、自动扩缩容、所有角色、全部 Tool 和生产级运维。

几个常被混淆的阶段：

| 阶段 | 核心问题 | 典型产物 |
| --- | --- | --- |
| PoC | 能不能做成 | 可运行的最小技术链路和测试结论 |
| Prototype | 产品交互应该长什么样 | 可演示页面或交互原型 |
| MVP | 最小产品是否有人愿意真实使用 | 面向一小批真实用户的可用版本 |
| Production | 能否稳定、安全、低成本地规模化运行 | 完整权限、监控、评测、容灾与运营体系 |

### 15.2 HP 不是“全部自研”，而是“套底座，不套产品”

不推荐的两个极端：

```text
极端一：把 Pi/Coding Agent 换一个教育 Prompt，直接当 HP Agent
极端二：从模型 HTTP API 开始，自己重新实现 Tool Loop、状态恢复、追踪和评测框架
```

推荐边界：

| 复用成熟框架 | HP 自己开发 |
| --- | --- |
| 模型适配与流式输出 | 教师、学生、家长的产品入口与引导 |
| Tool Calling 循环 | HP/ChatBI Domain Tool 与 Facade |
| Tool Calling 循环、模型适配 | AuthContext、数据域鉴权与 Tool 白名单 |
| 消息结构与上下文处理钩子 | 业务事实、RAG 证据和模型结论的隔离 |
| Trace、评测的基础能力 | 学情报告、讲题、备课文档等领域能力 |

一句话：**不套一个与教育业务不匹配的完整 Agent 产品；复用通用 Runtime/Harness，开发 HP 特有的领域应用层。**

### 15.3 Python 中值得参考的 Agent/Harness 项目

#### A. Pydantic AI 与 Pydantic AI Harness：最接近 Python 版 Pi 的学习材料

官方仓库：<https://github.com/pydantic/pydantic-ai>

Harness 文档：<https://pydantic.dev/docs/ai/harness/>

值得学习的部分：

- 类型化 Agent Loop、Tool 参数和结构化输出；
- 消息历史、上下文处理、Memory 和持久化接口；
- Tool 权限边界、执行环境与安全控制；
- Trace、Evaluation 以及可测试的依赖注入；
- Coder Harness 如何组织文件、Shell、计划、子任务与上下文压缩。

它与 Pi 一样能帮助理解“完整 Harness 由哪些部件组成”，但使用 Python，对当前学习成本更友好。HP 不需要复制其 Coding Tools；应迁移的是状态、上下文、安全和评测的设计思想。

#### B. Deep Agents：LangChain/LangGraph 生态中的 Python Agent Harness

官方文档：<https://docs.langchain.com/oss/python/deepagents/overview>

官方仓库：<https://github.com/langchain-ai/deepagents>

它提供规划、文件系统、子 Agent、长期 Memory，并基于 LangGraph 获得持久执行、流式事件和 Human-in-the-loop。它比 HP 第一版需要的能力更重，适合拆解学习 Harness，不建议把完整 Deep Agent 直接作为家长/学生 Agent。

#### C. OpenHands Software Agent SDK：Python 的完整 Coding Agent 参考

官方仓库：<https://github.com/OpenHands/software-agent-sdk>

它的核心 SDK 和 Agent Server 以 Python 实现，具有 Agent、Conversation、Tool、事件、远程执行环境等较完整的结构。它和 Pi 一样主要面向代码任务，因此不适合作为 HP 产品直接套壳，但适合阅读 Conversation、Agent Runtime、Tool 执行与沙箱隔离的工程实现。

#### D. smolagents：最适合看懂最小 Agent Loop

官方文档：<https://huggingface.co/docs/smolagents/main/index>

官方仓库：<https://github.com/huggingface/smolagents>

它用较少代码实现 Multi-step Agent、ToolCallingAgent 和 CodeAgent。适合先看懂 `模型决策 → Tool 调用 → Observation → 再决策` 的循环，但它不是 HP 所需的完整会话、权限、checkpoint 和评测平台。

#### E. LangGraph：`create_agent` 使用的底层 Runtime

官方仓库：<https://github.com/langchain-ai/langgraph>

LangGraph 提供显式 State、节点/边、checkpoint、interrupt、恢复与事件流。HP 使用 LangChain `create_agent`，因此底层会使用 LangGraph runtime 和 PostgreSQL checkpoint saver；业务代码不直接编排节点和边。普通追问仍以新 turn 结束本轮；服务重启后的任务发现与重触发由应用层任务状态和 worker/队列实现。

### 15.4 当前学习与落地顺序

```text
学习 Harness 组成：Pydantic AI Harness
        ↓
理解消息历史、Context、Memory 与评测
        ↓
HP/RunHub 实现：FastAPI + Pydantic + LangChain create_agent + PostgreSQL checkpointer
        ↓
Java/ChatBI 通过 Domain Facade 提供只读业务 Tool
```

第一版不要同时把 Pydantic AI、Deep Agents、LangGraph 全部引入同一个项目。当前建议是：

- **Pydantic AI Harness 用作源码和架构参考**；
- **HP/RunHub 使用 LangChain `create_agent` 与 PostgreSQL checkpointer；不手写 LangGraph 图，任务调度与幂等由应用层实现**；
- **HP 的角色权限、业务 Tool、Context Builder、RAG Evidence 和 Evaluation 由项目自己实现**。

## 16. FastAPI、Pydantic、LangChain Agent 与 LangGraph runtime 的职责边界

### 16.1 先看各层在一条请求链路中的位置

```text
教师/学生端小程序
        ↓ HTTP/SSE
HP Java Gateway / 登录体系
        ↓ 携带 userId、role、token、requestId
Java Controller：创建并返回 SseEmitter
        ↓
有界后台线程池：调用 Python AI API，并持续读取其模型流
        ↓
FastAPI：Python AI 服务的内部网络入口
        ↓
Pydantic：校验 Java 传来的请求、AuthContext 和上下文数据
        ↓
LangChain `create_agent`（底层 LangGraph runtime）：模型决策、执行获准 Tool、返回 Observation，直到回答或追问
        ↓ Tool Call
HP/ChatBI Domain Facade：重新鉴权并查询真实业务数据
        ↓
MySQL / MongoDB / Elasticsearch / VikingDB

Python 模型流 → Java 后台线程
        ├─ emitter 可写：通过 SseEmitter 推送文本片段
        └─ 前端已断开：继续消费模型流，收齐后保存最终问答
```

这几层各自负责不同边界：

| 组件 | 一句话职责 | 在 HP 中的角色 |
| --- | --- | --- |
| Java Controller + SseEmitter | 接收前端请求并返回 SSE | 面向用户的 API 与流式响应层 |
| FastAPI | 接收 Java 发来的内部 AI 请求并返回模型流 | Python AI 服务的内部 API 层 |
| Pydantic | 定义、校验、序列化数据 | 内部请求 DTO、AuthContext、Tool Schema |
| Java 后台线程池 | 调用 Python、消费上游模型流、推送 SSE、保存最终问答 | 与前端连接解耦的本轮执行器 |
| Java Conversation Service | 加载会话消息、构造传给 Python 的上下文、保存用户输入和最终回答 | 会话持久化 |
| LangChain `create_agent` + LangGraph runtime | 标准 Agent Loop、状态与 checkpoint；业务代码不手写节点/边 | Agent Runtime |

### 16.2 FastAPI：Python AI 服务的内部 Web 外壳

FastAPI 可以类比 Spring Boot 中的 `Controller + 参数绑定 + 一部分 Filter/Interceptor + OpenAPI`。

它面向 Java AI 调用层，不直接承担小程序的外层 SSE 连接。HP 中可由它提供：

```text
POST /internal/agent/stream                   返回模型流供 Java 消费
POST /api/workflows/learning-report
POST /api/knowledge/documents                 RAG 资料入库
GET  /health
```

主要职责：

- 接收 Java API 后台线程发来的内部 HTTP 请求；
- 接收并校验 Java 传入的 requestId、conversationId、turnId、AuthContext 和本轮上下文；
- 通过依赖注入构造数据库连接、模型客户端和 AuthContext；
- 做请求级认证、限流、异常转换和日志关联；
- 将模型输出以流式响应返回给 Java；Java 再通过 `SseEmitter` 推送给前端；
- 自动生成 OpenAPI/Swagger 文档，便于 Java 与前端联调；
- 承载健康检查和服务部署入口。

FastAPI 不负责：

- 决定 Agent 调用哪个 Tool；
- 管理复杂 Agent State；
- 自动保存对话；
- 替代 HP Java 服务的资源级鉴权；
- 实现 RAG 检索逻辑。

### 16.3 Pydantic：数据契约和边界校验

这里的 Pydantic 是数据校验库，不是 Pydantic AI Agent 框架。FastAPI 本身也用 Pydantic 处理请求和响应。

在 HP 中建议定义以下模型：

```python
class AuthContext(BaseModel):
    user_id: str
    role: Literal["teacher", "student", "parent"]
    tenant_id: str
    child_id: str | None = None

class ChatRequest(BaseModel):
    conversation_id: str
    turn_id: str
    message: str
    entry_context: dict | None = None

class HomeworkAnalysisInput(BaseModel):
    homework_ids: list[str]
    subject: str | None = None
    start_date: date | None = None
    end_date: date | None = None

class Citation(BaseModel):
    document_id: str
    title: str
    page: int | None = None
    chunk_id: str
```

主要职责：

- 校验前端和 Java 传入的字段类型、必填项和取值范围；
- 为每个 Tool 生成清晰、稳定的 JSON Schema；
- 校验模型返回的结构化输出，避免自由文本直接进入业务逻辑；
- 定义 AgentState 中允许保存的字段；
- 将 Python 对象可靠地序列化成 JSON、数据库记录或事件；
- 防止 Tool 因参数格式错误而查询错误范围的数据。

Pydantic 能保证“`student_id` 是字符串、时间范围合法、role 只能取三个值”，但不能保证“当前家长有权访问这个 student_id”。后者必须由业务鉴权完成。

### 16.4 LangChain `create_agent`：使用高层 Agent API

HP 使用 LangChain 的 `create_agent` 构造 Agent。`create_agent` 提供模型决策、Tool 调用和继续生成的标准循环，底层由 LangGraph runtime 执行；应用代码直接配置模型、Tools、提示词和 checkpointer，不手写 `StateGraph`、节点或边。

```python
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=system_prompt,
    checkpointer=checkpointer,
)
```

LangChain 统一 Message、模型调用、Tool Schema、Tool Calling 和结构化输出接口。模型提出 Tool Call 后仍由 Python 服务端执行获准的函数；HP 业务权限、Controller 逻辑和领域数据聚合由 Java/应用层负责。

### 16.5 会话、运行、消息与 checkpoint 的标识

- `conversation_id`：Java 产品层整段聊天的稳定标识。
- `thread_id`：LangGraph 状态分区键；推荐 `thread_id = conversation_id`，租户隔离时可加命名空间并保留映射。
- `run_id`：一次 Agent 执行，每轮新建，用于追踪、幂等、取消和 SSE 关联。
- `turn_id`：原文中的单轮业务标识；如保留，需与 run_id 明确关联，不能替代 thread_id。
- `message_id`：一条用户消息或最终助手消息的唯一标识；一次 run 可有多条内部消息。
- `checkpoint_id`：同一 thread 下某次状态快照的标识。

Java 保存会话元数据、用户问题与最终回答，负责历史查询和展示；具体业务表字段、物理存储与落库时机待定。Python 使用 PostgreSQL checkpointer 保存 messages、工具消息、中间状态及摘要后的 state。两边用途不同，写入通常不是跨库原子事务，需通过关联键、幂等和补偿保证最终一致。

### 16.6 PostgreSQL checkpoint、同步滚动摘要与 SSE

Python 使用 `create_agent` 和 `SummarizationMiddleware`，配置 PostgreSQL checkpointer。middleware 在模型调用前检查上下文，达到阈值时同步摘要旧消息并保留近期窗口，然后继续本轮模型/工具执行。摘要更新 Agent state，再由 checkpointer 持久化；不另建业务摘要表。摘要发生时经 Python → Java → 前端 SSE 显示“正在压缩上下文”，接受首字延迟增加。

后续轮次恢复同一 thread 的摘要后 state，只追加本轮输入，不默认回查 Java 全量历史。再次压缩按旧摘要与当前需要压缩的消息滚动推进。摘要不可逆，必要时从 Java 业务历史按需查原文；导入/重建状态需另行实现。

以下仅为配置示意，版本、模型与参数必须在实现时核实：

```python
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string(POSTGRES_URI) as checkpointer:
    # 初始化/迁移时执行，生产部署按锁定版本管理 schema。
    checkpointer.setup()
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=[SummarizationMiddleware(
            model=summary_model,
            trigger=("fraction", 0.7),  # 候选示例，非已定参数
            keep=("messages", 20),    # 消息数，不等于 20 轮
        )],
        checkpointer=checkpointer,
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": current_input}]},
        config={"configurable": {"thread_id": conversation_id}},
    )
```

60%/70%、保留消息数、token_counter 与 trim_tokens_to_summarize 均待压测和版本核对；token 预算还需预留 system prompt、工具 schema 与生成空间。摘要输入裁剪上限不等于近期消息保留窗口。工具调用与结果应成对安全处理。摘要状态事件需应用层接入，不能假设 middleware 自动生成 SSE。

同一 thread 的运行需要跨实例协调，不能假设 checkpointer 自动串行。排队/拒绝策略、锁或队列、租约、超时、取消和幂等仍待设计。摘要失败、checkpoint 写入失败、Java 最终回答写入失败需要可识别错误与补偿；禁止把摘要失败当成功。checkpoint 不自动发现并重触发未完成任务，也不自动重放 token。

前端请求到达 Java API 后，Controller 创建 `SseEmitter`，提交生成任务到有界后台线程池，并立即返回 emitter。后台线程调用 Python AI API 的流式接口，逐段读取模型输出；前端连接正常时，通过 `emitter.send` 转发片段，同时在内存中累计完整回答。前端断开导致 `emitter.send` 抛异常时，只记录/吞掉下游发送错误，后台线程继续读取 Python 上游流，模型完成后保存最终回答。

#### 已确认的 SSE 流式生成方式

```text
前端 → Java Controller
          ├─ 创建 SseEmitter 并返回
          └─ 后台线程 → Python 流式 API → 模型
                 ├─ emitter.send 成功：继续向前端推送
                 └─ emitter.send 失败：停止推送，但继续读完整上游流并保存回答
```

这只保证 Java 实例存活期间，前端断开不会取消该轮生成；checkpoint 不会持久化每个 SSE token，也不让已经退出的 Java 后台线程自动存活。因此，客户端重连到其他实例后，可以在生成完成后通过 `turn_id` 读取已保存的完整回答。若要求进程重启后恢复未完成 turn，应用需依据任务表/队列重新触发 Agent，并使用该未完成任务所属的 `thread_id` 读取 checkpoint；若要求重连后补发已经错过的 token，还需另建共享事件存储和按序补发机制。当前 SSE 方案不要求 token 补发。

如果需要后台任务在进程重启后重试，应用层可以维护轻量任务记录：

```json
{
  "task_id": "T123",
  "conversation_id": "C456",
  "turn_id": "U789",
  "status": "running",
  "attempt": 1,
  "started_at": "...",
  "last_heartbeat_at": "...",
  "result_ref": null,
  "error_code": null
}
```

状态约定：

- `pending`：任务已创建，等待 worker；
- `running`：worker 正在执行，配合心跳或租约识别超时任务；
- `completed`：结果已持久化；
- `failed`：执行失败，等待重试或人工处理。

服务重启后由 worker 启动扫描、队列重新投递或定时扫描超时任务，再使用任务记录中关联的 `thread_id` 读取 checkpoint 并重触发该 turn。若任务状态表和 checkpoint 更新时序不一致，应用需处理重复触发或恢复到最近完成步骤；只读查询可按策略重复执行，产物创建等写操作必须使用 `turn_id` 等幂等键。定时扫描不是必需条件：如果只需用户回来时续做，可在下一次请求中检查任务状态；如果用户离线后也必须完成，则需要后台 worker 和可靠触发机制。

Java 与 Python 分别保存业务历史和 PostgreSQL Agent checkpoint：产品消息保存用户输入与最终回答；checkpointer 按 Agent 执行步骤保存恢复所需的状态。checkpoint 不等于完整的 token 事件流或业务任务调度。若需要后台续跑，还需保存任务状态并实现 worker/队列触发；若需要更细排障，再结合 Trace：

| 数据 | 建议保存位置 |
| --- | --- |
| 会话标题、用户、角色、创建时间；用户输入和最终回答 | Java 管理的业务历史表，字段与物理存储待定 |
| Agent thread 的执行状态、消息状态、工具调用边界等 checkpoint | PostgreSQL checkpoint 基础设施表，由 `langgraph-checkpoint-postgres` saver 管理 |
| 需要后台续跑的任务状态和幂等键 | MySQL 或 MongoDB；按查询和事务需求选择，Redis 可作缓存/锁而非唯一长期来源 |
| 工具调用、耗时、错误、重试轨迹 | 日志/Trace；保存必要参数、结果摘要或业务结果引用 |
| 分数、作业、知识点等真实事实 | HP/ChatBI 原业务数据库 |

模型每次输入输出及工具输入输出不必全部作为产品消息长期保存。建议保存最终对话消息；保留 Tool 调用轨迹和必要的统计口径/结果引用以便排查与解释，并按敏感数据和保留期限要求决定是否保存完整内容。

### 16.7 一轮家长对话中各层如何协作

家长输入：

> 帮我看看孩子最近数学学得怎么样。

执行过程：

```text
1. Java Controller 接收请求，校验登录身份，创建并返回 `SseEmitter`，将本轮任务提交到后台线程池。

2. Java Conversation Service 校验会话归属、登记本轮输入并转发；不默认回传全部历史；Pydantic 校验 Java 后台线程发给 FastAPI 的内部请求和 AuthContext：
   role=parent、userId=P1001、childId=S2001。

3. Java 将本轮新消息、conversation_id、turn_id、页面上下文和可信 AuthContext 发给 Python Agent；同一会话复用 checkpoint 中的消息历史。

4. LangChain `create_agent` 读取本次请求指定的 checkpoint thread，
   将系统指令、应用传入的会话历史和家长允许使用的 Tool Schema 提供给模型。

5. 模型发现“最近”范围不明确，先生成追问：
   “您想看最近一周还是一个月？需要只看数学吗？”

6. 助手追问作为 T1 的最终回答保存。家长回答“最近一个月，只看数学”后，
   新请求使用新 turn_id=T2；Python 按 thread_id=C1 恢复 checkpoint，
   再调用 get_student_homework_analysis。推荐 thread_id=conversation_id，同一会话保持稳定。

7. Tool Executor 携带 AuthContext 调用 Java Domain Facade；
   Java 再次校验 P1001 是否仍绑定 S2001，然后查询 ChatBI/HP 数据。

8. Pydantic 校验 Tool 返回结构；`create_agent` 将结果写入 Agent 状态并继续模型/工具循环，
   checkpoint saver 持久化执行状态。

9. 模型基于真实数据生成结论。Python FastAPI 将模型流返回给 Java 后台线程；Java 通过 `SseEmitter` 逐段推送文本、引用和状态。

10. Java 业务历史保存用户可见问答，Python PostgreSQL checkpoint 保存 Agent 执行及摘要状态。
    若前端断开，Java 后台线程继续消费 Python 流并保存完整回答；Java 进程重启后的任务
    发现和重新触发仍需应用层任务调度。
```

### 16.8 哪些是必选，哪些可以替换

| 组件 | 第一版建议 | 可否替换 |
| --- | --- | --- |
| FastAPI | 保留 | 可用 Flask、Django、Litestar，但没有必要 |
| Pydantic | 保留 | FastAPI 已深度使用它，且 Tool Schema 很适合它 |
| LangGraph runtime | 通过 `create_agent` 间接使用 | 不手写 StateGraph；若未来需要定制状态图，可直接使用 LangGraph API |
| LangChain | 使用 `create_agent` 与所需模型集成包 | 不需要引入全部生态组件 |
| PostgreSQL checkpointer | 使用 `langgraph-checkpoint-postgres` | 可替换为其他实现 `BaseCheckpointSaver` 的持久化 saver |

最精确的技术栈表达应调整为：

```text
FastAPI + Pydantic
+ LangChain `create_agent`（底层 LangGraph runtime）
+ PostgreSQL checkpointer（`langgraph-checkpoint-postgres`）
+ Conversation Service + turn/task 调度 + Domain Tools + Worker
```

如果采用 LangChain 适配方式，Python 依赖通常按需安装，而不是把所有生态组件装进来：

```text
fastapi
uvicorn
pydantic
langchain
langgraph-checkpoint-postgres
模型 provider package
```

### 16.9 这些基础组件不会自动提供完整 RAG

它们可以承载 RAG 流程，但还需要另外实现或选择：

```text
文档解析/OCR
→ 章节识别与 Chunk
→ Embedding 模型
→ Elasticsearch 与向量库索引
→ Hybrid Retrieval
→ Rerank
→ ACL/组织/版权过滤
→ Evidence Pack
→ Citation 校验
```

在 HP 中：

- Agent Loop 或确定性 Workflow 按需调用检索步骤；
- LangChain Core 可以统一 Embedding/Retriever 接口，但不是必须；
- Pydantic 定义 Document、Chunk、Evidence、Citation 数据结构；
- FastAPI 提供资料上传、入库、检索和问答接口；
- Elasticsearch/VikingDB 才真正保存并召回教学资料；
- HP 自己实现 ACL、资料版本、删除同步和引用规则。

### 16.10 Pydantic AI 的定位与替代关系

`Pydantic AI` 是 Pydantic 团队开发的 Python Agent SDK，不等于数据校验库 `Pydantic`。它在 Pydantic 类型系统上提供：

```text
多模型适配
Agent Loop
Function Tool / Toolset
RunContext 与类型化依赖注入
结构化输出及校验重试
消息历史
流式输出
Tracing / Evaluation
可选 Harness、Memory、Context Management 与 Durable Execution
```

基本执行过程：

```text
agent.run(user_prompt, deps, message_history)
→ 调用模型
→ 模型产生 Tool Call
→ Pydantic 校验 Tool 参数
→ 执行 Tool，并把结果返回模型
→ 继续循环
→ Pydantic 校验最终结构化输出
```

它与现有方案不是叠加关系，而是可替代的另一种 Agent Runtime；当前落地路线不采用它：

```text
当前路线：FastAPI + Pydantic + LangChain `create_agent` + PostgreSQL checkpointer + 应用层会话与任务管理
可选替代：FastAPI + Pydantic + Pydantic AI
```

大致替代关系：

| 能力 | 本方案的实现方式 |
| --- | --- |
| Pydantic 数据校验 | 使用 Pydantic |
| 面向前端的 SSE | Java Controller + `SseEmitter`；生成逻辑由后台线程池执行 |
| Python AI 服务流式响应 | FastAPI 返回给 Java 后台线程，由 Java 转发到前端 |
| 模型、Message、Tool Calling | LangChain `create_agent` 与模型 provider 集成包 |
| 普通多轮上下文 | 同一 thread 的 PostgreSQL checkpoint state + 同步滚动摘要 |
| 后台任务重启后重试 | MySQL/MongoDB 任务状态 + worker/队列或定时扫描 + 幂等控制 |
| Agent 状态 checkpoint | LangGraph runtime 通过 PostgreSQL saver 持久化；应用层负责任务发现/重触发 |

对 HP 的判断：

- HP 当前使用 LangChain `create_agent`，接受其底层 LangGraph runtime，并通过 PostgreSQL saver 持久化 Agent thread；应用代码不手写图；
- `conversation_id` 标识完整聊天，每次提问使用新的 `turn_id`；追问结束当前 turn，用户补充后新建 turn 由 Python 恢复摘要后的 state；推荐 `thread_id = conversation_id`；
- checkpoint 提供恢复状态，但不负责服务重启后的任务发现和重触发；需要该能力时由任务状态、worker/队列或扫描器实现，并为写操作设置幂等键；
- 用户断网后，Java 后台线程继续消费 Python 模型流并保存完整回答；客户端可重连查询完整回答，不补发已错过的 token；
- 不建议同一版本同时采用 Pydantic AI Agent Loop、LangChain Agent 和自定义 Tool Loop，当前选择 LangChain `create_agent`；
- Pydantic AI Harness 适合作为 Memory、Context、安全、Trace 和 Evaluation 的参考，不代表 HP 必须采用其 Coding Agent 产品。
