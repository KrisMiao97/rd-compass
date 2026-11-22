"""Check the difference between completed research, remaining conditions and missing work."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from render_report import render
ROOT=Path(__file__).resolve().parents[1]
def fixture():
    d=json.loads((ROOT/'assets/report-data.methods.example.json').read_text(encoding='utf-8'))
    d['method_support']['research_check']={'status':'ready','data_version':d['data_version'],'content_review':'合成回查：未提供企业使用记录。','reading_review':'合成顺读检查。'}
    return d
class ResearchCompletionTests(unittest.TestCase):
    def test_supplied_constraints_remain_visible_in_opportunity_mode(self):
        d=fixture();d['decision_context']='明确的安装边界：不可移动现有接口。'
        result=render(d)
        self.assertIn('<section id="decision"',result)
        self.assertIn('<p>明确的安装边界：不可移动现有接口。</p>',result)
    def test_available_work_cannot_be_reported_ready(self):
        d=fixture();d['method_support']['evidence_actions'][0]['access']='available'
        with self.assertRaisesRegex(ValueError,'Complete accessible'):render(d)
    def test_work_in_progress_is_explicit(self):
        d=fixture();d['method_support']['evidence_actions'][0]['access']='available';d['method_support']['research_check']['status']='in_progress'
        self.assertIn('研究仍在进行',render(d))
    def test_remaining_condition_needs_judgment_and_reason(self):
        for key in ['current_judgment','remaining_reason']:
            d=fixture();del d['method_support']['evidence_actions'][0][key]
            with self.subTest(key=key),self.assertRaises(ValueError):render(d)
    def test_failed_access_needs_actual_attempt_record(self):
        d=fixture();a=d['method_support']['evidence_actions'][0];a['access']='unavailable'
        with self.assertRaisesRegex(ValueError,'actual attempts'):render(d)
        a['attempts']=[{'source':'合成来源','work':'合成取得尝试','finding':'合成访问失败','evidence':[]}]
        render(d)
    def test_attempt_cannot_reference_unknown_evidence(self):
        d=fixture();d['method_support']['evidence_actions'][0]['attempts']=[{'source':'来源','work':'工作','finding':'结果','evidence':['missing']}]
        with self.assertRaises(ValueError):render(d)
    def test_ready_requires_assessed_access_for_remaining_work(self):
        d=fixture();del d['method_support']['evidence_actions'][0]['access']
        with self.assertRaises(ValueError):render(d)
    def test_check_cannot_be_reused_for_new_version(self):
        d=fixture();d['data_version']='changed-after-review'
        with self.assertRaisesRegex(ValueError,'different data version'):render(d)
    def test_old_research_does_not_gain_new_assurance(self):
        d=fixture();del d['method_support']['research_check'];del d['method_support']['evidence_actions'][0]['access']
        result=render(d);self.assertIn('未记录新版主动补证验收',result)
    def test_completed_work_moves_to_records_without_future_task(self):
        d=json.loads((ROOT/'references/kettle-method-case.json').read_text(encoding='utf-8'))
        d['method_support']['evidence_actions']=[d['method_support']['evidence_actions'][1]]
        result=render(d)
        self.assertNotIn('id="evidence-actions"',result)
        self.assertLess(result.index('id="research-log"'),result.index('id="action-A2"'))
        self.assertIn('连接框架',result)
    def test_reader_paragraphs_preserve_full_argument(self):
        d=fixture();d['directions'][0]['narrative']=[{'text':'读者可顺读的合成结论。','evidence':['E1']}]
        result=render(d)
        self.assertLess(result.index('读者可顺读的合成结论。'),result.index('id="direction-detail-D1"'))
        self.assertIn(d['directions'][0]['reasoning'][0]['text'],result)
    def test_reader_narrative_requires_text_and_valid_sources(self):
        for value in [[],['not a paragraph object'],[{'text':'','evidence':[]}],[{'text':'正文','evidence':['missing']}]]:
            d=fixture();d['directions'][0]['narrative']=value
            with self.subTest(value=value),self.assertRaises(ValueError):render(d)
    def test_new_reader_fields_are_escaped(self):
        d=fixture();bad='</script><img src=x onerror=alert(1)>'
        d['directions'][0]['narrative']=[{'text':bad,'evidence':[]}]
        d['method_support']['comparison']['shared_findings']=[{'text':bad,'evidence':[]}]
        d['method_support']['evidence_actions'][0]['remaining_reason']=bad
        result=render(d);self.assertNotIn(bad,result);self.assertIn('&lt;img',result)
if __name__=='__main__':unittest.main()
