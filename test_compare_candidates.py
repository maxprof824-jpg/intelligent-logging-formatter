"""CPU protocol checks with tiny local fixtures; no weights or reserved corpus read."""
from contextlib import contextmanager, ExitStack
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import compare_candidates as compare
import core


def fixture_case(case_id='fixture-a', mode='draft', assist=True):
    return {'id': case_id, 'domain': 'fictional office', 'mode': mode, 'assist': assist,
            'source_text': 'EVENT: A\nDelay unknown.\nEVENT: B\nNo delay.',
            'expectations': {'event_count': 2, 'expected_event_labels': ['A', 'B'],
                             'checks': [{'event_label': 'B', 'section': 'impact',
                                         'required_fragments': ['No delay.'],
                                         'forbidden_fragments': ['Delay unknown.']}]}}


def inner_result(source):
    text = source.strip()
    return {'event_type': 'other',
            'sections': {field: [{'text': text, 'evidence': [text]}] if field == 'impact' else []
                         for field in core.FIELDS},
            'suggestions': [], 'questions': [], 'issues': [], 'review_excerpts': [],
            'missing_fields': [field for field in core.FIELDS if field != 'impact'],
            'status': 'needs_confirmation', 'human_approval_required': True,
            'chunk_count': 1, 'source_tokens': 5, 'raw_outputs': ['fixture JSON']}


class Parameter:
    def __init__(self): self.requires_grad = True
    def requires_grad_(self, value): self.requires_grad = value


class FakeModel:
    def __init__(self):
        self.weights = [Parameter(), Parameter(), Parameter()]
        self.active = None
        self.disabled = False
        self.training = True
        self.freeze_calls = []

    def set_requires_grad(self, names, value): self.freeze_calls.append((names, value))
    def parameters(self): return self.weights
    def eval(self): self.training = False

    def set_adapter(self, name):
        self.active = name
        # PEFT deliberately enables an adapter's gradients on selection.
        self.weights[1].requires_grad = True

    def get_model_status(self):
        return SimpleNamespace(active_adapters=[self.active], enabled=not self.disabled,
                               available_adapters=list(compare.ADAPTER_NAMES), merged_adapters=[],
                               requires_grad={name: False for name in compare.ADAPTER_NAMES},
                               trainable_params=sum(p.requires_grad for p in self.parameters()))

    @contextmanager
    def disable_adapter(self):
        previous = self.disabled
        self.disabled = True
        try: yield
        finally: self.disabled = previous


class CandidateProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'evaluation-v3').mkdir()
        self.rows = [fixture_case(), fixture_case('fixture-b', 'review', False)]
        self.write_rows(self.rows)

    def write_rows(self, rows, split='development'):
        path = self.root / 'evaluation-v3' / (split + '.jsonl')
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
        return path

    def args(self, **overrides):
        values = dict(output=self.root / 'comparison.json', split='development', case=None,
                      design_frozen=False, model_dir=self.root / 'model',
                      current_adapter=self.root / 'v2', candidate_adapter=self.root / 'v3')
        return SimpleNamespace(**(values | overrides))

    def test_selection_is_exact_subset_in_dataset_order(self):
        path = self.write_rows(self.rows + [fixture_case('fixture-c')])
        rows, info = compare.select_cases(self.root, case_ids=['fixture-b', 'fixture-a'])
        self.assertEqual([row['id'] for row in rows], ['fixture-a', 'fixture-b'])
        self.assertFalse(info['full_split_selected'])
        self.assertEqual(info['split_case_count'], 3)
        self.assertEqual(info['dataset_sha256'], compare.digest(path))
        for ids in (['unknown'], ['fixture-a', 'fixture-a']):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                compare.select_cases(self.root, case_ids=ids)

    def test_reserved_gate_checks_before_opening_any_file(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('Must not read')):
            with self.assertRaisesRegex(ValueError, 'design-frozen'):
                compare.select_cases(self.root, split='reserved')
            with self.assertRaisesRegex(ValueError, 'complete split'):
                compare.select_cases(self.root, split='reserved', design_frozen=True, case_ids=['x'])

    def test_reserved_explicit_ack_uses_only_temporary_fixture(self):
        self.write_rows([fixture_case('reserved-fixture-only')], split='reserved')
        rows, info = compare.select_cases(self.root, 'reserved', design_frozen=True)
        self.assertEqual(rows[0]['id'], 'reserved-fixture-only')
        self.assertTrue(info['design_frozen_acknowledged'])
        self.assertTrue(info['full_split_selected'])

    def test_base_disable_restores_after_exception_and_every_parameter_is_frozen(self):
        model = FakeModel()
        models = compare.MatchedModels(model, 'tokenizer')
        with self.assertRaisesRegex(RuntimeError, 'generation failed'):
            with models.activate('base') as selected:
                self.assertIs(selected, model)
                self.assertTrue(model.disabled)
                self.assertFalse(model.training)
                self.assertFalse(any(p.requires_grad for p in model.parameters()))
                raise RuntimeError('generation failed')
        self.assertFalse(model.disabled)
        for name in ('candidate_v3', 'current_v2', 'base'):
            with models.activate(name):
                self.assertEqual(model.disabled, name == 'base')
                self.assertEqual(model.active, 'current_v2' if name == 'base' else name)
                self.assertFalse(any(p.requires_grad for p in model.parameters()))
        self.assertTrue(all(names == list(compare.ADAPTER_NAMES) and not enabled
                            for names, enabled in model.freeze_calls))
        with self.assertRaises(ValueError):
            with models.activate('unrecognized'): pass

    def mock_run(self, args, process=None, loader=None):
        model = FakeModel()
        models = compare.MatchedModels(model, 'fixture-tokenizer')
        loaded = loader or Mock(return_value=models)
        fingerprints = {'runtime_commit': compare.FROZEN_COMMIT, 'generation_code_sha256': {'g': 'sha-g'},
                        'scoring_code_sha256': {'s': 'sha-s'}, 'comparison_code_sha256': 'sha-c'}
        with ExitStack() as stack:
            stack.enter_context(patch.object(compare, 'DEVELOPMENT_DATA_SHA256', compare.digest(self.root / 'evaluation-v3/development.jsonl')))
            stack.enter_context(patch.object(compare, 'runtime_fingerprints', return_value=fingerprints))
            stack.enter_context(patch.object(compare, 'adapter_fingerprint', return_value={'adapter_config_sha256': 'sha-a'}))
            stack.enter_context(patch.object(compare, 'model_fingerprint', return_value={'base_config_sha256': 'sha-b', 'tokenizer_sha256': 'sha-t'}))
            stack.enter_context(patch('coach.process_note', side_effect=lambda m, t, source, *args, **kwargs: inner_result(source)))
            if process:
                stack.enter_context(patch.object(compare.event_formatter, 'process_note', side_effect=process))
            printed = stack.enter_context(patch('builtins.print'))
            report = compare.run_comparison(args, loader=loaded, root=self.root)
        return report, loaded, printed

    def test_matched_variants_keep_exact_inputs_and_source_validation(self):
        (self.root / 'reports').mkdir()
        protocol = self.root / 'reports/V3-CANDIDATE-PROTOCOL.md'
        protocol.write_text('Frozen synthetic fixture protocol.', encoding='utf-8')
        seen = []
        original = compare.event_formatter.process_note
        def generate(model, tokenizer, source, **kwargs):
            seen.append((model.disabled, model.active, source, kwargs['mode'], kwargs['assist']))
            return original(model, tokenizer, source, **kwargs)
        report, loader, printed = self.mock_run(self.args(), generate)
        self.assertEqual(loader.call_count, 1)
        self.assertEqual(len(report['outputs']), 6)
        self.assertEqual(report['selection_scope'], 'full_development')
        self.assertTrue(report['complete'])
        self.assertEqual(report['expected_case_variant_pairs'], 6)
        self.assertEqual(report['protocol_files_sha256']['reports/V3-CANDIDATE-PROTOCOL.md'], compare.digest(protocol))
        for index, row in enumerate(self.rows):
            records = report['outputs'][index * 3:index * 3 + 3]
            self.assertEqual([r['model_variant'] for r in records], list(compare.MODEL_VARIANTS))
            for result in records:
                self.assertEqual(result['variant'], 'events')
                self.assertEqual(result['source_text'], row['source_text'])
                self.assertEqual((result['mode'], result['assist']), (row['mode'], row['assist']))
                self.assertTrue(result['checks']['complete_structured_output'])
                self.assertEqual(result['checks']['event_quote_issues'], [])
                self.assertEqual(result['expected_model_state'], result['observed_model_state'])
                self.assertIn('EVENT: B', result['draft'])
            expected = [(True, 'current_v2'), (False, 'current_v2'), (False, 'candidate_v3')]
            self.assertEqual([item[:2] for item in seen[index * 3:index * 3 + 3]], expected)
            self.assertTrue(all(item[2:] == (row['source_text'], row['mode'], row['assist'])
                                for item in seen[index * 3:index * 3 + 3]))
        self.assertTrue(all(call.kwargs.get('flush') for call in printed.call_args_list))
        self.assertTrue(any(call.args[0] == 'PROGRESS' for call in printed.call_args_list))
        self.assertEqual(json.loads(self.args().output.read_text(encoding='utf-8')), report)
        self.assertFalse(list(self.root.glob('*.tmp-*')))

    def test_failure_keeps_partial_result_and_does_not_cancel_other_variants(self):
        original = compare.event_formatter.process_note
        def generate(model, tokenizer, source, **kwargs):
            if not model.disabled and model.active == 'current_v2':
                error = RuntimeError('synthetic failure')
                error.result = {'event_results': [None], 'raw_outputs': ['malformed fixture']}
                raise error
            return original(model, tokenizer, source, **kwargs)
        report, _, _ = self.mock_run(self.args(case=['fixture-a']), generate)
        self.assertEqual(report['selection_scope'], 'subset_of_development')
        self.assertEqual(report['selected_ids'], ['fixture-a'])
        self.assertTrue(report['complete'])  # All planned attempts, not all successes.
        self.assertEqual(len(report['outputs']), 3)
        bad = report['outputs'][1]
        self.assertIn('synthetic failure', bad['error'])
        self.assertEqual(bad['result']['raw_outputs'], ['malformed fixture'])
        self.assertFalse(bad['checks']['complete_structured_output'])
        self.assertEqual(report['summary']['current_v2']['malformed_or_missing_group_count'], 2)
        self.assertFalse(report['summary']['current_v2']['group_accounting_complete'])
        self.assertTrue(report['outputs'][2]['checks']['complete_structured_output'])
        self.assertEqual(report['summary']['candidate_v3']['pending_ids'], [])

    def test_group_failures_and_untrustworthy_group_statuses_remain_separate(self):
        original = compare.event_formatter.process_note
        def generate(model, tokenizer, source, **kwargs):
            result = original(model, tokenizer, source, **kwargs)
            if not model.disabled and model.active == 'current_v2':
                result['event_results'][1]['result']['status'] = 'incomplete_draft'
                result['event_results'][1]['result']['issues'].append('One source chunk failed.')
            elif model.active == 'candidate_v3':
                result['event_results'][0]['source_segments'] = []
            return result
        report, _, _ = self.mock_run(self.args(case=['fixture-a']), generate)
        base, current, candidate = [report['summary'][name] for name in compare.MODEL_VARIANTS]
        self.assertEqual(base['failed_or_incomplete_group_count'], 0)
        self.assertTrue(base['group_accounting_complete'])
        self.assertEqual(current['failed_or_incomplete_group_count'], 1)
        self.assertEqual(current['failed_or_incomplete_groups'][0]['label'], 'B')
        self.assertEqual(current['malformed_or_missing_group_count'], 0)
        self.assertEqual(candidate['malformed_or_missing_group_count'], 1)
        self.assertEqual(candidate['malformed_or_missing_groups'][0]['label'], 'A')
        self.assertFalse(candidate['group_accounting_complete'])

    def test_malformed_group_status_does_not_abort_later_variants(self):
        original = compare.event_formatter.process_note
        def generate(model, tokenizer, source, **kwargs):
            result = original(model, tokenizer, source, **kwargs)
            if model.disabled: result['event_results'][0]['result']['status'] = []
            return result
        report, _, _ = self.mock_run(self.args(case=['fixture-a']), generate)
        self.assertTrue(report['complete'])
        self.assertEqual(report['summary']['base']['malformed_or_missing_group_count'], 1)
        self.assertTrue(report['outputs'][2]['checks']['complete_structured_output'])

    def test_changed_development_data_is_rejected_before_model_loading(self):
        loader = Mock()
        with self.assertRaisesRegex(ValueError, 'Development data differs'):
            compare.run_comparison(self.args(), loader=loader, root=self.root)
        loader.assert_not_called()
        self.assertFalse(self.args().output.exists())

    def test_wrong_observed_adapter_state_prevents_generation(self):
        model = FakeModel()
        models = compare.MatchedModels(model, 'fixture-tokenizer')
        snapshot = models.snapshot
        def wrong_snapshot(): return snapshot() | {'adapters_enabled': True}
        models.snapshot = wrong_snapshot
        seen = []
        original = compare.event_formatter.process_note
        def generate(model, tokenizer, source, **kwargs):
            seen.append(model.disabled)
            return original(model, tokenizer, source, **kwargs)
        report, _, _ = self.mock_run(self.args(case=['fixture-a']), generate, Mock(return_value=models))
        self.assertEqual(seen, [False, False])
        self.assertIn('Observed adapter', report['outputs'][0]['error'])
        self.assertNotEqual(report['outputs'][0]['expected_model_state'], report['outputs'][0]['observed_model_state'])

    def test_interruption_preserves_completed_pairs_and_pending_coverage(self):
        original = compare.event_formatter.process_note
        def generate(model, tokenizer, source, **kwargs):
            if not model.disabled: raise KeyboardInterrupt('fixture interruption')
            return original(model, tokenizer, source, **kwargs)
        with self.assertRaises(KeyboardInterrupt): self.mock_run(self.args(), generate)
        report = json.loads(self.args().output.read_text(encoding='utf-8'))
        self.assertFalse(report['complete'])
        self.assertEqual(report['status'], 'interrupted')
        self.assertEqual(len(report['outputs']), 1)
        self.assertEqual(report['summary']['base']['pending_ids'], ['fixture-b'])
        self.assertEqual(report['summary']['current_v2']['pending_ids'], ['fixture-a', 'fixture-b'])

    def test_loading_failure_is_recorded_without_claiming_attempts(self):
        loader = Mock(side_effect=RuntimeError('fixture load failure'))
        with self.assertRaisesRegex(RuntimeError, 'load failure'): self.mock_run(self.args(), loader=loader)
        report = json.loads(self.args().output.read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'loading_failed')
        self.assertFalse(report['complete'])
        self.assertEqual(report['outputs'], [])
        self.assertEqual(report['summary']['base']['attempted'], 0)

    def test_existing_report_is_never_opened_for_replacement(self):
        args = self.args()
        args.output.write_bytes(b'original report')
        loader = Mock()
        with self.assertRaises(FileExistsError): self.mock_run(args, loader=loader)
        self.assertEqual(args.output.read_bytes(), b'original report')
        loader.assert_not_called()


class CandidateFingerprintTests(unittest.TestCase):
    def test_installed_peft_named_load_and_disable_context_on_tiny_cpu_model(self):
        try:
            import torch
            from peft import LoraConfig, get_peft_model
            from transformers import GPT2Config, GPT2LMHeadModel
        except ImportError as error:
            self.skipTest('Optional installed-PEFT CPU integration check: ' + str(error))
        # This randomly initialized 8-wide model stays on CPU. No downloaded
        # weights, tokenizer, inference call, or real evaluation cases are used.
        base = GPT2LMHeadModel(GPT2Config(n_layer=1, n_embd=8, n_head=2, n_positions=16, vocab_size=16)).cpu()
        def config():
            return LoraConfig(task_type='CAUSAL_LM', target_modules=['c_attn'], r=2,
                              lora_alpha=4, bias='none', fan_in_fan_out=True)
        model = get_peft_model(base, config(), adapter_name='current_v2')
        model.add_adapter('candidate_v3', config())
        with tempfile.TemporaryDirectory() as temporary:
            model.save_pretrained(temporary)
            for name in compare.ADAPTER_NAMES:
                loaded = model.load_adapter(str(Path(temporary) / name), adapter_name=name,
                                            is_trainable=False, local_files_only=True, torch_device='cpu')
                self.assertEqual(loaded.missing_keys, [])
                self.assertEqual(loaded.unexpected_keys, [])
        models = compare.MatchedModels(model, None)
        for name in compare.MODEL_VARIANTS:
            with models.activate(name):
                self.assertEqual(models.snapshot(), compare.expected_state(name))
                self.assertTrue(all(parameter.device.type == 'cpu' for parameter in model.parameters()))
        with self.assertRaises(RuntimeError):
            with models.activate('base'): raise RuntimeError('fixture interrupted')
        self.assertTrue(models.snapshot()['adapters_enabled'])

    def test_release_generation_hashes_match_and_modified_source_is_rejected(self):
        fingerprints = compare.runtime_fingerprints()
        self.assertEqual(fingerprints['runtime_normalized_sha256'], compare.FROZEN_RUNTIME)
        self.assertIn('evaluate_events.py', fingerprints['scoring_code_sha256'])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in compare.GENERATION_FILES:
                (root / name).write_bytes((core.ROOT / name).read_bytes())
            (root / 'coach.py').write_text('changed runtime', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'coach.py'): compare.runtime_fingerprints(root)

    def test_adapter_weight_config_and_training_data_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            weights = root / 'adapter_model.safetensors'
            weights.write_bytes(b'fixture weights only')
            config = {'peft_type': 'LORA', 'task_type': 'CAUSAL_LM', 'bias': 'none', 'r': 16}
            config_path = root / 'adapter_config.json'
            config_path.write_text(json.dumps(config), encoding='utf-8')
            (root / 'training-config.json').write_text(json.dumps({'train_sha256': 'train-sha'}), encoding='utf-8')
            recorded = compare.adapter_fingerprint(root)
            self.assertEqual(recorded['adapter_model_sha256'], compare.digest(weights))
            self.assertEqual(recorded['adapter_config_sha256'], compare.digest(config_path))
            self.assertEqual(recorded['training_data_sha256'], {'train_sha256': 'train-sha'})
            for modification in ({'bias': 'all'}, {'lora_bias': True}, {'modules_to_save': ['lm_head']},
                                 {'layer_replication': [[0, 1]]}, {'use_dora': True},
                                 {'init_lora_weights': 'olora'}, {'init_lora_weights': 'pissa'}):
                with self.subTest(modification=modification):
                    config_path.write_text(json.dumps(config | modification), encoding='utf-8')
                    with self.assertRaises(ValueError): compare.adapter_fingerprint(root)

    def test_base_manifest_verifies_actual_config_tokenizer_and_weights(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = root / 'model'; model.mkdir()
            files = []
            for name in ('config.json', 'tokenizer.json', 'model.safetensors'):
                path = model / name; path.write_bytes(name.encode('ascii'))
                files.append({'file': name, 'sha256': compare.digest(path)})
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'repo': 'fixture', 'revision': 'fixture-ref', 'files': files}), encoding='utf-8')
            recorded = compare.model_fingerprint(model, manifest)
            self.assertEqual(recorded['base_config_sha256'], compare.digest(model / 'config.json'))
            self.assertEqual(recorded['tokenizer_sha256'], compare.digest(model / 'tokenizer.json'))
            extra = model / 'adapter_config.json'
            extra.write_bytes(b'unverified auto-loader configuration')
            with self.assertRaisesRegex(ValueError, 'unverified inference files'): compare.model_fingerprint(model, manifest)
            extra.unlink()
            (model / 'tokenizer.json').write_bytes(b'changed tokenizer')
            with self.assertRaisesRegex(ValueError, 'tokenizer.json'): compare.model_fingerprint(model, manifest)
            manifest.write_text(json.dumps({'files': files + [{'file': '../outside', 'sha256': 'x'}]}), encoding='utf-8')
            (model / 'tokenizer.json').write_bytes(b'tokenizer.json')
            with self.assertRaisesRegex(ValueError, 'outside'): compare.model_fingerprint(model, manifest)

    def test_loader_checks_both_named_checkpoint_results_without_gpu(self):
        for failing_name in (None, 'current_v2', 'candidate_v3'):
            for key_kind in ('missing_keys', 'unexpected_keys'):
                with self.subTest(failing_name=failing_name, key_kind=key_kind):
                    base = object(); model = FakeModel(); config = SimpleNamespace(inference_mode=False)
                    def load(directory, adapter_name, **kwargs):
                        self.assertFalse(kwargs['is_trainable'])
                        self.assertTrue(kwargs['local_files_only'])
                        keys = {'missing_keys': [], 'unexpected_keys': []}
                        if adapter_name == failing_name: keys[key_kind] = ['bad-key']
                        return SimpleNamespace(**keys)
                    model.load_adapter = Mock(side_effect=load)
                    peft = SimpleNamespace(PeftConfig=SimpleNamespace(from_pretrained=Mock(return_value=config)),
                                           get_peft_model=Mock(return_value=model))
                    torch = SimpleNamespace(set_num_threads=Mock())
                    transformers = SimpleNamespace(set_seed=Mock())
                    with patch.dict('sys.modules', {'torch': torch, 'peft': peft, 'transformers': transformers}), \
                            patch.object(core, 'MODEL_DIR', core.MODEL_DIR), \
                            patch.object(core, 'load_model', return_value=(base, 'fixture-tokenizer')) as core_loader:
                        if failing_name:
                            with self.assertRaisesRegex(RuntimeError, failing_name):
                                compare.load_models('fixture-model', 'fixture-v2', 'fixture-v3')
                        else:
                            models = compare.load_models('fixture-model', 'fixture-v2', 'fixture-v3')
                            self.assertIs(models.model, model)
                            self.assertEqual(model.load_adapter.call_count, 2)
                        core_loader.assert_called_once_with()
                        peft.get_peft_model.assert_called_once_with(base, config, adapter_name='current_v2')
                        self.assertTrue(config.inference_mode)


if __name__ == '__main__':
    unittest.main()
