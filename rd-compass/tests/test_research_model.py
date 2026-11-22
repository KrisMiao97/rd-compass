"""Synthetic behavioral regressions; these do not validate patent facts."""
import copy
import json
import re
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from render_report import render
from research_model import coverage, write_bundle, check_bundle
from test_reader_contract import fixture as reader_fixture

def fixture():
    return json.loads((Path(__file__).resolve().parents[1]/'assets/report-data.v2.example.json').read_text(encoding='utf-8'))

def recommendation_fixture():
    data = fixture()
    data.update(schema_version=3, modes=['opportunity'])
    data.pop('opportunity', None)
    data.pop('judgment', None)
    data['recommendations'] = [{
        'direction_id': data['directions'][0]['id'],
        'evidence': [data['evidence'][0]['id']],
        'conditions': '同一壳体、维护位置和打开空间。',
        'comparator': {'name': '固定盖', 'mechanism': '从同一开口做日常维护。',
                       'basis_type': 'engineering_baseline'},
        'check': '观察两种安装方式能否允许取件。',
        'elimination': {'trigger': '无法在工作空间取出部件。', 'action': '保留固定盖设计。'},
    }]
    return data


def guided_fixture():
    data = recommendation_fixture()
    data.update(report_contract_version=2, reader_contract=reader_fixture(),
                cutoff='2026-11-14', cutoff_scope='前次资料截止；后次仅回查该机构。',
                beginner_context='拿走容器前，先把上面的盖打开。')
    data['directions'][0].update(mechanism_kind='moving', narrative=[
        dict(text='闭合时挡片压住容器。打开盖时挡片向上转，使容器可以抽出。',
             evidence=['E1'], stages=['initial', 'trigger', 'motion', 'result']),
        dict(text='放回容器后再合上盖，挡片压回原位。', evidence=['E1'], stages=['reset']),
    ])
    return data

class ResearchTests(unittest.TestCase):
    def test_guided_report_requires_closing_the_motion_cycle(self):
        data = guided_fixture()
        narrative = data['directions'][0]['narrative']
        narrative.pop()
        with self.assertRaisesRegex(ValueError, 'result and reset'):
            render(data)
        narrative.append(dict(text='放回后手动锁合。', stages=['reset']))
        with self.assertRaisesRegex(ValueError, 'action block needs stages and evidence'):
            render(data)

    def test_guided_report_distinguishes_cutoff_and_analysis_date(self):
        data = guided_fixture()
        rendered = render(data)
        self.assertIn('基础资料记录截至 2026-11-14', rendered)
        self.assertIn('分析记录日期：2026-11-16', rendered)
        self.assertLess(rendered.index(data['beginner_context']), rendered.index('研究发现：'))
        self.assertIn('<p>放回容器后再合上盖，挡片压回原位。</p>', rendered)
        del data['cutoff_scope']
        with self.assertRaisesRegex(ValueError, 'cutoff_scope'):
            render(data)
        data['reader_contract']['as_of'] = '2026-11-13'
        with self.assertRaisesRegex(ValueError, 'cannot precede'):
            render(data)

    def test_technology_order(self):
        result=render(fixture())
        self.assertLess(result.index('<section id="background"'),result.index('<section id="timeline"'))
        self.assertLess(result.index('<section id="existing"'),result.index('<section id="compare"'))
        self.assertNotIn('决策阶段：',result)
    def test_opportunity_order(self):
        data=fixture();data['modes']=['opportunity'];result=render(data)
        self.assertLess(result.index('<section id="background"'),result.index('<section id="existing"'))
        self.assertLess(result.index('<section id="existing"'),result.index('<section id="routes"'))
        self.assertLess(result.index('<section id="routes"'),result.index('<section id="compare"'))
    def test_static_without_timeline_or_candidates(self):
        data=fixture();data['timeline']=[];data['directions']=[];data['evidence'][0]['directions']=[]
        data['routes'][0]['mechanism']='静态隔热层安装在内外壳之间，不涉及动作触发或复位。'
        result=render(data);self.assertIn('静态隔热层',result)
        self.assertNotIn('<section id="timeline"',result);self.assertNotIn('<section id="compare"',result)
    def test_unknown_date(self):
        data=fixture();data['timeline'][0].update(date=None,date_type='unknown')
        self.assertIn('日期未知',render(data))
    def test_grant_without_a_version_allowed(self):
        data=fixture();data['timeline'][0]['date_type']='grant'
        self.assertIn('授权公告',render(data))
    def test_grant_not_earliest_disclosure(self):
        data=fixture();data['timeline'][0].update(date_type='grant',earliest_verified_disclosure=True)
        with self.assertRaises(ValueError):render(data)
    def test_missing_date_type(self):
        data=fixture();del data['timeline'][0]['date_type']
        with self.assertRaises(ValueError):render(data)
    def test_research_priority_without_measurements(self):
        data=fixture();data['directions'][0]['judgment_kind']='research_priority'
        self.assertIn('优先研究',render(data))
    def test_performance_needs_conditions_and_evidence(self):
        data=fixture();data['directions'][0]['judgment_kind']='performance_comparison'
        with self.assertRaises(ValueError):render(data)
        data['directions'][0].update(comparison_conditions='相同模拟条件',comparison_evidence=['E1'])
        self.assertIn('性能比较',render(data))
    def test_plan_requires_task_intent(self):
        data=fixture();data['plan']=[{'title':'对照观察','text':'同一工况比较，此处为合成计划。'}]
        with self.assertRaises(ValueError):render(data)
        data['plan_requested']=True;self.assertIn('<section id="plan"',render(data))
        del data['plan_requested'];data['modes']=['decision'];data['decision_context']='比较维护可达性，空间固定，成本未知。';self.assertIn('决策阶段：',render(data))

    def test_v2_shared_ids_preserve_references_and_details(self):
        data = fixture()
        before = 'E1'
        after = 'CN123456789A-claim2-e1'
        def replace_ids(value):
            if isinstance(value, list):
                return [replace_ids(item) for item in value]
            if isinstance(value, dict):
                return {key: replace_ids(item) for key, item in value.items()}
            return after if value == before else value
        data = replace_ids(data)
        result = render(data)
        self.assertIn('id="e-' + after + '"', result)
        self.assertIn('href="#e-' + after + '"', result)
        start = result.index('<details class="evidence-item" id="e-' + after + '"')
        self.assertIn('装配排障', result[start:result.index('</details>',start)])
        self.assertIn(after, json.loads(
            re.search(r'<script id="report-data" type="application/json">(.*?)</script>', result, re.S)[1]
        )['evidence'][0]['id'])

    def test_many_to_many_cards(self):
        data=fixture();data['evidence'][0]['record_ids']=['source1','source2']
        other=copy.deepcopy(data['evidence'][0]);other.update(id='E2',record_ids=['source1'])
        data['evidence'].append(other);render(data)
        self.assertEqual(coverage(data)['detailed_cards'],2)
        self.assertEqual(coverage(data)['records_linked_to_cards'],2)
    def test_reading_and_review_separate(self):
        counts=coverage(fixture())
        self.assertEqual(sum(counts['sample_reading'].values()),2)
        self.assertEqual(sum(counts['sample_review'].values()),2)
    def test_independent_review_requires_record(self):
        data=fixture();data['records'][0]['review']='independent'
        with self.assertRaises(ValueError):render(data)
    def test_invalid_record_and_route_links(self):
        data=fixture();data['evidence'][0]['record_ids']=['missing']
        with self.assertRaises(ValueError):render(data)
        data=fixture();data['directions'][0]['route_ids']=['missing']
        with self.assertRaises(ValueError):render(data)
    def test_multiple_source_positions(self):
        result=render(fixture());self.assertIn('清洗说明',result);self.assertIn('装配排障',result)
    def test_locations_stay_in_their_own_card(self):
        data=fixture();other=copy.deepcopy(data['evidence'][0]);other['id']='E2';other['documents'][0]['locations']=[]
        data['evidence'].append(other);result=render(data)
        start=result.index('<details class="evidence-item" id="e-E2"')
        self.assertNotIn('装配排障',result[start:result.index('</details>',start)])
    def test_timeline_document_matches_source(self):
        data=fixture();data['timeline'][0]['document_id']='OTHER'
        with self.assertRaises(ValueError):render(data)
    def test_decision_requires_goal_context(self):
        data=fixture();data['modes']=['decision']
        with self.assertRaises(ValueError):render(data)
    def test_bundle_update_and_stale_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            data=fixture();write_bundle(data,folder,render);old=(Path(folder)/'reading.csv').read_bytes()
            data['records'][1].update(reading='targeted',read_scope='补读实施段，尚未完整阅读');data['data_version']='synthetic-2'
            write_bundle(data,folder,render);check_bundle(folder)
            self.assertIn('定点补读',(Path(folder)/'catalog.html').read_text(encoding='utf-8'))
            (Path(folder)/'reading.csv').write_bytes(old)
            with self.assertRaisesRegex(ValueError,'reading.csv'):check_bundle(folder)
    def test_invalid_input_preserves_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            write_bundle(fixture(),folder,render);before={p.name:p.read_bytes() for p in Path(folder).iterdir()}
            data=fixture();data['timeline'][0]['date_type']='invalid'
            with self.assertRaises(ValueError):write_bundle(data,folder,render)
            self.assertEqual(before,{p.name:p.read_bytes() for p in Path(folder).iterdir()})
    def test_text_is_escaped(self):
        data=fixture();data['routes'][0]['mechanism']='</script><script>alert(1)</script>'
        self.assertNotIn(data['routes'][0]['mechanism'],render(data))

    def test_current_report_links_summary_to_located_evidence_and_falsifier(self):
        data = recommendation_fixture()
        rendered = render(data)
        direction = data['directions'][0]['id']
        evidence = data['evidence'][0]['id']
        self.assertRegex(rendered, rf'<ul class="summary-recommendations"><li><a href="#r-{direction}">')
        panel = rendered.split(f'id="r-{direction}"', 1)[1].split('</article>', 1)[0]
        for text in [f'href="#e-{evidence}"', '同一壳体', '工程对照设定', '观察两种', '无法在工作空间取出', '保留固定盖']:
            self.assertIn(text, panel)
        card = rendered.split(f'id="e-{evidence}"', 1)[1].split('</details>', 1)[0]
        self.assertIn(data['evidence'][0]['location'], card)
        self.assertIn(data['evidence'][0]['documents'][0]['url'], card)

    def test_current_opportunity_cannot_omit_or_bypass_recommendations(self):
        data = recommendation_fixture()
        del data['recommendations']
        with self.assertRaisesRegex(ValueError, 'Provide recommendations'):
            render(data)
        data['judgment'] = '自由文字建议'
        with self.assertRaisesRegex(ValueError, 'free-text summary'):
            render(data)
        del data['judgment']
        data['recommendations'] = []
        self.assertIn('现有依据尚不足以提出首屏建议。', render(data))
        data['modes'] = ['technology']
        del data['recommendations']
        self.assertNotIn('<h2>研发建议</h2>', render(data))

    def test_current_recommendation_rejects_missing_and_unrelated_inputs(self):
        for key in ('conditions', 'comparator', 'check', 'elimination', 'evidence', 'direction_id'):
            with self.subTest(key=key):
                data = recommendation_fixture()
                del data['recommendations'][0][key]
                with self.assertRaises(ValueError):
                    render(data)
        data = recommendation_fixture()
        row = data['recommendations'][0]
        row['direction_id'] = 'D99'
        with self.assertRaisesRegex(ValueError, 'direction is unresolved'):
            render(data)
        data = recommendation_fixture()
        data['recommendations'][0]['evidence'] = ['E99']
        with self.assertRaisesRegex(ValueError, 'recommendation original evidence'):
            render(data)
        other = copy.deepcopy(data['evidence'][0])
        other.update(id='E99', directions=[data['directions'][0]['id']])
        data['evidence'].append(other)
        data['directions'][0]['reasoning'][1]['evidence'].append('E99')
        with self.assertRaisesRegex(ValueError, 'recommendation direction evidence'):
            render(data)
        data = recommendation_fixture()
        data['evidence'][0]['documents'] = []
        with self.assertRaisesRegex(ValueError, 'recommendation original evidence'):
            render(data)
        data = recommendation_fixture()
        data['recommendations'][0]['comparator']['basis_type'] = 'disclosure'
        with self.assertRaisesRegex(ValueError, 'Disclosed comparator needs'):
            render(data)

if __name__=='__main__':unittest.main()
