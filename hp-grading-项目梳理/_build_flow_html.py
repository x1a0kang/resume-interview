from pathlib import Path
from collections import defaultdict, deque
import re
import html
import json
import unicodedata

ROOT = Path(__file__).resolve().parent
E = html.escape
sources = []


def wrap(text, limit=22):
    lines, current, count = [], '', 0
    for char in text:
        units = 1 if unicodedata.east_asian_width(char) in 'WF' else .55
        if count + units > limit and current:
            lines.append(current)
            current, count = '', 0
        current += char
        count += units
    if current:
        lines.append(current)
    return lines


def chart(source):
    index = len(sources)
    sources.append(source)
    nodes, edges = {}, []
    node_pattern = re.compile(r'([A-Z]\d+[a-z]?)(\[|\{)"([^"]+)"[\]}]')
    for line in source.splitlines():
        for match in node_pattern.finditer(line):
            nodes.setdefault(match[1], (match[3], match[2] == '{'))
        clean = node_pattern.sub(lambda m: m[1], line).strip()
        match = re.fullmatch(r'([A-Z]\d+[a-z]?)\s*(?:--\s*(.*?)\s*)?-->\s*([A-Z]\d+[a-z]?)', clean)
        if match:
            edges.append((match[1], match[3], match[2] or ''))
    adj = defaultdict(list)
    for i, (a, b, label) in enumerate(edges):
        assert a in nodes and b in nodes, (a, b)
        adj[a].append((b, i))
    state, back = {}, set()
    def visit(a):
        state[a] = 1
        for b, i in adj[a]:
            if state.get(b) == 1:
                back.add(i)
            elif state.get(b, 0) == 0:
                visit(b)
        state[a] = 2
    for a in nodes:
        if not state.get(a):
            visit(a)
    indegree = {a: 0 for a in nodes}
    incoming = defaultdict(list)
    for i, (a, b, label) in enumerate(edges):
        if i not in back:
            indegree[b] += 1
            incoming[b].append(a)
    ranks = {a: 0 for a in nodes}
    q = deque(a for a in nodes if indegree[a] == 0)
    while q:
        a = q.popleft()
        for b, i in adj[a]:
            if i in back:
                continue
            ranks[b] = max(ranks[b], ranks[a] + 1)
            indegree[b] -= 1
            if indegree[b] == 0:
                q.append(b)
    assert all(v == 0 for v in indegree.values()), 'Unresolved cycle'
    layers = defaultdict(list)
    for a, rank in ranks.items():
        layers[rank].append(a)
    width = max(1160, max(len(v) for v in layers.values()) * 400 + 200)
    points, sizes, wrapped = {}, {}, {}
    y = 80
    for rank in sorted(layers):
        layer = layers[rank]
        layer.sort(key=lambda a: sum(points[p][0] for p in incoming[a] if p in points) / max(1, sum(p in points for p in incoming[a])))
        height = 0
        for a in layer:
            text, decision = nodes[a]
            lines = wrap(text, 13 if decision else 17)
            wrapped[a] = lines
            h = max(168, len(lines) * 24 + 120) if decision else max(82, len(lines) * 24 + 36)
            sizes[a] = (360 if decision else 324, h)
            height = max(height, h)
        step = 400
        for j, a in enumerate(layer):
            points[a] = (width / 2 + (j - (len(layer) - 1) / 2) * step, y + height / 2)
        y += height + 88
    height = y + 30
    parts = [f'<svg class="flow-svg" role="img" aria-label="{E(nodes[next(iter(nodes))][0])}" viewBox="0 0 {width} {height}" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg"><defs><marker id="arrow{index}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#7b8c9e"/></marker></defs>']
    parts.append('<g class="edges">')
    for i, (a, b, label) in enumerate(edges):
        ax, ay = points[a]
        bx, by = points[b]
        aw, ah = sizes[a]
        bw, bh = sizes[b]
        long = ranks[b] - ranks[a] > 1
        if i in back or long:
            left = (i in back) or (ax + bx <= width)
            sign = -1 if left else 1
            sx, sy = ax + sign * aw / 2, ay
            tx, ty = bx + sign * bw / 2, by
            lane = 30 + (i % 5) * 10 if left else width - 30 - (i % 5) * 10
            path = f'M {sx} {sy} H {lane} V {ty} H {tx}'
            lx, ly = lane + (12 if left else -12), (sy + ty) / 2
            anchor = 'start' if left else 'end'
        else:
            sx, sy = ax, ay + ah / 2
            tx, ty = bx, by - bh / 2
            middle = (sy + ty) / 2
            path = f'M {sx} {sy} V {middle} H {tx} V {ty}'
            lx, ly = (sx + tx) / 2 + (14 if sx == tx else 0), middle - 11
            anchor = 'start' if sx == tx else 'middle'
        error = any(word in label for word in ('\u5931\u8d25', '\u5f02\u5e38'))
        css = 'edge error' if error else 'edge'
        parts.append(f'<path class="{css}" d="{path}" marker-end="url(#arrow{index})"/>')
        if label:
            parts.append(f'<text class="edge-label" x="{lx}" y="{ly}" text-anchor="{anchor}">{E(label)}</text>')
    parts.append('</g><g class="nodes">')
    for a, (text, decision) in nodes.items():
        x, yy = points[a]
        w, h = sizes[a]
        if decision:
            kind = 'decision'
        elif any(word in text for word in ('\u629b\u51fa\u5f02\u5e38', '\u5931\u8d25', '\u7f3a\u5c11\u8be5')):
            kind = 'failure'
        elif any(word in text for word in ('\u89c6\u89c9\u6a21\u578b', '\u8bed\u8a00\u6a21\u578b', '\u5938\u514b', 'TextIn', 'OCR', '\u89c6\u89c9\u8bf7\u6c42')):
            kind = 'external'
        else:
            kind = 'local'
        parts.append(f'<g class="node {kind}"><title>{E(text)}</title>')
        if decision:
            parts.append(f'<polygon points="{x},{yy-h/2} {x+w/2},{yy} {x},{yy+h/2} {x-w/2},{yy}"/>')
        else:
            parts.append(f'<rect x="{x-w/2}" y="{yy-h/2}" width="{w}" height="{h}" rx="12"/>')
        start = yy - (len(wrapped[a]) - 1) * 12
        for j, line in enumerate(wrapped[a]):
            parts.append(f'<text x="{x}" y="{start+j*24}" dominant-baseline="middle" text-anchor="middle">{E(line)}</text>')
        parts.append('</g>')
    parts.append('</g></svg>')
    title = '\u5b8c\u6574\u6d41\u7a0b\u56fe'
    control = f'<div class="diagram-toolbar"><strong>{title}</strong><span>{len(nodes)} \u4e2a\u8282\u70b9 \u00b7 {len(edges)} \u6761\u8fde\u7ebf</span><label>\u7f29\u653e <input type="range" min="45" max="125" value="85" data-chart="{index}"><output>85%</output></label><button data-expand="{index}">\u5c55\u5f00\u5168\u56fe</button></div>'
    return f'<div class="diagram" id="diagram-{index}">{control}<div class="diagram-scroll"><div class="svg-sizing" style="width:{width*.85}px;height:{height*.85}px"><div class="svg-scale" style="transform:scale(.85)">{"".join(parts)}</div></div></div><details><summary>Mermaid \u56fe\u6e90\u7801</summary><pre><code>{E(source)}</code></pre></details></div>'


def inline(text):
    text = E(text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: f'<a href="{m[2]}">{m[1]}</a>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    return text


def markdown(text):
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('```'):
            typ = line[3:]
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                body.append(lines[i])
                i += 1
            out.append(chart('\n'.join(body)) if typ == 'mermaid' else f'<pre><code>{E(chr(10).join(body))}</code></pre>')
        elif line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = lines[i].strip().strip('|').split('|')
                if not all(re.fullmatch(r'[\s:-]+', c) for c in cells):
                    rows.append(cells)
                i += 1
            out.append('<div class="table-scroll"><table><thead><tr>' + ''.join(f'<th>{inline(c.strip())}</th>' for c in rows[0]) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{inline(c.strip())}</td>' for c in row) + '</tr>' for row in rows[1:]) + '</tbody></table></div>')
            continue
        elif line.startswith('#'):
            match = re.match(r'(#+) (.*)', line)
            if match:
                level = min(len(match[1]), 4)
                out.append(f'<h{level}>{inline(match[2])}</h{level}>')
        elif line.startswith('>'):
            out.append(f'<aside class="note">{inline(line.lstrip("> "))}</aside>')
        elif line.startswith('- '):
            items = []
            while i < len(lines) and lines[i].startswith('- '):
                items.append('<li>' + inline(lines[i][2:]) + '</li>')
                i += 1
            out.append('<ul>' + ''.join(items) + '</ul>')
            continue
        else:
            paragraph = [line]
            while i+1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith(('#', '|', '```', '> ', '- ')):
                i += 1
                paragraph.append(lines[i].strip())
            out.append('<p>' + inline(' '.join(paragraph)) + '</p>')
        i += 1
    return '\n'.join(out)


CSS = '\n:root{--ink:#163044;--muted:#566d7f;--paper:#f4f7fa;--blue:#145eaa;--line:#dbe4ed}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:26px}body{margin:0;color:var(--ink);background:var(--paper);font:16px/1.85 "Microsoft YaHei","PingFang SC",sans-serif}a{color:var(--blue);text-underline-offset:3px}header{padding:52px max(6vw,24px) 38px;background:#102d42;color:#fff}header .eyebrow{font-size:13px;letter-spacing:2px;color:#b6d7ee}h1{font-size:36px;line-height:1.4;margin:14px 0}header p{max-width:950px;color:#d8e5ef;margin:10px 0}.pills{display:flex;flex-wrap:wrap;gap:10px;margin:24px 0}.pills span{background:#24475f;padding:4px 14px;border-radius:5px;font-size:14px}.source-links{display:flex;gap:24px;flex-wrap:wrap}.source-links a{color:#c9e7ff;font-size:14px}.layout{max-width:1700px;display:grid;grid-template-columns:240px minmax(0,1fr);gap:28px;margin:28px auto;padding:0 28px}nav{position:sticky;top:24px;align-self:start;max-height:calc(100vh - 48px);overflow:auto;background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px}nav strong{display:block;padding:8px;color:#547186;font-size:13px}nav a{display:block;font-size:13px;padding:7px 10px;text-decoration:none;border-radius:5px}nav a:hover{background:#edf4fb}nav a.call-link{color:#617b70}main{min-width:0}section{padding:28px 30px;background:#fff;border:1px solid var(--line);border-radius:12px;margin-bottom:24px}.section-top{display:flex;align-items:start;gap:16px;margin-bottom:16px}.section-top>span{font-size:12px;color:#648199;letter-spacing:1px;border:1px solid var(--line);padding:4px 8px;border-radius:4px;white-space:nowrap}.section-top h2{margin:0;font-size:24px;line-height:1.55}h3{font-size:19px;margin:30px 0 12px}p{margin:14px 0}.note{background:#eef5fb;border-left:4px solid #6da3d0;border-radius:4px;padding:12px 16px;font-size:14px;color:#4b6376;margin:14px 0}.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:13px;margin:18px 0}.legend i{display:inline-block;width:13px;height:13px;margin-right:5px;vertical-align:-1px;border-radius:3px}.table-scroll{overflow:auto;border:1px solid var(--line);border-radius:8px;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:14px;min-width:690px;line-height:1.8}th{background:#edf3f8;font-weight:600;text-align:left;white-space:nowrap}th,td{padding:14px 16px;border-bottom:1px solid var(--line);vertical-align:top}tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#fafcfe}td:first-child{min-width:106px}pre{padding:20px;white-space:pre;overflow:auto;background:#142e42;color:#e3edf4;border-radius:6px;font:13px/1.7 Consolas,monospace}code{font-size:.9em}.diagram{border:1px solid #d3dfea;border-radius:10px;margin:20px 0;background:#fbfdff;overflow:hidden}.diagram-toolbar{display:flex;align-items:center;gap:18px;flex-wrap:wrap;background:#eff5fa;padding:13px 17px;border-bottom:1px solid var(--line);font-size:13px}.diagram-toolbar label{margin-left:auto;display:flex;align-items:center;gap:8px}input[type=range]{width:115px}button{font:inherit;border:1px solid #bdcede;background:#fff;color:#164c78;padding:5px 12px;border-radius:5px;cursor:pointer}.diagram-scroll{height:730px;overflow:auto;overscroll-behavior:contain;position:relative;background-image:radial-gradient(#dce6ee .7px,transparent .7px);background-size:18px 18px}.diagram.expanded .diagram-scroll{height:auto;max-height:none}.svg-sizing{margin:0 auto;position:relative}.svg-scale{transform-origin:0 0;position:absolute;top:0;left:0}.flow-svg{font-family:"Microsoft YaHei",sans-serif}.edge{stroke:#7b8c9e;stroke-width:2;fill:none;stroke-linejoin:round}.edge.error{stroke:#ba6670;stroke-dasharray:6 4}.edge-label{font-size:14px;fill:#516879;paint-order:stroke;stroke:#fbfdff;stroke-width:6px;stroke-linejoin:round}.node text{font-size:17px;fill:#15364e}.node rect,.node polygon{stroke-width:1.8}.node.local rect{fill:#f0f5fa;stroke:#9bafc1}.node.external rect{fill:#e6f3ff;stroke:#5195d0}.node.decision polygon{fill:#fff5dc;stroke:#c9a357}.node.failure rect{fill:#fff0f0;stroke:#cf8790}details{padding:10px 16px;border-top:1px solid var(--line);font-size:13px}summary{cursor:pointer;color:#346c97}footer{padding:24px;text-align:center;color:#708595;font-size:13px}.intro p{font-size:16px}@media(max-width:980px){.layout{grid-template-columns:1fr;padding:0 12px;gap:16px}nav{position:static;display:flex;flex-wrap:wrap;gap:3px;max-height:none}nav strong{width:100%}nav a{font-size:12px}section{padding:22px 18px}.section-top h2{font-size:21px}h1{font-size:29px}header{padding:32px 24px}.diagram-toolbar label{margin-left:0}.diagram-scroll{height:630px}}@media print{nav,.diagram-toolbar,details{display:none}.layout{display:block;padding:0}section{border:0;break-inside:auto}.diagram-scroll{height:auto;overflow:visible}.svg-sizing{transform:scale(.55);transform-origin:0 0}header{background:#fff;color:#163044}header p{color:#163044}}\n\n.explanation{padding:14px 18px;margin:20px 0;background:#f6f9fc;border-left:3px solid #9ab6ce;border-radius:5px}.explanation h3{margin:0 0 12px}.explanation-step{margin:10px 0}.explanation-step strong{margin-right:5px}.steps{padding-left:25px}.steps>li{padding:8px 0}.steps h3{margin:10px 0 6px}.io{padding:9px 14px;margin:8px 0;background:#f4f8fb;border-radius:5px;font-size:14px}.tag{font-size:12px;color:#536f86;padding:2px 6px;background:#eaf1f7;border-radius:4px}.example{padding:14px 18px;background:#f1f8f5;border-left:3px solid #84b5a1;margin:20px 0}.example h4{margin:0 0 8px}.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}.mini{padding:16px;background:#f6f9fc;border:1px solid #dbe4ed;border-radius:8px}.mini h3{margin:0 0 8px}.sources{font-size:13px;color:#5b7184}.lead{font-size:18px;color:#345069}.source-edit-note{display:none}'

SCRIPT = "\ndocument.querySelectorAll('input[data-chart]').forEach(input=>input.addEventListener('input',()=>{\n const d=document.getElementById('diagram-'+input.dataset.chart), s=d.querySelector('svg'), k=Number(input.value)/100;\n d.querySelector('.svg-scale').style.transform='scale('+k+')';\n const v=d.querySelector('.svg-sizing');v.style.width=s.getAttribute('width')*k+'px';v.style.height=s.getAttribute('height')*k+'px';input.nextElementSibling.textContent=input.value+'%';\n}));\ndocument.querySelectorAll('button[data-expand]').forEach(b=>b.addEventListener('click',()=>{const d=document.getElementById('diagram-'+b.dataset.expand);d.classList.toggle('expanded');b.textContent=d.classList.contains('expanded')?'收起全图':'展开全图';}));\n"

legend = '<div class="legend"><span><i style="background:#e6f3ff;border:1px solid #5195d0"></i>外部识别或模型步骤</span><span><i style="background:#f0f5fa;border:1px solid #9bafc1"></i>本地处理或输入输出</span><span><i style="background:#fff5dc;border:1px solid #c9a357"></i>条件判断</span><span><i style="background:#fff0f0;border:1px solid #cf8790"></i>异常或失败分支</span></div>'


def render(data):
    sources.clear()
    panels, links = [], []
    for i, block in enumerate(data['sections']):
        sid, heading = block['id'], block['title']
        cls = ' class="call-link"' if block.get('kind') == 'calls' else ''
        links.append(f'<a href="#{E(sid)}"{cls}>{E(heading.split("\uff1a")[0])}</a>')
        body = markdown(block.get('markdown', '')) + block.get('html', '')
        body = re.sub(r'<h3>(Q(\d+)[\uff1a:].*?)</h3>', lambda m: f'<h3 id="question-{m[2]}">{m[1]}</h3>', body)
        body = body.replace('<h4>\u8ffd\u95ee\uff1a\u878d\u5408\u5230\u5e95\u600e\u6837\u6539\u5b57\uff1f\u7528\u53ef\u590d\u6838\u7684\u4f8b\u5b50\u8bf4\u660e</h4>', '<h4 id="fusion-character-examples">\u8ffd\u95ee\uff1a\u878d\u5408\u5230\u5e95\u600e\u6837\u6539\u5b57\uff1f\u7528\u53ef\u590d\u6838\u7684\u4f8b\u5b50\u8bf4\u660e</h4>')
        if sid == 'layout-details':
            body = body.replace('<h3>7.1 ', '<h3 id="two-column-order">7.1 ', 1)
        panels.append(f'<section id="{E(sid)}"><div class="section-top"><span>{i+1:02d}</span><h2>{E(heading)}</h2></div>{body}</section>')
    intro = re.sub(r'(?m)^# .*\n', '', data['intro'], count=1)
    header_links = ''.join(f'<a href="{E(href)}">{E(label)}</a>' for href,label in data['header_links'])
    header = f'<header><div class="eyebrow">{E(data["eyebrow"])}</div><h1>{E(data["title"])}</h1><p>{E(data["description"])}</p><div class="source-links">{header_links}</div></header>'
    opening = f'<section class="intro">{markdown(intro)}{legend}<p>\u6bcf\u6761\u4e3b\u6d41\u7a0b\u5404\u6709\u4e00\u5f20\u5b8c\u6574\u56fe\uff0c\u53ef\u6eda\u52a8\u3001\u7f29\u653e\u6216\u5c55\u5f00\u3002\u6b65\u9aa4\u8bf4\u660e\u3001\u4f8b\u5b50\u548c\u5916\u90e8\u8c03\u7528\u6e05\u5355\u5747\u5728\u672c\u9875\uff1b\u56fe\u6e90\u7801\u4e5f\u4fdd\u5b58\u5728\u672c\u9875\uff0c\u53ef\u79bb\u7ebf\u9605\u8bfb\u3002</p></section>'
    source = json.dumps(data, ensure_ascii=False, indent=2).replace('<', '\u003c')
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(data["title"])}</title><style>{CSS}</style></head><body>{header}<div class="layout"><nav aria-label="\u76ee\u5f55"><strong>\u6d41\u7a0b\u4e0e\u8c03\u7528\u76ee\u5f55</strong>{"".join(links)}</nav><main>{opening}{"".join(panels)}</main></div><footer>\u4f9d\u636e\u5f53\u524d\u5de5\u4f5c\u533a\u6e90\u7801\u6574\u7406 \u00b7 \u6a21\u578b\u7248\u672c\u7531\u90e8\u7f72\u914d\u7f6e\u6307\u5b9a \u00b7 \u8c03\u7528\u6b21\u6570\u4e0d\u4ee3\u8868\u751f\u4ea7\u5ef6\u8fdf</footer><script>{SCRIPT}</script><!-- Edit document-source, then run _build_flow_html.py. This HTML is the sole content source. --><script id="document-source" type="application/json">{source}</script></body></html>'


def rebuild(path):
    current = path.read_text(encoding='utf-8-sig')
    match = re.search(r'<script id="document-source" type="application/json">(.*?)</script>', current, re.S)
    if not match:
        raise ValueError(f'Missing embedded document source: {path.name}')
    data = json.loads(match[1])
    rendered = render(data)
    assert len(sources) == 4
    path.write_text(rendered, encoding='utf-8')
    print(json.dumps({'file':path.name, 'charts':len(sources), 'sections':len(data['sections'])}, ensure_ascii=True))


if __name__ == '__main__':
    for pattern in ('13-*.html', '15-*.html'):
        rebuild(next(ROOT.glob(pattern)))
