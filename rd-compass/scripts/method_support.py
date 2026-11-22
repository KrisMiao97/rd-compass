"""Optional, evidence-linked research views. Never calculate scores or decisions.

This validates coverage and references, not the truth of the author's analysis.
Old schema-2 reports remain valid without method_support.
"""
from research_model import esc, chips, section, require_text, unique, references

METHODS = {'ifm': 'IfM 技术路线图思路', 'rand': 'RAND 稳健决策思路',
           'nasa': 'NASA 决策分析思路', 'morphology': '功能分解与形态分析',
           'jtbd': 'JTBD 使用任务', 'triz': 'TRIZ 技术矛盾', 'doe': 'DOE 试验设计'}
METHOD_URLS = {
    'ifm': 'https://engage.ifm.eng.cam.ac.uk/technology-roadmapping/',
    'rand': 'https://www.rand.org/pubs/tools/TL320/tool/robust-decision-making.html',
    'nasa': 'https://www.nasa.gov/reference/6-8-decision-analysis/',
    'morphology': 'https://www.ifm.eng.cam.ac.uk/research/dmg/tools-and-techniques/morphological-charts/',
    'jtbd': 'https://www.christenseninstitute.org/resources/theory/jobs-to-be-done/',
    'triz': 'https://www.wipo.int/export/sites/www/tisc/en/docs/tisc-toolkit-triz-description.pdf',
    'doe': 'https://www.itl.nist.gov/div898/handbook/pri/section3/pri33.htm'}
STATES = {'meets': '支持满足', 'fails': '支持不满足', 'unknown': '尚不能判断'}
BASES = {'measurement': '实测', 'model': '模型', 'inference': '工程推断',
         'disclosure': '原文披露', 'unknown': '证据不足'}


def rows(obj, key):
    value = obj.get(key, [])
    if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
        raise ValueError(key + ' must be a list of objects')
    return value


def links(obj, key, allowed, required=False):
    values = obj.get(key, [])
    if required and not values:
        raise ValueError('Missing ' + key)
    if not isinstance(values, list) or any(not isinstance(x, str) for x in values):
        raise ValueError('Invalid ' + key)
    references(values, allowed, key)


def validate_support(data):
    if 'method_support' not in data:
        return
    support = data['method_support']
    if not isinstance(support, dict) or support.get('version') != 1:
        raise ValueError('method_support.version must be 1')
    evidence = {e['id'] for e in data['evidence']}
    directions = {d['id'] for d in data['directions']}
    routes = {r['id'] for r in data['routes']}
    opportunities = rows(support, 'opportunities')
    opportunity_ids = unique(opportunities, 'opportunity')
    for item in opportunities:
        require_text(item, ['name', 'need', 'capability', 'mechanism', 'prerequisites', 'next_condition'])
        if item.get('need_state') not in ('hypothesis', 'stated_goal', 'observed'):
            raise ValueError('Specify opportunity need_state')
        links(item, 'direction_ids', directions, True)
        links(item, 'route_ids', routes)
        links(item, 'evidence', evidence)
        links(item, 'need_evidence', evidence, item['need_state'] == 'observed')
        if item['need_state'] == 'stated_goal': require_text(item, ['goal_source'])

    comparison = support.get('comparison')
    scenario_ids, criterion_ids = set(), set()
    if comparison is not None:
        if not isinstance(comparison, dict): raise ValueError('comparison must be an object')
        require_text(comparison, ['scope', 'baseline', 'depth'])
        links(comparison, 'direction_ids', directions, True)
        criteria = rows(comparison, 'criteria')
        scenarios = rows(comparison, 'scenarios')
        uncertainties = rows(comparison, 'uncertainties')
        criterion_ids = unique(criteria, 'criterion')
        scenario_ids = unique(scenarios, 'scenario')
        uncertainty_ids = unique(uncertainties, 'uncertainty')
        if not criteria or not scenarios: raise ValueError('Comparison needs criteria and scenarios')
        for finding in rows(comparison, 'shared_findings'):
            require_text(finding, ['text'])
            links(finding, 'evidence', evidence)
        for c in criteria:
            require_text(c, ['name', 'requirement', 'basis'])
            if c.get('kind') not in ('mandatory', 'preference'): raise ValueError('Invalid criterion kind')
            links(c, 'evidence', evidence)
        for u in uncertainties:
            require_text(u, ['name', 'range', 'basis'])
            links(u, 'evidence', evidence)
        for s in scenarios:
            require_text(s, ['name', 'conditions', 'why_plausible', 'judgment'])
            links(s, 'uncertainty_ids', uncertainty_ids)
        expected = {(d, s, c) for d in comparison['direction_ids'] for s in scenario_ids for c in criterion_ids}
        found = set()
        for cell in rows(comparison, 'cells'):
            require_text(cell, ['direction_id', 'scenario_id', 'criterion_id', 'reason'])
            key = (cell['direction_id'], cell['scenario_id'], cell['criterion_id'])
            if key not in expected or key in found: raise ValueError('Duplicate or unresolved comparison cell')
            found.add(key)
            if cell.get('status') not in STATES or cell.get('basis_type') not in BASES:
                raise ValueError('Invalid comparison judgment')
            links(cell, 'evidence', evidence, cell['basis_type'] in ('measurement', 'model', 'disclosure'))
            if cell['basis_type'] == 'unknown' and cell['status'] != 'unknown':
                raise ValueError('Unknown basis cannot assert a result')
        if found != expected: raise ValueError('Every candidate/scenario/criterion needs a cell; use unknown explicitly')
        for item in rows(comparison, 'vulnerabilities'):
            require_text(item, ['conditions', 'reason', 'adaptation', 'switch_signal'])
            links(item, 'direction_ids', set(comparison['direction_ids']), True)
            links(item, 'scenario_ids', scenario_ids, True)
            links(item, 'evidence', evidence)

    actions = rows(support, 'evidence_actions')
    unique(actions, 'evidence action')
    for action in actions:
        require_text(action, ['question', 'decision', 'known', 'approach', 'priority_reason', 'resources', 'timing', 'stop_rule', 'inconclusive'])
        if action.get('kind') not in ('document', 'records', 'interview', 'measurement', 'model', 'test'):
            raise ValueError('Invalid evidence action kind')
        if action['kind'] in ('measurement', 'model', 'test') and 'decision' not in data['modes'] and data.get('plan_requested') is not True:
            raise ValueError('A validation action requires decision mode or explicit plan request')
        links(action, 'direction_ids', directions, True)
        links(action, 'opportunity_ids', opportunity_ids)
        links(action, 'scenario_ids', scenario_ids)
        links(action, 'criterion_ids', criterion_ids)
        links(action, 'evidence', evidence)
        outcomes = rows(action, 'outcomes')
        unique(outcomes, 'outcome')
        if len(outcomes) < 2: raise ValueError('Evidence action needs contrasting possible outcomes')
        for outcome in outcomes: require_text(outcome, ['result', 'decision_change'])
        if action.get('status') not in ('proposed', 'in_progress', 'completed'):
            raise ValueError('Invalid evidence action status')
        if action['status'] == 'completed':
            result = action.get('result')
            if not isinstance(result, dict): raise ValueError('Completed action needs actual result')
            require_text(result, ['observed', 'decision_change', 'update_note'])
            links(result, 'evidence', evidence, True)
            if result.get('outcome_id') not in {x['id'] for x in outcomes} | {'inconclusive'}:
                raise ValueError('Actual result must identify its outcome or inconclusive')
        elif 'result' in action:
            raise ValueError('A proposed action cannot contain a completed result')
        if 'access' in action and action['access'] not in ('available', 'external', 'unavailable'):
            raise ValueError('Invalid evidence access state')
        for attempt in rows(action, 'attempts'):
            require_text(attempt, ['source', 'work', 'finding'])
            links(attempt, 'evidence', evidence)

    review = support.get('research_check')
    if review is not None:
        if not isinstance(review, dict) or review.get('status') not in ('in_progress', 'ready'):
            raise ValueError('Invalid research check status')
        require_text(review, ['data_version', 'content_review', 'reading_review'])
        if review['data_version'] != data['data_version']:
            raise ValueError('Research check refers to a different data version')
        if review['status'] == 'ready':
            for action in actions:
                if action['status'] == 'completed':
                    continue
                if action.get('access') not in ('external', 'unavailable'):
                    raise ValueError('Complete accessible evidence work before marking research ready')
                require_text(action, ['current_judgment', 'remaining_reason'])
                if action['access'] == 'unavailable' and not action.get('attempts'):
                    raise ValueError('Unavailable evidence needs a record of actual attempts')

    method_notes = rows(support, 'method_notes')
    seen = set()
    for note in method_notes:
        method = note.get('method')
        if method not in METHODS or method in seen: raise ValueError('Unknown or duplicate method note')
        seen.add(method)
        require_text(note, ['trigger', 'inputs', 'work', 'result', 'limits'])
        links(note, 'evidence', evidence)
        if method == 'doe' and 'decision' not in data['modes'] and data.get('plan_requested') is not True:
            raise ValueError('DOE needs a requested validation task')


def paragraph(label, value):
    return '<p><strong>' + esc(label) + '：</strong>' + esc(value) + '</p>'


def method_source(method):
    return f'<p class="key"><a href="{METHOD_URLS[method]}" rel="noopener">{METHODS[method]}：公开方法来源</a></p>'


def direction_links(ids, data):
    names = {d['id']: d['name'] for d in data['directions']}
    return ' · '.join(f'<a href="#r-{esc(x)}">{esc(x)} {esc(names[x])}</a>' for x in ids)


def linked_items(item, data):
    text = '<p>' + direction_links(item.get('direction_ids', []), data) + '</p>'
    for key, prefix, label in [('opportunity_ids', 'op-', '机会'), ('scenario_ids', 'scenario-', '情境')]:
        text += '<p>' + ' · '.join(f'<a class="research-link" href="#{prefix}{esc(x)}">{label} {esc(x)}</a>' for x in item.get(key, [])) + '</p>'
    return text


def method_badge(method, data):
    notes = data.get('method_support', {}).get('method_notes', [])
    target = '#method-' + method if any(n['method'] == method for n in notes) else METHOD_URLS[method]
    return '<a class="method-badge" href="' + target + '">参考 ' + METHODS[method] + '</a>'


def disclosure(key, title, body):
    return '<details class="appendix research-detail" id="' + key + '"><summary>' + esc(title) + '</summary><div class="appendix-body">' + body + '</div></details>'


def action_process(action, data):
    body = linked_items(action, data)
    criteria = {c['id']: c['name'] for c in (data.get('method_support', {}).get('comparison') or {}).get('criteria', [])}
    body += '<p>' + ' · '.join(f'<a class="research-link" href="#criterion-{esc(x)}">{esc(criteria[x])}</a>' for x in action.get('criterion_ids', [])) + '</p>'
    for label, key in [('影响的选择','decision'), ('已有认识','known'), ('补查方式','approach'), ('安排理由','priority_reason'), ('所需资源','resources'), ('时间与前置条件','timing'), ('停止条件','stop_rule')]:
        body += paragraph(label, action[key])
    for attempt in action.get('attempts', []):
        body += paragraph('实际查过的来源', attempt['source']) + paragraph('完成的工作', attempt['work']) + paragraph('取得的结果', attempt['finding']) + chips(attempt.get('evidence', []))
    return body + chips(action.get('evidence', []))


def render_support(data):
    support = data.get('method_support', {})
    parts = {}
    opportunities = support.get('opportunities', [])
    if opportunities:
        body = ''
        states = {'hypothesis': '用途假设', 'stated_goal': '明确目标', 'observed': '已有使用侧证据'}
        for o in opportunities:
            body += f'<article class="research-entry" id="op-{esc(o["id"])}"><h4>{esc(o["name"])}</h4>'
            body += paragraph(states[o['need_state']], o['need']) + chips(o.get('need_evidence', []))
            if o.get('goal_source'): body += paragraph('目标来源', o['goal_source'])
            for label, key in [('可能改善的能力', 'capability'), ('技术依据', 'mechanism'), ('成立前提', 'prerequisites'), ('推进条件', 'next_condition')]:
                body += paragraph(label, o[key])
            body += linked_items(o, data) + '<p>' + ' · '.join(f'<a href="#route-{esc(x)}">{esc(x)} 现有路线</a>' for x in o.get('route_ids', [])) + '</p>'
            body += chips(o.get('evidence', [])) + '</article>'
        parts['opportunities'] = disclosure('opportunities', '机会与实现条件的关联依据', body)

    comparison = support.get('comparison')
    if comparison:
        # The short overview is authored analysis, not a score or an automatic summary.
        body = '<div id="scenarios">' + method_badge('rand', data)
        body += '<p class="key">' + esc(comparison['scope']) + '</p>'
        body += '<div class="table-wrap condition-overview"><table><thead><tr><th>使用条件</th><th>对研究取舍的影响</th></tr></thead><tbody>'
        for scenario in comparison['scenarios']:
            body += '<tr><th scope="row">' + esc(scenario['name']) + '</th><td>' + esc(scenario['judgment']) + '</td></tr>'
        body += '</tbody></table></div>'
        for finding in comparison.get('shared_findings', []):
            body += '<p class="shared-finding">' + esc(finding['text']) + '</p>' + chips(finding.get('evidence', []))
        detail = paragraph('实际分析深度', comparison['depth']) + paragraph('简单基准', comparison['baseline'])
        for c in comparison['criteria']:
            detail += '<h4 id="criterion-' + esc(c['id']) + '">' + esc(c['name']) + ' · ' + ('必须满足' if c['kind'] == 'mandatory' else '偏好') + '</h4>'
            detail += paragraph('判断要求', c['requirement']) + paragraph('要求依据', c['basis']) + chips(c.get('evidence', []))
        for u in comparison.get('uncertainties', []):
            detail += '<h4>' + esc(u['name']) + '</h4>' + paragraph('考虑的变化', u['range']) + paragraph('依据', u['basis']) + chips(u.get('evidence', []))
        detail += '<label class="scenario-control" hidden>查看逐项依据 <select id="scenario-select"><option value="">全部情境</option>'
        detail += ''.join(f'<option value="{esc(s["id"])}">{esc(s["name"])}</option>' for s in comparison['scenarios']) + '</select></label><p id="scenario-live" class="key" aria-live="polite">当前显示全部已分析情境。</p>'
        cellmap = {(c['direction_id'], c['scenario_id'], c['criterion_id']): c for c in comparison['cells']}
        for s in comparison['scenarios']:
            detail += f'<article class="research-entry scenario-panel" id="scenario-{esc(s["id"])}" data-scenario="{esc(s["id"])}"><h4>{esc(s["name"])}</h4>'
            detail += paragraph('条件组合', s['conditions']) + paragraph('纳入依据', s['why_plausible'])
            detail += '<p class="scenario-hint">比较表可左右滑动；键盘可聚焦表格后使用方向键。</p><div class="table-wrap scenario-table" tabindex="0" role="region" aria-label="' + esc(s['name']) + '逐项比较"><table><thead><tr><th>候选方向</th>' + ''.join('<th>' + esc(c['name']) + '</th>' for c in comparison['criteria']) + '</tr></thead><tbody>'
            for d in comparison['direction_ids']:
                detail += '<tr><th scope="row">' + direction_links([d], data) + '</th>'
                for criterion in comparison['criteria']:
                    cell = cellmap[(d, s['id'], criterion['id'])]
                    detail += '<td><strong>' + STATES[cell['status']] + '</strong><span class="step-role">' + BASES[cell['basis_type']] + '</span><p>' + esc(cell['reason']) + '</p>' + chips(cell.get('evidence', [])) + '</td>'
                detail += '</tr>'
            detail += '</tbody></table></div></article>'
        for v in comparison.get('vulnerabilities', []):
            detail += '<article class="research-entry"><h4>失效条件与调整可能</h4>' + linked_items(v, data)
            for label, key in [('条件组合', 'conditions'), ('影响原因', 'reason'), ('可研究的调整', 'adaptation'), ('重新考虑的信号', 'switch_signal')]:
                detail += paragraph(label, v[key])
            detail += chips(v.get('evidence', [])) + '</article>'
        parts['comparison'] = body + disclosure('scenario-detail', '查看共同标准、逐项证据与失效条件', detail) + '</div>'

    pending = [a for a in support.get('evidence_actions', []) if a['status'] != 'completed']
    completed = [a for a in support.get('evidence_actions', []) if a['status'] == 'completed']
    if pending:
        body = '<div id="evidence-actions" class="remaining-conditions"><h3>仍影响判断的关键条件</h3>' + method_badge('nasa', data)
        for action in pending:
            body += f'<article class="research-entry" id="action-{esc(action["id"])}"><h4>{esc(action["question"])}</h4>'
            if action.get('current_judgment'): body += paragraph('当前判断', action['current_judgment'])
            else: body += paragraph('影响的选择', action['decision'])
            if action.get('remaining_reason'): body += paragraph('仍未解决的原因', action['remaining_reason'])
            else: body += '<p class="key">尚未记录证据可取得性；本项不能据此认定已完成主动补查。</p>'
            body += '<ul class="outcome-list">'
            for outcome in action['outcomes']:
                body += '<li><strong>' + esc(outcome['result']) + '</strong> ' + esc(outcome['decision_change']) + '</li>'
            body += '</ul>' + paragraph('仍不能区分时', action['inconclusive'])
            body += disclosure('action-process-' + esc(action['id']), '查看已有依据与补查安排', action_process(action, data)) + '</article>'
        parts['remaining'] = body + '</div>'
    log = ''
    for action in completed:
        result = action['result']
        log += f'<article class="research-entry" id="action-{esc(action["id"])}"><h4>{esc(action["question"])}</h4>'
        log += paragraph('核查结果', result['observed']) + paragraph('判断如何更新', result['decision_change']) + paragraph('已更新的位置', result['update_note']) + chips(result['evidence'])
        history = action_process(action, data)
        for outcome in action['outcomes']:
            history += paragraph('原先考虑的结果', outcome['result']) + paragraph('对应取舍', outcome['decision_change'])
        log += disclosure('action-process-' + esc(action['id']), '核查过程与原先考虑的分支', history) + '</article>'
    review = support.get('research_check')
    if review:
        log += '<h4>本轮交付前回查</h4>' + paragraph('被审版本', review['data_version']) + paragraph('补证与内容回查', review['content_review']) + paragraph('阅读主线回查', review['reading_review'])
        log += '<p class="key">这是分析者记录，程序仅检查结构与关联，不能证明阅读或研究结论正确。</p>'
    elif support:
        log += '<p>此份数据未记录新版主动补证验收；保留原阅读与复核状态。</p>'
    if log: parts['research-log'] = disclosure('research-log', '已完成的补查与交付前回查', log)

    notes = support.get('method_notes', [])
    if notes:
        body = ''
        for note in notes:
            body += '<article class="research-entry" id="method-' + note['method'] + '"><h4>' + METHODS[note['method']] + '</h4>' + method_source(note['method'])
            for label, key in [('为何启用', 'trigger'), ('输入', 'inputs'), ('实际工作', 'work'), ('产出', 'result'), ('应用深度', 'limits')]:
                body += paragraph(label, note[key])
            body += chips(note.get('evidence', [])) + '</article>'
        parts['method-use'] = disclosure('method-use', '方法来源与本次应用', body)
    return parts
