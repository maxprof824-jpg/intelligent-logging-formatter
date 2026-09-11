import json
from pathlib import Path
import tempfile
import unittest

from train import save_new_training_config, validate_training_run


class TrainingProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.checkpoint = self.output / 'checkpoint-20'
        self.checkpoint.mkdir()
        (self.checkpoint / 'trainer_state.json').write_text('{"global_step":20}', encoding='utf-8')
        self.config = {
            'base_model': {'repo': 'fictional-model', 'revision': 'pinned-revision'},
            'train_sha256': 'original-training-data', 'validation_sha256': 'original-validation-data',
            'rank': 16, 'accumulation': 8, 'epochs': 1.0, 'max_steps': -1, 'max_sequence_length': 4096,
        }
        self.path = self.output / 'training-config.json'
        self.original = json.dumps(self.config, indent=4).encode('utf-8') + b'\n'
        self.path.write_bytes(self.original)

    def test_matching_resume_preserves_original_configuration_bytes(self):
        validate_training_run(self.output, dict(self.config), True, self.checkpoint)
        save_new_training_config(self.output, dict(self.config), True)
        self.assertEqual(self.original, self.path.read_bytes())

    def test_changed_data_base_or_hyperparameters_are_rejected_without_mutation(self):
        changes = {'train_sha256': 'new-training-data', 'validation_sha256': 'new-validation-data',
                   'base_model': {'repo': 'fictional-model', 'revision': 'another-revision'},
                   'rank': 32, 'accumulation': 4, 'epochs': 2.0, 'max_steps': 100,
                   'max_sequence_length': 2048}
        for key, value in changes.items():
            with self.subTest(key=key):
                with self.assertRaisesRegex(RuntimeError, key):
                    validate_training_run(self.output, {**self.config, key: value}, True, self.checkpoint)
                self.assertEqual(self.original, self.path.read_bytes())

    def test_missing_original_field_cannot_silently_resume(self):
        with self.assertRaisesRegex(RuntimeError, 'seed'):
            validate_training_run(self.output, {**self.config, 'seed': 42}, True, self.checkpoint)
        self.assertEqual(self.original, self.path.read_bytes())

    def test_missing_checkpoint_preserves_configuration(self):
        with self.assertRaisesRegex(RuntimeError, 'No checkpoint'):
            validate_training_run(self.output, self.config, True, None)
        self.assertEqual(self.original, self.path.read_bytes())

    def test_incomplete_checkpoint_is_rejected(self):
        (self.checkpoint / 'trainer_state.json').unlink()
        with self.assertRaisesRegex(RuntimeError, 'trainer_state.json'):
            validate_training_run(self.output, self.config, True, self.checkpoint)
        self.assertEqual(self.original, self.path.read_bytes())

    def test_missing_configuration_cannot_resume(self):
        self.path.unlink()
        with self.assertRaisesRegex(RuntimeError, 'original training-config'):
            validate_training_run(self.output, self.config, True, self.checkpoint)
        self.assertFalse(self.path.exists())

    def test_fresh_training_refuses_existing_run(self):
        with self.assertRaisesRegex(RuntimeError, 'already contains a training run'):
            validate_training_run(self.output, self.config)
        self.assertEqual(self.original, self.path.read_bytes())
        self.path.unlink()
        with self.assertRaisesRegex(RuntimeError, 'already contains a training run'):
            validate_training_run(self.output, self.config)

    def test_new_configuration_is_written_once(self):
        new_output = self.output / 'new-run'
        new_output.mkdir()
        validate_training_run(new_output, self.config)
        save_new_training_config(new_output, self.config)
        with self.assertRaises(FileExistsError):
            save_new_training_config(new_output, {'unexpected': 'replacement'})
        self.assertEqual(self.config, json.loads((new_output / 'training-config.json').read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
