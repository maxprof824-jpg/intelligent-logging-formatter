"""Report a completed default v2 acceptance run; never label lexical checks accuracy."""
import json
from core import ROOT

def main():
    reports = ROOT/'reports'
    metrics = json.loads((reports/'adapter-v2-acceptance-metrics.json').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in (reports/'adapter-v2-acceptance.jsonl').read_text(encoding='utf-8').splitlines()]
    if (metrics.get('run_complete') is not True or metrics.get('selected_cases') != 18
            or metrics.get('attempted_cases') != 18 or metrics.get('remaining_cases') != 0
            or len(rows) != 18 or len({row['id'] for row in rows}) != 18):
        raise RuntimeError('Final v2 acceptance report requires a completed default 18-case run. No report was written.')
    if metrics.get('selected_ids') and set(metrics['selected_ids']) != {row['id'] for row in rows}:
        raise RuntimeError('Acceptance metrics and prediction case IDs differ. No report was written.')
    if metrics.get('base_model_only'):
        raise RuntimeError('The final adapter report cannot summarize a base-model run. No report was written.')
    training = json.loads((ROOT/'runs/adapter-v2/metrics.json').read_text(encoding='utf-8'))
    def count(key):
        value = metrics[key]
        suffix = ' (no items)' if value['denominator'] == 0 else ''
        return f"{value['numerator']}/{value['denominator']}{suffix}"
    versions = sorted({row.get('raw_result', {}).get('schema_version', 'unknown') for row in rows if row.get('raw_result')})
    lines = ['# Logging coach v2 — 18-case development evaluation', '',
             'V2 was trained on 480 richer fictional notes and evaluated against 48 validation notes during training. '
             'The 18 acceptance notes were authored independently and not used for model training; two are over 1,700 words. '
             'Their outputs were subsequently examined while refining the application pipeline. These are development '
             'acceptance results, not a pristine held-out estimate of generalization.', '',
             f"Training time: {training['train_runtime']/60:.1f} minutes. Peak allocated VRAM: {training['peak_allocated_vram_gib']:.2f} GiB; "
             f"peak reserved: {training['peak_reserved_vram_gib']:.2f} GiB.", '',
             f"Completed acceptance cases: {metrics['attempted_cases']}/{metrics['selected_cases']}. "
             'Results below describe the saved run, including conditional coaching assistance. Recorded schema: ' + ', '.join(versions) +
             '. Subsequent targeted fixes are reported separately in V2-REGRESSIONS.md; they do not retroactively change these scores.', '',
             '| Check | Result |', '|---|---:|',
             f"| Complete, structurally valid results | {count('complete_valid_results')} |",
             f"| Required literal strings retained in factual text | {count('literal_token_retention_in_factual_text')} |",
             f"| Expected absent factual sections left empty | {count('expected_absent_fact_sections_left_empty')} |",
             f"| Requested suggestion section coverage | {count('desired_suggestion_section_coverage')} |"]
    optional_checks = [
        ('raw_generated_chunk_schema_validity', 'Raw main-pass chunks matching the full output schema'),
        ('raw_unfiltered_fact_evidence_verbatim_quote_presence_in_cleaned_source', 'Raw main-pass fact evidence found verbatim in cleaned source'),
        ('raw_unfiltered_suggestion_basis_verbatim_quote_presence_in_cleaned_source', 'Raw main-pass suggestion basis found verbatim in cleaned source'),
        ('raw_coaching_output_schema_validity', 'Raw second-pass outputs matching the suggestions-only schema'),
        ('raw_coaching_suggestion_basis_verbatim_quote_presence_in_cleaned_source', 'Raw second-pass suggestion basis found verbatim in cleaned source'),
        ('fact_evidence_verbatim_quote_presence_in_cleaned_source', 'Final factual evidence found verbatim in cleaned source'),
        ('suggestion_basis_verbatim_quote_presence_in_cleaned_source', 'Final suggestion basis found verbatim in cleaned source'),
    ]
    for key, label in optional_checks:
        if key in metrics:
            lines.append(f'| {label} | {count(key)} |')
    lines += ['',
             'These are structural and literal-string checks, not semantic accuracy. A paraphrase may fail a literal check; '
             'a real quote can be interpreted incorrectly. Expected-empty-section checks sometimes penalize legitimate '
             'attributed future plans. Forbidden-phrase searches can produce false positives on negation or uncertainty. '
             'Suggestions still require human judgment and confirmation. '
             'The earlier v1 exact-match score uses a different task and dataset, so it is not directly comparable.', '',
             'Raw main-pass and second-pass checks are measured before source filtering and reported separately because '
             'their schemas differ. Quote denominators include quotations from schema-valid outputs only; malformed outputs '
             'are counted by schema checks but excluded from quote denominators. Final quote checks describe the retained '
             'draft after filtering and source-wording fallback. A second pass runs only when assistance is enabled and '
             'unresolved sections need suggestions; zero emitted outputs is not a perfect-score result.', '',
             '## Cases to inspect', '']
    cases_listed = 0
    for row in rows:
        checks = row['checks']
        problems = []
        if row.get('error'):
            error = row['error']
            message = error.get('message', str(error)) if isinstance(error, dict) else str(error)
            problems.append('pipeline error: '+message[:180])
        if checks['literal_token_retention']['missing']:
            problems.append('literal strings absent: '+', '.join(checks['literal_token_retention']['missing']))
        if checks['expected_absent_fact_sections']['nonempty']:
            problems.append('expected-empty sections populated: '+', '.join(checks['expected_absent_fact_sections']['nonempty']))
        if checks['desired_suggestion_section_coverage']['missing']:
            problems.append('suggestion sections absent: '+', '.join(checks['desired_suggestion_section_coverage']['missing']))
        if checks['forbidden_factual_claim_screen']['hits']:
            problems.append('factual-claim lexical screen needs contextual review')
        if checks['incomplete_draft_status']:
            problems.append('incomplete draft')
        if checks.get('raw_chunk_validation', {}).get('invalid_chunks'):
            problems.append('raw main-pass schema failure')
        if checks.get('raw_coaching_output_validation', {}).get('invalid_outputs'):
            problems.append('raw second-pass schema failure')
        raw_quotes = checks.get('raw_unfiltered_quote_support_in_cleaned_source', {})
        if any(raw_quotes.get(kind, {}).get('unsupported_quotes') for kind in ('fact_evidence', 'suggestion_basis')):
            problems.append('raw main-pass quotation not found verbatim')
        if checks.get('raw_coaching_quote_support_in_cleaned_source', {}).get('unsupported_quotes'):
            problems.append('raw second-pass quotation not found verbatim')
        if problems:
            lines.append('- '+row['id']+': '+'; '.join(problems)+'.')
            cases_listed += 1
    if not cases_listed:
        lines.append('No case was flagged by the checks listed above. Human review is still required.')
    lines += ['', '## What changed in the product', '',
              'The draft can reorganize and rephrase supplied facts. Items in the suggestions collection appear under separate '
              'visible labels within the five requested headings, with source-basis quotes and confirmation questions. '
              'The measured run also misclassified some proposals as factual sections; inspect the semantic reviews. A conditional second pass through the same '
              'adapter fills unresolved suggestion gaps; disabling assistance skips that additional pass. Simple numeric '
              'or initial mismatches preserve verified source wording in an UNASSIGNED review block, while unsupported source '
              'quotes are withheld. Recognized author editing requests, control lines and instruction-bearing delimited '
              'blocks are excluded. This filtering is not a complete defense against embedded instructions. Longer notes '
              'use overlapping chunks; unprocessed parts or missing source times remain visible as review issues.', '',
              'Initial raw failures were examined during pipeline refinement. This report describes one completed '
              'application run, not proof that the adapter alone resolves those failures on unseen notes. Both long cases remained '
              'below the 2,200-token chunk threshold (2,005 and 2,046 tokens), so this run did not exercise multiple input chunks. '
              'The separate chunking smoke report identifies its forced threshold and scope.', '',
              '## Semantic review', '',
              'Read [cases 01–09](V2-SEMANTIC-REVIEW-01-09.md) and [cases 10–18](V2-SEMANTIC-REVIEW-10-18.md). '
              'Known weaknesses include unsupported paraphrases, omitted or misplaced details, attribution errors, and inconsistent suggestions. '
              'A complete JSON result is not a correct or complete operational record.', '',
              'Raw main-model chunks, recorded second-pass outputs, the assembled result, every suggestion, per-case timing, errors, and the automated checks '
              'are preserved in adapter-v2-acceptance.jsonl. The full metrics file explains each denominator and limitation.']
    (reports/'V2-ACCEPTANCE.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines[:15]))

if __name__ == '__main__': main()
