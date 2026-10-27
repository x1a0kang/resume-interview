from pathlib import Path
import html, json, os, re, hashlib

ROOT = Path('E:/project')
OUT = Path(__file__).parent
M = '别人的项目/MODULAR-RAG-MCP-SERVER/'
P = '别人的项目/PaiSmart-main/'
J = P + 'src/main/java/com/yizhaoqi/smartpai/'
HP = '面试/hp-grading-项目梳理/06-HP教学资源RAG产品与技术方案.md'
E = html.escape

SOURCE_CACHE = {}
def ev(path, needle, note='', count=9):
    if path not in SOURCE_CACHE:
        SOURCE_CACHE[path] = (ROOT / path).read_bytes()
    lines = SOURCE_CACHE[path].decode('utf-8-sig').splitlines()
    idx = next(i for i, line in enumerate(lines) if needle in line)
    excerpt = '\n'.join(f'{i+1:>4}  {lines[i]}' for i in range(idx, min(idx+count, len(lines))))
    href = Path(os.path.relpath(ROOT/path, OUT)).as_posix()
    return f'<details class="evidence"><summary>{E(Path(path).name)} : {idx+1} <span>{E(note)}</span></summary><p class="sourcepath"><a href="{E(href)}">{E(path)}</a></p><pre>{E(excerpt)}</pre></details>'

def para(s): return '<p>' + s + '</p>'
def note(s): return '<aside class="note">' + s + '</aside>'
def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+x+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+x+'</td>' for x in r)+'</tr>' for r in rows)+'</tbody></table></div>'
def bullets(items): return '<ul>'+''.join('<li>'+x+'</li>' for x in items)+'</ul>'
def flow(title, steps):
    return '<div class="flow"><h3>'+title+'</h3><div class="flow-steps">'+''.join(f'<button class="flow-step" aria-expanded="true"><span class="step-title">{E(a)}</span><span class="step-desc">{b}</span></button>' for a,b in steps)+'</div><p class="flow-hint">点击步骤可收起或展开说明。顺序表示调用与数据流。</p></div>'
def sec(id,title,body): return {'id':id,'title':title,'body':body}

def cmdblock(text): return '<pre><code>'+E(text)+'</code></pre>'

GLOSSARY = [
('RAG','先从你自己的资料里找相关内容，再让 AI 根据找到的内容回答。'),
('MCP','一种通用连接方式，让 AI 助手可以调用外部工具或知识库。'),
('模型 / 大模型','负责理解文字、生成回答的软件；它本身不等于知识库。'),
('API','软件之间互相请求服务的入口，可以理解成窗口或电话线路。'),
('API Key','调用在线 AI 服务的密码；不要公开，也不要发给别人。'),
('向量 / Embedding','把一段话转换成一串数字，方便电脑按“意思相近”寻找资料。'),
('向量数据库','专门保存这些数字和原文，并按意思相似程度找资料的存储工具。'),
('关键词检索 / BM25','按问题里的词去找原文；常适合人名、术语、编号等明确词语。'),
('语义检索 / Dense','不要求字面完全相同，而是寻找意思接近的内容。'),
('混合检索 / Hybrid Search','同时用关键词查找和意思查找，再把结果合并。'),
('Chunk / 文本块','把长文档切成一小段一小段，方便查找和引用。'),
('RRF','把多种查找方式各自的排名合并；它不是准确率，也不是概率。'),
('重排 / Rerank','先找出一批候选资料，再重新比较谁更相关。'),
('分词','把句子拆成词，供关键词搜索使用。'),
('入库 / Ingestion','把文件读出来、切成小段、保存好，让之后能搜索。'),
('MCP Server','提供工具的程序；AI 助手通过 MCP 与它通信。'),
('MCP Host','运行 AI 助手并连接 MCP 工具的应用，例如某些桌面 AI 软件。'),
('Agent','能根据情况决定下一步调用什么工具的 AI 程序。'),
('Tool / 工具','Agent 可以调用的一项具体功能，例如搜索知识库。'),
('Trace / 过程记录','记下一次提问经过了哪些步骤、用了多久、在哪一步出错。'),
('LLM','Large Language Model 的缩写，即“大语言模型”，负责读文字和写回答。'),
('OCR','把图片或扫描件里的文字识别出来。'),
('Kafka / 消息队列','像待办事项传送带：先收下文件处理任务，后台再慢慢完成。'),
('Redis','速度很快的临时数据存储，常放短期状态或缓存。'),
('MySQL','常见的关系型数据库，适合保存用户、文件等结构清楚的数据。'),
('Elasticsearch / ES','搜索引擎，擅长按关键词搜索并管理大量文本。'),
('MinIO','像自建网盘一样保存文件的服务。'),
('权限过滤 / ACL','先确认当前用户能看哪些资料，再展示搜索结果。'),
('Outbox','把“数据库记录”和“待发送任务”一起保存，防止任务悄悄丢失。'),
('租约 / Lease','有时限的任务占用权；处理者失联后，其他处理者可以接手。'),
('幂等','同一任务重复执行，也不会重复写入或造成额外副作用。'),
('Docker / 容器','把服务连同运行环境打包运行，减少手工安装步骤。'),
('Maven','Java 项目的依赖安装和构建工具。'),
('pnpm','JavaScript 项目的依赖安装工具。'),
('Streamlit','用 Python 快速搭建网页操作面板的工具。'),
('评测集 / Golden Set','人工确认过的一批问题和正确答案，用来比较系统改动有没有变好。'),
('P95','把请求按耗时排序后，95% 的请求都不超过的时间；用于观察较慢情况。'),
('Recall@K','正确资料有没有进入前 K 个搜索结果的比例。'),
('MRR','正确资料在搜索结果里越靠前，分数越高的指标。'),
('Prompt','给 AI 的指令和背景文字。'),
('Token','模型处理文字时使用的计量单位；不严格等于一个汉字或一个词。'),
('MongoDB','一种适合保存对话记录、过程记录等内容的数据库。'),
('RabbitMQ','一种消息队列；项目用它把文件处理工作交给后台。'),
('VikingDB','一种向量数据库；HP 方案考虑用它按意思搜索教学资料。'),
('Cross-Encoder','一种逐对比较“问题和资料”的重排模型，通常比只看向量更细。'),
('RAGAS','一套帮助检查 AI 检索和回答质量的评测工具。'),
('Top-K','只取排名最前面的 K 条；例如 Top-5 就是前五条。'),
('P0','优先级最高、建议先处理的事项。'),
('Schema','约定数据里有哪些字段、字段叫什么、格式是什么。'),
('JSON / YAML','两种常见的配置或数据文件格式；本报告里的命令和代码需按原样复制。'),
('JDK','运行和编译 Java 程序所需的软件包；此项目需要 17 版。'),
('IDE','写代码和启动程序的软件，例如 IntelliJ IDEA。'),
('SDK','别人提供的一套代码工具，方便你的程序调用某项服务。'),
('HTTP','浏览器和网站、软件和服务之间常用的通信方式。'),
('WebSocket','一种保持连接的通信方式，适合实时逐段传输消息。'),
('工作流 / Workflow','按预先设定的步骤执行的一套流程。'),
('前端 / 后端','前端是浏览器里看到的网页；后端在电脑或服务器上处理数据和请求。'),
('PPTX / DOCX','PowerPoint 演示文稿和 Word 文档的文件格式。'),
('Baseline / 基线','比较优化效果时作为起点的原始版本。'),
('Provider / 服务提供方','真正提供大模型、向量或其他服务的厂商或软件。'),
('集合 / Collection','把同一类资料放在一起的一个资料组。'),
('ID','一条记录的唯一编号，用来区分不同文件或资料段落。'),
]

def beginner_box(text):
    terms = ''.join(f'<div><dt>{E(term)}</dt><dd>{E(definition)}</dd></div>' for term,definition in GLOSSARY)
    return '<aside class="note beginner"><strong>先看白话版：</strong>'+text+'</aside><details class="glossary"><summary>遇到陌生词？点这里看白话解释（不用背）</summary><dl>'+terms+'</dl></details>'

CSS = r'''
:root{color-scheme:light;--bg:#f6f8f8;--paper:#fff;--ink:#182b2d;--muted:#4e6264;--line:#d6e1e0;--accent:#07645a;--tint:#e7f3ef;--code:#edf2f2}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:100px}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.85 "Segoe UI","Microsoft YaHei",sans-serif}body.dark{color-scheme:dark;--bg:#121d1f;--paper:#19282a;--ink:#e5f1ef;--muted:#b0c3c2;--line:#3e5658;--accent:#78d7be;--tint:#203b36;--code:#203234}a{color:var(--accent);text-underline-offset:4px}button,input{font:inherit}button{cursor:pointer}button:focus-visible,a:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:4px}header{position:sticky;top:0;z-index:3;background:var(--paper);border-bottom:1px solid var(--line)}.topbar{max-width:1450px;margin:auto;display:flex;align-items:center;gap:24px;padding:14px 32px}.brand{font-weight:700;letter-spacing:.04em;white-space:nowrap;color:var(--ink);text-decoration:none}.topbar nav{display:flex;gap:22px;flex:1;font-size:14px}.topbar nav a{text-decoration:none;white-space:nowrap}.theme,.print,.filters button{border:1px solid var(--line);border-radius:8px;padding:7px 14px;background:var(--paper);color:var(--ink);white-space:nowrap}.layout{max-width:1450px;margin:auto;display:grid;grid-template-columns:220px minmax(0,1fr);gap:48px;padding:0 32px}.sidebar{position:sticky;top:92px;align-self:start;padding-top:42px;max-height:calc(100dvh - 110px);overflow:auto;font-size:14px}.sidebar a{display:block;text-decoration:none;color:var(--muted);padding:8px 10px;border-left:2px solid transparent}.sidebar a.active{color:var(--accent);border-color:var(--accent);background:var(--tint)}.side-title{font-weight:700;padding:0 10px 16px}.main{min-width:0;padding:48px 0 70px}.hero{padding-bottom:38px;border-bottom:1px solid var(--line)}.eyebrow{font:12px/1.4 Consolas,monospace;color:var(--accent);letter-spacing:.08em}.hero h1{font-size:clamp(32px,4vw,52px);line-height:1.3;margin:20px 0;letter-spacing:-.03em;overflow-wrap:anywhere}.hero .lead{font-size:20px;line-height:1.65;max-width:780px;color:var(--muted)}.facts{display:flex;flex-wrap:wrap;gap:12px 28px;font-size:13px;color:var(--muted);margin-top:30px}.facts b{color:var(--ink)}section{padding-top:44px;margin-top:12px}h2{font-size:28px;line-height:1.4;margin:0 0 22px}h3{font-size:20px;line-height:1.6;margin:26px 0 12px}p{margin:12px 0;max-width:92ch}ul,ol{padding-left:24px}li{padding:4px 0}strong{font-weight:650}code{font:14px/1.6 Consolas,"Microsoft YaHei",monospace;background:var(--code);padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}.note{border-left:4px solid var(--accent);padding:16px 22px;background:var(--tint);margin:22px 0}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:8px;margin:22px 0}table{border-collapse:collapse;min-width:630px;width:100%;background:var(--paper);font-size:14px}th{text-align:left;color:var(--accent);background:var(--tint);padding:13px 18px}td{vertical-align:top;padding:15px 18px}tbody tr:nth-child(even){background:var(--bg)}.flow{padding:24px;background:var(--paper);border:1px solid var(--line);border-radius:8px;margin:26px 0}.flow h3{margin:0 0 20px}.flow-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.flow-step{text-align:left;color:var(--ink);border:1px solid var(--line);background:var(--bg);padding:18px;border-radius:8px;min-width:0;position:relative}.flow-step:hover{border-color:var(--accent)}.step-title{font-weight:650;display:block;line-height:1.5;color:var(--accent)}.step-desc{display:block;font-size:14px;margin-top:9px;line-height:1.7}.flow-step[aria-expanded=false] .step-desc{display:none}.flow-hint{font-size:12px;color:var(--muted);margin:18px 0 0}.evidence{border:1px solid var(--line);border-radius:8px;margin:10px 0;background:var(--paper);font-size:13px}.evidence summary{padding:12px 16px;cursor:pointer;overflow-wrap:anywhere;font-family:Consolas,"Microsoft YaHei",monospace}.evidence summary span{display:block;color:var(--muted);font-family:"Segoe UI","Microsoft YaHei",sans-serif;margin-left:18px}.sourcepath{padding:0 18px;word-break:break-all}pre{font:12px/1.8 Consolas,"Microsoft YaHei",monospace;white-space:pre-wrap;overflow-wrap:anywhere;padding:18px;margin:0;background:var(--code);border-radius:0 0 8px 8px}.priority{border-top:1px solid var(--line);padding:25px 0}.priority h3{margin:0 0 13px}.priority .tag{color:var(--accent);font:13px/1.8 Consolas,monospace;margin-right:14px}.priority dl{display:grid;grid-template-columns:95px 1fr;gap:9px 20px;margin:0}.priority dt{font-weight:650}.priority dd{margin:0;color:var(--muted)}.filters{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}.filters button[aria-pressed=true]{color:var(--paper);background:var(--accent);border-color:var(--accent)}.rrf-demo{display:flex;flex-wrap:wrap;gap:20px;align-items:center;background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:22px}.rrf-demo input{width:80px;border:1px solid var(--line);border-radius:8px;padding:6px;background:var(--bg);color:var(--ink)}.rrf-output{font:22px Consolas,monospace;color:var(--accent)}.links-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:28px 0}.report-link{display:block;text-decoration:none;background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:28px;color:var(--ink)}.report-link:hover{border-color:var(--accent)}.report-link h3{margin:0 0 14px;color:var(--accent)}footer{border-top:1px solid var(--line);margin-top:50px;padding-top:22px;font-size:13px;color:var(--muted)}.skip{position:absolute;left:-9999px}.skip:focus{left:10px;top:10px;z-index:10;background:var(--paper);padding:10px}[hidden]{display:none!important}@media(max-width:1050px){.layout{grid-template-columns:170px 1fr;gap:26px}.topbar{gap:16px;padding:12px 20px}.topbar nav{gap:14px;font-size:13px}.brand{font-size:14px}.flow-steps{grid-template-columns:repeat(2,minmax(0,1fr))}.print{display:none}}@media(max-width:767px){.topbar{flex-wrap:wrap;gap:8px;padding:12px 16px}.topbar nav{order:3;flex-basis:100%;justify-content:space-between;gap:8px}.theme{margin-left:auto}.layout{display:block;padding:0 16px}.sidebar{position:static;display:none}.main{padding-top:30px}.hero .lead{font-size:18px}.flow{padding:16px}.flow-steps,.links-grid{grid-template-columns:1fr}.priority dl{grid-template-columns:1fr;gap:4px}.priority dd{margin-bottom:12px}h2{font-size:25px}.table-wrap{margin-left:0;margin-right:0}section{padding-top:30px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{header,.sidebar,.filters,.flow-hint,.rrf-demo,.skip{display:none}.layout{display:block;padding:0}.main{padding:0}.hero h1{font-size:30px}body{background:white;color:black;font-size:11pt}.flow-steps{grid-template-columns:repeat(3,1fr)}.flow-step{break-inside:avoid}.step-desc{display:block!important}section{break-before:auto}.evidence pre{font-size:8pt}.note,.priority{break-inside:avoid}.table-wrap{overflow:visible}table{min-width:0}a{color:#075a50}}
'''
CSS += 'body{overflow-wrap:anywhere}h3{overflow-wrap:anywhere}'
CSS += '.beginner{font-size:17px;padding:20px 24px}.glossary{border:1px solid var(--line);border-radius:8px;background:var(--paper);margin:18px 0 28px}.glossary summary{cursor:pointer;padding:16px 20px;font-weight:650;color:var(--accent)}.glossary dl{display:grid;grid-template-columns:1fr 1fr;gap:0 24px;padding:0 20px 18px;margin:0}.glossary dl div{border-top:1px solid var(--line);padding:10px 0}.glossary dt{font-weight:650}.glossary dd{margin:3px 0 0;color:var(--muted);font-size:14px}.startup-warning{border-left-color:#b66b00;background:color-mix(in srgb,#f4b84a 18%,var(--paper))}@media(max-width:767px){.glossary dl{grid-template-columns:1fr}}'
JS = r'''
const body=document.body; let stored=null;try{stored=localStorage.getItem('rag-report-theme')}catch{};if(stored==='dark'||(!stored&&matchMedia('(prefers-color-scheme: dark)').matches))body.classList.add('dark');
const theme=document.querySelector('.theme');function syncTheme(){theme.textContent=body.classList.contains('dark')?'浅色':'深色';theme.setAttribute('aria-label','切换至'+theme.textContent+'主题')}syncTheme();theme.onclick=()=>{body.classList.toggle('dark');syncTheme();try{localStorage.setItem('rag-report-theme',body.classList.contains('dark')?'dark':'light')}catch{}};
document.querySelector('.print').onclick=()=>window.print();document.querySelectorAll('.flow-step').forEach(b=>b.onclick=()=>b.setAttribute('aria-expanded',b.getAttribute('aria-expanded')!=='true'));
const observer=new IntersectionObserver(es=>{for(const e of es)if(e.isIntersecting){document.querySelectorAll('.sidebar a').forEach(a=>a.classList.toggle('active',a.hash==='#'+e.target.id));}},{rootMargin:'-15% 0px -65% 0px'});document.querySelectorAll('section[id]').forEach(e=>observer.observe(e));
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-filter]').forEach(x=>x.setAttribute('aria-pressed',x===b));document.querySelectorAll('.priority').forEach(x=>x.hidden=b.dataset.filter!=='ALL'&&x.dataset.priority!==b.dataset.filter)});
const ranks=document.querySelectorAll('.rrf-demo input');function rrf(){const a=Number(ranks[0].value),b=Number(ranks[1].value);const value=(a>0?1/(60+a):0)+(b>0?1/(60+b):0);document.querySelector('.rrf-output').textContent=value.toFixed(6)}if(ranks.length){ranks.forEach(x=>x.oninput=rrf);rrf()}
'''

def page(filename,title,lead,sections,kind):
    nav='<a href="index.html">总览</a><a href="modular-rag.html">Python 检索项目</a><a href="paismart.html">知识库网站项目</a><a href="hp-optimization.html">HP 方案建议</a>'
    toc=''.join(f'<a href="#{s["id"]}">{s["title"]}</a>' for s in sections)
    content=''.join(f'<section id="{s["id"]}"><h2>{s["title"]}</h2>{s["body"]}</section>' for s in sections)
    plain = {'modular-rag.html':'它把 PDF 文件切成小段并保存，然后可以按关键词和意思查找相关段落。重点是“找到资料并交给 AI 助手”；它不是开箱即用的聊天网站。', 'paismart.html':'它是一个完整的知识库网站：用户上传文件，后台处理后，用户可以提问并看到相关资料。后台用队列处理耗时任务，也会检查用户能不能看这些资料。', 'hp-optimization.html':'你的 HP 方案服务教学资料。参考项目提供的是工程做法，最终是否采用要看它能不能帮助学生、能不能用真实教学资料验证。', 'index.html':'这几份报告先用白话说明项目和启动条件；遇到技术词可以展开下方的解释。后面的详细代码证据可以先跳过。'}
    output=f'''<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{E(lead)}"><title>{E(title)} | RAG 源码研读</title><style>{CSS}</style></head><body><a class="skip" href="#content">跳到正文</a><header><div class="topbar"><a class="brand" href="index.html">RAG 项目说明（白话版）</a><nav aria-label="报告导航">{nav}</nav><button class="theme">深色</button><button class="print">打印 / PDF</button></div></header><div class="layout"><aside class="sidebar"><div class="side-title">本页目录</div><nav aria-label="本页目录">{toc}</nav></aside><main class="main" id="content"><div class="hero"><div class="eyebrow">{E(kind)}</div><h1>{E(title)}</h1><p class="lead">{lead}</p><div class="facts"><span><b>审阅日期</b> 2026-10-15</span><span><b>依据</b> 本地源码</span><span><b>未启动项目</b> 启动结论是按说明文件与当前电脑环境判断</span></div></div>{beginner_box(plain.get(filename,''))}{content}<footer>依据用户提供的本地项目与 HP 方案整理。未连接模型或数据库，也未运行参考项目；启动能力按源码、说明文件和当前电脑环境判断。页面里的“展开源码”提供代码位置和摘录；先看白话说明即可，技术细节可以之后再看。HTML 可离线阅读，跨文件链接需保持当前目录结构。</footer></main></div><script>{JS}</script></body></html>'''
    assert '—' not in output
    (OUT/filename).write_text(output,encoding='utf-8')

mod=[]
mod.append(sec('position','项目定位与阅读结论',para('<strong>它是一个面向 MCP Host 的知识检索服务，核心交付是可引用的检索片段。</strong>在线 query_knowledge_hub 路径把候选片段、来源和可选图片返回给 Host；这条路径没有服务内的最终答案生成。LLM 主要用于离线 Chunk 精炼、元数据补充、图片描述，以及可选的 LLM Rerank。')+note('适合学习：组件契约 → 双路召回 → RRF → 重排 → Trace → 评测。HP 应借用检索内核，把生成与教学任务放在自己的 Workflow / Agent 中。')+ev(M+'src/core/response/response_builder.py','    def build(','返回检索响应，未调用答案生成模型')))
mod.append(sec('stack','技术栈与模块边界',table(['层次','本地实现','职责与边界'],[
('语言 / 配置','Python ≥ 3.10 · PyYAML · Hatchling','settings.yaml 配置组件；main.py 启动 MCP。'),
('协议 / 操作台','MCP Python SDK · stdio · Streamlit','MCP 对外暴露工具，Streamlit 管理入库、查询追踪、数据浏览和评测。'),
('解析 / 分块','MarkItDown PDF · 可选 PyMuPDF / Pillow · langchain-text-splitters','实际入口为 PdfLoader；递归字符切分，不是全流程 LangChain Agent。'),
('存储','Chroma PersistentClient · 本地 BM25 JSON · SQLite','Chroma 保存向量与 Chunk 文本；自实现 BM25 保存倒排统计；SQLite 记录文件处理历史。'),
('中文 / 模型','jieba · OpenAI / Azure / Ollama Embedding · 多 LLM 适配','jieba 对齐稀疏侧分词；LLM 适配含 OpenAI、Azure、Ollama、DeepSeek。'),
('排序 / 评测','RRF · 可选 Cross-Encoder / LLM · Custom / Ragas','排序与评测均通过工厂抽象切换；不能把配置注释写出的候选 provider 当作已实现。'),
('工程验证','pytest · ruff · mypy · JSONL Trace','有单元、集成、端到端测试文件，本次未运行。')])+ev(M+'pyproject.toml','dependencies = [','核心依赖声明',12)+ev(M+'src/libs/splitter/splitter_factory.py','from src.libs.splitter.recursive_splitter','实际内置注册 recursive',5)+ev(M+'src/libs/vector_store/chroma_store.py','class ChromaStore','向量存储实现',5)))
mod.append(sec('ingest','离线流程：文件变成可检索知识',flow('IngestionPipeline.run',[
('文件完整性','SHA-256 计算指纹，查 SQLite；已成功处理且非 force 时跳过。'),
('PDF 解析','MarkItDown 提取文本，PyMuPDF 提取图片，生成 Document 及图片元数据。'),
('递归分块','默认 1000 字符 / 200 字符 overlap。Chunk ID 使用 document ID、序号、正文短哈希。'),
('三段 Transform','ChunkRefiner → MetadataEnricher → ImageCaptioner；可调用 LLM，失败使用规则或保留原内容。'),
('Dense / Sparse 编码','批处理 Embedding；稀疏侧用 jieba 生成词频、文档长度等统计，供 BM25 建索引。'),
('三类写入与完成','向量 Upsert → BM25 更新 → 图片登记；全部经过后才 mark_success，异常 mark_failed。')])+para('这是同步 Pipeline，不是具有消息队列、租约和断点提交的分布式入库任务。不同存储的写入按顺序发生，单次函数成功并不意味着跨存储有原子事务。')+ev(M+'src/ingestion/pipeline.py','    def run(','入库编排入口',10)+ev(M+'src/ingestion/pipeline.py','vector_ids = self.vector_upserter.upsert','向量写入与稀疏索引更新',19)+ev(M+'src/ingestion/chunking/document_chunker.py','return f"{doc_id}_{index:04d}_{content_hash}"','稳定 ID 的具体格式',1)))
mod.append(sec('retrieve','在线流程：查询变成证据',flow('QueryKnowledgeHubTool.execute',[
('MCP 参数校验','query 必填；top_k 默认 5、最大 20；collection 选择集合。'),
('QueryProcessor','jieba 分词、停用词、去重、解析 key:value 过滤语法；没有 LLM 教学意图改写。'),
('Dense + BM25','线程池并行召回；配置默认每路 20。Dense 使用 Embedding，Sparse 使用关键词。'),
('RRF 合并','按 Chunk ID 合并；k 默认 60；同分按 Chunk ID 稳定排序。部分分支失败可保留另一分支。'),
('可选 Rerank','工具先取更大候选集；配置默认 rerank.enabled=false。失败保留融合顺序并截取 TopK。'),
('证据与追踪','ResponseBuilder 组装 Markdown、citation 与图片；TraceCollector 保存阶段与最终片段。Host 据此继续生成。')])+ev(M+'src/core/query_engine/hybrid_search.py','    def _run_parallel_retrievals(','并行召回控制',10)+ev(M+'src/mcp_server/tools/query_knowledge_hub.py','initial_top_k =','工具候选放大',12)+ev(M+'src/core/query_engine/query_processor.py','    def _tokenize(','规则查询处理',8)))
mod.append(sec('identity','Chunk 身份：写入阶段还会重新计算 ID',para('DocumentChunker 的初始 ID 是 <code>doc_id + 序号 + 原文本短哈希</code>；最终 VectorUpserter 重新用 <code>source_path 短哈希 + 序号 + Transform 后文本短哈希</code>生成存储 ID。Pipeline 将 BM25 的 chunk_id 对齐到返回的向量 ID，双路才能合并。')+note('稳定指“相同路径、序号和最终内容”产生相同 ID。换文件路径、LLM 精炼内容漂移或分块序号变化均会改变 ID；它不是跨重建稳定的业务主键。HP 应独立逻辑 Unit ID、版本内 Chunk ID 和内容 hash，Trace / 标签绑定具体版本。')+ev(M+'src/ingestion/storage/vector_upserter.py','source_hash = hashlib.sha256','最终存储 ID',8)+ev(M+'src/ingestion/pipeline.py','for stat, vid in zip','BM25 对齐向量存储 ID',5)))
mod.append(sec('rrf','RRF：融合名次，不代表置信度',para('实现公式为 <code>score(d) = Σ 1 / (60 + rank(d))</code>，rank 从 1 开始。它让 BM25 与向量召回可以按名次融合，避免直接相加异质分数。两路第一的上界约为 0.032787；仅一路第一约为 0.016393。这个值<strong>不是答案正确概率</strong>。')+'<div class="rrf-demo"><label>Dense 名次 <input aria-label="Dense 名次" type="number" min="0" max="1000" value="1"></label><label>BM25 名次 <input aria-label="BM25 名次" type="number" min="0" max="1000" value="1"></label><output class="rrf-output" aria-live="polite"></output><span>0 表示该路未召回</span></div>'+ev(M+'src/core/query_engine/fusion.py','for rank, result in enumerate','按名次累加',14)))
mod.append(sec('quality','Trace、评测与实际能力边界',table(['能力','代码中的现状','对 HP 的意义'],[
('阶段 Trace','记录 load / split / transform / embed / upsert，以及查询、融合、重排等阶段；本地 JSONL 和 Streamlit 展示。','借鉴阶段快照，保留候选 ID、原始分、配置版本与失败原因；生产接入既有 Trace 平台。'),
('评测 Harness','EvalRunner 支持注入答案生成器与人工答案 override；未注入时使用片段拼接兜底。','必须标注“检索评测”还是“最终生成评测”，不能把拼接答案当作生产模型效果。'),
('Golden Set','提供五条样例问题，但 expected_chunk_ids / expected_sources 为空。','可参考数据格式；这些样例无法证明真实 Hit Rate / MRR。'),
('Provider 扩展','内置实际 splitter 为 recursive，向量实现为 Chroma；注释列出 semantic / Qdrant 等方向。','只给已经注册并可加载的实现开配置，启动时校验未知 provider。'),
('依赖收口','PdfLoader 可选依赖 PyMuPDF / Pillow；pyproject 的基础依赖未单独列明这两项，Cross-Encoder 所需包也需核对。','建立 parser / rerank extras、锁定依赖，做启动与离线降级检查。')])+ev(M+'tests/fixtures/golden_test_set.json','"expected_chunk_ids": []','Ground truth 尚为空',6)+ev(M+'src/observability/evaluation/eval_runner.py','    def _generate_answer(','评测生成入口',24)))
mod.append(sec('pitfalls','不能直接照搬的实现',bullets([
'<strong>图片关联：</strong>PdfLoader 把图片占位符追加到文本末尾，没有保真地建立图、正文、例题的版面关系；数学教材要保留 ContentBlock 坐标与 assetRefs。',
'<strong>原文与精炼：</strong>ChunkRefiner 生成新的 refined_text 写入 Chunk.text；HP 必须独立保存 sourceContent，检索副本只能追加上下文，不能覆盖证据原文。',
'<strong>幂等作用域：</strong>SQLite 的主键为 file_hash，should_skip 只查 hash。同一文件换 collection 也可能被跳过；模型或分块版本变化时不能只靠文件哈希决定跳过。',
'<strong>故障语义：</strong>工具的 _perform_search 捕获异常并返回 []，可能把检索失败变成“无相关结果”。HP 应返回结构化的 NO_EVIDENCE / DEGRADED / TIMEOUT / DEPENDENCY_ERROR。',
'<strong>过滤位置：</strong>Dense 传入 filters；HybridSearch 的 Sparse 路径主要提取 collection，并有融合后过滤。不能据此认为多租户授权已完成，也会有先截断再过滤导致候选不足的问题。',
'<strong>超时：</strong>future.result(timeout=30) 不等于底层 HTTP / 数据库调用被取消；ThreadPoolExecutor 退出仍可能等待工作结束。要配置依赖超时与请求总预算。'
])+ev(M+'src/libs/loader/pdf_loader.py','placeholder = f"[IMAGE:','图片位置的简化处理',8)+ev(M+'src/libs/loader/file_integrity.py','"SELECT status FROM ingestion_history WHERE file_hash = ?"','跳过条件只有文件指纹',7)+ev(M+'src/mcp_server/tools/query_knowledge_hub.py','logger.warning(f"Hybrid search failed','异常返回空列表',2)+ev(M+'src/ingestion/transform/chunk_refiner.py','text=refined_text','精炼结果写回 Chunk',6)))
mod.append(sec('hp','与你的 HP 方案如何对接',table(['可吸收','HP 中的位置','是否已在 06 方案中'],[
('Retriever / Loader / Splitter / Reranker 组件契约','FastAPI 内的 DocumentRetriever 和 SourceParser；MCP 仅作后续协议适配。','已写入 §21–23；下一步明确输入输出 schema 与错误状态。'),
('稳定 ID、Upsert、分阶段 Trace','MySQL canonical chunk + ES / VikingDB 索引副本。','已规划；补 pipeline_version 与索引对账。'),
('Dense + BM25 + RRF','ES BM25 + VikingDB Dense → 服务层融合。','§21–23 已收敛；同步 §17.5 与 §18.3 的残留 sparse / Hybrid 示例。'),
('Golden Set 与消融','固定字符 / 单页 Baseline 对照 PPT / Word TeachingUnit、查询改写与重排。','已规划；先补真实标签再选模型。')])+note('HP 的核心增量仍是：Question Retrieval Profile、Student Error Query、资料适配体系、Office 原生结构、跨页完整例题、关系型上下文扩展。参考项目不能替代这些教育领域设计。')))
mod.append(sec('run','我能在自己电脑上启动它吗？',
 para('<strong>可以跑它的网页操作面板、文件入库脚本、搜索脚本和真正的 MCP 服务。</strong>但仓库里的 <code>python main.py</code> 只是提示文字后退出，不会启动 MCP；要启动 MCP，请用下面的命令。第一次入库和搜索还需要能调用的文字向量模型，文件整理功能可能还需要大模型密钥。')+
 para('你这台电脑已有 Python 3.13，但项目明确列出的版本是 Python 3.10–3.12；没有找到已安装的 3.11/3.12，Python 依赖、虚拟环境也都没有。建议先安装 Python 3.11 或 3.12，再复制这些命令。')+
 cmdblock('cd "E:\\project\\别人的项目\\MODULAR-RAG-MCP-SERVER"\npy -3.11 -m venv .venv\n.\\.venv\\Scripts\\Activate.ps1\npython -m pip install --upgrade pip\npip install -e .')+
 para('如果 PowerShell 提示禁止运行激活脚本，只在当前窗口输入 <code>Set-ExecutionPolicy -Scope Process Bypass</code>，再运行激活命令。然后打开 <code>config/settings.yaml</code>，填入可用的模型服务地址和密钥；示例文件里的 <code>YOUR_API_KEY_HERE</code> 不能直接使用。密钥不要贴到聊天或公开仓库。')+
 cmdblock('''# 终端 A：启动操作网页，然后在浏览器打开 http://localhost:8501
python scripts/start_dashboard.py

# 终端 B：把 PDF 加入名为 demo 的资料库
python scripts/ingest.py --path "E:\\你的PDF文件夹" --collection demo

# 搜索刚加入的资料
python scripts/query.py --query "你想问的问题" --collection demo

# 需要接入支持 MCP 的 AI 软件时，另开终端运行真正的 MCP 服务
python -m src.mcp_server.server''')+
 note('这些命令说明“如何启动”，不表示本轮已经在你电脑安装了依赖或验证了模型账号。操作网页启动后资料库仍是空的；要搜索内容，先成功加入 PDF。')))
page('modular-rag.html','MODULAR-RAG-MCP-SERVER','从 PDF 入库到 MCP 检索响应，拆解模块、算法与可复用的工程契约。',mod,'PYTHON · RETRIEVAL CORE')

pai=[]
pai.append(sec('position','项目定位与源码范围',para('<strong>PaiSmart 是带上传、知识库、权限、会话与流式问答的完整企业知识产品。</strong>当前本地快照已包含双路并行召回、ReAct 工具循环、上下文检索、父上下文扩展、文件处理可靠性和评测模块。阅读结论以实现为准，不能用 README 中较早的简化流程代替当前源码。')+note('最值得 HP 借鉴的是服务故障与数据一致性的处理机制。Kafka、WebSocket、ES 单库向量检索属于该项目的基础设施选择，迁移时可用 HP 既有 RabbitMQ、HTTP / 流式协议和 ES + VikingDB。')))
pai.append(sec('stack','技术栈与数据分工',table(['层次','技术 / 本地版本','用途'],[
('后端','Java 17 · Spring Boot 3.4.2 · Maven · JPA / Hibernate','REST、用户/文件/会话主数据、事务与调度。'),
('前端','Vue 3.5.13 · TypeScript 5.8.3 · Vite 6.3.5 · Pinia · Naive UI · UnoCSS','知识库管理、聊天历史、引用预览、管理与评测 UI。'),
('异步 / 文件','Kafka · MinIO · Redis Bitmap','分片上传、合并对象、异步解析向量化、断点上传状态。'),
('解析 / 中文','PDF: LiteParse CLI + OCR；其他格式: Apache Tika 2.9.1；HanLP','PDF 页级文本与定位；段落、句子、中文分词边界切分。LiteParse 需要额外 CLI / OCR 环境。'),
('检索','Elasticsearch Java Client 8.10.0 · IK · dense_vector / cosine','同一 ES 文档保存原文、上下文、向量与权限字段。客户端版本不等于已核验的运行服务版本。'),
('模型','可配置 Provider Router；配置示例 DeepSeek、text-embedding-v4；gte-rerank-v2','调用供应商 LLM、Embedding、Rerank；模型名称是配置默认，不证明在线正在使用。'),
('稳定性','Resilience4j 2.2.0 · Outbox · 租约 / 心跳 · RequestDeadline','供应商隔离、消息补发、卡死恢复、在线预算和降级。'),
('持久化 / 缓存','MySQL · Redis','MySQL 保存解析 Chunk、用户、文件、对话等；Redis 负责短期上下文、状态、限流。')])+ev(P+'pom.xml','<java.version>17','后端版本基准',3)+ev(P+'frontend/package.json','"naive-ui":','前端依赖',10)+ev(J+'service/ParseService.java','public void parseAndSave(String fileMd5','PDF 与非 PDF 解析分流',16)))
pai.append(sec('ingest','上传与离线入库流程',flow('Upload → Outbox → Kafka → Index',[
('分片上传','浏览器计算文件 / 分片指纹；MinIO 存分片，Redis Bitmap 记录进度；数据库 ChunkInfo 可用于恢复进度。'),
('合并文件','MinIO Compose 形成 merged/{fileMd5}；后续消费者优先按对象 key 读取，避免预签名 URL 过期。'),
('事务登记任务','写文件待处理状态与 FileProcessingOutbox；提交后派发，定时任务补发未成功消息。'),
('消费者认领','租约 claim 防止重复处理；异常交给 Kafka 重试 / 死信；心跳与 RecoveryJob 处理卡住任务。'),
('解析与上下文','先清理旧分块及索引 → LiteParse / Tika → MySQL DocumentVector；可选分批生成 chunkContext。'),
('向量化与索引','按批次 Embedding，fileMd5_chunkId 稳定 ES ID；批次心跳，完成后写 token / Chunk 数 / modelVersion 并通知。')])+para('关键顺序是：<strong>本地事务确保任务登记可恢复，消费者确保处理可重试，稳定 ID 限制重复写入。</strong>Outbox 不是数据库与 Kafka 的全局 exactly-once；消息发送成功但标记失败仍会重复，因此必须有消费端幂等。')+ev(J+'service/reliability/FileProcessingOutboxService.java','public void enqueueVectorization','状态与 Outbox 的事务入口',18)+ev(J+'consumer/FileProcessingConsumer.java','Optional<VectorizationLease> claimed','认领、清理与解析',19)+ev(J+'service/VectorizationService.java','fileMd5 + "_" + chunk.getChunkId()','ES 索引 ID 与原文 / 上下文字段',15)))
pai.append(sec('chunk','分块、Contextual Retrieval 与父上下文',table(['能力','实际实现','与 HP 教材分块的差别'],[
('默认分块','application.yml: chunk-size=512、overlap-size=100、min-chunk-size=100；先段落后句子，超长句用 HanLP，末尾片段与 overlap 有合并规则。','属于文本边界启发式；HanLP 分词不能等同于教材教学单元识别。'),
('PDF 定位','LiteParse 产出页级文本，保存 pageNumber 与 anchorText。','可借鉴解析定位；HP 对外稳定定位仍是版本、册次、章节，页坐标仅做内部 sourceLocator。'),
('上下文检索','默认关闭；每批 8 Chunk、邻居 2、窗口 6000 字符、说明 200 字符、并发 2。说明存 chunkContext，原文存 textContent。','借鉴原文分离和有界并发；HP 先规则拼标题与结构，LLM 只处理低置信度片段。'),
('表示一致','Embedding 用 ContextualChunkText.compose；BM25 combined_fields 使用 chunkContext + textContent；Rerank 用同一 compose。','HP 定义 RetrievalTextBuilder，三条索引 / 排序路径使用同一表示版本。'),
('父上下文扩展','默认邻居 1、每命中 1500 字符、总 6000 字符；按同文件相邻 Chunk 拼接，共享 parentKey 去重。','这是邻接窗口，不是教学父子树。HP 按例题、图表、条件与方法关系扩展，同时借用预算和去重。')])+ev(J+'service/chunk/ContextualChunkText.java','public static String compose','统一检索文本表示',8)+ev(J+'service/search/ParentContextExpander.java','public List<SearchResult> expand','共享父上下文与预算',20)+ev(J+'config/ContextualRetrievalProperties.java','private boolean enabled = false','可选能力默认关闭',20)))
pai.append(sec('retrieve','在线检索：带权限的双路召回',flow('HybridSearchService.searchWithPermission',[
('解析服务端权限','根据可信用户身份得到数据库 ID 和有效组织标签；构造“自己 / 公开 / 组织”可访问集合。'),
('Embedding 与召回','先生成查询向量，然后异步发 BM25、kNN；Embedding 失败可走 BM25。向量生成与 BM25 并非全程并行。'),
('统一等待期限','两路 await 共用 deadline，受 RequestDeadline 剩余预算约束；单路失败标记 BM25_ONLY 或 KNN_ONLY。'),
('RRF 与候选集','默认 TopK × 30、每路最多 300；RRF k=60，送重排的候选上限默认 50。实际参数可被配置覆盖。'),
('重排与阈值','默认 gte-rerank-v2，阈值 0.1；预算不足或失败走 RRF；RRF 原始阈值默认 0.028，单路减半。'),
('返回与追踪','保留 mode、rawScore 与转换后的 score；详细模式返回单路、融合候选、阈值丢弃计数，供评测定位。')])+para('BM25 在 bool.filter 中带权限，kNN 在 knn.filter 内带同一过滤。公开/组织权限是参考项目自己的模型，HP 必须换成学校、角色、资料授权与教材版本约束，父上下文回源也必须保留约束。')+note('默认阈值来自该项目的场景，不能迁移成 HP 的“证据置信度”。归一化到 0～1 只是量纲换算，不是概率校准；RRF 与 Rerank 应分别评测和设阈值。')+ev(J+'service/HybridSearchService.java','private SearchTrace hybridSearch','并行召回与共用等待截止时间',22)+ev(J+'service/HybridSearchService.java','SearchRequest buildKnnRequest','kNN 内部预过滤',18)+ev(J+'service/HybridSearchService.java','private Ranked rrfTopK','按成功分支数调整阈值',16)))
pai.append(sec('chat','问答产品：Agent、流式、引用和历史',flow('ChatHandler → AgentToolRegistry → LlmProviderRouter',[
('接收用户消息','建立 generationId、会话绑定与请求 deadline；重复提交可以附着在进行中的生成任务。'),
('受限 ReAct 循环','模型返回 tool_calls；执行注册工具，再把 observation 放回消息；限制轮次、工具数和时间。'),
('知识工具','search_knowledge、generate_summary、submit_feedback、get_knowledge_stats；检索结果扩展父上下文并编号。'),
('流式最终回答','WebSocket 向前端推送；工具耗时受到“总 deadline 减最终回答预留”约束，预算不足时收尾。'),
('来源与历史','维护引用映射、parentContext 与生成状态；ConversationService 保存持久化消息，Redis 用于短期状态。'),
('可选引用核查','默认关闭；生成后抽取带引用陈述并核查支持关系，疑似引用标记 SUSPICIOUS，失败不阻断已生成回答。')])+para('当前流程包含 Agent tool loop，并非固定“每条消息先检索再生成”。第一轮带工具及知识库优先提示，也不能仅凭注释断言模型一定检索。HP 的确定性讲评按钮仍可走 Workflow，自由文本进入 Agent；默认自然呈现，同时按来源许可保留署名；不能照搬公开来源角标 UI。')+ev(J+'service/ChatHandler.java','private void runReActLoop(','模型与工具循环入口',24)+ev(J+'service/AgentToolRegistry.java','this.tools = List.of(','实际注册的工具',14)+ev(J+'service/citation/CitationVerificationService.java','public Map<Integer, CitationVerdict> verify','事后核查，默认开关控制',17)))
pai.append(sec('eval','评测与工程治理',table(['模块','代码可确认的能力','使用时的限制'],[
('分阶段评测','BM25 / kNN 命中与首次相关名次、RRF 候选命中、NDCG、阈值丢弃和最终回答判定。','本次只读实现，没有重跑数据集或核验文档宣称的收益。'),
('标注粒度','EvalCase 支持 expectedFileMd5s / expectedFileNames 与 expectedEvidence 短语。','只有文件标签时，同书任意 Chunk 都可能算命中；教材应标注章节、TeachingUnit 和证据跨度。'),
('人工校准','有人审抽样、Judge 解析、人机一致性与错误诊断测试。','借用校准与失效诊断，HP 的教学一致性仍需教研标注。'),
('模型版本与重建','KnowledgeIndexManager 按模型维度建新物理索引、保存 _meta，并原子切换 ES alias。','单 ES alias 切换不能直接解决 HP 的 ES + VikingDB 两个系统同步发布。'),
('任务恢复与背压','Outbox 补发、租约心跳、RecoveryJob、死信、ParseConcurrencyLimiter、堆内存背压。','RabbitMQ 也能实现相同机制，无需为学习该机制另引入 Kafka。'),
('测试资产','HybridSearch、ParentContext、Outbox、Lease、Parser、Citation、Eval 等专门测试文件。','有测试文件不代表当前环境测试已通过。')])+ev(J+'service/eval/EvalCase.java','public record EvalCase(','文件与 evidence 标注结构',10)+ev(J+'service/eval/RagEvalCaseRunner.java','draft.stages =','分阶段指标汇总',7)+ev(J+'service/index/KnowledgeIndexManager.java','public void createIndex','新索引与模型 metadata',13)))
pai.append(sec('limits','迁移前要理解的边界',bullets([
'<strong>先删除再重建：</strong>FileProcessingConsumer 清理旧索引后重新解析，重建中可能出现不可检索窗口。HP 已规划“新版本构建后发布”，应保留该设计并补全双索引一致发布。',
'<strong>哈希不是业务身份：</strong>ES ID 与回源按 fileMd5 / Chunk 序号组织；同一文件跨用户复用时，需审查权限、对象共享与 canonical 主键。HP 应独立 document_id、version_id 与 tenant 授权。',
'<strong>父块权限假设：</strong>ParentContextExpander 认为文件级权限已在检索校验，并按 fileMd5 查询邻居。HP 有学校和版本约束，不能只用文件指纹回源。',
'<strong>事后核查不拦截：</strong>引用核查失败或超时不影响回答，无法承担学生辅导输出前的强约束。HP 应区分生成前 Evidence Gate 与生成后的陈述检查。',
'<strong>默认配置需验收：</strong>ES mapping 声明 isPublic，但检索构造公开过滤使用 public；布尔属性序列化可能生成 public。应检查实际 JSON 与 mapping，不能仅凭字段声明推断正确。',
'<strong>ACL 错误语义：</strong>search 的权限解析异常会返回 SearchTrace.empty；HP 必须区分身份 / 授权失败与真实无证据，并且任何降级都不能放宽权限。'
])+ev(J+'service/search/ParentContextExpander.java','window = documentVectorRepository.findByFileMd5','父上下文回源范围',7)+ev(J+'service/HybridSearchService.java','b.should(s -> s.term(t -> t.field("public")','公开权限过滤字段',4)+ev(P+'src/main/resources/es-mappings/knowledge_base.json','"isPublic"','mapping 字段名与检索字段名需验证',3)))
pai.append(sec('hp','HP 最应该借鉴的五件事',table(['参考机制','HP 的具体落点'],[
('Outbox + claim / heartbeat + Dead Letter','kb_ingestion_job 与 ingestion_outbox 同事务登记；RabbitMQ 消费者幂等、租约续期、失联恢复。'),
('RequestDeadline + 模式化降级','Query Builder、ES / VikingDB、Reranker、生成共用预算；每阶段留出后续时间，错误状态可观察。'),
('上下文表示统一','sourceContent 与 retrievalText 分离；Embedding / BM25 / Rerank 对齐 retrieval_text_version。'),
('父上下文预算和去重','用 HP 教学关系取代邻居窗口；以 version_id + parentUnitId 去重，按模型 token 预算装配。'),
('阶段化评测与重建发布','对召回、融合、精排、扩展、生成分别验收；新索引评测通过后切 manifest，再清旧版本。')])+note('优先迁移机制与契约，保留 HP 既有基础设施和教学结构。无需为了与 PaiSmart 一致而把 HP 改成全 Java Agent 或 ES 单库向量检索。')))
pai.append(sec('run','我能在自己电脑上启动它吗？',
 para('<strong>可以，但这是完整网站，需要多个配套服务一起运行。</strong>除了前端网页和 Java 后端，还需要数据库、文件存储、搜索服务、消息队列和缓存。此电脑的 Node.js 22 与 pnpm 版本符合项目最低要求；Java 只有 8（项目要 Java 17），没有 Maven，Docker 的 Compose 命令当前也不可用，所以现在还不能直接启动完整网站。')+
 para('推荐的 Windows 操作顺序：安装 JDK 17、Maven 3.8.6 以上版本和 Docker Desktop（带 Compose v2）；然后调整项目提供的容器配置文件。当前 <code>infra.sh</code> 写着作者 Mac 电脑的固定目录，不能直接在你的 Windows 电脑上用；<code>docs/docker-compose.yaml</code> 里的部分文件夹也写成 Linux 专用路径，需要先改成普通容器数据卷。')+
 cmdblock('''# 在 PaiSmart-main 项目根目录打开 PowerShell
Copy-Item .env.example .env
# 用记事本打开 .env，填写数据库、缓存、文件服务、搜索服务及 AI 密钥
notepad .env

# Docker Compose v2 可用后，启动 MySQL、Redis、MinIO、Kafka、Elasticsearch
docker compose -f docs/docker-compose.yaml up -d

# 终端 A：在项目根目录启动 Java 后端（需 Java 17 和 Maven）
mvn spring-boot:run

# 终端 B：安装并启动网页（先进入 frontend 文件夹）
cd frontend
pnpm install
pnpm run dev

# 浏览器打开
http://localhost:9527''')+
 note('还要让 .env 中的数据库、缓存、文件、搜索服务地址和密码与容器配置一致，并配置能用的 AI 服务密钥。这里只核对了启动说明与本机软件版本，没有运行服务；聊天、上传文件等功能需依赖服务全部连通。',)+
 note('Docker 配置包含容器数据目录映射到 Linux 专用路径的写法；在 Windows 上启动前需先检查并调整。项目配置中的演示密码只适合本机学习，不要用于公开服务器。',)+
 para('启动成功后：网页地址是 <code>http://localhost:9527</code>，后端接口地址是 <code>http://localhost:8081</code>。首次启动可能还需要数据库初始化或管理员配置，请按项目 README 中的本地配置说明操作。')))
page('paismart.html','PaiSmart：完整 RAG 产品链路','从分片上传、可靠入库到受限 Agent 问答，理解检索算法之外的工程机制。',pai,'JAVA + VUE · PRODUCT PIPELINE')

# Recommendations are proposed designs, not claims of implementation in HP.
recommendations = [
('P0','统一架构口径，消除互相冲突的章节',
 '最新 §8、§9、§21–23 已统一 ES BM25 + VikingDB Dense，首期资料改为授权 PPTX / DOCX / 教辅。仍可收口的是 §17.5 将 VikingDB 写为 BM25 / Hybrid、§18.3 保留 teaching_resource_chunk_hybrid / sparse_vector，以及 §17 的历史 SQL checkpoint 讨论。',
 'MODULAR 的显式 provider 契约；PaiSmart 把检索实现集中在 HybridSearchService。参考它们的单一实现入口，不跟随其基础设施换选型。',
 '以 §21–23 的最新拆分为本报告基线：MySQL 主数据、Java 业务会话 / MongoDB Trace / PostgreSQL checkpoint、ES 关键词、VikingDB 独立教学资料 Dense collection。sparse 保留为备选；PostgreSQL checkpoint 已于 2026-10-23 确认，集中维护当前决策表。资料来源身份与教材适配分别保存，首期不以教材 PDF 为前提。',
 '文档中每个流程图与当前决策表一致；Retriever 明确 keyword_backend / vector_backend；两边各有独立连通、过滤和回源验收。',
 '这是文档收敛建议，本轮未修改 06 原方案。VikingDB 内置 Hybrid 若以后实测更合适，再单独决策迁移。'),
('P0','把多存储 READY 发布做成一个明确协议',
 '§18.3 已设计完整新版本后原子切换，但 ES 与 VikingDB 是两个系统，分别写成功不等于原子可见。',
 'PaiSmart KnowledgeIndexManager 的新物理索引 + alias；MODULAR 多存储顺序写入暴露的部分成功风险。',
 '新增 index_generation / publish_manifest：记录 version_id、pipeline_version、ES generation、Viking generation、预期 Chunk 数及对账结果。后台先完整构建和抽检，MySQL 事务切 active generation；每次查询读取一次 manifest 快照，两路与 canonical 回源都使用这组版本约束。旧版本在读请求排空后异步回收。',
 '故障注入覆盖 ES 成功 / Viking 失败、发布前宕机、发布后查询未结束等情况；未完成版本不进入 Evidence Pack。对账不只数 Chunk，还核对 ID / hash 与权限 / 版本元数据。',
 '不声称跨库 ACID；用逻辑发布与补偿修复实现一致可见。下架另设强制 deny 标记，使旧 manifest 和缓存立即失效。'),
('P0','给入库任务补 Outbox、租约与处理版本幂等',
 '已有 kb_ingestion_job、RabbitMQ + Worker、hash 去重与幂等方向，任务登记、消息投递、认领和卡死恢复协议仍需细化。',
 'PaiSmart FileProcessingOutboxService / VectorizationLeaseService / RecoveryJob；MODULAR should_skip 仅按文件 hash 的不足。',
 '任务与 outbox 同事务写入；派发按退避重试；worker 用 claim_token / lease_until 认领与心跳。幂等键采用 document_version_id + pipeline_version + stage，Chunk 写入使用稳定业务 ID。记录 parser / chunker / embedding / retrieval_text 版本；模型变化重新向量化，解析变化重新生成对应中间产物。消息传对象 key，不保存短期预签名 URL。',
 '重复消息、发送后未标记、worker 中途终止、租约过期、旧 worker 回写均有测试；旧 claim_token 不能写完成 / 发布状态，索引写入也限制在该 generation 内。非重试错误进入死信，运维可按阶段恢复。',
 'Kafka 无需引入。RabbitMQ 做至少一次投递即可；本地文件去重与消息幂等是不同问题。优先在新版本空间写入，避免照搬先删旧数据。'),
('P0','用一个总 deadline 约束整个教学请求',
 '§22 已要求区分超时和依赖故障，但 Query Builder、多意图召回、重排、上下文扩展与生成的预算分配没有统一协议。',
 'PaiSmart RequestDeadline 与保留最终回答时间；HybridSearchService 共用召回等待期限。',
 'RetrievalRequest 传 deadline / remaining_budget；阶段 timeout 取配置与剩余预算的较小值。为最终生成保留时间；Rerank 预算不足可跳过并标记 DEGRADED。先并行发 ES BM25 与查询 Embedding，Embedding 成功再发 Viking Dense，避免 BM25 被模型网络等待拖住。底层 HTTP 也配置超时与并发隔离。',
 '故障注入下测总时延与未取消请求数；依赖超时后仍能识别成功分支；不把单路失败当作完全无资料。生成、重排、每路召回均记录耗时和状态。',
 'future.cancel 或外层 timeout 不保证远端请求停止，需要连接 / 读取超时与容量上限。具体预算由目标 P95 和真实语料决定。'),
('P0','把 Evidence Gate 从一个阈值拆成可解释判定',
 '§9 已有 evidenceLevel、integrityStatus、错误隔离、缺少教材原始证据和降级；尚未给出不同排序模式的分数口径与 Gate 判定协议。',
 'PaiSmart 的 rawScore / mode / thresholdDroppedInTopK；它按双路 / 单路调整 RRF 阈值，但不能照搬数值。',
 '分别保存 dense_score、bm25_score、rrf_score、rerank_score、score_type。先做候选级 Gate，再对扩展后的完整 Pack 检查，避免 §9.1 先 Gate 后扩展时未验证新补条件；输出 PASS / PARTIAL / REJECT 与 reason_codes。完整、正确、来源可支持该结论、版本适配与相关性分别判定；阈值按模式和模型用正负样例校准。',
 '给出“接受证据中的正确率”和“应接受证据被拒绝的比例”；双路、单路、跳过重排分别统计。RRF 分数归一化不可被命名为 confidence_probability。无依据讲解不得声称来自教材。',
 '相关性与证据充分性不同。第一版先规则做结构 / 版本 / 授权校验，疑难事实支持关系用人工或离线 Judge，避免全量再加一次在线 LLM。'),
('P0','所有回源、缓存与降级路径都继承授权约束',
 '最新 §7.3、§10、§24.2 已明确 AllowedResourceSet、两路预过滤、回源 / 扩展 / 缓存复核和撤销失效。下一步是将这些要求变成可重放的授权快照与否定测试，而不是再次增加权限原则。',
 'PaiSmart 同时在 BM25 / kNN 内预过滤；ParentContextExpander 的文件级回源假设与无权限 search 兼容入口是应避免的边界。',
 '可信 AuthContext 在服务端生成，不允许 Agent 修改 school_id、角色和许可范围。AllowedResourceSet 固化 license / permission_version、用途、角色与期限；两路、回源与资产读取校验同一快照并检查最新撤销状态。缓存 key 在已有字段上加 index_generation / retrieval_text_version；Trace、草案导出与 Model Gateway 留下权限决策摘要。',
 '跨学校、跨角色、跨教材、已下架版本、缓存命中和父块扩展都有否定用例，返回正文 / 资产也必须授权；任何超时降级不放宽 scope。内部 FILTERED 状态不对外泄露无权限资料的标题或存在性。',
 '从“不返回越权结果”推进为“每条证据可验证 scope”。不能把 PaiSmart 的 public / orgTag 逻辑直接当作 HP 资料授权。'),
('P1','统一检索文本版本，让三条路径看到同一份表示',
 '§24.2 已提出 sourceContent / retrievalText / structuralMetadata / assetRefs；需要从数据字段落成唯一生成组件。',
 'PaiSmart ContextualChunkText.compose，把原文和 chunkContext 分离，Embedding / BM25 / Rerank 复用表示约定。',
 '新增 RetrievalTextBuilder：规则拼版本、章节、内容类型、公式文字化和原文；保存 retrieval_text_hash / version。Embedding 与 ES 都索引它，Rerank 使用同版本文本；sourceContent 独立只读。LLM 补充说明保存为独立字段，记录 prompt_version 与来源 Block IDs，不能覆盖原文。',
 '对相同 Chunk 检查三路表示版本一致；对 LLM 关闭 / 开启做消融。重建可按表示版本定位受影响 Chunk，能够回放原始证据。',
 '你已经采用了比参考项目更适合教材的四层模型；补法是工程契约，不是再增加一种分块算法。'),
('P1','给关系扩展加原子单元、去重和 token 装包规则',
 '§24.2 已明确完整例题、父子扩展、角色 / 授权复核与 token 预算；§24.3–24.4 给出 PPT 跨页和 Word 表格实例。下一步细化预算计算、合并键与扩展过程的质量状态。',
 'PaiSmart parentKey 去重、单命中与总字符上限；保留命中子 Chunk 的证据定位。',
 '先按 version_id + parentUnitId / assetId 合并；以 token 预算代替纯字符预算。装包优先级为必要条件与题干 → 图 / 公式 → 解法 → 方法补充 → 邻接说明。不可拆的例题超预算时，明确减少命中或请求针对性解释，不能静默裁掉条件；命中子 Chunk 与阅读扩展分别记录。',
 '例题完整率、图表关联完整率、重复 token 比例与截断原因可统计；同一父单元多次命中只装一次，不跨版本拼接，不跨权限扩展。',
 'HP 不应把关系扩展降级为前后各一块；字符预算可作为兜底，主要预算应按实际模型 tokenizer 计算。'),
('P1','多 Query 要按意图归组，控制重复票数和班级覆盖',
 '最新 §9.2–9.4 已规定受控改写、Question Retrieval Profile、学生错因与关联题号；还需规定作业多 Query 融合如何避免同义改写反复抬高同一 Chunk。',
 'MODULAR 的 rank-based RRF 适合单 Query 双路；PaiSmart 的候选窗口 / 重排上限可以作为预算机制。两项目并未直接解决 HP 的批量题目覆盖。',
 'QueryIntent 带 intent_id、question_ids、query_origin、必要业务上下文 hash。先对语义重复需求归组，组内融合 BM25 / Dense，组间按显式权重或配额分配；每道关键错题保留覆盖需求。Rerank 回看关联原题和标准解析，不使用不可靠知识点标签。规定 Query 数、候选总数、并行度与最大重排批量。',
 '增加逐题 evidence_coverage 与 duplicated_intent_ratio；同义改写数量增加不能无界提高证据分数。检索画像缓存随标准解析 / 题目版本失效，学生错误查询保持当前学生范围。',
 '分组融合是本报告提出的 HP 领域建议，不是参考项目已有能力。先验证双路基线，再用消融决定是否加权。'),
('P1','用阶段标签诊断失败，用隔离测试集决定上线',
 '§11、§21.2、§24.6 已有 Golden Set、公式保真、表格角色、跨页完整率、已知错误拦截等指标；缺的是可复现的 case schema、配置快照和结果诊断协议。',
 'PaiSmart EvalCase / RagEvalCaseRunner 的阶段结果、人审抽样；MODULAR Golden Set 空标注是反例。',
 'case 保存 source_version、可接受资料小节 / TeachingUnit、必需 Block / asset、角色、用途、should_retrieve、expected_degradation 与人工答案要点。按课件 / 教案文档家族划分调参与留出集，防止同一例题改写泄漏。运行绑定各组件版本与 index_generation。加入缺图、错顶点、缺听力素材、教师活动不能给学生等真实负例。',
 '分别统计未召回、精排丢失、Gate 拒绝、扩展丢条件、生成误用；报告只出现可复现运行的指标。先用代码评测 ID / scope / completeness，再对教学表达做校准过的人审 / Judge。',
 '30～50 条是首个验证集的起步规模，不足以证明全学段稳定。先复核真实失败再扩展指标，避免把指标目录全部搬进项目。'),
('P1','隐藏引用仍要保留陈述到证据的可追溯关系',
 '最新 §2.6 已规定自然呈现、按许可保留署名、定位到实际资料且教材页码为 secondaryReference；应进一步区分命中证据与最终回答使用证据。',
 'PaiSmart 的 reference mapping 持久化与事后 CitationVerification；HP 不需要复制其引用角标 UI。',
 'Evidence Pack 内给稳定 evidence_id；草案保存 claim_span → evidence_ids 与 support_status。检查 ID、版本、来源允许支持的结论，再抽样检查事实支持。引用按 license 署名规则渲染，定位返回 slide / shape 或 Word table / row / cell。无教材原始证据返回 NO_PRIMARY_TEXTBOOK_EVIDENCE，不能由配套资料推导教材原文。',
 '能从讲评中的具体结论追到 sourceContent / Unit / 文档版本；核查失败不得标为已通过。保存草案版本与 Trace 关系，历史引用不指向重建后的另一份正文。',
 '不能用异步“疑似”标签代替输出前的 Gate；全量在线 LLM 核查成本与延迟需先评估，首版可抽样。'),
('P2','将冲突处理落实为权威等级与版本关系',
 '§2、§9.5、§24.5 已区分来源权威与正确性，并发现具体顶点答案错误要求隔离。下一步定义内容错误、解析错误、版本差异和合法多解的不同治理路径。',
 'PaiSmart conflict 模块包含候选发现、键值比较、可选 LLM 确认。该机制更偏企业事实冲突，不直接等同数学教学冲突。',
 '明确 supersedes、effective_from、source_authority 与 evidenceLevel；不同解法不自动判冲突。源文答案错误走 quarantine / 人工修正版；OMML 结构解析错误走 parser 修复后重建；适配差异走版本配置。检索高分和出版社来源均不能覆盖数学正确性或缺失条件。',
 '构造“等价解法 / 适用条件不同 / 真正矛盾 / 旧版已替代”样例；只有需要拦截的冲突进入隔离，对合法多解保留教学选择。',
 '这是扩展方向，优先级低于解析、检索和发布闭环。首期少量教材可先人工治理，暂不建全库 LLM 两两比对。')
]

recommendations.insert(1, (
 'P0','将原生 Office 解析与内容质检做成独立门禁',
 '§23–24 已检查 18 份 PPTX / 6 份 DOCX，明确 OMML 保真、跨页例题、表格角色、纯图片首页与已知顶点错误。当前是样本检查与设计，未完成生产 Parser 和召回实验。',
 '两参考均提供 parser / transform 组件分层；PaiSmart 有并发解析闸门和任务状态。它们没有现成的 PPT 跨页教学单元和 Word 教学表格角色解析，不能直接替代 HP Parser。',
 '建立 OOXML 原生解析契约：OMML 树→原结构 / 可校验 LaTeX，shape 与关系文件→图资产，Word row / cell→教学角色；每个 Block 与 TeachingUnit 保存 parse_integrity、content_review_status。分别设 PARSE_INCOMPLETE 与 CONTENT_QUARANTINED，依赖缺失、原文错误、源文件未附听力等不混为一类。审核修正版另建版本并记录 reviewer / supersedes。',
 '用方案中专题 1 第 6–8 张、三视图“如图”例题、多列二次函数教案、错误顶点和缺听力样例做固定回归：条件 / 图 / 答案能一起取回；错误与缺素材单元不进入可用索引或 Pack，回放能分清源文问题与解析问题。',
 '这是补充可执行状态与回归样例，保留方案已有原生解析 / 按需 OCR 思路。首期不全量 LLM 纠错，不要求取得教材 PDF。'))

def rec_html(r):
    priority,title,current,reference,implementation,acceptance,cost=r
    return f'<article class="priority" data-priority="{priority}"><h3><span class="tag">{priority}</span>{title}</h3><dl><dt>方案现状</dt><dd>{current}</dd><dt>借鉴来源</dt><dd>{reference}</dd><dt>具体补法</dt><dd>{implementation}</dd><dt>验收方式</dt><dd>{acceptance}</dd><dt>取舍与边界</dt><dd>{cost}</dd></dl></article>'

opt=[]
opt.append(sec('judgment','先判断：你的方案已有优势',para('<strong>你的 HP 方案已经具备清晰的教育业务边界，当前最需要补的是可执行、可评测的工程协议。</strong>它已明确 Document Retriever、Question Retriever、Domain Tools 的分工，拒绝用不可靠知识点标签主导召回，并围绕 PPT 跨页与 Word 表格角色保留完整教学单元。首期资料是合作采购 / 已授权教辅，教材正文是后续可选来源。两个参考项目没有直接覆盖这些教学需求。')+table(['设计','06 方案中已有','这次应补'],[
('教学查询','§9.2–9.4：规则基线、受约束 LLM 改写、题目画像 / 学生错误查询','意图归组、缓存失效、逐题覆盖与查询预算。'),
('教材结构','§23–24：PPT / Word 原生解析、四层模型、跨页例题与表格角色','token 装包、原子单元截断策略和表示版本。'),
('版本与权限','学校适配配置、AllowedResourceSet、角色 / 用途 / 许可与 active version','双索引发布 manifest、回源与缓存 scope。'),
('质量与评测','Evidence Gate、真实 Golden Set、已知内容错误隔离、分块 / Query 消融','模式化阈值、阶段失败归因、留出集与陈述追踪。')])+note('事实边界：HP 原有作业、批改、Workflow 是真实能力；本文 RAG 与下列优化均为演进建议。未在 HP 实现、上线或验证收益，也未将两个参考项目的指标写成你的成绩。')+ev(HP,'## 21. 当前技术选型结论','目标架构与实施边界',10)+ev(HP,'## 24. 教学资料 Chunk 专项设计','教育领域的结构设计',10)))
opt.append(sec('comparison','两套参考如何分工',table(['维度','MODULAR-RAG','PaiSmart','HP 的吸收方式'],[
('定位','MCP 检索内核，Host 完成后续生成','完整知识库问答产品，服务内模型 / 工具循环','FastAPI 内核 + 明确 Workflow / Agent，不以协议决定架构。'),
('存储','Chroma + BM25 JSON + SQLite','MySQL canonical + ES 文本 / 向量 + Redis + MinIO','保留 MySQL / MongoDB / ES / VikingDB / 既有对象存储与 MQ 分工。'),
('查询','规则分词和过滤语法','自由文本 Tool Loop + Hybrid Search','领域 Query Builder，硬约束来自服务端，教学意图来自当前事实。'),
('上下文','固定字符 Chunk，可精炼并补描述','分句 Chunk + 可选 chunkContext + 邻接扩展','保留 TeachingUnit 与关系扩展；补统一表示、去重与预算。'),
('可靠性','本地幂等与降级，跨存储发布较弱','Outbox、租约、恢复、deadline、模式化降级','学习机制，映射到 RabbitMQ / Python，不换全套基础设施。'),
('评测','接口清楚，Golden Set 标注为空','阶段指标、人审 / Judge、重建与阈值诊断','真实教材标签、独立留出集、阶段诊断与发布 Gate。')])+para('优先读 PaiSmart 的 reliability / HybridSearch / parent-context / eval 模块；MODULAR 重点看 types / pipeline / fusion / Trace / factory。无需以“迁移整个仓库”为目标。')))
opt.append(sec('target','建议的目标链路',flow('离线：先完整构建，再发布一个版本快照',[
('登记','原文件、授权、教材版本 → MySQL 文档版本 + job + outbox。'),
('解析与结构化','Worker → ContentBlock → SectionNode → TeachingUnit，保留资产与原文。'),
('构建索引代次','canonical → 统一 retrievalText → ES BM25 + VikingDB Dense，记录 generation。'),
('对账和检验','核对 Chunk ID / hash / 元数据 / 资产，跑当前 Golden Set 与检索探针。'),
('逻辑发布','事务切 active manifest；查询快照同时约束两路召回和回源版本。'),
('恢复与清理','保留旧代次供在途请求和回滚；失败不发布，旧代次异步回收。')])+flow('在线：在可信作用域内找到足够证据',[
('任务入口','确定按钮走 Workflow；自由文本进 Agent；服务端附加 AuthContext 与教材版本。'),
('受控 Query Builder','按任务输入生成意图，归组去重，保留题号关联，受总 deadline 约束。'),
('两路检索与融合','ES BM25 与 VikingDB Dense → RRF，保留每路 score / mode / generation。'),
('重排与结构扩展','可选 Rerank；按教学关系回源，验证 scope，按 token 装包并去重。'),
('Evidence Gate','有效、授权、主题、必要条件、资料正确性与结论权限检查；不足则明确降级。'),
('生成与审计','生成可编辑讲评 / 讲解；内部 evidence_id / claim 关联；自然呈现并遵守来源署名要求。')])+note('publish_manifest、意图分组融合和 claim 关联是本报告的建议设计，不能表述成参考项目已经完整实现或 HP 已经具备。')))
opt.append(sec('priority','优化清单：按风险与价值排序','<div class="filters" aria-label="按优先级筛选"><button data-filter="ALL" aria-pressed="true">全部建议</button><button data-filter="P0" aria-pressed="false">P0 · 闭环必需</button><button data-filter="P1" aria-pressed="false">P1 · 质量与成本</button><button data-filter="P2" aria-pressed="false">P2 · 后续扩展</button></div>'+''.join(rec_html(r) for r in recommendations)))
metrics=[
('P0','已有，细化','跨学校 / 教材 / 下架污染','规则检查返回证据的 scope、edition、version / generation','任何违规阻断发布，不用总体召回率抵消。'),
('P0','已有，细化','例题与图表完整率','人工标注必要 Block / asset 集合，核对 Pack 包含率','决定能否使用当前 TeachingUnit 分块与扩展。'),
('P0','已有，细化','Section / Unit Hit、Recall@K / MRR','人工标注可接受资料小节、相关 Unit；按单路 / 融合 / 精排统计','决定是否引入 Query Rewrite / Rerank。'),
('P0','已有，细化','无证据正确降级与证据接受准确率','负例与 Gate reason；人工判定主题 / 充分性','决定各模式阈值与是否允许教材化讲解。'),
('P1','新增协议','阶段失败归因与发布一致性','候选 / Pack 快照、manifest、故障注入结果','定位责任环节，失败版本不发布。'),
('P1','已有，细化','教学一致性 / 陈述支持关系','教研 rubric，人审优先；Judge 做人工校准','决定是否接入默认讲评，而不只是资料检索。'),
('P1','已有，细化','P95 / token / 单次成本 / 逐题覆盖','Trace 与计费字段，按任务类型拆分','决定查询数量、并发度、缓存与重排预算。')
]
opt.append(sec('evaluation','如何证明优化确实有效',para('先用九年级数学二次函数 / 圆的少量授权课件、教案和真实问题跑出可复现结果。原方案的 30～50 条标注问题可做起步验证；增加错版本、教师内容误给学生、源文错答案、OMML 丢结构、跨页 / 图文例题、短公式题与批量讲评样例，并划出不参与调参的留出集。')+table(['实验组','只改变什么','要回答的决策'],[
('A 基线','规则拼接 Query + 固定字符 Chunk + 单路 / 双路召回','原始数据和索引是否真的可检索？'),
('B 结构分块','保持 Query / 模型不变，改为 TeachingUnit 与关系扩展','完整率和章节召回是否改善，token 成本是否可接受？'),
('C 查询改写','保持 Chunk 不变，加受约束 Query Rewriter','纯公式 / 错因查询的增益能否抵消成本与错误改写？'),
('D 重排 / Gate','固定候选，分别加 Reranker 与模式化阈值','是否提高接受证据准确率，并降低误拒？'),
('E 上下文说明 / 生成核查','分开打开 chunkContext 与陈述核查','额外模型调用是否改善实际教学结果？')])+table(['优先级','现状','指标','可测证据','改变的决策'],metrics)+para('指标应关联具体失败与上线决策，并同时覆盖质量、约束与运维成本；这与 <a href="https://langfuse.com/academy/evaluate/choosing-what-to-evaluate">Langfuse 的评测指标选择指南</a>一致。这里提供评测建议，没有创建在线 evaluator 或运行模型评分。')+note('不要直接复用 PaiSmart 的文件级标签做教材评测：同一本书任意 Chunk 命中会高估效果。也不要用 MODULAR 样例中空 expected_chunk_ids 作为 Golden Set。')))
opt.append(sec('contract','首个 Retriever 契约建议',para('这个契约先由普通 API 驱动评测，稳定后再包装为 Agent Tool。schema_version、score_type、status 和 generation 是可回放与可诊断的关键。')+'<pre>'+E(json.dumps({
 'schema_version':'proposal.v1',
 'request':{'task_type':'STUDENT_ERROR_EXPLANATION','intent_ids':['i1'],'scope_fingerprint':'由服务端生成','aligned_edition_id':'审核的资料适配体系','index_generation':'请求级 manifest 快照','deadline_ms':'由调用链传递','query_origin':'PROFILE / STUDENT_ERROR / USER_QUESTION'},
 'response':{'status':'OK / NO_EVIDENCE / DEGRADED / TIMEOUT / DEPENDENCY_ERROR / ACCESS_DENIED / NO_PRIMARY_TEXTBOOK_EVIDENCE','recall_mode':'HYBRID / BM25_ONLY / DENSE_ONLY','generation':'与请求一致','evidence':[{'unit_id':'稳定教学单元 ID','version_id':'权威文档版本','source_content_ref':'原文和资产引用','retrieval_text_version':'索引表示版本','score_type':'RERANK / RRF','raw_scores':{'dense':'保留','bm25':'保留','rrf':'保留','rerank':'按是否执行保留'},'gate_result':'PASS / PARTIAL / REJECT','gate_reasons':[]}],'trace_id':'统一请求链标识'}
 },ensure_ascii=False,indent=2))+'</pre>'+para('status 表示执行是否正常；Gate 结果表示证据是否足够；recall_mode 表示使用哪条排序路径，三者不能混成一个布尔值。内部“被作用域过滤”不直接暴露无权限资源的存在。')))
opt.append(sec('rollout','建议实施顺序与完成标准',table(['阶段','具体产物','进入下一阶段的条件'],[
('先收口径与模型','当前决策表、SourceParser / Unit / Retriever schema、版本与 scope 规则','无架构矛盾；能明确每条数据的权威存储。'),
('跑通离线与查询','小语料、canonical、ES / VikingDB 两路、job / outbox / lease、manifest','入库可重试、发布可回滚、权限与版本否定用例通过。'),
('补教学增益','TeachingUnit / Query Builder / Context Builder、真实 Golden Set、分阶段报告','留出集证明收益，成本与质量达到项目设定的门槛。'),
('接一个讲評场景','先确定性讲评 Workflow，再开放受控 Retriever Tool','默认输出可编辑，不伪称教材证据，Trace 可追踪到具体结论。')])+para('HP 无法连接原公司数据时，仍按 §21.2 在 RunHub 验证统一接口与工程机制。RunHub 语料能证明检索、幂等、Trace 和评测方法；教学资料例题完整性、数学公式与教学表达仍须用授权 PPT / DOCX 专门验证，不能用赛事文章效果代替。')+note('面试可讲：“我基于真实批改业务设计教学 RAG，并从参考项目学习模块、可靠性和评测机制；教育方向的增量是教学单元、受控查询和证据装配。”具体 PoC 的已实现范围、样本和结果必须以实际产物为准。')))
opt.append(sec('sources','关键源码与方案定位',
 ev(HP,'## 22. MODULAR-RAG-MCP-SERVER 参考项目吸收结论','已有的吸收结论与 ES / VikingDB 分工',13)+
 ev(J+'service/reliability/VectorizationLeaseService.java','public void heartbeat','租约续期与失效检查',7)+
 ev(J+'service/HybridSearchService.java','private Ranked rerankAndTruncate','可选重排、预算与阈值',20)+
 ev(J+'service/search/ParentContextExpander.java','int cap = Math.min','扩展预算与去重',13)+
 ev(J+'service/eval/EvalCase.java','public boolean hasExpectedEvidence','分块证据标注依赖文件标注',3)+
 para('预过滤的语义可对照 <a href="https://www.elastic.co/docs/solutions/search/vector/knn">Elastic 官方 kNN 文档</a>。官方文档用于核对机制，不代表本地项目运行服务已升级至其最新版。')))
page('hp-optimization.html','HP RAG：参考与优化建议','保留教育领域设计，补齐任务可靠性、版本发布、在线预算和可验证的证据链。',opt,'HP DESIGN REVIEW · ACTIONABLE PROPOSALS')

overview=[sec('read','阅读顺序',
 '<div class="links-grid"><a class="report-link" href="modular-rag.html"><h3>MODULAR-RAG-MCP-SERVER</h3><p>一个 Python 项目：把 PDF 变成可搜索资料，并介绍如何安装、运行和连接 AI 助手。</p><span>查看项目介绍与启动步骤 →</span></a><a class="report-link" href="paismart.html"><h3>PaiSmart</h3><p>一个完整知识库网站：包括文件上传、资料搜索、权限检查和 AI 问答。</p><span>查看项目介绍与启动步骤 →</span></a></div><a class="report-link" href="hp-optimization.html"><h3>你的 HP 教学资料方案</h3><p>把两个项目里的做法和你的方案逐项对照，说明哪些值得借鉴、哪些要先验证。</p><span>查看建议 →</span></a>'),
 sec('conclusion','最重要的结论',para('沿用已收敛的 ES BM25 + VikingDB Dense，先把 Office 原生解析、错误隔离、可靠入库与版本发布做成可运行闭环。检索质量上，把已有教学资料结构、查询改写与 Evidence Gate 变成有版本的组件契约和独立可评测的垂直切片。')+para('MODULAR 帮你理解算法骨架，PaiSmart 帮你看到产品运行时的故障和状态；HP 需要自行验证教学单元与数学查询的增益。')),
 sec('scope','审阅边界与附件',para('基于 <code>E:/project/别人的项目/</code> 中两个本地快照，以及用户给定的 06 HP 方案。没有修改参考源码或覆盖原方案；没有从网络下载或运行参考项目。全部 HTML 内置 CSS / JavaScript，无 CDN，支持离线阅读、手机布局、主题切换与打印。')+para('<a href="hp-optimization.md">优化建议 Markdown</a> · <a href="evidence-index.json">源码证据索引</a> · <a href="build_reports.py">报告生成脚本</a>'))]
page('index.html','两个 RAG 项目，一份 HP 对照报告','从参考源码看清流程与技术栈，再把可借鉴的机制落实到你的教学资源方案。',overview,'RAG SOURCE STUDY · READING GUIDE')

md=['# HP 教学资源 RAG：参考与优化建议','',
 '> 审阅日期：2026-10-14。依据用户提供的本地源码与 06 方案。静态分析，未运行参考项目或模型；建议不代表 HP 已上线能力。',
 '', '你的教育场景设计已覆盖查询改写、结构教材分块、Evidence Gate 和真实评测。优先补工程协议，不需要因为参考项目不同而整体换栈。',
 '', '当前架构按 §21–23 收敛为 MySQL 主数据 / Java 业务会话 / MongoDB Trace / PostgreSQL checkpoint / ES BM25 / VikingDB Dense / RabbitMQ Worker；应清理 §17.5 与 §18.3 的少量历史示例；首期资料为授权 PPT / Word 教案 / 教辅，不要求取得教材 PDF。',
 '', 'HTML：[阅读入口](index.html) · [MODULAR-RAG](modular-rag.html) · [PaiSmart](paismart.html) · [HP 优化](hp-optimization.html)', '']
for r in recommendations:
    pri,title,current,reference,implementation,acceptance,cost=r
    md += [f'## {pri}：{title}','',f'**方案现状：** {current}','',f'**借鉴来源：** {reference}','',f'**具体补法：** {implementation}','',f'**验收方式：** {acceptance}','',f'**取舍与边界：** {cost}','']
md += ['## 建议实施顺序','',
 '1. 统一当前技术决策表与组件 schema。',
 '2. 小语料跑通 canonical、双路检索、Outbox / lease 与 manifest 发布。',
 '3. 固定分层 Golden Set 与留出集，分别验证结构分块、查询改写、Rerank 和扩展。',
 '4. 先接一个确定性讲评 Workflow，再将稳定 Retriever 包装为 Agent Tool。','',
 '指标分别覆盖授权 / 版本、例题完整性、检索排序、无证据降级、教学一致性和运行成本。每个指标关联具体上线决策。参考 [Langfuse 指标选择指南](https://langfuse.com/academy/evaluate/choosing-what-to-evaluate)。','',
 'RunHub 可以验证通用检索与工程机制；赛事文章不能证明数学教材解析、公式关系和教学表达质量。PPT / Word 教辅的原生结构、公式、跨页与资料错误样例仍需单独评测。','',
 '所有建议的源码位置与摘录见 HTML 源码抽屉与 evidence-index.json。原始 06 方案未修改。']
(OUT/'hp-optimization.md').write_text('\n'.join(md)+'\n',encoding='utf-8')

# Snapshot source coordinates, independently resolvable by code editors.
index=[]
for filename in ('modular-rag.html','paismart.html','hp-optimization.html'):
    text=(OUT/filename).read_text(encoding='utf-8')
    for match in re.finditer(r'<details class="evidence"><summary>(.*?) : (\d+) .*?<p class="sourcepath"><a href="(.*?)">(.*?)</a>',text,re.S):
        index.append({'report':filename,'source':html.unescape(match.group(4)),'line':int(match.group(2))})
(OUT/'evidence-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'source-fingerprints.json').write_text(json.dumps({path:hashlib.sha256(data).hexdigest() for path,data in SOURCE_CACHE.items()},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'output':str(OUT),'html_pages':4,'recommendations':len(recommendations),'evidence_entries':len(index)},ensure_ascii=False))

