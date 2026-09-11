"""Run synthetic acceptance/regression cases through the complete v2 pipeline.

Metrics are structural checks and lexical screens, never semantic accuracy.
Inference is sequential; importing this module does not load a model.
"""
import argparse
import hashlib
import json
import re
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import coach
from core import FIELDS, ROOT, TYPES, load_model


VALID_STATUSES = {'needs_confirmation', 'ready_for_human_review', 'incomplete_draft'}
COACHING_OUTPUT_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['suggestions'],
    'properties': {'suggestions': {'type': 'array', 'maxItems': 3, 'items': coach.SUGGESTION}},
}
DATASET_USAGE = {
    'independently_authored': True,
    'used_during_pipeline_refinement': True,
    'pristine_holdout': False,
    'interpretation': 'Acceptance/regression set inspected during pipeline refinement; these results are not an untouched held-out generalization estimate.',
}
LIMITATIONS = [
    'This small synthetic administrative set was independently authored but has since been used during pipeline refinement. It is an acceptance/regression set, not a pristine holdout, and does not establish readiness for real operations.',
    'Factual-text retention, emptiness, suggestion coverage, and forbidden-claim screens use final v2 pipeline output after filtering and assembly. Raw chunk outputs, schema validity, and pre-filter quote presence are recorded separately.',
    'Literal token retention uses case-insensitive substring matching in concatenated factual section texts only. It is not semantic accuracy: paraphrases or formatting changes can fail, and misplaced or negated strings can pass.',
    'Expected section emptiness is a strict structural check, not a judgment of field accuracy. A supported statement that a detail is unknown can populate a section and fail this check; inspect the displayed text.',
    'Suggestion coverage counts a suggestion with the requested section label; it does not establish usefulness, correctness, calibrated uncertainty, or proper administrative scope.',
    'A quote found verbatim in cleaned source establishes lexical quote presence only; it does not prove the generated claim follows from that quote.',
    'Forbidden factual claims are case-insensitive substring screens of factual texts only, excluding suggestions, evidence, questions, and source text. Negation can trigger false positives; paraphrases can evade the screen.',
    'A valid schema or status does not establish a correct, complete, or human-approved log. Incomplete chunks are tracked explicitly; a partial result is not a completed case.',
    'Failed or invalid results contribute no successes to expectation-based metrics. Final quote-support and forbidden-claim screens use only structurally valid final results; their denominators are shown.',
    'Raw quote-support metrics inspect all evidence and basis quotes in schema-valid raw chunk records before source filtering, against the entire cleaned source. Invalid raw chunks are excluded, and included/excluded chunk counts are shown. Repeated quotes across chunks count as separate emissions.',
    'Conditional coaching-helper outputs use a separate suggestions-only schema and are scored separately from main-model chunks. Helper quote metrics include only schema-valid helper outputs retained in result.coaching_outputs; malformed outputs are counted but excluded from quote denominators. A helper failure does not itself imply that the main factual draft is incomplete.',
    'Human review must still assess chronology, attribution, negation, claim entailment, fact/suggestion separation, relevance, and the practicality of suggestions. Do not report these metrics as field accuracy or operational reliability.',
]


def fraction(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'rate': numerator / denominator if denominator else None}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source_file:
        for block in iter(lambda: source_file.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def artifact_hashes(adapter, dataset):
    """Fingerprint the evaluated code, available datasets, and selected adapter."""
    code = {name: sha256_file(ROOT / name) for name in
            ('coach.py', 'coaching_pass.py', 'core.py', 'evaluate_v2.py', 'app.py')}
    datasets = {'data-v2/acceptance.jsonl': sha256_file(dataset)}
    for name in ('train.jsonl', 'validation.jsonl'):
        path = ROOT / 'data-v2' / name
        datasets[f'data-v2/{name}'] = sha256_file(path) if path.is_file() else None
    adapter_details = None
    if adapter is not None:
        adapter = Path(adapter)
        weights = sorted(set(adapter.glob('adapter_model*.safetensors')) |
                         set(adapter.glob('adapter_model*.bin')))
        if not weights:
            raise FileNotFoundError(f'No adapter weight files found in {adapter}.')
        files = [adapter / 'adapter_config.json', *weights]
        adapter_details = {'path': str(adapter.resolve()),
                           'files': {path.name: sha256_file(path) for path in files}}
    return {
        'algorithm': 'sha256', 'captured_utc': datetime.now(timezone.utc).isoformat(),
        'code': code, 'datasets': datasets, 'adapter': adapter_details,
        'coverage': 'Computed before model load. Covers the listed code and dataset files plus selected adapter configuration/weights. Base-model weights and runtime dependencies are not hashed.',
    }


def validate_result(result):
    """Validate assembled structure without imposing per-chunk fact-count limits."""
    from jsonschema import validate

    errors = []
    if not isinstance(result, dict):
        return ['No result object was returned.']
    if result.get('event_type') not in TYPES:
        errors.append('event_type is missing or invalid.')
    sections = result.get('sections')
    if not isinstance(sections, dict) or set(sections) != set(FIELDS):
        errors.append('sections must contain exactly the five required field keys.')
    else:
        for field in FIELDS:
            if not isinstance(sections[field], list):
                errors.append(f'{field} is not a list.')
                continue
            for i, fact in enumerate(sections[field]):
                try:
                    validate(fact, coach.FACT)
                except Exception as error:
                    errors.append(f'{field}[{i}]: {error.message if hasattr(error, "message") else error}')
    suggestions = result.get('suggestions')
    if not isinstance(suggestions, list):
        errors.append('suggestions is not a list.')
    else:
        for i, suggestion in enumerate(suggestions):
            try:
                validate(suggestion, coach.SUGGESTION)
            except Exception as error:
                errors.append(f'suggestions[{i}]: {error.message if hasattr(error, "message") else error}')
    if result.get('status') not in VALID_STATUSES:
        errors.append('status is missing or invalid.')
    if result.get('human_approval_required') is not True:
        errors.append('human_approval_required must be true.')
    if not isinstance(result.get('issues'), list):
        errors.append('issues is not a list.')
    if isinstance(sections, dict) and all(isinstance(sections.get(f), list) for f in FIELDS):
        actual_missing = {f for f in FIELDS if not sections[f]}
        declared_missing = result.get('missing_fields')
        if not isinstance(declared_missing, list) or set(declared_missing) != actual_missing:
            errors.append('missing_fields disagrees with the empty factual sections.')
    return errors


def inspect_coaching_outputs(result, cleaned_source):
    """Score raw suggestions-only helper output before source-quote filtering."""
    from jsonschema import validate

    outputs = result.get('coaching_outputs', []) if isinstance(result, dict) else []
    collection_error = None
    if not isinstance(outputs, list):
        collection_error = 'result.coaching_outputs must be a list of raw JSON strings.'
        outputs = []
    valid_count, invalid = 0, []
    quote_counts = {'checked_quotes': 0, 'verbatim_supported_quotes': 0, 'unsupported_quotes': []}
    for output_index, raw in enumerate(outputs, start=1):
        try:
            if not isinstance(raw, str):
                raise TypeError('Raw coaching output must be a JSON string.')
            record = json.loads(raw.strip())
            validate(record, COACHING_OUTPUT_SCHEMA)
        except Exception as error:
            invalid.append({'output_index': output_index, 'error': str(error)})
            continue
        valid_count += 1
        for item_index, suggestion in enumerate(record['suggestions']):
            for quote_index, quote in enumerate(suggestion['basis']):
                quote_counts['checked_quotes'] += 1
                if quote and quote in cleaned_source:
                    quote_counts['verbatim_supported_quotes'] += 1
                else:
                    quote_counts['unsupported_quotes'].append({
                        'output_index': output_index, 'section': suggestion['section'],
                        'item_index': item_index, 'quote_index': quote_index, 'quote': quote,
                    })
    return {
        'validation': {'emitted_outputs': len(outputs), 'schema_valid_outputs': valid_count,
                       'invalid_outputs': invalid, 'collection_error': collection_error},
        'quote_support': {'schema_valid_outputs_included': valid_count,
                          'schema_invalid_outputs_excluded': len(invalid), **quote_counts},
    }


def inspect_case(row, result, raw_outputs, error=None):
    cleaned_source, removed = coach.clean_source(row['source_text'])
    validation_errors = validate_result(result)
    valid = not validation_errors
    sections = result['sections'] if valid else {f: [] for f in FIELDS}
    suggestions = result['suggestions'] if valid else []
    factual_by_section = {f: '\n'.join(item['text'] for item in sections[f]) for f in FIELDS}
    factual_text = '\n'.join(factual_by_section.values())
    expected = row['expected']
    retained = [s for s in expected['must_retain'] if s.lower() in factual_text.lower()]
    missing = [s for s in expected['must_retain'] if s.lower() not in factual_text.lower()]
    empty = [f for f in expected['absent_fact_sections'] if valid and not sections[f]]
    nonempty = {f: factual_by_section[f] for f in expected['absent_fact_sections']
                if valid and sections[f]}
    actual_suggestion_sections = {s['section'] for s in suggestions}
    covered = [f for f in expected['suggestion_sections'] if valid and f in actual_suggestion_sections]
    uncovered = [f for f in expected['suggestion_sections'] if f not in covered]

    forbidden_hits = []
    if valid:
        for phrase in expected['forbidden_factual_claims']:
            for field, text in factual_by_section.items():
                position = text.lower().find(phrase.lower())
                if position >= 0:
                    forbidden_hits.append({'phrase': phrase, 'section': field,
                        'context': text[max(0, position - 100):position + len(phrase) + 100]})

    quote_results = {}
    for label, items, quote_key in [
        ('fact_evidence', [(field, item) for field in FIELDS for item in sections[field]], 'evidence'),
        ('suggestion_basis', [(item['section'], item) for item in suggestions], 'basis'),
    ]:
        total, supported, unsupported = 0, 0, []
        for item_index, (field, item) in enumerate(items):
            for quote_index, quote in enumerate(item[quote_key]):
                total += 1
                if quote and quote in cleaned_source:
                    supported += 1
                else:
                    unsupported.append({'section': field, 'item_index': item_index,
                                        'quote_index': quote_index, 'quote': quote})
        quote_results[label] = {'checked_quotes': total, 'verbatim_supported_quotes': supported,
                                'unsupported_quotes': unsupported}

    raw_valid = 0
    raw_errors = []
    raw_quote_results = {
        kind: {'checked_quotes': 0, 'verbatim_supported_quotes': 0, 'unsupported_quotes': []}
        for kind in ('fact_evidence', 'suggestion_basis')
    }
    for i, raw in enumerate(raw_outputs):
        try:
            raw_record = coach.parse_coached_output(raw)
        except Exception as parse_error:
            raw_errors.append({'chunk_index': i + 1, 'error': str(parse_error)})
            continue
        raw_valid += 1
        for kind, items, quote_key in [
            ('fact_evidence', [(field, index, item) for field in FIELDS
                               for index, item in enumerate(raw_record['sections'][field])], 'evidence'),
            ('suggestion_basis', [(item['section'], index, item)
                                 for index, item in enumerate(raw_record['suggestions'])], 'basis'),
        ]:
            counts = raw_quote_results[kind]
            for field, item_index, item in items:
                for quote_index, quote in enumerate(item[quote_key]):
                    counts['checked_quotes'] += 1
                    if quote and quote in cleaned_source:
                        counts['verbatim_supported_quotes'] += 1
                    else:
                        counts['unsupported_quotes'].append({
                            'chunk_index': i + 1, 'section': field, 'item_index': item_index,
                            'quote_index': quote_index, 'quote': quote,
                        })
    coaching_checks = inspect_coaching_outputs(result, cleaned_source)
    status = result.get('status') if isinstance(result, dict) else None
    issues = result.get('issues', []) if isinstance(result, dict) else []
    incomplete_marker = any(str(issue).startswith('INCOMPLETE DRAFT:') for issue in issues)
    raw_invalid = len(raw_outputs) - raw_valid
    partial_result_detected = bool(result is not None and (raw_invalid or incomplete_marker))
    incomplete_status = status == 'incomplete_draft'
    status_consistent = bool(valid and incomplete_status == partial_result_detected)

    failures = []
    if error:
        failures.append('pipeline_error')
    if not valid:
        failures.append('invalid_result_structure_or_status')
    if missing:
        failures.append('literal_retention_strings_missing')
    if nonempty:
        failures.append('expected_absent_fact_section_nonempty')
    if uncovered:
        failures.append('desired_suggestion_sections_missing')
    if forbidden_hits:
        failures.append('forbidden_factual_claim_lexical_screen_hit')
    if any(v['unsupported_quotes'] for v in quote_results.values()):
        failures.append('retained_quote_not_in_cleaned_source')
    if partial_result_detected or incomplete_status:
        failures.append('incomplete_draft')
    if valid and not status_consistent:
        failures.append('incomplete_chunk_status_mismatch')
    return {
        'valid_result': valid, 'result_validation_errors': validation_errors,
        'status': status, 'status_valid': status in VALID_STATUSES,
        'incomplete_draft_status': incomplete_status,
        'incomplete_chunks_detected': partial_result_detected,
        'incomplete_status_consistent': status_consistent,
        'raw_chunk_validation': {'emitted_chunks': len(raw_outputs), 'schema_valid_chunks': raw_valid,
                                 'invalid_chunks': raw_errors},
        'raw_coaching_output_validation': coaching_checks['validation'],
        'raw_coaching_quote_support_in_cleaned_source': coaching_checks['quote_support'],
        'literal_token_retention': {'expected': expected['must_retain'], 'retained': retained,
                                    'missing': missing, 'all_retained': bool(valid and not missing)},
        'expected_absent_fact_sections': {'expected': expected['absent_fact_sections'],
                                        'empty': empty, 'nonempty': nonempty,
                                        'unscored_due_to_invalid_result': not valid},
        'desired_suggestion_section_coverage': {'expected': expected['suggestion_sections'],
                                               'covered': covered, 'missing': uncovered},
        'forbidden_factual_claim_screen': {'checked_phrases': len(expected['forbidden_factual_claims']) if valid else 0,
                                          'hits': forbidden_hits, 'screened': valid},
        'verbatim_quote_support_in_cleaned_source': quote_results,
        'raw_unfiltered_quote_support_in_cleaned_source': {
            'schema_valid_chunks_included': raw_valid,
            'schema_invalid_chunks_excluded': len(raw_errors),
            **raw_quote_results,
        },
        'explicit_instruction_lines_removed': len(removed),
        'cleaned_source_characters': len(cleaned_source),
        'failures': failures, 'review_notes': expected['notes'],
    }


def summarize(outputs, selected_count):
    checks = [o['checks'] for o in outputs]
    count = len(checks)
    retention_total = sum(len(c['literal_token_retention']['expected']) for c in checks)
    retention_hits = sum(len(c['literal_token_retention']['retained']) for c in checks)
    absent_total = sum(len(c['expected_absent_fact_sections']['expected']) for c in checks)
    absent_empty = sum(len(c['expected_absent_fact_sections']['empty']) for c in checks)
    desired_total = sum(len(c['desired_suggestion_section_coverage']['expected']) for c in checks)
    desired_covered = sum(len(c['desired_suggestion_section_coverage']['covered']) for c in checks)
    metrics = {
        'selected_cases': selected_count, 'attempted_cases': count,
        'dataset_usage': DATASET_USAGE,
        'remaining_cases': selected_count - count,
        'valid_final_result_structure_and_status': fraction(sum(c['valid_result'] for c in checks), count),
        'complete_valid_results': fraction(sum(c['valid_result'] and not c['incomplete_draft_status']
                                              and not c['incomplete_chunks_detected'] and not o['error']
                                              for c, o in zip(checks, outputs)), count),
        'literal_token_retention_in_factual_text': fraction(retention_hits, retention_total),
        'cases_with_all_literal_retention_strings': fraction(sum(c['literal_token_retention']['all_retained'] for c in checks), count),
        'expected_absent_fact_sections_left_empty': fraction(absent_empty, absent_total),
        'desired_suggestion_section_coverage': fraction(desired_covered, desired_total),
        'forbidden_factual_claim_screen': {
            'cases_screened': sum(c['forbidden_factual_claim_screen']['screened'] for c in checks),
            'phrases_screened': sum(c['forbidden_factual_claim_screen']['checked_phrases'] for c in checks),
            'cases_with_lexical_hits': sum(bool(c['forbidden_factual_claim_screen']['hits']) for c in checks),
            'phrase_section_hits': sum(len(c['forbidden_factual_claim_screen']['hits']) for c in checks),
            'interpretation': 'Lexical screen only; inspect hit contexts for negation and paraphrase limitations.',
        },
        'raw_generated_chunk_schema_validity': fraction(
            sum(c['raw_chunk_validation']['schema_valid_chunks'] for c in checks),
            sum(c['raw_chunk_validation']['emitted_chunks'] for c in checks)),
        'incomplete_draft_cases': sum(c['incomplete_draft_status'] or c['incomplete_chunks_detected'] for c in checks),
        'incomplete_status_consistency_in_valid_results': fraction(
            sum(c['incomplete_status_consistent'] for c in checks), sum(c['valid_result'] for c in checks)),
        'pipeline_error_cases': sum(bool(o['error']) for o in outputs),
        'case_failures': [{'id': o['id'], 'failures': o['checks']['failures'],
                           'missing_literal_strings': o['checks']['literal_token_retention']['missing'],
                           'review_notes': o['checks']['review_notes']}
                          for o in outputs if o['checks']['failures']],
        'limitations': LIMITATIONS,
    }
    for kind in ('fact_evidence', 'suggestion_basis'):
        counts = [c['verbatim_quote_support_in_cleaned_source'][kind] for c in checks]
        metrics[f'{kind}_verbatim_quote_presence_in_cleaned_source'] = fraction(
            sum(v['verbatim_supported_quotes'] for v in counts), sum(v['checked_quotes'] for v in counts))
        raw_counts = [c['raw_unfiltered_quote_support_in_cleaned_source'][kind] for c in checks]
        metrics[f'raw_unfiltered_{kind}_verbatim_quote_presence_in_cleaned_source'] = fraction(
            sum(v['verbatim_supported_quotes'] for v in raw_counts), sum(v['checked_quotes'] for v in raw_counts))
    metrics['raw_unfiltered_quote_support_scope'] = {
        'schema_valid_chunks_included': sum(c['raw_unfiltered_quote_support_in_cleaned_source']['schema_valid_chunks_included'] for c in checks),
        'schema_invalid_chunks_excluded': sum(c['raw_unfiltered_quote_support_in_cleaned_source']['schema_invalid_chunks_excluded'] for c in checks),
        'cases_with_unsupported_fact_evidence_quotes': sum(bool(c['raw_unfiltered_quote_support_in_cleaned_source']['fact_evidence']['unsupported_quotes']) for c in checks),
        'cases_with_unsupported_suggestion_basis_quotes': sum(bool(c['raw_unfiltered_quote_support_in_cleaned_source']['suggestion_basis']['unsupported_quotes']) for c in checks),
        'interpretation': 'Before coach source filtering; case-sensitive continuous quote match against the entire cleaned source. Includes schema-valid raw chunks even if the final pipeline result failed.',
    }
    helper_validation = [c['raw_coaching_output_validation'] for c in checks]
    helper_quotes = [c['raw_coaching_quote_support_in_cleaned_source'] for c in checks]
    metrics['raw_coaching_output_schema_validity'] = fraction(
        sum(v['schema_valid_outputs'] for v in helper_validation),
        sum(v['emitted_outputs'] for v in helper_validation))
    metrics['raw_coaching_suggestion_basis_verbatim_quote_presence_in_cleaned_source'] = fraction(
        sum(v['verbatim_supported_quotes'] for v in helper_quotes),
        sum(v['checked_quotes'] for v in helper_quotes))
    metrics['raw_coaching_quote_support_scope'] = {
        'schema_valid_outputs_included': sum(v['schema_valid_outputs_included'] for v in helper_quotes),
        'schema_invalid_outputs_excluded': sum(v['schema_invalid_outputs_excluded'] for v in helper_quotes),
        'cases_with_helper_outputs': sum(bool(v['emitted_outputs']) for v in helper_validation),
        'cases_with_invalid_helper_outputs': sum(bool(v['invalid_outputs']) for v in helper_validation),
        'cases_with_invalid_coaching_outputs_collection': sum(bool(v['collection_error']) for v in helper_validation),
        'cases_with_unsupported_helper_basis_quotes': sum(bool(v['unsupported_quotes']) for v in helper_quotes),
        'interpretation': 'Suggestions-only helper outputs scored before source filtering, separately from main-model chunks. Exact case-sensitive quote match against the entire cleaned source; malformed helper outputs excluded from quote denominators.',
    }
    return metrics


def run_case(model, tokenizer, row):
    """Capture emitted chunks without changing generation or filtering behavior."""
    captured_chunks, result, rendered, error = [], None, None, None
    original_generate = coach.generate_coached

    def capture(*args, **kwargs):
        chunk_start = time.perf_counter()
        entry = {'chunk_index': len(captured_chunks) + 1, 'raw': None, 'error': None}
        captured_chunks.append(entry)
        try:
            entry['raw'] = original_generate(*args, **kwargs)
            return entry['raw']
        except Exception as chunk_error:
            entry['error'] = {'type': type(chunk_error).__name__, 'message': str(chunk_error)}
            raise
        finally:
            entry['runtime_seconds'] = time.perf_counter() - chunk_start

    start = time.perf_counter()
    coach.generate_coached = capture
    try:
        result = coach.process_note(model, tokenizer, row['source_text'], mode='draft', assist=True)
        rendered = coach.render_coached_log(result)
    except Exception as case_error:
        error = {'type': type(case_error).__name__, 'message': str(case_error),
                 'traceback': traceback.format_exc()}
    finally:
        coach.generate_coached = original_generate
    raw_outputs = [c['raw'] for c in captured_chunks if c['raw'] is not None]
    output = {'id': row['id'], 'source_text': row['source_text'], 'expected': row['expected'],
              'raw_result': result, 'raw_chunks': captured_chunks, 'rendered_draft': rendered,
              'runtime_seconds': time.perf_counter() - start, 'error': error}
    output['checks'] = inspect_case(row, result, raw_outputs, error)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', default='runs/adapter-v2', help='Adapter path, absolute or relative to this project.')
    parser.add_argument('--name', default='adapter-v2', help='Report filename prefix; letters, digits, dots, underscores, or hyphens.')
    parser.add_argument('--limit', type=int, default=None, help='Run at most this many cases, after applying --ids.')
    parser.add_argument('--ids', default=None, help='Comma-separated case IDs; execution follows dataset order.')
    parser.add_argument('--base', action='store_true', help='Use the original base model without any adapter, under the same v2 pipeline.')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', args.name):
        parser.error('--name must be a simple filename prefix.')
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be a positive integer.')
    dataset = ROOT / 'data-v2' / 'acceptance.jsonl'
    rows = [json.loads(line) for line in dataset.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len({r['id'] for r in rows}) != len(rows):
        parser.error('The acceptance dataset contains duplicate case IDs.')
    if args.ids is not None:
        requested = {item.strip() for item in args.ids.split(',') if item.strip()}
        unknown = requested - {r['id'] for r in rows}
        if unknown or not requested:
            parser.error('Unknown or empty --ids selection: ' + ', '.join(sorted(unknown)))
        rows = [r for r in rows if r['id'] in requested]
    if args.limit is not None:
        rows = rows[:args.limit]
    if not rows:
        parser.error('No acceptance cases selected.')
    adapter = None if args.base else Path(args.adapter)
    if adapter is not None and not adapter.is_absolute():
        adapter = ROOT / adapter
    if adapter is not None and not (adapter / 'adapter_config.json').is_file():
        parser.error(f'Adapter configuration not found: {adapter / "adapter_config.json"}')
    reports = ROOT / 'reports'
    reports.mkdir(exist_ok=True)
    predictions_path = reports / f'{args.name}-acceptance.jsonl'
    metrics_path = reports / f'{args.name}-acceptance-metrics.json'
    start = time.perf_counter()
    fingerprints = artifact_hashes(adapter, dataset)
    metadata = {'run_name': args.name, 'started_utc': datetime.now(timezone.utc).isoformat(),
                'adapter': str(adapter) if adapter else None, 'base_model_only': args.base,
                'pipeline': 'coach.process_note(mode=draft, assist=True)',
                'dataset': str(dataset), 'selected_ids': [r['id'] for r in rows],
                'dataset_usage': DATASET_USAGE,
                'artifact_hashes': fingerprints,
                'predictions_path': str(predictions_path), 'mode': 'draft', 'assist': True,
                'sequential_inference': True}
    outputs = []

    def save_metrics(run_complete=False, load_error=None):
        metrics = summarize(outputs, len(rows))
        metrics.update(metadata, wall_seconds=time.perf_counter() - start,
                       run_complete=run_complete, model_load_error=load_error)
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
        return metrics

    with predictions_path.open('w', encoding='utf-8') as log:
        save_metrics()
        try:
            import torch
            torch.set_num_threads(4)
            model, tokenizer = load_model(adapter)
        except Exception as model_error:
            save_metrics(load_error={'type': type(model_error).__name__, 'message': str(model_error)})
            raise
        for row in rows:
            output = run_case(model, tokenizer, row)
            outputs.append(output)
            log.write(json.dumps(output, ensure_ascii=False) + '\n')
            log.flush()
            save_metrics()
            checks = output['checks']
            print(f"{args.name} {len(outputs)}/{len(rows)} {row['id']} "
                  f"status={checks['status']} literal_missing={len(checks['literal_token_retention']['missing'])} "
                  f"seconds={output['runtime_seconds']:.1f}", flush=True)
    save_metrics(run_complete=True)
    print(f'Results: {predictions_path}\nMetrics: {metrics_path}', flush=True)


if __name__ == '__main__':
    main()
