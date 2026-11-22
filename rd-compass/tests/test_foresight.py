import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from foresight_report import counts, export_template
from render_report import render, validate
from research_model import check_bundle, write_bundle


class FutureStudy(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'assets/foresight/steam-oven.example.json').read_text(encoding='utf8'))
        self.study = self.data['foresight']
        self.review = self.study['direction_reviews'][0]
        self.member = self.review['members'][0]

    def invalid(self, pattern):
        with self.assertRaisesRegex(ValueError, pattern):
            validate(self.data)

    def test_real_report_chapters_links_and_evidence(self):
        page = render(self.data)
        self.assertEqual(re.findall(r'<section class="chapter" id="(s\d\d)"', page),
                         [f's{i:02}' for i in range(1,14)])
        history = page.split('<section class="chapter" id="s04"')[1].split('</section>')[0]
        for event, evidence in zip(self.data['timeline'],self.data['evidence']):
            article = next(a for a in history.split('</article>') if event['date'] in a)
            self.assertIn(evidence['documents'][0]['url'],article)
            self.assertIn(event['attribution'],article)
            self.assertIn(event['locator'],article)
        self.assertIn('id="proof-E2"',page)
        self.assertIn('id="proof-E02"',page)
        self.assertIn('尚待全文复核',page)
        self.assertIn('<dt>相关同族</dt><dd>未统计</dd>',page)

    def test_engineering_condition_is_shown_once_and_distinct_rules_survive(self):
        rec = next(r for r in self.data['recommendations'] if r['action_kind'] == 'engineering_validation')
        rec['elimination'] = {'trigger': '若观察到样件异常', 'action': '暂停当前样件。'}
        rec['change_condition'] = '若观察到样件异常  暂停当前样件。'
        def chapter():
            return render(self.data).split('id="s09"', 1)[1].split('</section>', 1)[0]
        self.assertEqual(chapter().count('若观察到样件异常'), 1)
        rec['change_condition'] = '若任一组丢失参照，暂停两组。'
        self.assertIn(rec['change_condition'], chapter())
        self.assertIn(rec['elimination']['action'], chapter())

    def test_direction_conclusion_precedes_counts(self):
        section = render(self.data).split('id="s08"', 1)[1].split('</section>', 1)[0]
        conclusion = self.review['conclusion']
        self.assertEqual(section.count(conclusion), 1)
        self.assertLess(section.index(conclusion), section.index('相关同族</dt>'))

    def test_approved_workbook_exact_and_export_is_nondestructive(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'guide'
            export_template(target)
            for filename, digest in {
                'index.html':'bb2772044d3293a24c198e21dfe800f8f2fa71d8b34f2776d98b6868f0352c8c',
                '填写模板.md':'5dd63e55aaf90ab5be23ae72c69d308d881712ac58ba1e14d377fb9812d6d45f'
            }.items():
                self.assertEqual(hashlib.sha256((target/filename).read_bytes()).hexdigest(),digest)
            (target/'私人笔记').write_text('x')
            with self.assertRaisesRegex(ValueError,'empty'):
                export_template(target)
            self.assertEqual((target/'私人笔记').read_text(),'x')

    def test_first_mention_shows_decision_before_closed_method_notes(self):
        page = render(self.data)
        intro, rest = page.split('<section class="chapter" id="s01"', 1)
        summary = rest.split('</section>', 1)[0]
        visible, details = summary.split('<details class="research-scope">', 1)
        self.assertNotIn(self.study['scope_note'], intro)
        self.assertIn(self.study['scope_note'], details)
        self.assertNotIn(self.data['boundary'], intro)
        self.assertIn(self.data['boundary'], details)
        for point in self.study['finding_points']:
            self.assertIn(point['label'], visible)
        for rec in self.data['recommendations']:
            for text in rec['first_read'].values():
                self.assertIn(text, visible)
        candidates = rest.split('<section class="chapter" id="s06"', 1)[1].split('</section>', 1)[0]
        self.assertIn(self.data['recommendations'][0]['first_read']['comparison'], candidates)

    def test_current_limit_and_timeline_sources_are_separate(self):
        horizon = self.study['horizons'][0]
        horizon['reader_limit'] = '当前决定取决于独立参照。'
        page = render(self.data)
        section = page.split('id="s01"', 1)[1].split('</section>', 1)[0]
        self.assertIn(horizon['reader_limit'], section.split('<details')[0])
        history = page.split('id="s04"', 1)[1].split('</section>', 1)[0]
        self.assertIn(self.study['history_boundary'], history.split('日期与收录说明</summary>',1)[1])
        self.assertNotIn(self.study['history_boundary'], history.split('日期与收录说明</summary>',1)[0])

    def test_unregistered_figure_is_rejected(self):
        self.study['figures'] = [dict(title='位置',caption='关系',alt='位置',locator='图1',
                                      image='data:image/png;base64,AA==',evidence_id='missing')]
        self.invalid('illustration needs')

    def test_first_read_rejects_missing_comparison_and_unregistered_source(self):
        rec = self.data['recommendations'][0]
        comparison = rec['first_read'].pop('comparison')
        self.invalid('comparison')
        rec['first_read']['comparison'] = comparison
        self.study['finding_points'][0]['evidence'] = ['unregistered']
        self.invalid('foresight evidence')

    def test_old_previews_do_not_require_new_fields_or_invent_new_copy(self):
        self.study['version'] = 1
        del self.study['scope_note'], self.study['finding_points']
        for rec in self.data['recommendations']:
            del rec['first_read']
        page = render(self.data)
        self.assertNotIn('<div class="first-read">', page)
        self.assertIn(self.data['boundary'], page)
        self.assertIn(self.data['reader_contract']['questions'][0]['answer'], page)

    def test_bundle_checks_and_invalid_input_preserves_output(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            write_bundle(self.data,folder,render)
            check_bundle(folder)
            before={p.name:p.read_bytes() for p in folder.iterdir()}
            self.review['closest']['evidence_id']='bad'
            with self.assertRaises(ValueError):
                write_bundle(self.data,folder,render)
            self.assertEqual(before,{p.name:p.read_bytes() for p in folder.iterdir()})

    def test_cannot_lower_schema_to_skip_checks(self):
        self.data['schema_version']=3
        self.invalid('uture|oresight')

    def test_requires_both_horizons_in_full_study(self):
        self.study['horizons'].pop()
        self.invalid('both near and reserve')

    def test_one_window_when_scope_explicitly_limited(self):
        self.study['scope']='limited'
        self.study['horizons'].pop()
        self.data['recommendations'].pop()
        self.study['roadmap'].pop()
        self.data['reader_contract']['questions'].pop()
        self.assertIn('本次限定任务未约定这一视野',render(self.data))

    def test_empty_recommendation_not_complete_coverage(self):
        self.study['horizons'][0]['recommendation_ids']=[]
        self.invalid('coverage')

    def test_no_recommendation_can_be_declared(self):
        self.data['recommendations'].pop()
        h=self.study['horizons'][1]
        h.update(recommendation_ids=[],status='insufficient')
        self.data['reader_contract']['questions'][1].update(status='insufficient',answer='尚无适用资料。')
        self.assertIn('证据不足',render(self.data))

    def test_duplicate_action_in_one_horizon(self):
        self.data['recommendations'].append(dict(self.data['recommendations'][1],id='A3'))
        self.invalid('Duplicate recommendation')

    def test_conflicting_stance_needs_scope(self):
        self.data['recommendations'][1]['stance']='hold'
        self.invalid('scope_explanation')

    def test_action_kind_controls_baseline_not_time_horizon(self):
        self.data['recommendations'][1]['action_kind']='engineering_validation'
        self.invalid('comparator')

    def test_stored_capability_needs_review_trigger(self):
        del self.data['recommendations'][1]['review_trigger']
        self.invalid('review_trigger')

    def test_nonmechanical_narrative_is_not_empty(self):
        for block in self.data['directions'][0]['narrative']:
            block['evidence']=[]
        self.invalid('sourced narrative')

    def test_unknown_maturity_when_no_evidence(self):
        self.study['readiness'][0]['dimensions']['production']['status']='supported'
        self.invalid('maturity')

    def test_requires_all_readiness_dimensions(self):
        del self.study['readiness'][0]['dimensions']['durability']
        self.invalid('four dimensions')

    def test_history_cannot_use_a_different_source_location(self):
        self.data['timeline'][0]['locator']=self.data['timeline'][1]['locator']
        self.invalid('location')

    def test_future_date_is_not_history(self):
        self.data['timeline'][1]['date']='2030-01-01'
        self.invalid('Future events')

    def test_closest_requires_same_version(self):
        self.review['closest']['document_id']='EP4579134B1'
        self.invalid('candidate record')

    def test_tied_sources_keep_original_and_locator_together(self):
        self.review['equally_close']=[dict(self.review['closest'],document_id='EP1975516A1',evidence_id='E02',
                                          locator=self.data['evidence'][0]['location'])]
        page=render(self.data).split('<section class="chapter" id="s08"')[1].split('</section>')[0]
        self.assertEqual(page.count('尚待全文复核</h3>'),2)
        self.assertIn('EP1975516NWA1',page)

    def test_targeted_claim_visible_without_family_credit(self):
        page=render(self.data).split('<section class="chapter" id="s08"')[1].split('</section>')[0]
        self.assertIn('本方向的基本组合已经公开',page)
        self.assertIn('不适用（尚无全文复核样本）',page)
        self.assertIn('<dt>全文复核覆盖的同族</dt><dd>0 族</dd>',page)

    def test_localized_fact_must_match_a_specific_document(self):
        self.review['members'][1]['located_finding']['evidence_id']='E02'
        self.invalid('Located finding')

    def test_targeted_reading_does_not_count_as_full_text(self):
        self.member['direct']=True
        self.invalid('full-text')

    def test_direct_disclosure_must_reference_registered_location(self):
        self.data['records'][0]['reading']='complete'
        self.member.update(direct=True,locator='another place')
        self.invalid('reviewed publication')

    def test_count_families_independently_of_document_count(self):
        del self.review['uncounted_reason']
        for idx, m in enumerate(self.review['members']):
            m.update(family_id='F',family_basis='仅用于测试的优先权组',direct=bool(idx),
                     locator=self.data['evidence'][idx]['location'])
            self.data['records'][idx]['reading']='complete'
        validate(self.data)
        records={r['id']:r for r in self.data['records']}
        self.assertEqual(counts(self.review,records),(1,2,1,1))
        self.review['members'][1]['direct']=None
        self.assertEqual(counts(self.review,records),(1,2,1,None))

    def test_duplicate_document_not_counted_twice(self):
        extra=copy.deepcopy(self.data['records'][0])
        extra['id']='P3'
        self.data['records'].append(extra)
        self.review['members'].append(dict(self.member,record_id='P3'))
        self.invalid('publication version')

    def test_roadmap_dependency_cycle(self):
        self.study['roadmap'][0]['requires']=['N2']
        self.invalid('Cyclic')

    def test_reversed_window_is_invalid(self):
        self.study['roadmap'][0].update({'from':'2029','to':'2027'})
        self.invalid('Reversed')

    def test_elapsed_window_is_not_a_verified_outcome(self):
        self.study['roadmap'][0].update({'to':'2022'})
        self.assertIn('观察窗口已过，请复核',render(self.data))
        self.study['roadmap'][0]['outcome']='achieved'
        self.invalid('follow-up evidence')

    def test_progress_is_visible(self):
        self.data['method_support']['research_check']['status']='in_progress'
        self.assertIn('研究进行中',render(self.data))
