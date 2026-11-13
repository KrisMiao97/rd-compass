"""Synthetic behavioral regressions; these do not validate patent facts."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from render_report import render
from research_model import coverage, write_bundle, check_bundle

def fixture():
    return json.loads((Path(__file__).resolve().parents[1]/'assets/report-data.v2.example.json').read_text(encoding='utf-8'))

class ResearchTests(unittest.TestCase):
    def test_technology_order(self):
        result=render(fixture())
        self.assertLess(result.index('<section id="background"'),result.index('<section id="timeline"'))
        self.assertLess(result.index('<section id="existing"'),result.index('<section id="compare"'))
        self.assertNotIn('决策阶段：',result)
    def test_opportunity_order(self):
        data=fixture();data['modes']=['opportunity'];result=render(data)
        self.assertLess(result.index('<section id="compare"'),result.index('<section id="existing"'))
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

if __name__=='__main__':unittest.main()
