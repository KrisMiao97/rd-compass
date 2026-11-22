"""Behavioral checks for research links; synthetic data do not verify patent facts."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from render_report import render, write_report
from research_model import write_bundle, check_bundle

ROOT = Path(__file__).resolve().parents[1]
def fixture():
    return json.loads((ROOT/'assets/report-data.methods.example.json').read_text(encoding='utf-8'))

class MethodTests(unittest.TestCase):
    def test_old_reports_do_not_gain_claimed_methods(self):
        data=fixture();del data['method_support']
        result=render(data)
        self.assertNotIn('id="scenarios"', result)
        self.assertNotIn('id="opportunities"', result)

    def test_views_are_connected_and_complete(self):
        result=render(fixture())
        for key in ['op-O1','r-D1','scenario-S1','scenario-S2','criterion-C1','action-A1']:
            self.assertIn('id="'+key+'"', result)
        self.assertIn('尚不能判断', result)
        self.assertIn('仍不能区分时', result)

    def test_evidence_action_can_stand_without_comparison(self):
        data=fixture();support=data['method_support'];support['comparison']=None
        support['evidence_actions'][0]['scenario_ids']=[]
        support['evidence_actions'][0]['criterion_ids']=[]
        result=render(data)
        self.assertIn('id="action-A1"', result)
        self.assertNotIn('id="scenarios"', result)

    def test_missing_or_duplicate_cell_rejected(self):
        for duplicate in [False,True]:
            data=fixture();cells=data['method_support']['comparison']['cells']
            if duplicate: cells.append(copy.deepcopy(cells[0]))
            else: cells.pop()
            with self.assertRaises(ValueError): render(data)

    def test_unknown_cannot_assert_meets(self):
        data=fixture();cell=data['method_support']['comparison']['cells'][1]
        cell.update(status='meets',basis_type='unknown')
        with self.assertRaisesRegex(ValueError,'Unknown basis'): render(data)

    def test_measured_claim_needs_source(self):
        data=fixture();cell=data['method_support']['comparison']['cells'][0]
        cell.update(basis_type='measurement',evidence=[])
        with self.assertRaises(ValueError): render(data)

    def test_observed_need_requires_distinct_source_reference(self):
        data=fixture();op=data['method_support']['opportunities'][0]
        op['need_state']='observed'
        with self.assertRaises(ValueError): render(data)
        op['need_evidence']=['E1'];render(data) # Semantic fitness still needs content review.

    def test_broken_links_rejected_across_views(self):
        for key in ['direction_ids','opportunity_ids','scenario_ids','criterion_ids','evidence']:
            data=fixture();data['method_support']['evidence_actions'][0][key]=['missing']
            with self.subTest(key=key),self.assertRaises(ValueError): render(data)

    def test_real_tests_require_task_intent(self):
        data=fixture();data['method_support']['evidence_actions'][0]['kind']='test'
        with self.assertRaises(ValueError): render(data)
        data['plan_requested']=True;render(data)

    def test_doe_is_not_silently_enabled(self):
        data=fixture();data['method_support']['method_notes'][0]['method']='doe'
        with self.assertRaises(ValueError): render(data)

    def test_action_requires_contrasting_outcomes(self):
        data=fixture();data['method_support']['evidence_actions'][0]['outcomes'].pop()
        with self.assertRaises(ValueError): render(data)

    def test_completed_action_requires_actual_result(self):
        data=fixture();a=data['method_support']['evidence_actions'][0];a['status']='completed'
        with self.assertRaises(ValueError): render(data)
        a['result']=dict(observed='合成记录证实可取出空间。',decision_change='保持候选。',update_note='合成示例关联内容已回查。',evidence=['E1'],outcome_id='B1')
        self.assertIn('合成记录证实可取出空间。',render(data))
        a['result']['outcome_id']='wrong'
        with self.assertRaises(ValueError): render(data)
        a['result']['outcome_id']='inconclusive';render(data)
        a['status']='proposed'
        with self.assertRaises(ValueError): render(data)

    def test_user_content_escaped_in_each_view(self):
        data=fixture();bad='</script><img src=x onerror=alert(1)>'
        s=data['method_support'];s['opportunities'][0]['need']=bad
        s['comparison']['scenarios'][0]['judgment']=bad
        s['evidence_actions'][0]['outcomes'][0]['decision_change']=bad
        s['method_notes'][0]['result']=bad
        result=render(data);self.assertNotIn(bad,result);self.assertIn('&lt;img',result)

    def test_bad_support_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'report.html';write_report(fixture(),path);before=path.read_bytes()
            data=fixture();data['method_support']['comparison']['cells'].pop()
            with self.assertRaises(ValueError): write_report(data,path)
            self.assertEqual(before,path.read_bytes())

    def test_case_bundle_retains_links_and_rejects_stale_artifacts(self):
        data=json.loads((ROOT/'references/kettle-method-case.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as folder:
            write_bundle(data,folder,render);check_bundle(folder)
            saved=json.loads((Path(folder)/'research-data.json').read_text(encoding='utf-8'))
            self.assertEqual(data['method_support'],saved['method_support'])
            path=Path(folder)/'report.html';path.write_text('stale',encoding='utf-8')
            with self.assertRaises(ValueError):check_bundle(folder)

if __name__=='__main__':unittest.main()
