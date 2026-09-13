"""Matched base/v2/v3 comparison under the frozen formatter 2.5 runtime.

One quantized base model holds two named, frozen LoRA adapters. Every selected
case runs as base (inside PEFT's disable_adapter context), current_v2, then
candidate_v3. Inputs, mode, assistance and runtime are identical. Elapsed time
can differ because helper passes depend on gaps left in each model's draft.

Development is the default. Use repeated --case options for separately recorded
stages; each stage is explicitly a subset, never an implied full comparison.
Reserved evaluation requires a separate --split reserved --design-frozen call
after the candidate and evaluation design are frozen. This is a protocol
acknowledgment, not evidence of independent human validation. The command never
trains, merges adapters, changes prompts, or overwrites an existing report.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import time
import uuid

import coach
import core
import event_formatter
from event_groups import split_events
from evaluate_events import GENERATION_FILES, SCORING_FILES, score_safely, summarize
from evaluate_v2 import VALID_STATUSES


MODEL_VARIANTS = ('base', 'current_v2', 'candidate_v3')
ADAPTER_NAMES = ('current_v2', 'candidate_v3')
FROZEN_COMMIT = '33d2361b0883911bbe792a69079b3eb099c260ec'
DEVELOPMENT_DATA_SHA256 = '2dea24c5016a739076b0d4e30829b3385e9c1097f55e00ef9b40c898dcd5672a'
# SHA-256 of release source bytes after CRLF-to-LF normalization. This also
# works in a downloaded ZIP without a Git checkout, on Windows or Linux.
FROZEN_RUNTIME = {
    'event_formatter.py': 'db004c42a0f0742cdedc8b35424f6fa914cbce495e904810fd5ecbc89d5ccf1a',
    'event_groups.py': 'a4eda5aae1f9a863455a96badd0b98b22abd6281f51c1cf86d036ef4fb851777',
    'coach.py': '4ea6ab74d6c97486359694491af1c9bbe3849b5b857746cc0350c422773650bf',
    'coaching_pass.py': '852052124972ebc6c121df9e0e29f7ef47c6fcc1cf1809e68879b5b924034aed',
    'evidence_checks.py': 'e6f87b0e7c28b6c80a2ae4916f365f26d757e1929c004fc15f4103653c6e011c',
    'source_coverage.py': 'bdf40ca98629532f2a88c4620e64fd4f72b0b86e4b55588b85408b621b112584',
    'core.py': 'e5d964fc065b9755ac07ec30aced4d1be828091eebc34d3f26a62df11c7cdce3',
}


def digest(path):
    """Hash large weight shards without reading them all into RAM."""
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def runtime_fingerprints(root=core.ROOT):
    root = Path(root)
    actual = {name: hashlib.sha256((root / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
              for name in GENERATION_FILES}
    changed = [name for name, expected in FROZEN_RUNTIME.items() if actual.get(name) != expected]
    if changed:
        raise ValueError('Formatter runtime differs from frozen release 33d2361: ' + ', '.join(changed))
    return {'runtime_commit': FROZEN_COMMIT, 'runtime_normalized_sha256': actual,
            'generation_code_sha256': {name: digest(root / name) for name in GENERATION_FILES},
            'scoring_code_sha256': {name: digest(root / name) for name in SCORING_FILES},
            'comparison_code_sha256': digest(__file__)}


def select_cases(root, split='development', case_ids=None, design_frozen=False):
    """The reserved gate runs before any attempt to open its file."""
    if split not in ('development', 'reserved'):
        raise ValueError('Choose development or reserved.')
    if split == 'reserved' and not design_frozen:
        raise ValueError('Reserved evaluation requires --design-frozen after freezing the candidate and evaluation design.')
    if split == 'reserved' and case_ids:
        raise ValueError('--case selects development stages only; reserved evaluation runs its complete split.')
    relative = f'evaluation-v3/{split}.jsonl'
    path = Path(root) / relative
    payload = path.read_bytes()
    rows = [json.loads(line) for line in payload.decode('utf-8').splitlines()]
    ids = [row['id'] for row in rows]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('Evaluation split must contain nonempty, unique case IDs.')
    for row in rows:
        if not isinstance(row.get('source_text'), str) or row.get('mode') not in ('draft', 'review') or not isinstance(row.get('assist'), bool):
            raise ValueError(f"Invalid source/mode/assist in evaluation case {row['id']}.")
        if not isinstance(row.get('expectations'), dict) or not isinstance(row['expectations'].get('checks'), list):
            raise ValueError(f"Missing evaluation expectations for {row['id']}.")
    requested = list(case_ids or [])
    if len(set(requested)) != len(requested):
        raise ValueError('Repeat --case for different IDs; duplicate selections are not allowed.')
    unknown = set(requested) - set(ids)
    if unknown:
        raise ValueError('Unknown development case IDs: ' + ', '.join(sorted(unknown)))
    selected = [row for row in rows if not requested or row['id'] in requested]
    return selected, {'dataset': relative, 'dataset_sha256': hashlib.sha256(payload).hexdigest(),
                      'split': split, 'split_case_count': len(rows),
                      'selected_ids': [row['id'] for row in selected],
                      'selected_case_count': len(selected), 'full_split_selected': len(selected) == len(rows),
                      'selection_order': 'Frozen dataset order, independent of --case argument order.',
                      'design_frozen_acknowledged': bool(design_frozen)}


def adapter_fingerprint(directory):
    directory = Path(directory)
    config_path = directory / 'adapter_config.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    # disable_adapter can only represent this project's original base when no
    # separately trained bias/base modules or alternative adaptation scheme exist.
    if (config.get('peft_type') != 'LORA' or config.get('task_type') != 'CAUSAL_LM'
            or config.get('bias', 'none') != 'none' or config.get('lora_bias', False)
            or config.get('modules_to_save') or config.get('layer_replication')
            or config.get('use_dora', False) or config.get('trainable_token_indices')
            or config.get('alora_invocation_tokens')
            or config.get('init_lora_weights', True) not in (True, False, 'gaussian')):
        raise ValueError(f'{directory.name} is not a compatible ordinary bias-free causal-LM LoRA adapter.')
    result = {'adapter_model_sha256': digest(directory / 'adapter_model.safetensors'),
              'adapter_config_sha256': digest(config_path),
              'adapter_configuration': {key: config.get(key) for key in
                                        ('peft_type', 'task_type', 'r', 'lora_alpha', 'lora_dropout',
                                         'target_modules', 'bias', 'modules_to_save', 'use_rslora', 'use_dora')}}
    for name in ('training-config.json', 'metrics.json', 'trainer_state.json'):
        path = directory / name
        if path.is_file():
            result[name.replace('.json', '').replace('-', '_') + '_sha256'] = digest(path)
    training_path = directory / 'training-config.json'
    if training_path.is_file():
        training = json.loads(training_path.read_text(encoding='utf-8'))
        result['training_data_sha256'] = {key: training[key] for key in ('train_sha256', 'validation_sha256') if key in training}
    return result


def model_fingerprint(directory, manifest_path):
    """Verify actual inference files against the project's pinned base manifest."""
    directory = Path(directory).resolve()
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    names = {item['file'] for item in manifest['files']}
    # Transformers can prefer a single-file checkpoint or consume added-token
    # settings even when all pinned shards are also present. Do not claim the
    # pinned base was loaded if such inference inputs were never verified.
    unverified = sorted(path.name for path in directory.iterdir()
                        if path.is_file() and path.name not in names
                        and path.suffix in ('.json', '.bin', '.safetensors', '.model'))
    if unverified:
        raise ValueError('Base directory contains unverified inference files: ' + ', '.join(unverified))
    files = {}
    for item in manifest['files']:
        name = item['file']
        if name in ('README.md', 'LICENSE'):
            continue
        path = (directory / name).resolve()
        if not path.is_relative_to(directory):
            raise ValueError('Base model manifest contains a path outside its model directory.')
        actual = digest(path)
        if actual != item['sha256']:
            raise ValueError(f'Base model file differs from its pinned manifest: {name}')
        files[name] = actual
    if 'config.json' not in files or 'tokenizer.json' not in files or not any(name.endswith('.safetensors') for name in files):
        raise ValueError('Base model manifest does not identify config, tokenizer, and model weights.')
    return {'repo': manifest['repo'], 'revision': manifest['revision'],
            'manifest_sha256': digest(manifest_path), 'files_sha256': files,
            'base_config_sha256': files['config.json'], 'tokenizer_sha256': files['tokenizer.json']}


class MatchedModels:
    """Select one of two named LoRA adapters or the same unadapted base."""
    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer
        self._freeze()

    def _freeze(self):
        # PEFT set_adapter intentionally enables its gradients; reset every
        # parameter, including base flags, before each inference context.
        self.model.set_requires_grad(list(ADAPTER_NAMES), False)
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)
        self.model.eval()

    def snapshot(self):
        status = self.model.get_model_status()
        return {'active_adapters': status.active_adapters, 'adapters_enabled': status.enabled,
                'available_adapters': sorted(status.available_adapters), 'merged_adapters': status.merged_adapters,
                'adapter_requires_grad': status.requires_grad, 'trainable_parameters': status.trainable_params,
                'trainable_parameter_tensors': sum(bool(p.requires_grad) for p in self.model.parameters()),
                'model_training': self.model.training}

    @contextmanager
    def activate(self, variant):
        if variant not in MODEL_VARIANTS:
            raise ValueError('Unknown model variant: ' + str(variant))
        self.model.set_adapter('current_v2' if variant == 'base' else variant)
        self._freeze()
        if variant == 'base':
            with self.model.disable_adapter():
                yield self.model
        else:
            yield self.model


def expected_state(variant):
    return {'active_adapters': ['current_v2' if variant == 'base' else variant],
            'adapters_enabled': variant != 'base', 'available_adapters': sorted(ADAPTER_NAMES),
            'merged_adapters': [], 'adapter_requires_grad': {name: False for name in ADAPTER_NAMES},
            'trainable_parameters': 0, 'trainable_parameter_tensors': 0, 'model_training': False}


def load_models(model_dir, current_adapter, candidate_adapter):
    import torch
    from peft import PeftConfig, get_peft_model
    from transformers import set_seed
    torch.set_num_threads(4)
    set_seed(42)
    core.MODEL_DIR = Path(model_dir)
    base, tokenizer = core.load_model()
    config = PeftConfig.from_pretrained(str(current_adapter), local_files_only=True)
    config.inference_mode = True
    model = get_peft_model(base, config, adapter_name='current_v2')
    # Unlike from_pretrained's model-only return value, load_adapter exposes
    # missing AND unexpected keys. Require an exact checkpoint for both names.
    for name, directory in zip(ADAPTER_NAMES, (current_adapter, candidate_adapter)):
        loaded = model.load_adapter(str(directory), adapter_name=name,
                                    is_trainable=False, local_files_only=True)
        if loaded.missing_keys or loaded.unexpected_keys:
            raise RuntimeError(f'{name} adapter did not load exactly; missing or unexpected state-dict keys were reported.')
    return MatchedModels(model, tokenizer)


def save_checkpoint(path, report):
    """Replace only this invocation's already-reserved report, atomically."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def comparison_summary(outputs, selected_ids):
    summary = {}
    for variant in MODEL_VARIANTS:
        records = [row for row in outputs if row['model_variant'] == variant]
        scored = [{**row, 'variant': variant} for row in records]
        measures = summarize({'outputs': scored}).get(variant, {'attempted': 0})
        measures.update(expected_cases=len(selected_ids), attempted_ids=[row['id'] for row in records],
                        pending_ids=[case_id for case_id in selected_ids if case_id not in {row['id'] for row in records}])
        groups = [row['group_outcomes'] for row in records]
        failed = [item for group in groups for item in group['failed_or_incomplete_groups']]
        malformed = [item for group in groups for item in group['malformed_or_missing_groups']]
        measures.update(failed_or_incomplete_group_count=len(failed), failed_or_incomplete_groups=failed,
                        malformed_or_missing_group_count=len(malformed), malformed_or_missing_groups=malformed,
                        unexpected_output_group_count=sum(group['unexpected_output_group_count'] for group in groups),
                        group_accounting_errors=[group['accounting_error'] for group in groups if group['accounting_error']],
                        group_accounting_complete=len(records) == len(selected_ids) and all(not group['accounting_error'] and not group['malformed_or_missing_groups']
                                                      and not group['unexpected_output_group_count'] for group in groups))
        summary[variant] = measures
    return summary


def group_outcomes(record):
    """Count explicit failures separately from groups whose status cannot be trusted.

    Missing or malformed groups are not silently counted as successful. Expected
    identity comes from the original source, and existing scorer errors identify
    invalid nested structures/locations. Ordinary missing-field issues are not
    generation errors; the frozen wrapper uses incomplete_draft for failures.
    """
    outcomes = {'expected_group_count': None, 'failed_or_incomplete_groups': [],
                'malformed_or_missing_groups': [], 'unexpected_output_group_count': 0, 'accounting_error': None}
    try: expected = split_events(record['source_text'])
    except Exception as error:
        outcomes['accounting_error'] = record['id'] + ': ' + coach._short_error(error)
        return outcomes
    outcomes['expected_group_count'] = len(expected)
    result = record.get('result')
    actual = result.get('event_results') if isinstance(result, dict) else None
    actual = actual if isinstance(actual, list) else []
    outcomes['unexpected_output_group_count'] = max(0, len(actual) - len(expected))
    errors = record['checks'].get('structure_errors', [])
    for index, group in enumerate(expected):
        identity = {'case_id': record['id'], 'event_id': group['event_id'], 'label': group['label']}
        event = actual[index] if index < len(actual) else None
        nested = event.get('result') if isinstance(event, dict) else None
        reasons = [error for error in errors if error.startswith(f'event_results[{index}]')]
        if not isinstance(event, dict): reasons.append('Expected event group is missing or is not an object.')
        elif any(event.get(key) != group[key] for key in ('event_id', 'label', 'grouping', 'source_text', 'source_segments')):
            reasons.append('Event identity or source mapping differs from the original notes.')
        if not isinstance(nested, dict): reasons.append('Nested group result is missing or malformed.')
        elif not isinstance(nested.get('status'), str) or nested['status'] not in VALID_STATUSES:
            reasons.append('Nested group status is absent or unrecognized.')
        if reasons:
            outcomes['malformed_or_missing_groups'].append({**identity, 'reasons': reasons})
        elif nested['status'] == 'incomplete_draft' or event.get('error') or nested.get('error'):
            outcomes['failed_or_incomplete_groups'].append({**identity, 'status': nested['status'],
                                                           'error': event.get('error') or nested.get('error'),
                                                           'issues': nested.get('issues', [])})
    return outcomes


def run_comparison(args, loader=None, root=core.ROOT):
    root = Path(root)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError('Choose a new --output path; comparison reports are never overwritten.')
    rows, selection = select_cases(root, args.split, args.case, args.design_frozen)
    if args.split == 'development' and selection['dataset_sha256'] != DEVELOPMENT_DATA_SHA256:
        raise ValueError('Development data differs from the frozen v3 candidate protocol.')
    fingerprints = runtime_fingerprints(root)
    print('VERIFY base model files and both adapter checkpoints', flush=True)
    current = adapter_fingerprint(args.current_adapter)
    candidate = adapter_fingerprint(args.candidate_adapter)
    base = model_fingerprint(args.model_dir, root / 'model-manifest.json')
    versions = {}
    for package in ('torch', 'transformers', 'peft', 'bitsandbytes', 'jsonschema'):
        try: versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError: versions[package] = 'unavailable'
    report = {'created_utc': datetime.now(timezone.utc).isoformat(), 'runtime': '2.5',
              **selection, **fingerprints, 'base_model': base,
              'adapters': {'current_v2': current, 'candidate_v3': candidate},
              'environment': {'python': platform.python_version(), 'packages': versions},
              'inference_configuration': {'load_in_4bit': True, 'quant_type': 'nf4',
                                          'double_quantization': True, 'compute_dtype': 'bfloat16',
                                          'model_dtype': 'bfloat16', 'attention_implementation': 'sdpa',
                                          'device_map': {'': 0}, 'do_sample': False,
                                          'use_cache': True, 'local_files_only': True, 'trust_remote_code': False,
                                          'organizer_max_new_tokens': 2600, 'helper_max_new_tokens': 1100,
                                          'organizer_max_prompt_tokens': 3500, 'helper_max_prompt_tokens': 6000,
                                          'source_character_limit': 120000, 'source_token_limit_per_event': 12000,
                                          'chunk_tokens': 2200, 'overlap_tokens': 160,
                                          'event_group_limit_including_preamble': 8, 'event_label_character_limit': 100,
                                          'evidence_quote_limit_per_entry': 64,
                                          'adapter_autocast_dtype': True, 'random_seed': 42,
                                          'torch_num_threads': 4, 'all_parameters_require_grad': False},
              'model_variants': list(MODEL_VARIANTS), 'model_order_per_case': list(MODEL_VARIANTS),
              'expected_case_variant_pairs': len(rows) * len(MODEL_VARIANTS),
              'protocol': 'One shared pinned NF4/BF16 base, two named frozen adapters; base uses disable_adapter. Every selected case uses its saved source, mode and assist flag for all three models. No training or adapter merging.',
              'selection_scope': ('full_' if selection['full_split_selected'] else 'subset_of_') + args.split,
              'limitations': 'Synthetic development/reserved records only. Structural and substring checks are not semantic accuracy, human workflow validation, or generalization. Case timings include variable helper passes and adapter activation; exclude initial loading and fingerprinting. This report covers only its listed IDs.',
              'training_performed_by_this_command': False, 'outputs': [],
              'status': 'loading_models', 'complete': False}
    report['protocol_files_sha256'] = {name: digest(root / name) for name in
                                      ('reports/V3-CANDIDATE-PROTOCOL.md', 'reports/V3-REVIEW-CHECKLIST.json',
                                       'reports/V3-REVIEW-EXPANSION-CHECKLIST.json', 'reports/V3-REVIEW-SCOPE.md')
                                      if (root / name).is_file()}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    models = None
    try:
        print('LOAD one quantized base and two named adapters', flush=True)
        models = (loader or load_models)(args.model_dir, args.current_adapter, args.candidate_adapter)
        report['loaded_model_state'] = models.snapshot()
        report['status'] = 'running'
        save_checkpoint(output, report)
        for row in rows:
            for variant in MODEL_VARIANTS:
                print('RUN', row['id'], variant, flush=True)
                result = {}; error = None; observed_state = None; started = time.monotonic()
                def progress(fraction, description):
                    print('PROGRESS', row['id'], variant, f'{fraction:.0%}', description, flush=True)
                try:
                    with models.activate(variant) as model:
                        observed_state = models.snapshot()
                        if observed_state != expected_state(variant):
                            raise RuntimeError('Observed adapter, evaluation, or gradient state does not match the intended model variant.')
                        result = event_formatter.process_note(model, models.tokenizer, row['source_text'],
                                                              mode=row['mode'], assist=row['assist'], progress=progress)
                except Exception as exception:
                    error = f'{type(exception).__name__}: {coach._short_error(exception)}'
                    result = getattr(exception, 'result', {})
                checks, scoring_error = score_safely(row, result, 'events', error)
                record = {'id': row['id'], 'domain': row['domain'], 'variant': 'events', 'model_variant': variant,
                          'source_text': row['source_text'], 'mode': row['mode'], 'assist': row['assist'],
                          'source_sha256': hashlib.sha256(row['source_text'].encode('utf-8')).hexdigest(),
                          'seconds': round(time.monotonic() - started, 3), 'error': error,
                          'expected_model_state': expected_state(variant), 'observed_model_state': observed_state,
                          'result': result, 'checks': checks}
                if scoring_error: record['scoring_error'] = scoring_error
                record['group_outcomes'] = group_outcomes(record)
                if not checks['structure_errors']:
                    try: record['draft'] = event_formatter.render_coached_log(result)
                    except Exception as exception: record['rendering_error'] = f'{type(exception).__name__}: {coach._short_error(exception)}'
                report['outputs'].append(record)
                report['summary'] = comparison_summary(report['outputs'], selection['selected_ids'])
                save_checkpoint(output, report)
                print('DONE', row['id'], variant, record['seconds'], 'seconds; complete structure:', checks['complete_structured_output'], flush=True)
        report.update(status='complete', complete=True)
    except BaseException as exception:
        report.update(status='loading_failed' if models is None else 'interrupted',
                      run_error=f'{type(exception).__name__}: {coach._short_error(exception)}')
        report['summary'] = comparison_summary(report['outputs'], selection['selected_ids'])
        save_checkpoint(output, report)
        raise
    save_checkpoint(output, report)
    print('Comparison complete for', len(rows), 'selected cases;', len(report['outputs']), 'model/case records.', flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, default=core.MODEL_DIR)
    parser.add_argument('--current-adapter', type=Path, default=core.ROOT / 'runs/adapter-v2')
    parser.add_argument('--candidate-adapter', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--split', choices=('development', 'reserved'), default='development')
    parser.add_argument('--case', action='append', help='Development case ID; repeat for a separately recorded matched stage.')
    parser.add_argument('--design-frozen', action='store_true', help='Acknowledge frozen candidate and evaluation design before the separate reserved invocation.')
    run_comparison(parser.parse_args())


if __name__ == '__main__':
    main()
