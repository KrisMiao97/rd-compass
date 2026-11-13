"""Schema 2: purpose-aware reports and a single-source reading catalog.

Checks identity and artifact consistency, never patent truth or reading quality.
All dependencies are Python standard library modules.
"""
import csv
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import date

MODES = {'technology': '技术理解与演进', 'opportunity': '研发机会探索', 'decision': '路线比较与立项准备'}
READING = {'not_started': '未开始', 'screened': '初筛', 'targeted': '定点补读', 'complete': '完整阅读'}
REVIEW = {'not_reviewed': '未复核', 'self_checked': '原分析者回查', 'independent': '独立复核'}
DATES = {'publication': '专利公开', 'grant': '授权公告', 'product_release': '产品发布', 'source_date': '资料日期', 'unknown': '日期类型未知'}
KINDS = {'conditional_candidate': '条件候选', 'research_priority': '优先研究', 'comparison_baseline': '比较基准', 'performance_comparison': '性能比较'}

def esc(value):
    return html.escape(str(value), quote=True)

def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def fingerprint(data):
    return hashlib.sha256(canonical(data).encode('utf-8')).hexdigest()

def require_text(obj, keys):
    for key in keys:
        if not isinstance(obj.get(key), str) or not obj[key].strip():
            raise ValueError('Missing text: ' + key)

def unique(rows, label):
    if not isinstance(rows, list): raise ValueError(label + ' must be a list')
    found = set()
    for row in rows:
        require_text(row, ['id'])
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', row['id']) or row['id'] in found:
            raise ValueError('Duplicate or invalid ' + label + ' ID')
        found.add(row['id'])
    return found

def references(values, allowed, label):
    if not isinstance(values, list) or len(values) != len(set(values)) or any(x not in allowed for x in values):
        raise ValueError('Unresolved or duplicate ' + label + ' reference')

def legacy_data(data):
    """Only reuse presentation of candidates and sources; do not invent research."""
    result = {k: data[k] for k in ('title', 'cutoff', 'finding', 'boundary', 'directions', 'evidence')}
    result.update(schema_version=1, opportunity=data.get('opportunity', '本次未提出产品机会。'),
                  judgment=data.get('judgment', '研究结论见正文。'))
    for key in ('worklog', 'appendix', 'references', 'decision_boundary'):
        if key in data: result[key] = data[key]
    return result

def validate_v2(data):
    if not isinstance(data, dict) or data.get('schema_version') != 2: raise ValueError('schema_version must be 2')
    require_text(data, ['title', 'cutoff', 'finding', 'boundary', 'data_version'])
    date.fromisoformat(data['cutoff'])
    modes = data.get('modes')
    if not isinstance(modes, list) or not modes or len(modes) != len(set(modes)) or any(x not in MODES for x in modes):
        raise ValueError('Select valid research modes')
    for key in ('records', 'routes', 'directions', 'evidence'):
        if not isinstance(data.get(key), list): raise ValueError(key + ' must be a list')
    record_ids = unique(data['records'], 'record')
    route_ids = unique(data['routes'], 'route')
    evidence_ids = unique(data['evidence'], 'evidence')
    if 'technology' in modes:
        if not data.get('background'): raise ValueError('Technology mode needs product context (known facts or explicit unknowns)')
        require_text(data, ['current_landscape'])
    if 'decision' in modes:
        require_text(data, ['decision_context'])
    for block in data.get('background', []):
        require_text(block, ['title', 'text'])
        references(block.get('evidence', []), evidence_ids, 'background evidence')
    for record in data['records']:
        require_text(record, ['document_id', 'read_scope'])
        if not isinstance(record.get('in_sample'), bool): raise ValueError('Record in_sample must be boolean')
        if record.get('reading') not in READING or record.get('review') not in REVIEW:
            raise ValueError('Invalid reading/review state')
        if record['review'] == 'independent': require_text(record, ['reviewer', 'review_scope'])
    for evidence in data['evidence']:
        references(evidence.get('record_ids', []), record_ids, 'source record')
        for doc in evidence.get('documents', []):
            for location in doc.get('locations', []): require_text(location, ['statement', 'locator'])
    for route in data['routes']:
        require_text(route, ['name', 'task', 'mechanism', 'development', 'limitations'])
        references(route.get('evidence', []), evidence_ids, 'route evidence')
    for direction in data['directions']:
        references(direction.get('route_ids', []), route_ids, 'existing route')
        if direction.get('judgment_kind') not in KINDS: raise ValueError('Specify what the candidate judgment means')
        require_text(direction, ['rationale'])
        if direction['judgment_kind'] == 'performance_comparison':
            require_text(direction, ['comparison_conditions'])
            if not direction.get('comparison_evidence'): raise ValueError('Performance comparison needs cited comparative evidence')
            references(direction['comparison_evidence'], evidence_ids, 'performance evidence')
    previous = ''
    for node in data.get('timeline', []):
        require_text(node, ['title', 'change', 'document_id'])
        if node.get('date_type') not in DATES: raise ValueError('Timeline date_type is required')
        if node.get('date') is not None:
            date.fromisoformat(node['date'])
            if node['date'] < previous: raise ValueError('Known events must be sorted by event date')
            previous = node['date']
        if not node.get('evidence'): raise ValueError('Timeline event needs evidence')
        references(node['evidence'], evidence_ids, 'timeline evidence')
        sources = [e for e in data['evidence'] if e['id'] in node['evidence']]
        linked_ids = {rid for e in sources for rid in e.get('record_ids', [])}
        documents = {doc['number'] for e in sources for doc in e.get('documents', [])}
        documents.update(r['document_id'] for r in data['records'] if r['id'] in linked_ids)
        if node['document_id'] not in documents:
            raise ValueError('Timeline document does not match its evidence')
        if node.get('earliest_verified_disclosure'):
            if node['date_type'] != 'publication' or not node.get('date'):
                raise ValueError('Earliest verified disclosure needs a known publication event')
            require_text(node, ['disclosure_locator', 'search_scope'])
    if data.get('plan'):
        if 'decision' not in modes and data.get('plan_requested') is not True:
            raise ValueError('A work plan requires decision mode or an explicit plan request')
        for block in data['plan']: require_text(block, ['title', 'text'])
    # Preserve existing source URL, evidence ID, candidate and image checks.
    from render_report import validate_legacy
    validate_legacy(legacy_data(data))

def coverage(data):
    records = data['records']
    sample = [r for r in records if r['in_sample']]
    linked = {x for e in data['evidence'] for x in e.get('record_ids', [])}
    return {'sample_records': len(sample), 'supplement_records': len(records)-len(sample),
            'detailed_cards': len(data['evidence']), 'records_linked_to_cards': len(linked),
            'sample_reading': {k: sum(r['reading'] == k for r in sample) for k in READING},
            'sample_review': {k: sum(r['review'] == k for r in sample) for k in REVIEW}}

def chips(ids):
    return ''.join(f'<a class="e-link" href="#e-{esc(x)}">{esc(x)} 证据</a>' for x in ids)

def section(key, title, body, note=''):
    return f'<section id="{key}"><div class="section-head"><h2>{esc(title)}</h2><p>{esc(note)}</p></div>{body}</section>'

def render_v2(data, legacy_renderer):
    validate_v2(data)
    base = legacy_renderer(legacy_data(data))
    inherited = {m[1]: m[0] for m in re.findall(r'(<section id="([^"]+)".*?</section>)', base, re.S)}
    parts = {}
    if data.get('decision_context'):
        parts['decision'] = section('decision', '比较目标与约束', '<p>'+esc(data['decision_context'])+'</p>')
    if data.get('background'):
        parts['background'] = section('background', '产品怎样工作，为什么需要这些技术', ''.join(
            f'<article class="route"><h3>{esc(b["title"])}</h3><p>{esc(b["text"])}</p>{chips(b.get("evidence",[]))}</article>' for b in data['background']))
    if data.get('timeline'):
        parts['timeline'] = section('timeline', '技术与资料的时间记录', '<ol class="timeline">'+''.join(
            f'<li><time>{esc(n.get("date") or "日期未知")}</time> · {DATES[n["date_type"]]}<h3>{esc(n["title"])}</h3><p>{esc(n["change"])}</p><p>{esc(n["document_id"])}</p>'
            +(f'<p>本次检索范围内较早披露：{esc(n["search_scope"])}；{esc(n["disclosure_locator"])}</p>' if n.get('earliest_verified_disclosure') else '')
            +chips(n['evidence'])+'</li>' for n in data['timeline'])+'</ol>', '事件日期分别标注；先后不自动表示继承、替代或行业首次。')
    if data.get('routes') or data.get('current_landscape'):
        body = f'<p>{esc(data.get("current_landscape", "现有实现按任务分别说明。"))}</p>'
        for r in data['routes']:
            body += f'<article class="route" id="route-{esc(r["id"])}"><h3>{esc(r["id"])} {esc(r["name"])}</h3>'
            for key, label in [('task','解决的问题'),('mechanism','结构与工作过程'),('development','变化及其原因'),('limitations','现有条件与限制')]:
                body += f'<p><strong>{label}：</strong>{esc(r[key])}</p>'
            body += chips(r.get('evidence',[]))+'</article>'
        parts['existing'] = section('existing','现有技术路线与发展',body)
    if data['directions']:
        parts['compare'] = inherited['compare']
        body = inherited['routes'].replace('结构差异怎样形成产品机会','后续研发方向及推导依据')
        for d in data['directions']:
            target = f'<h3>{d["id"]} {esc(d["name"])}</h3>'
            related = ' · '.join(f'<a href="#route-{esc(r)}">{esc(r)} 现有路线</a>' for r in d.get('route_ids', []))
            body = body.replace(target,target+f'<p class="key">{KINDS[d["judgment_kind"]]}：{esc(d["rationale"])}</p><p>{related}</p>')
            if d.get('comparison_conditions'):
                body = body.replace(target,target+'<p>比较条件：'+esc(d['comparison_conditions'])+'</p>'+chips(d.get('comparison_evidence',[])))
        if 'decision' not in data['modes']:
            body = re.sub(r'<span>决策阶段：.*?</span>', '', body)
        parts['routes'] = body
    # Explicit source statements support several locations in one document.
    evidence = inherited['evidence'].replace('逐条看了哪些证据','详细证据卡与原文定位').replace('个条目','张详细证据卡')
    for e in data['evidence']:
        locations = ''.join(f'<p><strong>{esc(doc["number"])}：</strong>{esc(loc["statement"])} · {esc(loc["locator"])}</p>'
                            for doc in e.get('documents',[]) for loc in doc.get('locations',[]))
        target = f'<p><strong>原文位置：</strong>{esc(e["location"])}</p>'
        pattern = r'(<details class="evidence-item" id="e-'+re.escape(e['id'])+r'".*?</details>)'
        evidence = re.sub(pattern,lambda m:m[1].replace(target,target+locations),evidence,flags=re.S)
    parts['evidence'] = evidence
    if data.get('plan'):
        parts['plan'] = section('plan','按任务需要展开的验证安排',''.join(f'<h3>{esc(b["title"])}</h3><p>{esc(b["text"])}</p>' for b in data['plan']))
    parts['catalog'] = section('catalog','逐件阅读与复核记录',catalog_table(data), '阅读、复核和证据卡关联分别记录；完整阅读以逐件注明的阅读范围为准。')
    parts['next'] = inherited['next']
    order = (['background','timeline','existing','decision','compare','routes'] if 'technology' in data['modes'] else
             ['decision','compare','existing','routes','background','timeline']) + ['evidence','catalog','plan','next']
    names = {'summary':'研究结论','decision':'目标与约束','background':'产品与问题','timeline':'时间记录','existing':'现有路线','compare':'方向比较','routes':'后续方向','evidence':'详细证据','catalog':'逐件记录','plan':'验证安排','next':'依据与边界'}
    nav = ''.join(f'<a href="#{key}">{names[key]}</a>' for key in ['summary']+order if key=='summary' or key in parts)
    counts = coverage(data)
    identity = fingerprint(data)
    summary = f'<header class="top"><div class="wrap"><span class="brand">研发罗盘</span><nav aria-label="报告目录">{nav}</nav></div></header><main class="wrap"><div id="summary"><p class="meta">'+ ' · '.join(MODES[m] for m in data['modes'])+f' · 资料截至 {esc(data["cutoff"])}</p><h1>{esc(data["title"])}</h1><div class="executive">'
    for key,label in [('finding','研究发现'),('opportunity','产品机会'),('judgment','条件判断')]:
        if data.get(key): summary += f'<p><strong>{label}：</strong>{esc(data[key])}</p>'
    summary += f'</div><p class="boundary">{esc(data["boundary"])}</p><p class="scope">主样本记录 {counts["sample_records"]} 条；补充记录 {counts["supplement_records"]} 条；详细证据卡 {counts["detailed_cards"]} 张。卡片与文献记录为关联关系，不代表相同阅读数量。</p><div class="toolbar"><a class="btn" id="data-download" download="research-data.json">下载研究数据</a><button class="btn" id="print">打印完整报告</button><a class="btn" href="#catalog">完整逐件记录</a></div></div>'
    body = summary + ''.join(parts[key] for key in order if key in parts) + f'<footer>研发罗盘 · {esc(data["data_version"])}<span hidden data-fingerprint="{identity}"></span></footer></main>'
    base = re.sub(r'<header class="top">.*?</main>', lambda _: body, base, count=1, flags=re.S)
    payload = canonical(data).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    return re.sub(r'(<script id="report-data" type="application/json">).*?(</script>)',lambda m:m[1]+payload+m[2],base,flags=re.S)

def catalog_rows(data):
    for r in data['records']:
        cards = [e['id'] for e in data['evidence'] if r['id'] in e.get('record_ids',[])]
        yield [r['id'],r['document_id'],'主样本' if r['in_sample'] else '补充',READING[r['reading']],r['read_scope'],REVIEW[r['review']],', '.join(cards),data['data_version']]

HEADERS = ['记录ID','文献及版本','来源范围','阅读状态','实际阅读范围','复核状态','关联证据卡','数据版本']

def catalog_table(data):
    return '<div class="table-wrap generic"><table><thead><tr>'+''.join('<th>'+x+'</th>' for x in HEADERS)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td data-label="{h}">{esc(v)}</td>' for h,v in zip(HEADERS,row))+'</tr>' for row in catalog_rows(data))+'</tbody></table></div>'

def write_bundle(data, folder, renderer):
    validate_v2(data)
    rendered = renderer(data)
    identity = fingerprint(data)
    stream = io.StringIO(newline='')
    writer = csv.writer(stream); writer.writerow(HEADERS); writer.writerows(catalog_rows(data))
    catalog = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>逐件阅读记录</title><style>body{font:16px/1.8 system-ui;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #bbc;padding:10px;vertical-align:top}.table-wrap{overflow:auto}</style><h1>逐件阅读记录</h1><p>'+esc(data['data_version'])+'</p><a href="report.html#catalog">返回研究报告</a>'+catalog_table(data)+f'<p hidden>{identity}</p></html>'
    files = {'report.html': rendered.encode('utf-8'), 'catalog.html': catalog.encode('utf-8'),
             'reading.csv': ('\ufeff'+stream.getvalue()).encode('utf-8'), 'research-data.json': canonical(data).encode('utf-8')}
    manifest = {'data_version':data['data_version'],'data_fingerprint':identity,'coverage':coverage(data),
                'files':{name:hashlib.sha256(content).hexdigest() for name,content in files.items()}}
    files['manifest.json'] = json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    # All content is prepared before mutation. Manifest is committed last; a crash
    # between files is detectable by check_bundle, not falsely called atomic.
    with tempfile.TemporaryDirectory(dir=folder) as staging:
        for name,content in files.items(): (Path(staging)/name).write_bytes(content)
        for name in files: os.replace(Path(staging)/name,folder/name)
    check_bundle(folder)

def check_bundle(folder):
    folder=Path(folder)
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    expected={'report.html','catalog.html','reading.csv','research-data.json'}
    if set(manifest['files']) != expected: raise ValueError('Unexpected artifact set')
    for name,digest in manifest['files'].items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest: raise ValueError('Stale or changed artifact: '+name)
    data=json.loads((folder/'research-data.json').read_text(encoding='utf-8'))
    validate_v2(data)
    if fingerprint(data)!=manifest['data_fingerprint'] or coverage(data)!=manifest['coverage'] or data['data_version']!=manifest['data_version']:
        raise ValueError('Manifest and research data differ')
