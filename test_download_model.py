"""CPU-only regressions for model integrity, offline checks, and setup diagnostics."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import doctor
import download_model as downloader


class ModelDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.content = b'{"value": 1}'
        self.record = {'file': 'config.json', 'bytes': len(self.content),
                       'sha256': hashlib.sha256(self.content).hexdigest(), 'upstream_sha256': None}
        self.manifest = {'repo': downloader.REPO, 'revision': 'a' * 40, 'files': [self.record]}
        self.manifest_path = self.root / 'model-manifest.json'
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()
        self.addCleanup(self.quiet.__exit__, None, None, None)

    def test_same_size_non_lfs_corruption_is_replaced(self):
        dest = self.root / self.record['file']
        dest.write_bytes(b'{"value": 2}')
        opener = Mock(return_value=io.BytesIO(self.content))
        downloader.download(self.record, self.manifest['revision'], self.root, opener=opener)
        self.assertEqual(dest.read_bytes(), self.content)
        self.assertEqual(opener.call_count, 1)
        self.assertIn('/resolve/' + self.manifest['revision'] + '/config.json', opener.call_args.args[0])

    def test_verified_file_never_requires_network(self):
        (self.root / self.record['file']).write_bytes(self.content)
        opener = Mock(side_effect=AssertionError('Network must not be used'))
        downloader.download(self.record, self.manifest['revision'], self.root, opener=opener)
        opener.assert_not_called()

    def test_bad_download_does_not_replace_existing_file(self):
        dest = self.root / self.record['file']
        dest.write_bytes(b'old content')
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            downloader.download(self.record, self.manifest['revision'], self.root,
                                opener=lambda _: io.BytesIO(b'{"value": 2}'), attempts=1)
        self.assertEqual(dest.read_bytes(), b'old content')
        self.assertFalse(dest.with_name(dest.name + '.partial').exists())

    def test_truncated_download_does_not_become_model_file(self):
        with self.assertRaisesRegex(ValueError, 'Size mismatch'):
            downloader.download(self.record, self.manifest['revision'], self.root,
                                opener=lambda _: io.BytesIO(b'{'), attempts=1)
        self.assertFalse((self.root / 'config.json').exists())
        self.assertFalse((self.root / 'config.json.partial').exists())

    def test_transient_download_error_retries(self):
        opener = Mock(side_effect=[OSError('temporary'), io.BytesIO(self.content)])
        with patch.object(downloader.time, 'sleep'):
            downloader.download(self.record, self.manifest['revision'], self.root, opener=opener, attempts=2)
        self.assertTrue(downloader.verified(self.root / 'config.json', self.record))
        self.assertEqual(opener.call_count, 2)

    def test_manifest_rejects_unsafe_or_duplicate_filenames(self):
        for name in ('../outside', '/outside', 'C:/outside', r'..\outside', 'a/../outside'):
            with self.subTest(name=name):
                self.manifest['files'] = [dict(self.record, file=name)]
                self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'filename'):
                    downloader.load_manifest(self.manifest_path)
        self.manifest['files'] = [self.record, dict(self.record, file='CONFIG.JSON')]
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'filename'):
            downloader.load_manifest(self.manifest_path)

    def test_manifest_requires_hash_for_every_file(self):
        self.manifest['files'] = [dict(self.record, sha256='')]
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            downloader.load_manifest(self.manifest_path)

    def test_manifest_rejects_unpinned_revision(self):
        self.manifest['revision'] = 'main'
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'exact revision'):
            downloader.load_manifest(self.manifest_path)

    def test_complete_install_is_offline_and_manifest_is_unchanged(self):
        before = self.manifest_path.read_bytes()
        (self.root / 'config.json').write_bytes(self.content)
        with patch.object(downloader, 'ROOT', self.root), patch.object(
                downloader.urllib.request, 'urlopen', side_effect=AssertionError('No network')):
            downloader.main(['--destination', str(self.root)])
        self.assertEqual(self.manifest_path.read_bytes(), before)

    def test_verify_only_reports_bad_files_without_downloading(self):
        with patch.object(downloader, 'ROOT', self.root), patch.object(downloader, 'download') as download:
            with contextlib.redirect_stderr(io.StringIO()) as output, self.assertRaises(SystemExit) as error:
                downloader.main(['--verify-only', '--destination', str(self.root)])
        self.assertEqual(error.exception.code, 1)
        self.assertIn('config.json', output.getvalue())
        download.assert_not_called()

    def test_verify_only_accepts_valid_files(self):
        (self.root / 'config.json').write_bytes(self.content)
        with patch.object(downloader, 'ROOT', self.root), patch.object(downloader, 'download') as download:
            downloader.main(['--verify-only', '--destination', str(self.root)])
        download.assert_not_called()


class DoctorTests(unittest.TestCase):
    def test_gpu_failure_is_saved_and_has_failure_exit_code(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(doctor, 'ROOT', Path(temp)), \
                patch.object(doctor, 'probe_gpu', side_effect=RuntimeError('CUDA unavailable')), \
                contextlib.redirect_stdout(io.StringIO()):
            result = doctor.main()
            report = json.loads((Path(temp) / 'reports' / 'environment.json').read_text(encoding='utf-8'))
        self.assertEqual(result, 1)
        self.assertEqual(report['status'], 'failed')
        self.assertIn('CUDA unavailable', report['error'])
        self.assertIn('python', report)

    def test_missing_cuda_has_actionable_error(self):
        fake_torch = Mock()
        fake_torch.cuda.is_available.return_value = False
        with patch.dict('sys.modules', {'torch': fake_torch}), self.assertRaisesRegex(RuntimeError, 'NVIDIA driver'):
            doctor.probe_gpu({})


if __name__ == '__main__':
    unittest.main()
