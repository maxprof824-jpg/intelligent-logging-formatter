import unittest
import json
from pathlib import Path
import tempfile
from core import ROOT
from evaluate_v2 import artifact_hashes, new_run_name, reserve_report_paths
from summarize_v2 import write_summary


class EvaluationEntrypointTests(unittest.TestCase):
    def test_fingerprints_match_files_in_distributed_source(self):
        result=artifact_hashes(None,ROOT/'data-v2/acceptance.jsonl')
        self.assertIn('app_v2.py',result['code'])
        self.assertIn('evidence_checks.py',result['code'])
        self.assertIn('source_coverage.py',result['code'])
        self.assertNotIn('app.py',result['code'])
        self.assertTrue(all(len(digest)==64 for digest in result['code'].values()))


class EvaluationReportProtectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.reports = Path(self.temporary.name)

    def test_default_run_names_are_distinct_and_identify_model_kind(self):
        names = {new_run_name() for _ in range(20)}
        self.assertEqual(len(names), 20)
        self.assertTrue(all(name.startswith('adapter-v2-') for name in names))
        self.assertTrue(new_run_name(base=True).startswith('base-v2-'))

    def test_each_existing_artifact_blocks_run_without_touching_files(self):
        for suffix in ('-acceptance.jsonl', '-acceptance-metrics.json', '-acceptance.md'):
            with self.subTest(suffix=suffix):
                existing = self.reports / ('original' + suffix)
                existing.write_text('historical evidence', encoding='utf-8')
                with self.assertRaisesRegex(FileExistsError, '--overwrite'):
                    reserve_report_paths(self.reports, 'original')
                self.assertEqual(existing.read_text(encoding='utf-8'), 'historical evidence')
                self.assertEqual(list(self.reports.iterdir()), [existing])
                existing.unlink()

    def test_new_run_reserves_files_and_explicit_overwrite_reuses_paths(self):
        paths = reserve_report_paths(self.reports, 'new-run')
        for path in paths:
            path.write_text('saved evidence', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            reserve_report_paths(self.reports, 'new-run')
        self.assertEqual(reserve_report_paths(self.reports, 'new-run', overwrite=True), paths)
        self.assertTrue(all(path.read_text(encoding='utf-8') == 'saved evidence' for path in paths))

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(ValueError):
            reserve_report_paths(self.reports, '../outside')
        self.assertEqual(list(self.reports.iterdir()), [])

    def fixture(self, **updates):
        metrics = {'run_name': 'sample', 'selected_cases': 1, 'attempted_cases': 1, 'remaining_cases': 0,
                   'run_complete': True, 'selected_ids': ['case-one'], 'base_model_only': True,
                   'mode': 'draft', 'assist': False,
                   'complete_valid_results': {'numerator': 1, 'denominator': 1},
                   'raw_coaching_output_schema_validity': {'numerator': 0, 'denominator': 0}}
        metrics.update(updates)
        (self.reports / 'sample-acceptance-metrics.json').write_text(json.dumps(metrics), encoding='utf-8')
        row = {'id': 'case-one', 'raw_result': {'schema_version': 'test-runtime'}, 'checks': {'failures': []}}
        (self.reports / 'sample-acceptance.jsonl').write_text(json.dumps(row) + '\n', encoding='utf-8')

    def test_summary_uses_selected_run_and_never_claims_old_results(self):
        self.fixture()
        path = write_summary('sample', reports=self.reports)
        text = path.read_text(encoding='utf-8')
        self.assertIn('1/1', text)
        self.assertIn('test-runtime', text)
        self.assertIn('Base model without an adapter', text)
        self.assertIn('No scored items', text)
        self.assertNotIn('18/18', text)
        self.assertNotIn('2,005', text)
        self.assertNotIn('v2.1', text)

    def test_summary_refuses_incomplete_or_mismatched_run(self):
        for updates in ({'run_complete': False}, {'selected_ids': ['another-case']}, {'run_name': 'other'}):
            with self.subTest(updates=updates):
                self.fixture(**updates)
                with self.assertRaises(RuntimeError):
                    write_summary('sample', reports=self.reports)
                self.assertFalse((self.reports / 'sample-acceptance.md').exists())

    def test_summary_preserves_existing_file_unless_explicit_overwrite(self):
        self.fixture()
        path = self.reports / 'sample-acceptance.md'
        path.write_text('old summary', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            write_summary('sample', reports=self.reports)
        self.assertEqual(path.read_text(encoding='utf-8'), 'old summary')
        write_summary('sample', overwrite=True, reports=self.reports)
        self.assertIn('test-runtime', path.read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
