"""Summarize one completed evaluation without changing historical reports."""
import argparse
import json
import re
from core import ROOT


def write_summary(name, overwrite=False, reports=None):
    reports = ROOT / 'reports' if reports is None else reports
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name):
        raise ValueError('--name must be a simple filename prefix.')
    metrics_path = reports / f'{name}-acceptance-metrics.json'
    predictions_path = reports / f'{name}-acceptance.jsonl'
    destination = reports / f'{name}-acceptance.md'
    if destination.exists() and not overwrite:
        raise FileExistsError(f'{destination.name} already exists. Use --overwrite to replace it.')
    metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in predictions_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    count = metrics.get('selected_cases')
    if (not isinstance(count, int) or count < 1 or metrics.get('run_complete') is not True
            or metrics.get('attempted_cases') != count or metrics.get('remaining_cases') != 0
            or len(rows) != count or len({row['id'] for row in rows}) != count):
        raise RuntimeError('Summary requires one completed run with matching case counts. No report was written.')
    if metrics.get('run_name') != name or set(metrics.get('selected_ids', [])) != {row['id'] for row in rows}:
        raise RuntimeError('Metrics and prediction run/case IDs differ. No report was written.')
    versions = sorted({(row.get('raw_result') or {}).get('schema_version', 'unknown') for row in rows})
    model = 'Base model without an adapter' if metrics.get('base_model_only') else 'Model with the selected adapter'
    usage = metrics.get('dataset_usage', {})
    lines = [
        '# Intelligent Logging Formatter — evaluation report', '',
        f"Run: `{name}`. Started: {metrics.get('started_utc', 'not recorded')}. Completed cases: **{count}/{count}**.", '',
        f"{model}. Output schema: {', '.join(versions)}. Mode: `{metrics.get('mode', 'not recorded')}`; "
        f"assistance enabled: `{metrics.get('assist', 'not recorded')}`.", '',
        usage.get('interpretation', 'Dataset independence was not recorded; do not assume this is an untouched holdout.'), '',
        '**These checks describe structure and literal strings, not semantic accuracy.** '
        'A quotation can exist in the note while its paraphrase is wrong, a retained detail can be in the wrong section, '
        'and a suggested action still needs human judgment.', '',
        '| Check | Result |', '|---|---:|',
    ]
    checks = [
        ('complete_valid_results', 'Complete, structurally valid results'),
        ('literal_token_retention_in_factual_text', 'Required literal strings in factual text'),
        ('expected_absent_fact_sections_left_empty', 'Expected absent factual sections left empty'),
        ('desired_suggestion_section_coverage', 'Requested suggestion section coverage'),
        ('raw_generated_chunk_schema_validity', 'Raw main outputs matching the schema'),
        ('raw_unfiltered_fact_evidence_verbatim_quote_presence_in_cleaned_source', 'Raw fact quotes found in source'),
        ('raw_unfiltered_suggestion_basis_verbatim_quote_presence_in_cleaned_source', 'Raw suggestion quotes found in source'),
        ('raw_coaching_output_schema_validity', 'Raw helper outputs matching the schema'),
        ('raw_coaching_suggestion_basis_verbatim_quote_presence_in_cleaned_source', 'Raw helper quotes found in source'),
        ('fact_evidence_verbatim_quote_presence_in_cleaned_source', 'Retained fact quotes found in source'),
        ('suggestion_basis_verbatim_quote_presence_in_cleaned_source', 'Retained suggestion quotes found in source'),
    ]
    for key, label in checks:
        if key in metrics:
            value = metrics[key]
            denominator = value['denominator']
            result = f"{value['numerator']}/{denominator}" if denominator else 'No scored items'
            lines.append(f'| {label} | {result} |')
    lines += ['', '## Cases flagged for review', '']
    flagged = [(row['id'], row.get('checks', {}).get('failures', [])) for row in rows]
    flagged = [(case_id, failures) for case_id, failures in flagged if failures]
    if flagged:
        lines.extend(f"- `{case_id}`: {', '.join(failures)}." for case_id, failures in flagged)
    else:
        lines.append('No cases were flagged by the recorded automated checks. Human review is still required.')
    lines += ['', '## Scope', '',
              'This report summarizes only the selected run. It does not update earlier measurements or establish '
              'that fine-tuning outperformed the base model. That requires a matched comparison.', '',
              'Read source notes and outputs to assess actor attribution, chronology, negation, omitted details, '
              'field placement, and whether suggestions are useful. Quote checks exclude malformed outputs from '
              'their denominators; the separate schema checks count those failures. An empty-section check may '
              'penalize a supported statement of uncertainty. Literal and forbidden-phrase checks can miss paraphrases '
              'or flag negated statements.', '',
              f'Full outputs: [{predictions_path.name}]({predictions_path.name}). '
              f'Metrics, per-case failures, timing, and artifact fingerprints: [{metrics_path.name}]({metrics_path.name}).']
    with destination.open('w' if overwrite else 'x', encoding='utf-8') as output:
        output.write('\n'.join(lines) + '\n')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True, help='Exact evaluation run name to summarize.')
    parser.add_argument('--overwrite', action='store_true', help='Explicitly replace this run\'s Markdown summary.')
    args = parser.parse_args()
    print(write_summary(args.name, args.overwrite))


if __name__ == '__main__':
    main()
