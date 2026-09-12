"""Corpus integrity checks only; these tests never generate model output."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from validate_evaluation_v3 import ROOT, event_sources, validate_corpus, validate_rows


class EvaluationV3IntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.development = [json.loads(line) for line in (ROOT / 'evaluation-v3/development.jsonl').read_text(encoding='utf-8').splitlines()]

    def test_distributed_corpus_has_valid_structure_and_distinct_sources(self):
        report = validate_corpus(ROOT / 'evaluation-v3')
        self.assertTrue(report['valid'], report['problems'])
        self.assertEqual(report['splits']['development']['rows'], 20)
        self.assertEqual(report['splits']['reserved']['rows'], 10)

    def test_revisited_heading_joins_only_its_own_source(self):
        labels, groups, headings = event_sources(
            'Date context before events.\nEVENT: Alpha\nFirst alpha detail.\n'
            'EVENT: Beta\nSeparate beta detail.\nEVENT: alpha\nLater alpha detail.')
        self.assertEqual(labels, ['Alpha', 'Beta'])
        self.assertEqual(headings, 3)
        self.assertIn('First alpha', groups['alpha'])
        self.assertIn('Later alpha', groups['alpha'])
        self.assertNotIn('beta detail', groups['alpha'])
        self.assertNotIn('Date context', '\n'.join(groups.values()))

    def test_unlabeled_text_is_not_invented_as_explicit_events(self):
        labels, groups, headings = event_sources('Two notes mention different desks, but their relationship is unknown.')
        self.assertEqual((labels, groups, headings), ([], {}, 0))

    def test_duplicate_source_ignores_whitespace_and_case(self):
        rows = copy.deepcopy(self.development)
        rows[1]['source_text'] = '  ' + rows[0]['source_text'].upper().replace('\n', '   ') + '  '
        problems, _ = validate_rows(rows, 'development', 20)
        self.assertTrue(any('duplicate normalized source' in problem for problem in problems))

    def test_label_count_and_check_target_must_match_source(self):
        rows = copy.deepcopy(self.development)
        rows[0]['expectations']['event_count'] = 9
        rows[0]['expectations']['expected_event_labels'] = ['Another label']
        rows[0]['expectations']['checks'][0]['event_label'] = 'Nonexistent event'
        problems, _ = validate_rows(rows, 'development', 20)
        self.assertTrue(any('event_count' in problem for problem in problems))
        self.assertTrue(any('expected labels' in problem for problem in problems))
        self.assertTrue(any('invalid event_label' in problem for problem in problems))

    def test_required_fragment_cannot_belong_only_to_another_event(self):
        rows = copy.deepcopy(self.development)
        rows[0]['expectations']['checks'][0]['required_fragments'] = ['LABEL-55']
        problems, _ = validate_rows(rows, 'development', 20)
        self.assertTrue(any('requires a fragment absent from its event source' in problem for problem in problems))

    def test_mode_assistance_confounds_are_detected_per_domain(self):
        rows = copy.deepcopy(self.development)
        rows[1]['assist'] = True
        problems, _ = validate_rows(rows, 'development', 20)
        self.assertTrue(any('maintenance_paperwork must cover all four' in problem for problem in problems))

    def test_inconsistent_and_empty_lexical_checks_are_rejected(self):
        rows = copy.deepcopy(self.development)
        rows[0]['expectations']['checks'][0]['forbidden_fragments'] = ['SERVICE-318']
        rows[0]['expectations']['checks'][1]['required_fragments'] = []
        rows[0]['expectations']['checks'][1]['forbidden_fragments'] = []
        problems, _ = validate_rows(rows, 'development', 20)
        self.assertTrue(any('conflicting fragments' in problem for problem in problems))
        self.assertTrue(any('no lexical expectation' in problem for problem in problems))

    def test_invalid_schema_does_not_echo_reserved_content(self):
        problems, _ = validate_rows([{'id': 'reserved-v3-test-01', 'source_text': 'OPAQUE CONTENT MARKER'}], 'reserved', 10)
        self.assertTrue(any('schema error' in problem for problem in problems))
        self.assertNotIn('OPAQUE CONTENT MARKER', '\n'.join(problems))

    def test_development_requires_two_substantive_long_notes(self):
        rows = copy.deepcopy(self.development)
        for row in rows:
            row['source_text'] = row['source_text'][:500]
        problems, _ = validate_rows(rows, 'development', 20)
        self.assertTrue(any('at least two substantive notes' in problem for problem in problems))

    def test_cross_split_overlap_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for split in ('development', 'reserved'):
                (directory / f'{split}.jsonl').write_bytes((ROOT / f'evaluation-v3/{split}.jsonl').read_bytes())
            rows = [json.loads(line) for line in (directory / 'reserved.jsonl').read_text(encoding='utf-8').splitlines()]
            rows[0]['source_text'] = self.development[0]['source_text']
            (directory / 'reserved.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
            report = validate_corpus(directory)
            self.assertFalse(report['valid'])
            self.assertTrue(any('source overlaps development' in problem for problem in report['problems']))

    def test_report_contains_metadata_and_no_note_text(self):
        report = validate_corpus(ROOT / 'evaluation-v3')
        text = json.dumps(report)
        self.assertNotIn('source_text', text)
        self.assertNotIn('required_fragments', text)
        self.assertNotIn(self.development[0]['source_text'], text)
        self.assertIn('sha256', report['splits']['reserved'])


if __name__ == '__main__':
    unittest.main()
