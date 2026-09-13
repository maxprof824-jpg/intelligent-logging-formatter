"""CPU-only adapter-export integrity and failure tests; no base model is loaded."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from safetensors.numpy import save_file

import export_candidate as exporter


REVISION = 'cdbee75f17c01a7cc42f958dc650907174af0554'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


class CandidateExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'run'
        self.source.mkdir()
        self.output = self.root / 'export'
        self.license = self.root / 'license.txt'
        self.license.write_bytes(b'Upstream license fixture\n')
        self.model_manifest = self.root / 'model-manifest.json'
        write_json(self.model_manifest, {'repo': exporter.BASE_REPO, 'revision': REVISION,
                   'files': [{'file': 'LICENSE', 'sha256': exporter.sha256(self.license)}]})
        self.training = {'base_model': {'repo': exporter.BASE_REPO, 'revision': REVISION},
                         'examples': 10, 'micro_batch': 1, 'accumulation': 4,
                         'epochs': 1.0, 'max_steps': -1, 'rank': 16, 'alpha': 32, 'dropout': 0.05}
        self.state = {'global_step': 3, 'max_steps': 3, 'epoch': 1.0, 'train_batch_size': 1}
        self.metrics = {'epoch': 1.0, 'train_runtime': 1.0, 'train_loss': 0.5, 'eval_loss': 0.6}
        self.private_path = 'C:' + chr(92) + 'Users' + chr(92) + 'example' + chr(92) + 'base-model'
        self.config = {'base_model_name_or_path': self.private_path, 'revision': None,
                       'peft_type': 'LORA', 'task_type': 'CAUSAL_LM', 'inference_mode': True,
                       'r': 16, 'lora_alpha': 32, 'lora_dropout': 0.05,
                       'target_modules': ['q_proj', 'v_proj'], 'bias': 'none'}
        self.save_records()
        save_file({'base_model.model.q_proj.lora_A.weight': np.zeros((2, 4), dtype=np.float32)},
                  self.source / exporter.WEIGHTS, metadata={'format': 'pt'})
        for name in ('README.md', 'training_args.bin', 'tokenizer.json', 'optimizer.pt'):
            (self.source / name).write_text('private run artifact', encoding='utf-8')
        (self.source / 'checkpoint-2').mkdir()
        (self.source / 'checkpoint-2' / 'scheduler.pt').write_bytes(b'private state')

    def save_records(self):
        for name, value in (('training-config.json', self.training), ('trainer_state.json', self.state),
                            ('metrics.json', self.metrics), ('adapter_config.json', self.config)):
            write_json(self.source / name, value)

    def export(self):
        return exporter.export_candidate(self.source, self.output, self.model_manifest, self.license)

    def assert_rejected(self, message):
        with self.assertRaisesRegex(ValueError, message):
            self.export()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.candidate-export-*')))

    def test_exact_export_preserves_weights_source_and_only_normalizes_two_fields(self):
        originals = {str(p.relative_to(self.source)): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        result = self.export()
        expected_names = {'adapter_config.json', exporter.WEIGHTS, 'README.md', 'EXPORT-MANIFEST.json',
                          'QWEN-LICENSE.txt', 'THIRD-PARTY-NOTICES.md'}
        self.assertEqual({p.name for p in self.output.iterdir()}, expected_names)
        exported = json.loads((self.output / 'adapter_config.json').read_text())
        expected_config = dict(self.config, base_model_name_or_path=exporter.BASE_REPO, revision=REVISION)
        self.assertEqual(exported, expected_config)
        self.assertEqual((self.output / exporter.WEIGHTS).read_bytes(), originals[exporter.WEIGHTS])
        self.assertEqual((self.output / 'QWEN-LICENSE.txt').read_bytes(), self.license.read_bytes())
        self.assertEqual(result['input_configuration_sha256'], hashlib.sha256(originals['adapter_config.json']).hexdigest())
        self.assertEqual(result['export_configuration_sha256'], exporter.sha256(self.output / 'adapter_config.json'))
        self.assertEqual(result['input_weights_sha256'], result['export_weights_sha256'])
        self.assertFalse(result['weight_bytes_modified'])
        self.assertFalse(result['default_model_changed'])
        self.assertTrue(result['experimental'])
        for name, expected_hash in result['files'].items():
            self.assertEqual(exporter.sha256(self.output / name), expected_hash)
        for name in expected_names - {exporter.WEIGHTS}:
            text = (self.output / name).read_text(encoding='utf-8')
            self.assertNotIn(self.private_path, text)
            self.assertNotIn(self.private_path.replace(chr(92), chr(92) * 2), text)
            self.assertNotIn(str(self.source), text)
        self.assertIn('synthetic-data proof of concept', (self.output / 'README.md').read_text(encoding='utf-8'))
        self.assertEqual(originals, {str(p.relative_to(self.source)): p.read_bytes() for p in self.source.rglob('*') if p.is_file()})

    def test_missing_completion_or_adapter_files_leave_no_destination(self):
        for name in (*exporter.SOURCE_JSON, exporter.WEIGHTS):
            with self.subTest(name=name):
                path = self.source / name
                payload = path.read_bytes()
                path.unlink()
                self.assert_rejected('Missing')
                path.write_bytes(payload)

    def test_incomplete_or_excess_steps_and_wrong_epoch_are_rejected(self):
        for key, value in (('global_step', 2), ('global_step', 4), ('max_steps', 4), ('epoch', 0.9), ('train_batch_size', 2)):
            with self.subTest(key=key, value=value):
                original = self.state[key]
                self.state[key] = value
                self.save_records()
                self.assert_rejected('Trainer|single-device')
                self.state[key] = original

    def test_completion_metrics_must_agree_and_be_finite(self):
        for key, value in (('epoch', 0.9), ('train_runtime', float('nan')),
                           ('train_loss', float('inf')), ('eval_loss', -1)):
            with self.subTest(key=key):
                original = self.metrics[key]
                self.metrics[key] = value
                self.save_records()
                self.assert_rejected('metrics|Invalid')
                self.metrics[key] = original

    def test_nondivisible_batches_and_fractional_epoch_schedule(self):
        self.training['epochs'] = 1.5
        self.state.update(global_step=5, max_steps=5, epoch=1.8)
        self.metrics['epoch'] = 1.8
        completion = exporter.completed_run(self.training, self.state, self.metrics)
        self.assertEqual(completion['expected_optimizer_steps'], 5)
        self.assertEqual(completion['completed_epoch'], 1.8)

    def test_positive_max_steps_overrides_epochs(self):
        self.training.update(epochs=20, max_steps=4)
        self.state.update(global_step=4, max_steps=4, epoch=1.4)
        self.metrics['epoch'] = 1.4
        self.assertEqual(exporter.completed_run(self.training, self.state, self.metrics)['expected_optimizer_steps'], 4)

    def test_only_explicit_three_step_smoke_can_omit_final_evaluation(self):
        self.metrics.pop('eval_loss')
        self.save_records()
        self.assert_rejected('validation loss')
        self.training['max_steps'] = 3
        self.save_records()
        self.assertTrue(self.export()['experimental'])

    def test_zero_step_limit_and_invalid_numeric_settings_are_rejected(self):
        for key, value in (('max_steps', 0), ('examples', 0), ('micro_batch', True),
                           ('accumulation', 0), ('epochs', 0), ('max_steps', -2)):
            with self.subTest(key=key, value=value):
                original = self.training[key]
                self.training[key] = value
                self.save_records()
                self.assert_rejected('Invalid|Unsupported|positive')
                self.training[key] = original

    def test_existing_destination_is_not_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / 'keep.txt'
        sentinel.write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.export()
        self.assertEqual(sentinel.read_bytes(), b'keep')
        self.assertEqual(list(self.output.iterdir()), [sentinel])

    def test_destination_inside_source_is_rejected(self):
        self.output = self.source / 'export'
        self.assert_rejected('outside')

    def test_wrong_pinned_base_and_malformed_identity_are_rejected(self):
        for value in ({'repo': 'other/base', 'revision': REVISION}, {'repo': exporter.BASE_REPO, 'revision': '0' * 40}, None):
            with self.subTest(value=value):
                self.training['base_model'] = value
                self.save_records()
                self.assert_rejected('base-model identity')

    def test_config_settings_must_match_recorded_training(self):
        for key, value in (('r', 8), ('lora_alpha', 64), ('lora_dropout', 0.1),
                           ('peft_type', 'OTHER'), ('inference_mode', False)):
            with self.subTest(key=key):
                original = self.config[key]
                self.config[key] = value
                self.save_records()
                self.assert_rejected('configuration|LoRA|inference')
                self.config[key] = original

    def test_unexpected_private_metadata_is_rejected_without_echoing_it(self):
        for extra in ({'custom': self.private_path}, {'custom': '/' + 'home' + '/example/model'},
                      {'custom': 'ghp_' + 'A' * 36}, {'nested': {'api_key': 'value'}}):
            with self.subTest(keys=list(extra)):
                unsafe = dict(self.config, **extra)
                write_json(self.source / 'adapter_config.json', unsafe)
                with self.assertRaisesRegex(ValueError, 'metadata|Private path') as caught:
                    self.export()
                self.assertNotIn(self.private_path, str(caught.exception))
                self.assertNotIn('A' * 36, str(caught.exception))
                self.assertFalse(self.output.exists())

    def test_nonfinite_extra_config_does_not_generate_invalid_json(self):
        self.config['unexpected'] = float('nan')
        self.save_records()
        self.assert_rejected('Out of range')

    def test_invalid_safetensors_and_private_header_metadata_are_rejected(self):
        (self.source / exporter.WEIGHTS).write_bytes(b'not a tensor file')
        self.assert_rejected('valid safetensors')
        save_file({'lora_A.weight': np.zeros((1, 1), dtype=np.float32)}, self.source / exporter.WEIGHTS,
                  metadata={'source': self.private_path})
        self.assert_rejected('Private path')

    def test_corrupt_or_missing_upstream_license_is_rejected(self):
        self.license.write_bytes(b'changed')
        self.assert_rejected('license does not match')
        self.license.unlink()
        self.assert_rejected('upstream license')

    def test_windows_license_checkout_preserves_bytes_and_verifies_upstream_text(self):
        self.license.write_bytes(self.license.read_bytes().replace(b'\n', b'\r\n'))
        result = self.export()
        self.assertEqual((self.output / 'QWEN-LICENSE.txt').read_bytes(), self.license.read_bytes())
        self.assertEqual(result['upstream_license']['source_and_export_sha256'], exporter.sha256(self.license))
        self.assertNotEqual(result['upstream_license']['source_and_export_sha256'], result['upstream_license']['pinned_upstream_sha256'])
        self.assertIn('CRLF-to-LF', result['upstream_license']['verification'])

    def test_copy_failure_leaves_no_partial_export(self):
        with patch.object(exporter.shutil, 'copyfile', side_effect=OSError('copy interrupted')):
            with self.assertRaises(OSError):
                self.export()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.candidate-export-*')))

    def test_source_mutation_during_copy_is_detected(self):
        original_copy = shutil.copyfile

        def mutate_then_copy(source, destination):
            original_copy(source, destination)
            self.state['global_step'] = 2
            write_json(self.source / 'trainer_state.json', self.state)

        with patch.object(exporter.shutil, 'copyfile', side_effect=mutate_then_copy):
            self.assert_rejected('Source run changed')

    def test_corrupt_copy_is_detected_before_publication(self):
        with patch.object(exporter.shutil, 'copyfile', side_effect=lambda source, destination: Path(destination).write_bytes(b'bad')):
            self.assert_rejected('checksum mismatch')

    def test_destination_created_during_copy_is_preserved(self):
        original_copy = shutil.copyfile

        def another_writer(source, destination):
            original_copy(source, destination)
            self.output.mkdir()
            (self.output / 'keep').write_bytes(b'existing')

        with patch.object(exporter.shutil, 'copyfile', side_effect=another_writer):
            with self.assertRaisesRegex(ValueError, 'appeared during export'):
                self.export()
        self.assertEqual({p.name for p in self.output.iterdir()}, {'keep'})
        self.assertFalse(list(self.root.glob('.candidate-export-*')))


if __name__ == '__main__':
    unittest.main()
