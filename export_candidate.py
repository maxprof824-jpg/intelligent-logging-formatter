"""Export a completed experimental adapter without changing its training run.

CPU-only; use the project's environment. Example:
  python export_candidate.py --source runs/experiments/YOUR-RUN --output exports/YOUR-RUN
The destination must not exist. Exporting does not select the adapter as the app's
new default or establish that it performs better than another model.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
BASE_REPO = 'Qwen/Qwen3-4B-Instruct-2507'
WEIGHTS = 'adapter_model.safetensors'
SOURCE_JSON = ('training-config.json', 'trainer_state.json', 'metrics.json', 'adapter_config.json')
SENSITIVE_KEYS = {'api_key', 'access_token', 'auth_token', 'password', 'secret', 'authorization', 'private_key', 'client_secret'}
PRIVATE_TEXT = re.compile(
    r'[A-Za-z]:[\\/]|/(?:Users|home|tmp|mnt|private|var|srv|opt)/\S+'
    r'|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9]{20,}'
    r'|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_object(path):
    require(path.is_file() and not path.is_symlink(), 'Missing or redirected required file: ' + path.name)
    payload = path.read_bytes()
    try:
        value = json.loads(payload)
    except (ValueError, UnicodeError) as error:
        raise ValueError('Invalid JSON in ' + path.name) from error
    require(isinstance(value, dict), 'Expected a JSON object in ' + path.name)
    return value, hashlib.sha256(payload).hexdigest()


def integer(value, label, minimum=1):
    require(type(value) is int and value >= minimum, 'Invalid ' + label)
    return value


def finite_number(value, label, minimum=0):
    require(type(value) in (int, float) and math.isfinite(value) and value >= minimum, 'Invalid ' + label)
    return value


def completed_run(config, state, metrics):
    """Match Transformers 4.57.6's single-device, non-dropping Trainer schedule.

    set_initial_training_values uses ceil(batches/accumulation) and ceil(epochs
    * updates_per_epoch). Its loop flushes the final partial accumulation group
    and records epoch as epoch_index + consumed_batches / batches_in_epoch.
    """
    examples = integer(config.get('examples'), 'configured example count')
    micro = integer(config.get('micro_batch'), 'configured microbatch')
    accumulation = integer(config.get('accumulation'), 'configured accumulation')
    epochs = finite_number(config.get('epochs'), 'configured epochs')
    require(epochs > 0, 'Configured epochs must be positive.')
    maximum = integer(config.get('max_steps'), 'configured max_steps', minimum=-1)
    require(maximum != 0, 'Unsupported max_steps=0; use -1 or a positive update limit.')
    batches = math.ceil(examples / micro)
    updates_per_epoch = math.ceil(batches / accumulation)
    expected_steps = maximum if maximum > 0 else math.ceil(epochs * updates_per_epoch)
    require(expected_steps > 0, 'Training configuration describes no optimizer updates.')
    whole_epochs, remaining_updates = divmod(expected_steps, updates_per_epoch)
    expected_epoch = whole_epochs + min(remaining_updates * accumulation, batches) / batches
    require(integer(state.get('global_step'), 'trainer global_step', minimum=0) == expected_steps,
            'Trainer global_step does not match completed configured training.')
    require(integer(state.get('max_steps'), 'trainer max_steps') == expected_steps,
            'Trainer max_steps differs from the configured step schedule.')
    if state.get('train_batch_size') is not None:
        require(state['train_batch_size'] == micro,
                'This exporter supports the recorded single-device microbatch schedule only.')
    state_epoch = finite_number(state.get('epoch'), 'trainer epoch')
    metric_epoch = finite_number(metrics.get('epoch'), 'metrics epoch')
    require(math.isclose(state_epoch, expected_epoch, abs_tol=1e-6, rel_tol=0),
            'Trainer epoch does not match completed configured training.')
    require(math.isclose(metric_epoch, state_epoch, abs_tol=1e-6, rel_tol=0),
            'Completion metrics and trainer epoch disagree.')
    finite_number(metrics.get('train_runtime'), 'completed training runtime')
    finite_number(metrics.get('train_loss'), 'completed training loss')
    # train.py deliberately skips its final validation pass only for the
    # explicit three-update smoke configuration; all other runs save eval_loss.
    if maximum != 3:
        finite_number(metrics.get('eval_loss'), 'completed validation loss')
    return {'examples': examples, 'micro_batch': micro, 'gradient_accumulation': accumulation,
            'configured_epochs': epochs, 'configured_max_steps': maximum,
            'expected_optimizer_steps': expected_steps, 'completed_optimizer_steps': state['global_step'],
            'completed_epoch': state_epoch, 'basis': 'Configured single-device Trainer schedule, final trainer state and completion metrics.'}


def check_public_metadata(value, label):
    """Reject unexpected private metadata; never rewrite additional config fields."""
    if isinstance(value, dict):
        for key, item in value.items():
            require(not (str(key).lower() in SENSITIVE_KEYS and item not in (None, '')),
                    'Sensitive metadata in ' + label)
            check_public_metadata(str(key), label)
            check_public_metadata(item, label)
    elif isinstance(value, list):
        for item in value:
            check_public_metadata(item, label)
    elif isinstance(value, str):
        require(not PRIVATE_TEXT.search(value), 'Private path or credential pattern in ' + label)


def canonical_config(config, training, model_manifest):
    repository = model_manifest.get('repo')
    revision = model_manifest.get('revision')
    require(repository == BASE_REPO and isinstance(revision, str) and re.fullmatch(r'[0-9a-f]{40}', revision),
            'Model manifest must identify the supported base repository and a pinned revision.')
    base = training.get('base_model', {})
    require(isinstance(base, dict), 'Training base-model identity must be an object.')
    require(base.get('repo') == repository and base.get('revision') == revision,
            'Training base-model identity does not match the pinned model manifest.')
    require(config.get('peft_type') == 'LORA' and config.get('task_type') == 'CAUSAL_LM',
            'Expected a causal-language-model LoRA adapter.')
    for setting, key in (('rank', 'r'), ('alpha', 'lora_alpha'), ('dropout', 'lora_dropout')):
        require(setting in training and config.get(key) == training[setting],
                'Adapter configuration differs from training settings: ' + key)
    require(config.get('inference_mode') is True, 'Expected a saved inference adapter configuration.')
    exported = dict(config)
    exported['base_model_name_or_path'] = repository
    exported['revision'] = revision
    check_public_metadata(exported, 'exported adapter configuration')
    return exported


def check_safetensors(path):
    require(path.is_file() and not path.is_symlink(), 'Missing or redirected adapter weights.')
    # safe_open validates the container/header without materializing tensors.
    # The NumPy framework avoids importing the GPU model stack.
    from safetensors import safe_open
    try:
        with safe_open(str(path), framework='numpy', device='cpu') as handle:
            names = list(handle.keys())
            require(bool(names), 'Adapter weights contain no tensors.')
            check_public_metadata(names, 'weight tensor names')
            check_public_metadata(handle.metadata() or {}, 'weight metadata')
    except ValueError:
        raise
    except Exception as error:
        raise ValueError('Adapter weights are not a valid safetensors file.') from error


def export_candidate(source, destination, model_manifest_path=ROOT / 'model-manifest.json',
                     license_path=ROOT / 'licenses' / 'QWEN-LICENSE.txt'):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    require(source.is_dir(), 'Training-run directory is missing.')
    require(not destination.exists(), 'Export destination already exists; choose a fresh directory.')
    require(not destination.is_relative_to(source), 'Export destination must be outside the original training run.')
    records, hashes = {}, {}
    for name in SOURCE_JSON:
        records[name], hashes[name] = read_object(source / name)
    completion = completed_run(records['training-config.json'], records['trainer_state.json'], records['metrics.json'])
    model_manifest, model_manifest_hash = read_object(Path(model_manifest_path))
    configuration = canonical_config(records['adapter_config.json'], records['training-config.json'], model_manifest)
    license_path = Path(license_path)
    require(license_path.is_file() and not license_path.is_symlink(), 'Missing or redirected upstream license.')
    license_bytes = license_path.read_bytes()
    license_hash = hashlib.sha256(license_bytes).hexdigest()
    require(isinstance(model_manifest.get('files'), list), 'Pinned model manifest must list its source files.')
    license_records = [entry for entry in model_manifest['files']
                       if isinstance(entry, dict) and entry.get('file') == 'LICENSE']
    upstream_license_hash = license_records[0].get('sha256') if len(license_records) == 1 else None
    license_lf_hash = hashlib.sha256(license_bytes.replace(b'\r\n', b'\n')).hexdigest()
    require(upstream_license_hash in (license_hash, license_lf_hash),
            'Upstream license does not match the pinned model manifest.')
    weights_path = source / WEIGHTS
    check_safetensors(weights_path)
    hashes[WEIGHTS] = sha256(weights_path)
    config_bytes = (json.dumps(configuration, indent=2, allow_nan=False) + '\n').encode('utf-8')
    config_hash = hashlib.sha256(config_bytes).hexdigest()
    readme = f'''# Intelligent Logging Formatter — experimental adapter

This synthetic-data proof of concept is a separately trained candidate adapter, not the application's default model. Exporting it makes no performance claim. Compare its drafts with the current model and review facts and suggestions before relying on them.

The adapter requires `{configuration['base_model_name_or_path']}` at revision `{configuration['revision']}` and the Intelligent Logging Formatter application. It contains adapter weights, not the base model or a complete Python installation.

From an installed project, choose this adapter explicitly:

```powershell
.venv\\Scripts\\python.exe app_v2.py --adapter PATH-TO-THIS-EXPORT
```

The weights are byte-identical to the completed source run. Only the base-model repository and revision fields were normalized in the copied configuration. EXPORT-MANIFEST.json records completion checks and input/output hashes without copying the private training-run paths. Checkpoints, optimizer state, training arguments, tokenizer copies and the autogenerated run README are excluded.

See THIRD-PARTY-NOTICES.md and QWEN-LICENSE.txt for upstream attribution and licensing context.
'''
    notices = f'''# Third-party notices

This experimental adapter is a synthetic-data proof of concept created by modifying {configuration['base_model_name_or_path']} through QLoRA fine-tuning. The upstream model is published by the Qwen team at https://huggingface.co/{configuration['base_model_name_or_path']}, pinned to revision `{configuration['revision']}`.

The upstream model uses the Apache License 2.0. The project's copy of its license is reproduced byte for byte in QWEN-LICENSE.txt and verified against the pinned upstream text, allowing Windows line endings. This notice does not assign a new project-wide reuse license to the application's original code, dataset or adapter contribution; no such license has been selected. Upstream licensing and attribution remain applicable.
'''
    payloads = {'adapter_config.json': config_bytes, 'README.md': readme.encode('utf-8'),
                'QWEN-LICENSE.txt': license_bytes, 'THIRD-PARTY-NOTICES.md': notices.encode('utf-8')}
    file_hashes = {name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()}
    file_hashes[WEIGHTS] = hashes[WEIGHTS]
    manifest = {'format_version': 1, 'experimental': True, 'default_model_changed': False,
                'created_utc': datetime.now(timezone.utc).isoformat(),
                'base_model': {'repo': configuration['base_model_name_or_path'], 'revision': configuration['revision'],
                               'model_manifest_sha256': model_manifest_hash},
                'upstream_license': {'file': 'QWEN-LICENSE.txt', 'source_and_export_sha256': license_hash,
                                     'pinned_upstream_sha256': upstream_license_hash,
                                     'verification': 'exact bytes' if license_hash == upstream_license_hash
                                                     else 'exact upstream bytes after CRLF-to-LF normalization; exported copy unchanged'},
                'completion': completion, 'source_artifacts_sha256': hashes,
                'input_configuration_sha256': hashes['adapter_config.json'], 'export_configuration_sha256': config_hash,
                'input_weights_sha256': hashes[WEIGHTS], 'export_weights_sha256': hashes[WEIGHTS],
                'weight_bytes_modified': False,
                'configuration_fields_normalized': ['base_model_name_or_path', 'revision'],
                'files': file_hashes,
                'hash_scope': 'Exact exported file bytes. This manifest does not hash itself.',
                'interpretation': 'Configured training completion and unchanged export bytes do not establish model quality or promotion readiness.'}
    check_public_metadata(manifest, 'export manifest')
    payloads['EXPORT-MANIFEST.json'] = (json.dumps(manifest, indent=2, allow_nan=False) + '\n').encode('utf-8')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Work privately until all copies verify. Validation/copy failures leave no
    # partially populated destination and do not modify source-run artifacts.
    with tempfile.TemporaryDirectory(prefix='.candidate-export-', dir=destination.parent) as temporary:
        staging = Path(temporary) / 'payload'
        staging.mkdir()
        for name, payload in payloads.items():
            (staging / name).write_bytes(payload)
        shutil.copyfile(weights_path, staging / WEIGHTS)
        for name, expected in file_hashes.items():
            require(sha256(staging / name) == expected, 'Exported file checksum mismatch: ' + name)
        for name, expected in hashes.items():
            require(sha256(source / name) == expected, 'Source run changed during export; retry after it is stable.')
        require(not destination.exists(), 'Export destination appeared during export; no files were replaced.')
        staging.rename(destination)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Completed private training-run directory')
    parser.add_argument('--output', type=Path, required=True, help='Fresh export directory outside the source run')
    parser.add_argument('--model-manifest', type=Path, default=ROOT / 'model-manifest.json', help='Pinned base-model manifest')
    args = parser.parse_args()
    try:
        result = export_candidate(args.source, args.output, args.model_manifest)
    except (ValueError, OSError) as error:
        parser.exit(1, 'Export failed: ' + (str(error) if isinstance(error, ValueError) else 'filesystem operation failed') + '\n')
    print(json.dumps({'exported': True, 'experimental': True, 'default_model_changed': False,
                      'weights_sha256': result['export_weights_sha256'],
                      'configuration_sha256': result['export_configuration_sha256']}))


if __name__ == '__main__':
    main()
