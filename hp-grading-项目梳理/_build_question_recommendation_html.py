from pathlib import Path
from html.parser import HTMLParser
import html, re

root = Path(__file__).resolve().parent
src = root / "16-错题推题优化方案.md"
out = root / "16-错题推题流程图解.html"

def node(title, text="", kind=""):
    return '<div class="node '+kind+'"><strong>'+title+'</strong>'+('<span>'+text+'</span>' if text else '')+'</div>'

def arrow(label=""):
    return '<div class="arrow" aria-hidden="true">'+(('<small>'+label+'</small>') if label else '')+'↓</div>'

main_flow = '<figure class="diagram" aria-label="推荐主流程：读会话、硬过滤召回、去重排序、缺题补足、原子登记、返回">'
main_flow += node("首次推荐 / 换一批", "sessionId 记录会话 · requestId 标识本次点击") + arrow()
main_flow += node("读取 Redis 会话", "校验用户与条件，取出此前已返回题；同 requestId 取回原批次") + arrow()
main_flow += '<div class="branches"><div class="branch"><div class="branch-label">WRONG_QUESTION · 错题推荐</div>'+node("VikingDB 题干语义 TopM", "来源 / 学科 / 学段 / 年级硬过滤<br>知识点不作召回门槛；保留标签缺失或不匹配候选", "primary")+'</div><div class="branch"><div class="branch-label">KNOWLEDGE_POINT · 知识点推荐</div>'+node("VikingDB 目标知识点标量召回", "目标知识点 must ＋相同硬条件<br>无原题，不计算题干相似度", "primary")+'</div></div>'+arrow()
main_flow += node("项目层核验详情 → 去重 → 分模式排序", "错题：题干相关性主导，可信知识点交集小幅加权，排除同题与近重复<br>知识点：复核目标点与标签可信度，控制同题干簇和会话历史") + arrow()
main_flow += '<div class="decision">合格且未返回的题够 N 道？</div><div class="branches"><div class="branch"><div class="branch-label">足够</div>'+node("准备提交本批", "保持相关性排序")+'</div><div class="branch"><div class="branch-label">不足</div>'+node("按需补召回", "有界扩大 Viking 候选 → 学科网补题<br>新题核验并就绪后准入", "fallback")+'</div></div>'+arrow()
main_flow += node("Redis 原子确认与登记", "重查最新历史；满批或明确接受部分结果时提交<br>登记最终题目，缓存本 requestId 的响应", "primary") + arrow()
main_flow += node("返回新批次", "题目 + sessionId + batchId + 状态")
main_flow += '<figcaption>换一批 → 回到开头：保留 sessionId，生成新的 requestId。并发不足时有界补召回；未提交前不扣题。</figcaption></figure>'

session_flow = '<figure class="diagram" aria-label="同一会话连续换批，历史集合累计排除，重试取回原批次">'
session_flow += '<div class="sequence">'
for title, request, items, seen in [
    ("首次推荐","S1 / R1","Q1 · Q2 · Q3","累计排除 Q1—Q3"),
    ("换一批","S1 / R2","Q4 · Q5 · Q6","累计排除 Q1—Q6"),
    ("再换一批","S1 / R3","Q7 · Q8 · Q9","累计排除 Q1—Q9")]:
    session_flow += '<div class="batch"><span class="branch-label">'+title+'</span><strong>'+request+'</strong><div class="questions">'+items+'</div><span>'+seen+'</span></div>'
session_flow += '</div>'+arrow()
session_flow += node("Redis 持续累计当前会话历史", "questionId / recommend_key / stem_hash<br>返回前原子重查，防止并发取到同题", "primary")
session_flow += '<figcaption>网络重试 S1 / R2 → 仍返回 Q4、Q5、Q6，不新增历史。示例题号仅用于说明行为。</figcaption></figure>'

external_flow = '<figure class="diagram" aria-label="学科网两个入口汇入统一核验入库流程">'
external_flow += '<div class="branches"><div class="branch"><div class="branch-label">补题</div>'+node("本地未返回题不足 N", "补足请求，最多等待至耗时预算", "fallback")+'</div><div class="branch"><div class="branch-label">探索扩库</div>'+node("本地足够也按比例调用", "配置 p · 后台运行<br>比例按请求统计，不按返回题数", "primary")+'</div></div>'+arrow()
for title, text in [
    ("幂等调用学科网","错题模式按原题文本探索；知识点模式按目标点探索；保留学科 / 学段 / 年级"),
    ("核验内容与硬条件，排除已存在题","错题模式允许待核验知识点；知识点模式须确认目标点"),
    ("保存 Mongo → 清洗题干与去重","统一标签、文本规则和元数据版本"),
    ("同步独立推荐 Collection → Index","只对干净题干向量化；失败重试与补扫<br>索引就绪后才进入候选池"),
    ("后续推荐可用","统计新增合格非重复题量，而不仅是调用次数")]:
    external_flow += node(title,text) + arrow()
external_flow = external_flow.removesuffix(arrow()) + '<figcaption>首次推荐和换一批都是有效新请求；requestId 重试与任务轮询不重复计入探索比例。</figcaption></figure>'

diagrams = iter([main_flow, session_flow, external_flow])

def inline(s):
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    def link(m):
        dest = html.unescape(m.group(2))
        if dest.startswith("/D:/"):
            dest = "file:///" + dest[1:]
        return '<a href="'+html.escape(dest, quote=True)+'">'+m.group(1)+'</a>'
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, s)

lines = src.read_text(encoding="utf-8").splitlines()
parts = []
i = 0
while i < len(lines):
    line = lines[i]
    if not line.strip():
        i += 1
        continue
    if line.startswith("```"):
        lang = line[3:].strip()
        block = []
        i += 1
        while i < len(lines) and not lines[i].startswith("```"):
            block.append(lines[i])
            i += 1
        i += 1
        if lang == "mermaid":
            parts.append(next(diagrams))
        else:
            parts.append('<pre><code>'+html.escape("\n".join(block))+'</code></pre>')
        continue
    if line.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            if not all(re.fullmatch(r"[:\- ]+", c) for c in cells):
                rows.append(cells)
            i += 1
        table = '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+inline(c)+'</th>' for c in rows[0])+'</tr></thead><tbody>'
        table += ''.join('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in row)+'</tr>' for row in rows[1:])
        parts.append(table+'</tbody></table></div>')
        continue
    m = re.match(r"^(#{1,3}) (.+)$", line)
    if m:
        level = len(m.group(1))
        label = m.group(2)
        anchor = re.match(r"(\d+)\.", label)
        aid = (' id="section-'+anchor.group(1)+'"') if level == 2 and anchor else ''
        parts.append('<h'+str(level)+aid+'>'+inline(label)+'</h'+str(level)+'>')
        i += 1
        continue
    if line.startswith(">"):
        q = []
        while i < len(lines) and lines[i].startswith(">"):
            q.append(lines[i].lstrip("> "))
            i += 1
        parts.append('<aside class="note">'+inline(" ".join(q))+'</aside>')
        continue
    if re.match(r"^(- |\d+\. )", line):
        ordered = bool(re.match(r"^\d+\. ", line))
        tag = "ol" if ordered else "ul"
        items = []
        while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
            items.append(re.sub(r"^(- |\d+\. )", "", lines[i]))
            i += 1
        parts.append('<'+tag+'>'+''.join('<li>'+inline(t)+'</li>' for t in items)+'</'+tag+'>')
        continue
    paragraph = []
    while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,3} |\||```|> |- |\d+\. )", lines[i]):
        paragraph.append(lines[i])
        i += 1
    parts.append('<p>'+inline(" ".join(paragraph))+'</p>')

style = """
:root{color-scheme:light dark;--bg:light-dark(#f7f9fc,#121720);--paper:light-dark(#fff,#1a2230);--ink:light-dark(#172637,#e8eef5);--muted:light-dark(#52647a,#b4c0d0);--line:light-dark(#d8e1eb,#3a4658);--main:light-dark(#075b73,#81d3e4);--main-bg:light-dark(#edf7fa,#173440);--backup:light-dark(#815210,#edc27f);--backup-bg:light-dark(#fff8eb,#3b3020);}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.8 "Microsoft YaHei",system-ui,sans-serif}
main{max-width:1040px;margin:28px auto;padding:34px 42px;background:var(--paper)}
h1{font-size:29px;line-height:1.45;margin:0 0 18px}h2{font-size:23px;line-height:1.5;margin:42px 0 14px;padding-top:12px;border-top:1px solid var(--line);scroll-margin-top:12px}h3{font-size:18px;margin:24px 0 10px}p{margin:12px 0}li{margin:8px 0}
a{color:var(--main);text-underline-offset:3px}nav{display:flex;gap:10px 20px;flex-wrap:wrap;padding:14px 0;margin:12px 0 24px;border-bottom:1px solid var(--line)}nav a{font-size:15px}
.note{background:var(--main-bg);padding:12px 16px;color:var(--muted);font-size:14px}code{font-family:Consolas,monospace;font-size:.93em;overflow-wrap:anywhere}pre{padding:16px;background:var(--bg);overflow:auto;line-height:1.65}pre code{white-space:pre;font-size:14px}
.table-wrap{width:100%;overflow:auto;margin:16px 0}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.75}th,td{padding:11px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:var(--bg);font-weight:600}th:first-child,td:first-child{min-width:125px}
.diagram{margin:22px 0 28px;padding:22px 16px;background:var(--bg);border-radius:12px}.node{max-width:730px;margin:auto;padding:13px 18px;background:var(--paper);border:1px solid var(--line);border-radius:8px;text-align:center}.node strong{display:block;font-size:17px;line-height:1.5}.node span{display:block;color:var(--muted);font-size:14px;line-height:1.75;margin-top:5px}.node.primary{background:var(--main-bg);border-color:var(--main)}.node.fallback{background:var(--backup-bg);border-color:var(--backup)}
.arrow{text-align:center;color:var(--muted);font-size:22px;line-height:1.5;padding:3px}.arrow small{display:block;font-size:13px}.branches{display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:820px;margin:auto}.branch-label{display:block;text-align:center;color:var(--muted);font-size:14px;margin:6px 0}.branch .node{height:calc(100% - 37px)}.decision{max-width:460px;margin:0 auto 10px;padding:11px 16px;text-align:center;font-weight:600;background:var(--main-bg);border-radius:6px}
figcaption{text-align:center;color:var(--muted);font-size:14px;padding-top:14px}.sequence{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.batch{text-align:center;border-top:3px solid var(--main);background:var(--paper);padding:14px 8px}.batch>strong{display:block;font-size:18px}.batch>span:last-child{color:var(--muted);font-size:14px}.questions{font-weight:600;padding:12px 0;color:var(--main)}
footer{margin-top:36px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:14px}
@media(max-width:680px){main{padding:22px 18px;margin:0}h1{font-size:25px}h2{font-size:21px}.branches,.sequence{grid-template-columns:1fr}.branch .node{height:auto}.diagram{padding:18px 10px}.node strong{font-size:16px}.table-wrap table{min-width:540px}}
@media print{body{background:#fff;color:#111}main{max-width:none;padding:0;margin:0}nav{display:none}.diagram{break-inside:avoid}h2{break-after:avoid}.table-wrap{overflow:visible}a{color:inherit}}
"""
nav = '<nav aria-label="文档导航"><a href="#section-2">推荐主流程</a><a href="#section-3">逐步说明</a><a href="#section-4">字段优化</a><a href="#section-5">换一批</a><a href="#section-7">学科网扩库</a><a href="#section-8">接口草案</a><a href="#section-10">面试回答</a></nav>'
# Navigation follows the title and status note.
body = "\n".join(parts[:2]) + nav + "\n".join(parts[2:])
out.write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>错题推题优化方案 · 流程图解</title><style>'+style+'</style></head><body><main>'+body+'<footer>待实施设计 · 内容源自同目录 16-错题推题优化方案.md · 流程图无需联网即可阅读</footer></main></body></html>', encoding="utf-8")
generated = out.read_text(encoding="utf-8")
HTMLParser().feed(generated)
assert generated.count('<figure class="diagram"') == 3
assert all(('id="section-' + str(n) + '"') in generated for n in [2, 3, 4, 5, 7, 8, 10])
assert all(x in generated for x in ["sessionId", "requestId", "recommend_eligible"])
assert all(x in generated for x in ["question_recommend_v1", "doubao-embedding-vision", "Chroma", "4.7 新推荐"])
assert "\ufffd" not in generated and "flowchart TD" not in generated
print("HTML generated and parsed: 3 diagrams, navigation links and required design fields present.")

