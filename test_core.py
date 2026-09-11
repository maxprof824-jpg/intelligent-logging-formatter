import json
import unittest
from core import ROOT, FIELDS, parse_output, review, render_log
from build_data import blank, tests

class GuardrailTests(unittest.TestCase):
    def test_fabricated_values_are_suppressed(self):
        r = blank('equipment_error')
        r.update(situation='A display error occurred', impact='No impact', agencies_contacted='Agency (AB)')
        checked = review(r, 'A display error occurred')
        self.assertIsNone(checked['record']['impact'])
        self.assertIsNone(checked['record']['agencies_contacted'])
        self.assertIn('impact', checked['missing_fields'])
        self.assertEqual(checked['status'], 'needs_details')

    def test_incomplete_time_and_initials(self):
        r = blank('conversation')
        r.update(situation='14:05: a conversation occurred', agencies_contacted='Fictional scheduling office')
        checked = review(r, '\n'.join(v for v in r.values() if v))
        self.assertTrue(any('date' in issue for issue in checked['issues']))
        self.assertTrue(any('time zone' in issue for issue in checked['issues']))
        self.assertTrue(any('initials' in issue for issue in checked['issues']))

    def test_complete_examples_and_explicit_none(self):
        for i in [8, 20, 21]:
            row = tests()[i]
            checked = review(row['expected'], row['source_text'])
            self.assertEqual(checked['status'], 'ready_for_human_review', checked)
            self.assertTrue(checked['human_approval_required'])

    def test_omitted_time_flagged(self):
        r = blank('equipment_error')
        r['situation'] = '2026-10-03 08:10 UTC: error occurred'
        result = review(r, r['situation'] + '. 08:20 UTC: a reply arrived')
        self.assertTrue(any('not retained' in x for x in result['issues']))

    def test_invalid_json_and_extra_fields_rejected(self):
        with self.assertRaises(Exception): parse_output('```json\n{}\n```')
        r = blank(); r['invented_field'] = 'x'
        with self.assertRaises(Exception): parse_output(json.dumps(r))

    def test_explicit_unknown_stays_visible_and_needs_followup(self):
        r = blank('equipment_error')
        r.update(situation='2026-10-03 08:10 UTC: error occurred', impact='Impact not yet assessed',
                 agencies_contacted='None contacted', action='Ticket opened', plan='Owner and due time unknown')
        source = '\n'.join(r[f] for f in FIELDS)
        result = review(r, source)
        self.assertEqual(result['record']['impact'], 'Impact not yet assessed')
        self.assertEqual(result['status'], 'needs_details')
        self.assertTrue(any('IMPACT' in x for x in result['issues']))
        self.assertTrue(any('PLAN' in x for x in result['issues']))

    def test_sections_match_user_format(self):
        result = review(blank(), '')
        output = render_log(result)
        for header in ['SITUATION (With times of particular events):', 'IMPACT:', 'AGENCIES CONTACTED (W/Initials):', 'ACTION:', 'PLAN:']:
            self.assertIn(header, output)
        self.assertEqual(len(result['questions']), 5)

    def test_source_split_and_targets(self):
        seen = set()
        for split in ['train', 'validation', 'test']:
            for line in (ROOT/f'data/{split}.jsonl').read_text(encoding='utf-8').splitlines():
                row = json.loads(line)
                self.assertNotIn(row['source_text'], seen)
                seen.add(row['source_text'])
                parse_output(json.dumps(row['expected']))
                for field in FIELDS:
                    self.assertTrue(row['expected'][field] is None or row['expected'][field] in row['source_text'])

if __name__ == '__main__': unittest.main()
