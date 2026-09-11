"""CPU-only dataset integrity and authoring regressions; no evaluation corpus access."""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import build_data_v3 as builder


class SyntheticCurriculumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(builder.__file__).resolve().parent
        cls.splits={split:[json.loads(line) for line in (cls.root/'data-v3'/f'{split}.jsonl').read_text(encoding='utf-8').splitlines()]
                    for split in ('train','validation')}
        cls.report=json.loads((cls.root/'data-v3/BUILD-REPORT.json').read_text(encoding='utf-8'))

    def test_actual_counts_and_per_family_task_mode_balance(self):
        expected={'train':{'main':600,'helper':120},'validation':{'main':120,'helper':24}}
        for split,rows in self.splits.items():
            self.assertEqual(Counter(row['task'] for row in rows),expected[split])
            groups=defaultdict(Counter)
            for row in rows:groups[(row['scenario_family'],row['task'])][row['mode']]+=1
            self.assertTrue(all(counts['draft']==counts['review']>0 for counts in groups.values()))
        builder.validate_splits(self.splits)

    def test_every_written_target_follows_its_live_prompt_and_evidence_contract(self):
        for rows in self.splits.values():
            for row in rows:
                with self.subTest(id=row['id']):builder.validate_target(row)

    def test_full_chat_budget_and_long_source_coverage_are_reported(self):
        for rows in self.splits.values():
            self.assertTrue(all(0<row['token_count']<=4096 for row in rows))
            long=[row for row in rows if row['scenario_family'] in builder.LONG_FAMILIES]
            self.assertTrue(long)
            self.assertTrue(all(2000<=row['source_token_count']<=2200 for row in long))
            # Later event evidence must appear after substantial background,
            # rather than always being collected at the beginning of a note.
            for row in long:
                if row['task']!='main':continue
                latest=max(row['source_text'].rfind(q) for facts in row['expected']['sections'].values() for item in facts for q in item['evidence'])
                self.assertGreater(latest,len(row['source_text'])*.8)

    def test_saved_hashes_match_dataset_and_generator(self):
        for name,digest in self.report['sha256'].items():
            self.assertEqual(hashlib.sha256((self.root/'data-v3'/name).read_bytes()).hexdigest(),digest)
        self.assertEqual(hashlib.sha256(Path(builder.__file__).read_bytes()).hexdigest(),self.report['generator_sha256'])
        self.assertEqual(self.report['failed_target_checks'],0)

    def test_helper_focus_is_balanced_across_modes_inside_each_family(self):
        for rows in self.splits.values():
            groups=defaultdict(Counter)
            for row in rows:
                if row['task']=='helper':
                    focus=tuple(json.loads(row['messages'][1]['content'])['focus_sections'])
                    groups[(row['scenario_family'],focus)][row['mode']]+=1
            self.assertTrue(all(counts['draft']==counts['review'] for counts in groups.values()))

    def test_known_no_impact_and_no_followup_have_no_new_suggestions(self):
        for family in ('visitor_desk_actual_no_impact','warehouse_count_correction'):
            rows=[row for row in self.splits['train'] if row['scenario_family']==family]
            self.assertTrue(rows)
            self.assertTrue(all(not row['expected']['suggestions'] for row in rows))
            helpers=[row for row in rows if row['task']=='helper']
            self.assertTrue(all(json.loads(row['messages'][1]['content'])['existing_log_facts_context']['plan'] for row in helpers))

    def test_promised_requests_are_not_treated_as_existing_completed_requests(self):
        for family in ('service_desk_promised_not_done','recreation_signoff_retracted'):
            rows=[row for values in self.splits.values() for row in values if row['scenario_family']==family]
            self.assertTrue(rows)
            for row in rows:
                for item in row['expected']['suggestions']:
                    self.assertNotIn('existing request',item['text'])

    def test_unassessed_labeling_suggestions_do_not_presuppose_impact(self):
        rows=[row for row in self.splits['train'] if row['scenario_family']=='office_unknown_impact']
        plans=[item for row in rows for item in row['expected']['suggestions'] if item['section']=='plan']
        self.assertTrue(plans)
        for item in plans:
            self.assertIn('whether any labeling work was affected',item['text'])
            self.assertIn('whether any labeling work was affected',item['confirm'])
            self.assertNotIn('the affected labeling work',item['text'])

    def test_long_parks_comparison_is_a_completed_action_with_actor_and_time(self):
        row=next(row for row in self.splits['validation'] if row['id']=='validation-v3-main-parks_amendment_long-010')
        sections=row['expected']['sections']
        comparisons=[item for item in sections['action'] if 'compared the original amendment question' in item['text']]
        self.assertEqual(len(comparisons),1)
        self.assertTrue(comparisons[0]['text'].startswith('07:19Z Avery compared'))
        self.assertFalse(any('compared the original amendment question' in item['text'] for item in sections['situation']))

    def test_long_record_opening_and_comparison_are_actions_without_duplicate_facts(self):
        families={'archive_accession_long','facilities_booking_long','college_attendance_long','museum_loan_long'}
        for row in self.splits['train']:
            if row['task']!='main' or row['scenario_family'] not in families:continue
            with self.subTest(id=row['id']):
                sections=row['expected']['sections']
                self.assertEqual(len(sections['action']),3)
                self.assertEqual(sum('opened the ' in item['text'] for item in sections['action']),1)
                self.assertEqual(sum('compared the source paperwork' in item['text'] for item in sections['action']),1)
                self.assertEqual(sum('confirmed the discrepancy' in item['text'] for item in sections['action']),1)
                self.assertFalse(any('opened the ' in item['text'] or 'compared the source paperwork' in item['text'] for item in sections['situation']))

    def test_library_reference_check_is_an_action_and_keeps_uncertainty(self):
        rows=[row for row in self.splits['validation'] if row['task']=='main' and row['scenario_family']=='library_request_long']
        for row in rows:
            actions=row['expected']['sections']['action']
            findings=[item for item in actions if 'found one reference' in item['text']]
            self.assertEqual(len(findings),1)
            self.assertIn('neither was confirmed as the current reference',findings[0]['text'])

    def test_factual_quote_not_in_source_is_rejected(self):
        row=deepcopy(next(row for row in self.splits['train'] if row['task']=='main'))
        fact=next(item for items in row['expected']['sections'].values() for item in items)
        fact['evidence']=['A fabricated source sentence.']
        row['messages'][-1]['content']=json.dumps(row['expected'])
        with self.assertRaisesRegex(ValueError,'Factual evidence absent'):builder.validate_target(row)

    def test_proposal_in_factual_sections_is_rejected(self):
        row=deepcopy(next(row for row in self.splits['train'] if row['task']=='main'))
        fact=next(item for items in row['expected']['sections'].values() for item in items)
        fact['text']='Consider inventing a completed action.'
        row['messages'][-1]['content']=json.dumps(row['expected'])
        with self.assertRaisesRegex(ValueError,'suggestion in factual section'):builder.validate_target(row)

    def test_helper_cannot_ignore_requested_sections(self):
        story=builder.create_story('service_desk_promised_not_done',120,'train','helper','draft')
        row=builder.pack(story,story.source())
        row['expected']['suggestions'][0]['section']='plan'
        row['messages'][-1]['content']=json.dumps(row['expected'])
        with self.assertRaisesRegex(ValueError,'outside requested section'):builder.validate_target(row)

    def test_generator_rejects_an_unverified_tokenizer(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'pinned base tokenizer'):builder.verify_tokenizer(Path(temp))

    def test_identity_stripped_diagnostics_reveal_template_reuse(self):
        report=self.report['overlap_diagnostics']
        self.assertEqual(report['exact_identity_stripped_cross_split_overlap'],0)
        self.assertLess(report['unique_identity_stripped_sources']['train'],len(self.splits['train']))
        self.assertGreater(report['validation_nearest_train_jaccard']['max'],.5)


if __name__=='__main__':unittest.main()
