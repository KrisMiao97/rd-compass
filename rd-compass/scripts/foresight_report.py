"""The approved workbook and the evidence-backed future-study report are distinct outputs."""
from base64 import b64encode, b64decode
from binascii import Error as Base64Error
from itertools import groupby
from datetime import date
from functools import lru_cache
from html import escape
import json
from pathlib import Path
import re
import shutil
import tempfile

from evidence_ids import evidence_anchor
from research_model import DATES, references, require_text, unique

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'foresight'
DIMENSIONS = {'performance': '机理与性能', 'integration': '系统集成', 'production': '制造与供应', 'durability': '长期使用与安全'}
HORIZONS = {'near': '近期预研', 'reserve': '中长期储备'}
ACTIONS = {'engineering_validation': '工程验证', 'capability_reserve': '能力储备', 'watch': '观察线索'}
STANCES = {'advance': '推进', 'hold': '暂缓', 'stop': '停止'}
OUTCOMES = {'assessed_with_recommendations': '有条件的行动建议', 'assessed_no_recommendation': '本轮未形成建议',
            'insufficient': '证据不足', 'out_of_scope': '经确认调整范围'}
QUESTION_STATUS = dict(zip(OUTCOMES, ('answered', 'answered', 'insufficient', 'scope_changed')))
FIRST_READ = {'mechanism': '怎样起作用', 'comparison': '怎样对照', 'decision': '什么结果会改变决定'}

def export_template(destination):
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError('Export the blank workbook to a new or empty directory')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        staged = Path(temp) / 'workbook'
        staged.mkdir()
        shutil.copyfile(ASSETS / 'template.html', staged / 'index.html')
        shutil.copyfile(ASSETS / '填写模板.md', staged / '填写模板.md')
        if destination.exists():
            destination.rmdir()  # Only succeeds for the still-empty destination.
        staged.rename(destination)

@lru_cache(maxsize=1)
def workbook():
    template = (ASSETS / 'template.html').read_text(encoding='utf-8')
    catalog = re.search(r'<script type="application/json" id="template-data">(.*?)</script>', template, re.S)
    chapters = json.loads(catalog[1])
    if [s['id'] for s in chapters] != [f's{i:02}' for i in range(1, 14)]:
        raise ValueError('Incomplete approved workbook')
    return chapters, re.search(r'<style>(.*?)</style>', template, re.S)[1]

def rows(obj, key):
    result = obj.get(key)
    if not isinstance(result, list) or any(not isinstance(row, dict) for row in result):
        raise ValueError(key + ' must be a list of objects')
    return result

def cited(item, allowed, required=False):
    ids = item.get('evidence', [])
    references(ids, allowed, 'foresight evidence')
    if required and not ids:
        raise ValueError('A supported finding needs located evidence')

def window(row, as_of):
    def bound(value, upper):
        if value is None: return None
        if not isinstance(value, str): raise ValueError('Invalid roadmap date')
        return date.fromisoformat(value + ('-12-31' if upper else '-01-01') if re.fullmatch(r'\d{4}', value) else value)
    start, end = bound(row.get('from'), False), bound(row.get('to'), True)
    if start and end and start > end: raise ValueError('Reversed roadmap window')
    if end and end < as_of: return '观察窗口已过，请复核'
    if start and start > as_of: return '未来观察窗口'
    if not end and not start: return '待条件满足后评估'
    return '当前或开放窗口'

def counts(review, records):
    """Do not turn targeted reading, unknown family membership or an unspecified search into zero."""
    members = review['members']
    read = [m for m in members if records[m['record_id']]['reading'] == 'complete'
            and records[m['record_id']]['review'] != 'not_reviewed']
    docs = {records[m['record_id']]['document_id'] for m in read}
    if review.get('uncounted_reason'):
        return None, len(docs), None if docs else 0, None
    families = {m['family_id'] for m in members}
    checked = {m['family_id'] for m in read}
    direct = {m['family_id'] for m in read if m['direct']}
    undecided = {m['family_id'] for m in read if m['direct'] is None} - direct
    direct_count = len(direct) if not undecided and (checked or not families) else None
    return len(families), len(docs), len(checked), direct_count

def validate_foresight(data):
    f = data['foresight']
    if type(f.get('version')) is not int or f['version'] not in (1, 2) or f.get('scope') not in ('full','limited'):
        raise ValueError('Expected foresight.version 1 or 2 and scope full or limited')
    required_modes = {'technology','foresight'} | ({'opportunity'} if f['scope']=='full' else set())
    if not required_modes <= set(data['modes']) or not isinstance(data.get('recommendations'), list):
        raise ValueError('Incomplete future-report modes or recommendations')
    if not isinstance(data.get('method_support',{}).get('research_check'),dict):
        raise ValueError('Foresight requires method_support.research_check')
    require_text(f, ['search_scope','family_rule','history_boundary','portfolio','update_note','revisit','resource_boundary'])
    evidence = {e['id']: e for e in data['evidence']}
    for figure in rows(f, 'figures') if 'figures' in f else []:
        require_text(figure, ['title','caption','alt','locator','image','evidence_id'])
        if figure['evidence_id'] not in evidence:
            raise ValueError('An illustration needs a registered evidence source')
        match = re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)',figure['image'])
        if not match:
            raise ValueError('Use an embedded PNG, JPEG or WebP for illustrations')
        try:
            payload = b64decode(match[2],validate=True)
        except Base64Error as err:
            raise ValueError('Invalid image encoding') from err
        signatures = {'png': b'\x89PNG\r\n\x1a\n','jpeg': b'\xff\xd8\xff','webp': b'RIFF'}
        if not payload.startswith(signatures[match[1]]) or (match[1]=='webp' and payload[8:12]!=b'WEBP'):
            raise ValueError('Illustration type does not match its contents')
    for item in evidence.values():
        require_text(item, ['origin','kind'])
        for doc in item.get('documents',[]):
            require_text(doc,['number'])
            if not doc.get('locations'): raise ValueError('An original document needs a specific location')
    questions = {q['id']: q for q in data['reader_contract']['questions']}
    directions = {d['id']: d for d in data['directions']}
    records = {r['id']: r for r in data['records']}
    horizons = rows(f, 'horizons')
    if any('reader_limit' in h and not isinstance(h['reader_limit'],str) for h in horizons):
        raise ValueError('reader_limit must be text')
    hids = unique(horizons, 'horizon')
    if not hids or not hids <= HORIZONS.keys() or (f['scope']=='full' and hids != HORIZONS.keys()):
        raise ValueError('Full future study needs both near and reserve')
    recommendations = rows(data,'recommendations')
    rec_ids = unique(recommendations,'recommendation')
    if f['version'] == 2:
        require_text(f, ['scope_note'])
        points = rows(f, 'finding_points')
        if not points:
            raise ValueError('finding_points must explain the finding or its evidence gap')
        for point in points:
            require_text(point, ['label', 'text'])
            cited(point, evidence)
        covered = {r['direction_id'] for r in recommendations}
        for item in recommendations + [d for d in directions.values() if d['id'] not in covered]:
            if not isinstance(item.get('first_read'), dict):
                raise ValueError('Missing first_read for ' + item['id'])
            if 'title' in item['first_read']: require_text(item['first_read'],['title'])
            require_text(item['first_read'], FIRST_READ)
    occupied = set()
    for rec in recommendations:
        if rec.get('action_kind') not in ACTIONS or rec.get('stance') not in STANCES or not rec.get('horizon_ids'):
            raise ValueError('Invalid future recommendation action, stance or horizons')
        references(rec['horizon_ids'], hids, 'recommendation horizon')
        if not rec.get('change_condition'): raise ValueError('Missing adjustment condition')
        for h in rec['horizon_ids']:
            key = (rec['direction_id'], rec['action_kind'], h)
            if key in occupied: raise ValueError('Duplicate recommendation action within horizon')
            occupied.add(key)
        if any(other['direction_id']==rec['direction_id'] and other['stance']!=rec['stance'] for other in recommendations):
            require_text(rec,['scope_explanation'])
    for h in horizons:
        require_text(h, ['window','reason','question_id'])
        q = questions.get(h['question_id'])
        if not q or h.get('status') not in OUTCOMES or q['status'] != QUESTION_STATUS[h['status']]:
            raise ValueError('Horizon outcome must match its research question')
        references(h.get('recommendation_ids'), rec_ids, 'coverage recommendation')
        linked = {r['id'] for r in recommendations if h['id'] in r['horizon_ids']}
        if linked != set(h['recommendation_ids']) or bool(linked) != (h['status']=='assessed_with_recommendations'):
            raise ValueError('Horizon coverage must match actual recommendations')
    if len({h['question_id'] for h in horizons}) != len(horizons):
        raise ValueError('Each horizon needs its own question and answer')
    for node in data.get('timeline',[]):
        if node.get('date') and node['date'] > data['reader_contract']['as_of']:
            raise ValueError('Future events cannot appear on the historical timeline')
        require_text(node,['locator','attribution'])
        if not any(doc['number']==node['document_id'] and node['locator'] in
                   [loc['locator'] for loc in doc.get('locations',[])]
                   for eid in node['evidence'] for doc in evidence[eid].get('documents',[])):
            raise ValueError('Timeline location must match a registered location in the cited publication')
    trends = rows(f,'trends')
    for t in trends:
        require_text(t,['title','observation','hypothesis','independence','alternative','condition','review_trigger'])
        cited(t,evidence,True)
    if not trends: require_text(f,['trend_gap'])
    for key in ('readiness','direction_reviews'):
        entries = rows(f,key)
        ids = [r.get('direction_id') for r in entries]
        if len(set(ids))!=len(ids) or set(ids)!=set(directions):
            raise ValueError(key+' must cover each candidate direction once')
    for row in f['readiness']:
        require_text(row,['bottleneck'])
        if set(row.get('dimensions',{})) != DIMENSIONS.keys(): raise ValueError('Readiness requires four dimensions')
        for item in row['dimensions'].values():
            require_text(item,['judgment','gap'])
            cited(item,evidence)
            if not item.get('evidence') and item.get('status')!='unknown':
                raise ValueError('Unsupported maturity must be unknown')
            if item.get('status') not in ('unknown','partial','supported'): raise ValueError('Invalid readiness status')
    for review in f['direction_reviews']:
        require_text(review,['target','search_log','structure_gap','performance_gap','next_step','completion','conclusion'])
        entries=rows(review,'members')
        refs=[m.get('record_id') for m in entries]
        references(refs,records,'searched record')
        if len({records[k]['document_id'] for k in refs}) != len(refs):
            raise ValueError('List each publication version only once per candidate')
        for m in entries:
            if not review.get('uncounted_reason'): require_text(m,['family_id','family_basis'])
            if 'direct' not in m or (m['direct'] is not None and type(m['direct']) is not bool):
                raise ValueError('Direct disclosure must be true, false or null')
            if 'located_finding' in m:
                local=m['located_finding']
                require_text(local,['evidence_id','locator','text'])
                e=evidence.get(local['evidence_id'])
                record=records[m['record_id']]
                if (not e or m['record_id'] not in e.get('record_ids',[]) or
                    not any(doc['number']==record['document_id'] and
                            any(loc['locator']==local['locator'] for loc in doc.get('locations',[]))
                            for doc in e.get('documents',[]))):
                    raise ValueError('Located finding must match the reviewed original and position')
            if m['direct'] is not None:
                r=records[m['record_id']]
                if r['reading']!='complete' or r['review']=='not_reviewed':
                    raise ValueError('Cannot count direct disclosure without full-text review')
                require_text(m,['locator'])
                if not any(m['record_id'] in e.get('record_ids',[]) and
                           any(doc['number']==r['document_id'] and
                               any(loc['locator']==m['locator'] for loc in doc.get('locations',[]))
                               for doc in e.get('documents',[])) for e in evidence.values()):
                    raise ValueError('Disclosure judgment needs a registered location in the reviewed publication')
        nearest = review.get('closest')
        if nearest is None: require_text(review,['closest_gap'])
        ties = rows(review,'equally_close') if 'equally_close' in review else []
        if ties and not nearest: raise ValueError('Tied publications need a primary closest record')
        seen_documents = set()
        for nearest in ([nearest] if nearest is not None else []) + ties:
            require_text(nearest,['evidence_id','document_id','locator','match','difference'])
            if nearest['document_id'] in seen_documents: raise ValueError('Duplicate closest publication')
            seen_documents.add(nearest['document_id'])
            e=evidence.get(nearest['evidence_id'])
            if not e or not any(records[rid]['document_id']==nearest['document_id']
                                for rid in set(e.get('record_ids',[])) & set(refs)):
                raise ValueError('Closest disclosure must come from a candidate record')
            if not any(nearest['locator']==loc['locator'] for d in e['documents'] if d['number']==nearest['document_id']
                       for loc in d.get('locations',[])):
                raise ValueError('Closest disclosure must cite a registered original location')
    roadmap = rows(f,'roadmap')
    nodes = unique(roadmap,'roadmap node')
    dependencies = {}
    for n in roadmap:
        require_text(n,['title','condition','action','fallback','time_basis'])
        references(n.get('requires'),nodes,'roadmap prerequisite')
        references(n.get('horizon_ids'),hids,'roadmap horizon')
        if not n['horizon_ids']: raise ValueError('Roadmap needs a horizon')
        window(n,date.fromisoformat(data['reader_contract']['as_of']))
        cited(n,evidence)
        state = n.get('outcome','unknown')
        if state not in ('unknown','achieved','not_achieved'): raise ValueError('Unknown roadmap outcome')
        references(n.get('outcome_evidence',[]),evidence,'roadmap outcome')
        if state != 'unknown' and not n.get('outcome_evidence'):
            raise ValueError('A verified outcome needs follow-up evidence')
        dependencies[n['id']]=set(n['requires'])
    completed=set()
    while len(completed)<len(dependencies):
        next_nodes={k for k,v in dependencies.items() if v<=completed}-completed
        if not next_nodes: raise ValueError('Cyclic roadmap prerequisites')
        completed.update(next_nodes)
    if not roadmap: require_text(f,['roadmap_gap'])
    for key, reason in [('routes','route_gap'),('directions','candidate_gap')]:
        if not data[key]: require_text(f,[reason])

def render_foresight(data):
    chapters, css = workbook()
    f, reader = data['foresight'], data['reader_contract']
    evidence = {e['id']: e for e in data['evidence']}
    directions = {d['id']: d for d in data['directions']}
    records = {r['id']: r for r in data['records']}
    questions = {q['id']: q for q in reader['questions']}
    blocks = {c['id']: [] for c in chapters}
    def anchor(eid): return 'proof-' + evidence_anchor(eid)
    def proof_links(ids):
        return ' '.join(f'<a class="proof" href="#{anchor(i)}">{escape(evidence[i]["title"])}（{escape(i)}）</a>' for i in ids)
    def compact_links(ids):
        return ' '.join(f'<a class="proof" href="#{anchor(i)}" aria-label="{escape(i)} {escape(evidence[i]["title"])}">{escape(i)}</a>' for i in ids)
    def originals(e, number=None):
        return ' '.join(f'<a class="proof" href="{escape(d["url"])}" target="_blank" rel="noopener noreferrer">查看原文 · {escape(d["number"])}</a>'
                        for d in e.get('documents',[]) if number is None or d['number']==number)
    def card(ch, title, text, ids=(), link='', label='', body=''):
        suffix = proof_links(ids) + link
        blocks[ch].append('<article class="study-block">'+(f'<span class="kind">{escape(label)}</span>' if label else '')+
                          '<h3>'+escape(title)+'</h3><p>'+escape(text)+'</p>'+body+
                          (f'<div class="proofs">{suffix}</div>' if suffix else '')+'</article>')
    def paragraph(ch, text):
        blocks[ch].append('<p class="study-line">'+escape(text)+'</p>')
    def facts(ch, pairs):
        blocks[ch].append('<dl class="study-facts">'+''.join('<div><dt>'+escape(k)+'</dt><dd>'+escape(str(v))+'</dd></div>' for k,v in pairs)+'</dl>')

    def fold(ch, start, label):
        content = blocks[ch][start:]
        if content:
            blocks[ch][start:] = ['<details class="source-notes"><summary>'+escape(label)+'</summary><div>'+''.join(content)+'</div></details>']

    def first_read(item, title=''):
        if f['version'] == 1:
            return ''
        entries = ''.join('<div><dt>'+label+'</dt><dd>'+escape(item['first_read'][key])+'</dd></div>'
                          for key, label in FIRST_READ.items())
        heading = '<h4>'+escape(item['first_read'].get('title') or title)+'</h4>' if title else ''
        sources = compact_links(item.get('evidence', [])) if title else ''
        return '<div class="first-read">'+heading+'<dl>'+entries+'</dl>'+sources+'</div>'

    paragraph('s01',data['finding'])
    if f['version'] == 2:
        points = ''.join('<li><strong>'+escape(p['label'])+'</strong><p>'+escape(p['text'])+'</p>'+
                         compact_links(p.get('evidence', []))+'</li>' for p in f['finding_points'])
        finding_list='<ul class="finding-points">'+points+'</ul>'
    by_id = {r['id']: r for r in data['recommendations']}
    for h in f['horizons']:
        q=questions[h['question_id']]
        selected = ([by_id[i] for i in h['recommendation_ids']] if f['version'] == 2 else
                    [r for r in data['recommendations'] if r['id'] in h['recommendation_ids']])
        status = '仅形成观察线索' if selected and all(r['action_kind']=='watch' for r in selected) else OUTCOMES[h['status']]
        ch='s09' if h['id']=='near' else 's10'
        previews = ''.join(first_read(r, ACTIONS[r['action_kind']]+' · '+directions[r['direction_id']]['name']) for r in selected)
        card('s01',HORIZONS[h['id']]+' · '+h['window'],q['answer'],q.get('evidence_ids',[]) if f['version']==1 else [],label=status,body=previews)
        reader_limit = h.get('reader_limit', q['boundary'])
        if reader_limit:
            paragraph('s01',reader_limit)
        card(ch,q['question'],h['reason'] if selected else q['answer'],q.get('evidence_ids',[]),label=h['window'])
        if reader_limit:
            paragraph(ch,reader_limit)
        if q['boundary'] != reader_limit:
            start = len(blocks[ch])
            paragraph(ch,q['boundary'])
            fold(ch,start,'这组建议的资料范围')
        for r in selected:
            ch='s09' if h['id']=='near' else 's10'
            card(ch,STANCES[r['stance']]+' · '+(r.get('first_read',{}).get('title') or directions[r['direction_id']]['name']),r['conditions'],r['evidence'],label=ACTIONS[r['action_kind']],body=first_read(r))
            start = len(blocks[ch])
            if r['action_kind']=='engineering_validation':
                comp = r['comparator']
                el = r['elimination']
                trigger, action = el['trigger'], el['action']
                decision = trigger + ' ' + action
                observations = [('现在先做什么', r['check'])]
                if r['change_condition'].split() not in (decision.split(), (trigger + action).split()):
                    observations.append(('什么情况改变安排', r['change_condition']))
                facts(ch, observations)
                card(ch,'对照 · '+comp['name'],comp['mechanism'],comp.get('evidence',[]))
                facts(ch, [('淘汰或调整候选方案的条件', trigger), ('条件成立时的处理', action)])
            else:
                facts(ch,[('现在先做什么',r['check']),('什么情况改变安排',r['change_condition']),
                          ('替代选择',r['alternative']),('复审信号',r['review_trigger'])])
            if r.get('scope_explanation'): paragraph(ch,r['scope_explanation'])
            if f['version']==2: fold(ch,start,'具体安排与复核依据')
    for hid,ch in [('near','s09'),('reserve','s10')]:
        if hid not in {h['id'] for h in f['horizons']}: paragraph(ch,'本次限定任务未约定这一视野。')
    if f['version'] == 2:
        start=len(blocks['s01'])
        blocks['s01'].append(finding_list)
        for h in f['horizons']:
            ids=questions[h['question_id']].get('evidence_ids',[])
            if ids: blocks['s01'].append('<p>'+escape(HORIZONS[h['id']])+' · '+compact_links(ids)+'</p>')
        fold('s01',start,'建议依据哪些技术变化？')
    blocks['s01'].append('<details class="research-scope"><summary>研究范围与核对限制</summary><p>'+
                         (escape(f['scope_note'])+'</p><p>' if f['version']==2 else '')+escape(data['boundary'])+'</p><a href="#s02">查看研究范围与阅读记录说明</a></details>')
    facts('s02',[('研发问题',reader['purpose']),('研究范围',reader['scope'])])
    for h in f['horizons']: paragraph('s02',HORIZONS[h['id']]+' · '+h['window'])
    start = len(blocks['s02'])
    facts('s02',[('资料截止',data['cutoff']),
                 ('分析基准日',reader['as_of']),('检索与取样',f['search_scope']),('同族归并口径',f['family_rule']),
                 ('市场资料范围',reader['market_search']['statement']),('适用边界',reader['common_boundary'])])
    for g in reader['role_guides'].values(): card('s02',g['question'],g['answer']+' '+g['focus'],g.get('evidence_ids',[]))
    horizon_questions={h['question_id'] for h in f['horizons']}
    for q in reader['questions']:
        if q['id'] not in horizon_questions: card('s02',q['question'],q['answer']+' '+q['boundary'],q.get('evidence_ids',[]))
    for h in f['horizons']: paragraph('s02',HORIZONS[h['id']]+'的观察窗口为'+h['window']+'。'+questions[h['question_id']]['question'])
    for review in f['direction_reviews']:
        card('s02',review['direction_id']+' · '+directions[review['direction_id']]['name'],review['search_log'])
    fold('s02',start,'取样、阅读范围与逐方向检索记录')
    paragraph('s03',data['beginner_context'])
    if f.get('figures'):
        figures=[]
        for fig in f['figures']:
            ref=fig['evidence_id']
            figures.append('<figure><img src="'+escape(fig['image'])+'" alt="'+escape(fig['alt'])+'"><figcaption><strong>'+escape(fig['title'])+'</strong><p>'+escape(fig['caption'])+'</p>'+escape(fig['locator'])+' · '+compact_links([ref])+'</figcaption></figure>')
        blocks['s03'].append('<div class="figure-pair">'+''.join(figures)+'</div>')
    paragraph('s03',data['current_landscape'])
    for item in data['background']: card('s03',item['title'],item['text'],item.get('evidence',[]))
    events=sorted(data.get('timeline',[]),key=lambda n:(not bool(n['date']),n['date'] or ''))
    if events:
        paragraph('s04','按资料记载的事件日期排列。公开或授权公告日期表示该文本何时公告。')
        for year, group in groupby(events,key=lambda n:n['date'][:4] if n['date'] else '日期待核'):
            blocks['s04'].append('<h3 class="year">'+escape(year)+'</h3>')
            for n in group:
                sources=' '.join(originals(evidence[i],n['document_id']) for i in n['evidence'])
                label=' · '.join(str(v) for v in (n['date'] or '日期待核',DATES[n['date_type']],n['document_id'],n['attribution']) if v)
                blocks['s04'].append('<article class="event"><small>'+escape(label)+'</small><h4>'+escape(n['title'])+'</h4><details><summary>技术变化与出处</summary><p>'+escape(n['change'])+'</p><p>'+escape(n['locator'])+'</p>'+compact_links(n['evidence'])+' '+sources+'</details></article>')
    start = len(blocks['s04'])
    paragraph('s04',f['history_boundary'])
    omitted=[i for i in evidence if not any(i in n['evidence'] for n in events)]
    if omitted: blocks['s04'].append('<p>仅列入证据索引：</p>'+proof_links(omitted))
    fold('s04',start,'日期与收录说明')
    for t in f['trends']:
        card('s05',t['title'],t['observation'],t['evidence'],label='已观察到的变化')
        facts('s05',[('趋势假设',t['hypothesis']),('其他解释',t['alternative']),('成立条件',t['condition']),('什么证据会改变判断',t['review_trigger'])])
        start=len(blocks['s05'])
        paragraph('s05',t['independence'])
        fold('s05',start,'核对这项趋势的来源关系')
    if not f['trends']: paragraph('s05',f['trend_gap'])
    for a in reader.get('assessments',[]):
        card('s05',a['subject'],a['conclusion']+' '+a['reasoning'],
             list(dict.fromkeys(a.get('evidence_ids',[])+a.get('external_evidence',[]))))
        facts('s05',[('适用边界',a['boundary']),('重新核查的条件',a['review_trigger'])])
    for r in data['routes']:
        card('s06',r['name'],r['task']+' '+r['mechanism'],r.get('evidence',[]))
        paragraph('s06',r['development']+' '+r['limitations'])
    for d in directions.values():
        actions = [r for r in data['recommendations'] if r['direction_id'] == d['id']]
        previews = ''.join(first_read(r, ACTIONS[r['action_kind']]) for r in actions) if actions else first_read(d)
        card('s06',d['name'],d['rationale'],body=previews)
        start=len(blocks['s06'])
        for block in d.get('narrative',[]): card('s06',block.get('heading','作用过程'),block['text'],block.get('evidence',[]))
        if d.get('mechanism_kind') in ('material','algorithm','process','system'):
            facts('s06',[('输入',d['input']),('处理过程',d['process']),('输出',d['output']),('适用条件',d['application_conditions'])])
        if f['version']==2: fold('s06',start,'查看技术过程与逐项出处')
        for c in d['conditions']: paragraph('s06',c['if']+' '+c['then'])
    comparison = data['method_support'].get('comparison')
    if comparison:
        facts('s06',[('共同任务',comparison['scope']),('简单基准',comparison['baseline'])])
        for scenario in comparison['scenarios']: card('s06',scenario['name'],scenario['judgment'])
        for finding in comparison.get('shared_findings',[]): paragraph('s06',finding['text'])
    if not data['routes']: paragraph('s06',f['route_gap'])
    for r in f['readiness']:
        paragraph('s07',directions[r['direction_id']]['name'])
        facts('s07',[('最先影响投入的瓶颈',r['bottleneck'])])
        start=len(blocks['s07'])
        for key,title in DIMENSIONS.items():
            item=r['dimensions'][key]
            card('s07',title,item['judgment']+' '+item['gap'],item.get('evidence',[]),label={'unknown':'未知','partial':'部分有据','supported':'有证据支持'}[item['status']])
        fold('s07',start,'性能、集成、制造与长期使用依据')
    if f['direction_reviews']:
        paragraph('s08','以下判断限于本次已读资料。')
        start=len(blocks['s08'])
        paragraph('s08', reader['common_boundary'])
        fold('s08',start,'研究覆盖范围')
    for r in f['direction_reviews']:
        original=r.get('closest')
        related, documents, reviewed, direct = counts(r,records)
        def quantity(n,unit): return '未统计' if n is None else str(n)+unit
        card('s08',r['direction_id']+' · '+directions[r['direction_id']]['name'],r['conclusion'],label='方向结论')
        start=len(blocks['s08'])
        facts('s08',[('方向与检索范围',r['target']+' '+r['search_log'])])
        if r.get('uncounted_reason'): paragraph('s08',r['uncounted_reason'])
        for m in r['members']:
            if 'located_finding' in m:
                local=m['located_finding']
                document=records[m['record_id']]['document_id']
                card('s08',document+' · '+local['locator'],local['text'],[local['evidence_id']],
                     originals(evidence[local['evidence_id']],document),label='已在原文定位')
        facts('s08',[('相关同族',quantity(related,' 族')),('已全文复核的公开文本',quantity(documents,' 份')),
                     ('全文复核覆盖的同族',quantity(reviewed,' 族')),('复核范围内直接披露组合的同族',
                      '不适用（尚无全文复核样本）' if documents==0 and related!=0 else quantity(direct,' 族'))])
        if r['members']:
            entries=[]
            for m in r['members']:
                rec=records[m['record_id']]
                disclosure={True:'直接披露',False:'按本次复核范围未找到完整组合',None:'未作整件披露统计'}[m['direct']]
                entries.append('<li>'+escape(rec['document_id']+' · '+(m.get('family_id') or '同族待核')+'。'+
                                            (m.get('family_basis') or '')+' '+rec['read_scope']+' '+disclosure+'。'+
                                            (m.get('locator') or ''))+'</li>')
            blocks['s08'].append('<details><summary>查看这个方向的逐件计数依据</summary><ul>'+''.join(entries)+'</ul></details>')
        if not original: paragraph('s08','最接近的专利尚未确定。'+r['closest_gap'])
        for original in ([original] if original else []) + r.get('equally_close',[]):
            e=evidence[original['evidence_id']]
            fully_read=any(records[m['record_id']]['document_id']==original['document_id'] and
                           records[m['record_id']]['reading']=='complete' and records[m['record_id']]['review']!='not_reviewed'
                           for m in r['members'])
            title='最接近的专利及原文位置' if fully_read else '限定材料中最接近的原文 · 尚待全文复核'
            card('s08',title,e['title']+' · '+original['locator']+'。'+original['match']+' '+original['difference'],[e['id']],originals(e,original['document_id']))
        fold('s08',start,'专利出处、阅读深度与计数依据')
        facts('s08',[('尚缺的结构证据',r['structure_gap']),('尚缺的性能证据',r['performance_gap']),('优先动作',r['next_step']),
                     ('完成条件',r['completion'])])
    if not directions:
        for ch in ('s07','s08'): paragraph(ch,f['candidate_gap'])
    nodes = {n['id']:n['title'] for n in f['roadmap']}
    for n in f['roadmap']:
        timing=' — '.join(v for v in (n.get('from'),n.get('to')) if v)
        if n.get('from') and not n.get('to'): timing+='及以后'
        if n.get('to') and not n.get('from'): timing='截至'+timing
        card('s11',n['title'],n['condition'],n.get('evidence',[]),label=' · '.join(v for v in (timing,window(n,date.fromisoformat(reader['as_of']))) if v))
        facts('s11',[('时间依据',n['time_basis']),('需要先完成','、'.join(nodes[i] for i in n['requires']) or '无前置节点'),
                     ('条件满足后',n['action']),('条件不成立时',n['fallback'])])
        if n.get('outcome','unknown') != 'unknown':
            card('s11','兑现情况','后续证据显示已兑现。' if n['outcome']=='achieved' else '后续证据显示未兑现。',n['outcome_evidence'])
    if not nodes: paragraph('s11',f['roadmap_gap'])
    paragraph('s12',f['portfolio'])
    paragraph('s12',f['resource_boundary'])
    if 'decision_context' in data: paragraph('s12',data['decision_context'])
    for plan in data.get('plan',[]): card('s12',plan['title'],plan['text'])
    start=len(blocks['s13'])
    paragraph('s13',f['update_note']+' '+f['revisit'])
    check=data['method_support']['research_check']
    facts('s13',[('内容核对',check['content_review']),('阅读复核',check['reading_review'])])
    fold('s13',start,'本版的核对与更新记录')
    for e in evidence.values():
        blocks['s13'].append(f'<details class="evidence-note" id="{anchor(e["id"])}"><summary>{escape(e["id"])} · {escape(e["title"])}</summary>'+
                             '<p>'+escape(e['disclosure'])+'</p><p>'+escape(e['location'])+'</p><p>'+escape(e['limitation'])+'</p>'+
                             '<p>来源性质与出处：'+escape(e['kind']+' · '+e['origin'])+'</p>'+originals(e)+'</details>')
    # Provide the reading ledger in standalone files as well as in bundles.
    from research_model import catalog_table
    blocks['s13'].append('<details id="catalog"><summary>逐件阅读与复核记录</summary>'+catalog_table(data)+'</details>')
    sections=[]; nav=[]; options=[]
    for c in chapters:
        cid,num,title=c['id'],c['num'],escape(c['title'])
        sections.append(f'<section class="chapter" id="{cid}"><header class="chapter-header"><span class="chapter-num">{num}</span><h2>{title}</h2></header>'+''.join(blocks[cid])+'</section>')
        nav.append(f'<a href="#{cid}"><span>{num}</span>{title}</a>')
        options.append(f'<option value="{cid}">第 {num} 章 · {title}</option>')
    guide=b64encode((ASSETS/'template.html').read_bytes()).decode('ascii')
    extra = '''.study-block{padding:17px 0;border-bottom:1px solid var(--line)}.study-block h3{font-size:18px;margin:5px 0 9px}.study-block p,.study-line,.study-facts dd{max-width:54em;white-space:pre-line;overflow-wrap:anywhere}.study-line{margin:14px 0}.proofs{display:flex;flex-wrap:wrap;gap:8px 14px}.proof{display:inline-block;text-decoration:underline;font-size:14px;margin:3px 0}.kind{font-size:13px;color:#315f79}.study-facts{margin:12px 0}.study-facts div{display:grid;grid-template-columns:10em 1fr;gap:12px;padding:9px 0}.study-facts dt{font-weight:650}.study-facts dd{margin:0}.study-intro{padding:46px 0 28px;max-width:55em}.study-intro h1{font-size:clamp(26px,4vw,44px);margin-bottom:16px}.chapter,.study-block[id],#catalog{scroll-margin-top:86px}.table-wrap{overflow:auto}table{border-collapse:collapse}td,th{padding:6px;text-align:left}.mobile-nav-wrap{min-width:0}.topbar .mobile-toc{position:static;opacity:1}.topbar .brand{white-space:nowrap}.study .top-actions a{white-space:nowrap}.study .chapter[hidden]{display:none}@media(max-width:600px){.study-facts div{grid-template-columns:1fr;gap:3px}.study-block h3{font-size:16px}.study-intro{padding:25px 0 14px}.study .mobile-nav-wrap{flex:1}.topbar .brand{font-size:14px}.study .top-actions a{font-size:12px;padding:7px}}@media print{.study-intro{padding:0}.study-intro h1{font-size:22pt}.study-block{break-inside:avoid}.chapter{padding:12px 0}.table-wrap{overflow:visible}}'''
    extra += '''.finding-points{list-style:none;padding:0;margin:12px 0 24px}.finding-points li{padding:10px 14px;border-left:3px solid #85aec1;margin:8px 0;background:#f3f7f9}.finding-points p,.first-read dl{margin:4px 0}.finding-points p,.first-read dd,.research-scope p{max-width:54em;overflow-wrap:anywhere;white-space:pre-line}.first-read{padding:12px 0 5px}.first-read h4{margin:0 0 5px}.first-read dl>div{display:grid;grid-template-columns:9.5em 1fr;gap:10px;padding:6px 0}.first-read dt{font-weight:650}.first-read dd{margin:0}.research-scope{margin:20px 0}.research-scope summary{cursor:pointer}.research-scope a{display:inline-block;margin:6px 0}@media(max-width:600px){.first-read dl>div{display:block}.first-read dd{margin-top:3px}}@media print{.study-block:has(.first-read){break-inside:auto}.first-read dl>div,.finding-points li{break-inside:avoid}}'''
    js = """const menu=document.querySelector('#study-nav'),chapters=[...document.querySelectorAll('.chapter')],links=[...document.querySelectorAll('.toc a')];
let printClosed=[];addEventListener('beforeprint',()=>{printClosed=[...document.querySelectorAll('details:not([open])')];printClosed.forEach(d=>d.open=true)});addEventListener('afterprint',()=>{printClosed.forEach(d=>d.open=false);printClosed=[]});
function sync(){let id='';const line=document.querySelector('.topbar').getBoundingClientRect().bottom+32;for(const ch of chapters){if(ch.getBoundingClientRect().top>line)break;id=ch.id}menu.value=id;for(const a of links){const active=a.hash==='#'+id;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current')}}
menu.onchange=()=>{if(menu.value){location.hash=menu.value;document.getElementById(menu.value).scrollIntoView();sync()}};
addEventListener('scroll',sync,{passive:true});addEventListener('resize',sync);addEventListener('pageshow',sync);sync();"""
    js += """
const figureDialog=document.createElement('dialog');
if(typeof figureDialog.showModal==='function' && document.querySelector('.figure-pair img')){
  figureDialog.className='figure-dialog';figureDialog.setAttribute('aria-label','原件附图');
  const close=document.createElement('button'), enlarged=document.createElement('img');let previous;
  close.type='button';close.textContent='关闭附图';figureDialog.append(close,enlarged);document.body.append(figureDialog);
  close.onclick=()=>figureDialog.close();figureDialog.addEventListener('close',()=>previous?.focus());
  for(const img of document.querySelectorAll('.figure-pair img')){
    const b=document.createElement('button');b.type='button';b.className='figure-open';b.setAttribute('aria-label','放大附图：'+img.alt);
    const hint=document.createElement('span');hint.textContent='放大图';img.replaceWith(b);b.append(img,hint);
    b.onclick=()=>{previous=b;enlarged.src=img.src;enlarged.alt=img.alt;figureDialog.showModal();close.focus()};
  }
}
const folds=[...document.querySelectorAll('main details')],button=document.getElementById('read-all');
function revealTarget(){const target=document.getElementById(location.hash.slice(1));if(!target)return;for(let n=target;n;n=n.parentElement){if(n.tagName==='DETAILS')n.open=true}target.scrollIntoView()}
function updateAll(){const open=folds.every(d=>d.open);button.textContent=open?'收起详情':'展开全文';button.setAttribute('aria-pressed',String(open))}
button.hidden=false;button.onclick=()=>{const open=!folds.every(d=>d.open);folds.forEach(d=>d.open=open);updateAll()};folds.forEach(d=>d.addEventListener('toggle',updateAll));
addEventListener('hashchange',revealTarget);document.addEventListener('click',e=>{const a=e.target.closest('a[href^="#"]');if(a&&a.hash===location.hash)revealTarget()});if(location.hash)revealTarget();
"""
    extra += (ASSETS/'reading.css').read_text(encoding='utf-8')
    title=escape(data['title']); status='研究进行中' if data['method_support']['research_check']['status']=='in_progress' else '范围内研究已完成'
    tools = '<button id="read-all" type="button" hidden aria-pressed="false">展开全文</button>'
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{css}{extra}</style></head><body class="study" id="top"><header class="topbar"><a class="brand" href="#top">研发罗盘</a><div class="mobile-nav-wrap"><select id="study-nav" class="mobile-toc" aria-label="章节目录，跳到章节"><option value="">章节目录</option>{''.join(options)}</select></div><div class="top-actions"><a class="btn" download="未来技术趋势与研发储备报告-填写模板.html" href="data:text/html;base64,{guide}">下载填写模板</a></div></header><div class="shell"><header class="study-intro"><h1>{title}</h1><p>{escape(reader['purpose'])}</p><small>{status} · 资料截止 {escape(data['cutoff'])} · 分析基准日 {escape(reader['as_of'])}</small> {tools}</header><div class="workbench"><aside class="sidebar"><nav class="toc" aria-label="章节导航">{''.join(nav)}</nav></aside><main>{''.join(sections)}</main></div></div><script>{js}</script></body></html>'''
