"""Purpose-aware reports, structured recommendations and a single-source catalog.

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
from evidence_ids import evidence_anchor
import reader_contract

MODES = {'technology': '技术理解与演进', 'opportunity': '研发机会探索', 'decision': '路线比较与立项准备'}
READING = {'not_started': '未开始', 'screened': '初筛', 'targeted': '定点补读', 'complete': '完整阅读'}
REVIEW = {'not_reviewed': '未复核', 'self_checked': '原分析者回查', 'independent': '独立复核'}
DATES = {'publication': '专利公开', 'grant': '授权公告', 'product_release': '产品发布', 'source_date': '资料日期', 'unknown': '日期类型未知'}
KINDS = {'conditional_candidate': '条件候选', 'research_priority': '优先研究', 'comparison_baseline': '比较基准', 'performance_comparison': '性能比较'}
COMPARATOR_BASES = {'disclosure': '原文披露', 'engineering_baseline': '工程对照设定'}

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
        if row['id'] in found or (label != 'evidence' and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', row['id'])):
            raise ValueError('Duplicate or invalid ' + label + ' ID')
        if label == 'evidence': evidence_anchor(row['id'])
        found.add(row['id'])
    return found

def references(values, allowed, label):
    if (not isinstance(values, list) or any(not isinstance(x, str) or x not in allowed for x in values)
            or len(values) != len(set(values))):
        raise ValueError('Unresolved or duplicate ' + label + ' reference')

def legacy_data(data):
    """Only reuse presentation of candidates and sources; do not invent research."""
    result = {k: data[k] for k in ('title', 'cutoff', 'finding', 'boundary', 'directions', 'evidence')}
    result.update(schema_version=1, opportunity=data.get('opportunity', '本次未提出产品机会。'),
                  judgment=data.get('judgment', '研究结论见正文。'))
    for key in ('worklog', 'appendix', 'references', 'decision_boundary'):
        if key in data: result[key] = data[key]
    return result

def validate_recommendations(data):
    if data['schema_version'] in (3, 4):
        if any(key in data for key in ('opportunity', 'judgment')):
            raise ValueError('Use structured recommendations instead of a free-text summary')
        if {'opportunity', 'decision'}.intersection(data['modes']) and 'recommendations' not in data:
            raise ValueError('Provide recommendations, or an explicit empty list if none are supported')
    if 'recommendations' not in data:
        return
    recommendations = data['recommendations']
    if not isinstance(recommendations, list) or any(not isinstance(row, dict) for row in recommendations):
        raise ValueError('recommendations must be a list of objects')
    directions = {row['id']: row for row in data['directions']}
    routes = {row['id']: row for row in data['routes']}
    located = {row['id'] for row in data['evidence']
               if any(isinstance(doc.get('number'), str) and doc['number'].strip()
                      for doc in row.get('documents', []))}
    seen = set()
    for row in recommendations:
        require_text(row, ['direction_id', 'conditions', 'check'])
        direction_id = row['direction_id']
        if direction_id not in directions or (data['schema_version'] != 4 and direction_id in seen):
            raise ValueError('Recommendation direction is unresolved or duplicate: ' + direction_id)
        seen.add(direction_id)
        if not row.get('evidence'):
            raise ValueError('Recommendation needs located original evidence: ' + direction_id)
        references(row['evidence'], located, 'recommendation original evidence')
        direction = directions[direction_id]
        # Step 1 is the direction's disclosed mechanism. Other steps may cite a
        # comparator, whose evidence can also appear in the direction filter.
        supporting = set(direction['reasoning'][0].get('evidence', []))
        for route_id in direction.get('route_ids', []):
            supporting.update(routes[route_id].get('evidence', []))
        references(row['evidence'], supporting, 'recommendation direction evidence')
        if data['schema_version'] == 4 and row.get('action_kind') in ('capability_reserve', 'watch'):
            require_text(row, ['alternative', 'review_trigger'])
            continue
        comparator = row.get('comparator')
        if not isinstance(comparator, dict):
            raise ValueError('Recommendation needs a comparator: ' + direction_id)
        require_text(comparator, ['name', 'mechanism', 'basis_type'])
        if comparator['basis_type'] not in COMPARATOR_BASES:
            raise ValueError('Unknown recommendation comparator basis type')
        if comparator['basis_type'] == 'disclosure' and not comparator.get('evidence'):
            raise ValueError('Disclosed comparator needs located original evidence: ' + direction_id)
        references(comparator.get('evidence', []), located, 'comparator original evidence')
        elimination = row.get('elimination')
        if not isinstance(elimination, dict):
            raise ValueError('Recommendation needs an elimination rule: ' + direction_id)
        require_text(elimination, ['trigger', 'action'])

def validate_reader_generation(data, evidence_ids):
    """Check that promised explanations are present before rendering."""
    require_text(data, ['beginner_context'])
    reviewed = date.fromisoformat(data['reader_contract']['as_of'])
    cutoff = date.fromisoformat(data['cutoff'])
    if reviewed < cutoff:
        raise ValueError('Analysis record date cannot precede the material cutoff')
    if reviewed != cutoff:
        require_text(data, ['cutoff_scope'])

    recommendations = {row['direction_id'] for row in data.get('recommendations', [])}
    for direction in data['directions']:
        kind = direction.get('mechanism_kind')
        if direction['id'] not in recommendations and kind is None:
            continue
        if data['schema_version'] == 4 and kind in ('material', 'algorithm', 'process', 'system'):
            require_text(direction, ['input', 'process', 'output', 'application_conditions'])
            if not any(p.get('evidence') for p in direction.get('narrative', [])):
                raise ValueError('Non-mechanical explanation needs a sourced narrative')
            if not direction.get('has_moving_part'):
                continue
            kind = 'moving'
        if kind not in ('moving', 'static'):
            raise ValueError(f'{direction["id"]}: identify moving or static mechanism')
        narrative = direction.get('narrative', [])
        if kind == 'static':
            if not any(block.get('evidence') for block in narrative):
                raise ValueError(f'{direction["id"]}: a static mechanism needs a sourced explanation')
            continue

        stages = []
        for block in narrative:
            if 'stages' not in block:
                continue
            marked = block['stages']
            if not isinstance(marked, list) or not marked or not block.get('evidence'):
                raise ValueError(f'{direction["id"]}: each action block needs stages and evidence')
            references(block['evidence'], evidence_ids, 'action evidence')
            stages.extend(marked)
        if stages != ['initial', 'trigger', 'motion', 'result', 'reset']:
            raise ValueError(f'{direction["id"]}: explain initial state, trigger, motion, result and reset in order; state any gap in its block')


def validate_v2(data):
    if not isinstance(data, dict) or data.get('schema_version') not in (2, 3, 4):
        raise ValueError('schema_version must be 2, 3 or 4')
    future = data['schema_version'] == 4
    if future and (data.get('report_contract_version') != 3 or not isinstance(data.get('foresight'),dict)):
        raise ValueError('Schema 4 requires report_contract_version 3 and a foresight record')
    if not future and ('foresight' in data or data.get('report_contract_version') == 3 or any('action_kind' in r or 'horizon_ids' in r for r in data.get('recommendations',[]) if isinstance(r,dict))):
        raise ValueError('Future-report fields require explicit migration to schema 4')
    require_text(data, ['title', 'cutoff', 'finding', 'boundary', 'data_version'])
    date.fromisoformat(data['cutoff'])
    modes = data.get('modes')
    allowed_modes = set(MODES) | ({'foresight'} if future else set())
    if not isinstance(modes, list) or not modes or len(modes) != len(set(modes)) or any(x not in allowed_modes for x in modes):
        raise ValueError('Select valid research modes')
    for key in ('records', 'routes', 'directions', 'evidence'):
        if not isinstance(data.get(key), list): raise ValueError(key + ' must be a list')
    record_ids = unique(data['records'], 'record')
    route_ids = unique(data['routes'], 'route')
    evidence_ids = unique(data['evidence'], 'evidence')
    if data.get('report_contract_version') in (1, 2, 3) and 'reader_contract' not in data:
        raise ValueError('New report contract requires reader_contract')
    if 'reader_contract' in data:
        reader_contract.validate(data['reader_contract'], evidence_ids)
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
        if 'narrative' in direction:
            reader_contract.validate_blocks(direction['narrative'])
            if (not isinstance(direction['narrative'], list) or not direction['narrative']
                    or any(not isinstance(p, dict) for p in direction['narrative'])):
                raise ValueError('A reader narrative needs substantive paragraphs')
            for paragraph in direction['narrative']:
                require_text(paragraph, ['text'])
                references(paragraph.get('evidence', []), evidence_ids, 'narrative evidence')
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
        references(node.get('route_ids', []), route_ids, 'timeline route')
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
    validate_recommendations(data)
    if data.get('report_contract_version') in (2, 3):
        validate_reader_generation(data, evidence_ids)
    from method_support import validate_support
    validate_support(data)
    if future:
        from foresight_report import validate_foresight
        validate_foresight(data)

def coverage(data):
    records = data['records']
    sample = [r for r in records if r['in_sample']]
    linked = {x for e in data['evidence'] for x in e.get('record_ids', [])}
    return {'sample_records': len(sample), 'supplement_records': len(records)-len(sample),
            'detailed_cards': len(data['evidence']), 'records_linked_to_cards': len(linked),
            'sample_reading': {k: sum(r['reading'] == k for r in sample) for k in READING},
            'sample_review': {k: sum(r['review'] == k for r in sample) for k in REVIEW}}

def chips(ids):
    return ''.join(f'<a class="e-link" href="#e-{evidence_anchor(x)}">{esc(x)} 证据</a>' for x in ids)

def section(key, title, body, note=''):
    return f'<section id="{key}"><div class="section-head"><h2>{esc(title)}</h2><p>{esc(note)}</p></div>{body}</section>'

def section_content(markup):
    match = re.fullmatch(r'<section id="[^"]+"><div class="section-head">.*?</div>(.*)</section>', markup, re.S)
    if not match: raise ValueError('Cannot preserve inherited report section')
    return match[1]

def recommendation_detail(row):
    comparator = row['comparator']
    elimination = row['elimination']
    return (
        '<div class="conditions recommendation-detail"><h4>原文依据与同工况比较</h4>'
        '<dl><dt>本方向的原文依据</dt><dd>' + chips(row['evidence']) + '</dd>'
        '<dt>双方共同工况</dt><dd>' + esc(row['conditions']) + '</dd>'
        '<dt>对照方案 · ' + esc(COMPARATOR_BASES[comparator['basis_type']]) + '</dt><dd>'
        + esc(comparator['name']) + '。' + esc(comparator['mechanism'])
        + chips(comparator.get('evidence', [])) + '</dd>'
        '<dt>比较时观察什么</dt><dd>' + esc(row['check']) + '</dd>'
        '<dt>淘汰条件</dt><dd>' + esc(elimination['trigger']) + '</dd>'
        '<dt>触发后怎么做</dt><dd>' + esc(elimination['action']) + '</dd></dl></div>'
    )

def reader_directions(data):
    from method_support import disclosure, method_badge
    body = method_badge('ifm', data) if data.get('method_support', {}).get('opportunities') else ''
    route_names = {r['id']: r['name'] for r in data['routes']}
    recommendations = {row['direction_id']: row for row in data.get('recommendations', [])}
    for d in data['directions']:
        body += f'<article class="direction-story" id="r-{esc(d["id"])}"><h3>{esc(d["name"])}</h3><p class="judgment">{esc(d["judgment"])}</p>'
        if d.get('figure'):
            body += '<figure class="story-figure"><div class="figure-scroll" tabindex="0" role="region" aria-label="结构图，可横向滚动查看"><img src="' + esc(d['figure']) + '" alt="' + esc(d['caption']) + '"></div><figcaption>' + esc(d['caption']) + '</figcaption></figure>'
        reasoning = ''
        for step in d['reasoning']:
            reasoning += '<div class="reasoning-paragraph"><h4>' + esc(step['title']) + '</h4><p>' + esc(step['text']) + '</p>' + chips(step.get('evidence', [])) + '</div>'
        reasoning += '<p class="key">' + KINDS[d['judgment_kind']] + '：' + esc(d['rationale']) + '</p>'
        reasoning += '<p class="key">证据状态：' + esc(d['evidence_state']) + '</p>'
        if 'decision' in data['modes']: reasoning += '<p class="key">决策阶段：' + esc(d['decision_state']) + '</p>'
        reasoning += '<dl class="story-conditions">' + ''.join('<dt>' + esc(c['if']) + '</dt><dd>' + esc(c['then']) + '</dd>' for c in d['conditions']) + '</dl>'
        if d.get('comparison_conditions'):
            reasoning += '<p>比较条件：' + esc(d['comparison_conditions']) + '</p>' + chips(d.get('comparison_evidence', []))
        related = ' · '.join('<a href="#route-' + esc(r) + '">' + esc(route_names[r]) + '</a>' for r in d.get('route_ids', []))
        if related: reasoning += '<p>结构依据：' + related + '</p>'
        if d.get('narrative'):
            for paragraph in d['narrative']:
                body += reader_contract.blocks_html([paragraph]) + chips(paragraph.get('evidence', []))
            if d['id'] in recommendations:
                body += recommendation_detail(recommendations[d['id']])
            body += disclosure('direction-detail-' + esc(d['id']), '推导依据与适用条件', reasoning)
        else:
            # Old data has no separately reviewed narrative: retain its full argument.
            body += reasoning
            if d['id'] in recommendations:
                body += recommendation_detail(recommendations[d['id']])
        body += '</article>'
    return body

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
        parts['timeline'] = section('timeline', '技术时间图', '<ol class="timeline">'+''.join(
            f'<li><time>{esc(n.get("date") or "日期未知")}</time> · {DATES[n["date_type"]]}<h3>{esc(n["title"])}</h3><p>{esc(n["change"])}</p><p>{esc(n["document_id"])}</p>'
            +(f'<p>本次检索范围内较早披露：{esc(n["search_scope"])}；{esc(n["disclosure_locator"])}</p>' if n.get('earliest_verified_disclosure') else '')
            + ''.join(f'<a class="route-link" href="#route-{esc(route_id)}">查看 {esc(route_id)} 路线</a>'
                      for route_id in n.get('route_ids', []))
            + chips(n['evidence']) + '</li>' for n in data['timeline']) + '</ol>',
            '日期对应所列文献事件。时间先后不表示技术继承、替代、上市或首次披露。')
    if data.get('routes') or data.get('current_landscape'):
        body = f'<p>{esc(data.get("current_landscape", "现有实现按任务分别说明。"))}</p>'
        for r in data['routes']:
            body += f'<article class="route" id="route-{esc(r["id"])}"><h3>{esc(r["id"])} {esc(r["name"])}</h3>'
            for key, label in [('task','解决的问题'),('mechanism','结构与工作过程'),('development','变化及其原因'),('limitations','现有条件与限制')]:
                body += f'<p><strong>{label}：</strong>{esc(r[key])}</p>'
            body += chips(r.get('evidence',[]))+'</article>'
        parts['existing'] = section('existing','现有技术路线与发展',body)
    from method_support import render_support, disclosure
    support = render_support(data)
    if data['directions']:
        parts['routes'] = section('routes', '哪些改变值得研究', reader_directions(data) + support.get('opportunities', ''))
        comparison = support.get('comparison', section_content(inherited['compare']))
        parts['compare'] = section('compare', '条件比较与当前建议', comparison + support.get('remaining', ''))
    elif support.get('remaining'):
        parts['compare'] = section('compare', '当前判断与关键条件', support['remaining'])
    # Explicit source statements support several locations in one document.
    evidence = inherited['evidence'].replace('逐条看了哪些证据','详细证据卡与原文定位').replace('个条目','张详细证据卡')
    for e in data['evidence']:
        locations = ''.join(f'<p><strong>{esc(doc["number"])}：</strong>{esc(loc["statement"])} · {esc(loc["locator"])}</p>'
                            for doc in e.get('documents',[]) for loc in doc.get('locations',[]))
        target = f'<p><strong>原文位置：</strong>{esc(e["location"])}</p>'
        pattern = r'(<details class="evidence-item" id="e-'+re.escape(evidence_anchor(e['id']))+r'".*?</details>)'
        evidence = re.sub(pattern,lambda m:m[1].replace(target,target+locations),evidence,flags=re.S)
    parts['evidence'] = evidence
    if data.get('plan'):
        parts['plan'] = section('plan','按任务需要展开的验证安排',''.join(f'<h3>{esc(b["title"])}</h3><p>{esc(b["text"])}</p>' for b in data['plan']))
    counts = coverage(data)
    source_body = '<p class="key">主样本记录 ' + str(counts['sample_records']) + ' 条；补充记录 ' + str(counts['supplement_records']) + ' 条；详细证据卡 ' + str(counts['detailed_cards']) + ' 张。记录、实际阅读与复核分别注明。</p>'
    source_body += disclosure('evidence', '专利证据与原文定位', section_content(parts.pop('evidence')))
    source_body += disclosure('catalog', '逐件阅读与复核记录', catalog_table(data))
    source_body += support.get('research-log', '') + support.get('method-use', '')
    source_body += disclosure('next', '研究范围与补充说明', section_content(inherited['next']))
    parts['sources'] = section('sources', '证据与研究记录', source_body)
    order = (['decision'] if 'decision' in parts else []) + ['background','timeline','existing','routes','compare','plan','sources']
    names = {'summary':'研究结论','decision':'目标与约束','background':'产品与问题','timeline':'技术时间图','existing':'现有路线','routes':'研发机会','compare':'条件与建议','plan':'验证安排','sources':'依据与记录'}
    nav = ''.join(f'<a href="#{key}">{names[key]}</a>' for key in ['summary']+order if key=='summary' or key in parts)
    counts = coverage(data)
    identity = fingerprint(data)
    guided = data.get('report_contract_version') == 2
    date_label = '基础资料记录截至' if guided else '资料截至'
    summary = f'<header class="top"><div class="wrap"><span class="brand">研发罗盘</span><nav aria-label="报告目录">{nav}</nav></div></header><main class="wrap"><div id="summary"><p class="meta">'+ ' · '.join(MODES[m] for m in data['modes'])+f' · {date_label} {esc(data["cutoff"])}</p><h1>{esc(data["title"])}</h1><div class="executive">'
    if guided:
        summary += f'<p class="beginner-context">{esc(data["beginner_context"])}</p>'
    summary += f'<p><strong>研究发现：</strong>{esc(data["finding"])}</p>'
    if data.get('recommendations'):
        directions = {row['id']: row for row in data['directions']}
        summary += '<h2>研发建议</h2><ul class="summary-recommendations">'
        for row in data['recommendations']:
            direction = directions[row['direction_id']]
            summary += (f'<li><a href="#r-{esc(direction["id"])}">{esc(direction["name"])}</a>'
                        f'<p>{esc(direction["judgment"])}</p></li>')
        summary += '</ul>'
    elif 'recommendations' in data:
        summary += '<p class="key">现有依据尚不足以提出首屏建议。</p>'
    elif data['schema_version'] == 2:
        for key, label in [('opportunity', '历史产品机会'), ('judgment', '历史条件判断')]:
            if data.get(key): summary += f'<p><strong>{label}：</strong>{esc(data[key])}</p>'
    summary += f'</div><p class="boundary">{esc(data["boundary"])}</p><div class="toolbar"><a class="btn" id="data-download" download="research-data.json">下载研究数据</a><button class="btn" id="print">打印完整报告</button><a class="btn" href="#sources">查看依据与记录</a></div></div>'
    review = data.get('method_support', {}).get('research_check', {})
    if review.get('status') == 'in_progress':
        summary += '<p class="draft-notice">研究仍在进行，尚未通过本轮交付前回查。</p>'
    contract = data.get('reader_contract')
    if contract:
        link = lambda eid: '<a class="e-link" href="#e-' + evidence_anchor(eid) + '">原文 ' + esc(eid) + '</a>'
        summary += reader_contract.render(contract, evidence_link=link)
        parts['answers'] = reader_contract.render(
            contract, 'answers', link,
            date_label='分析记录日期' if guided else '判断资料截止',
            date_scope=data.get('cutoff_scope', '') if guided else '',
        )
        order.insert(order.index('sources'), 'answers')
    body = summary + ''.join(parts[key] for key in order if key in parts) + f'<footer>研发罗盘 · {esc(data["data_version"])}<span hidden data-fingerprint="{identity}"></span></footer></main>'
    base = re.sub(r'<header class="top">.*?</main>', lambda _: body, base, count=1, flags=re.S)
    if contract:
        base = base.replace('</head>', '<style>' + reader_contract.STYLE + '</style></head>')
        base = base.replace('</body>', '<script>' + reader_contract.SCRIPT + '</script></body>')
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
