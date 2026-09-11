"""Expose source text outside accepted factual evidence; this is not semantic validation."""
import re


def evidence_coverage(source, sections):
    """Return literal source coverage and unquoted spans in original source order.

    A broad or repeated quote can overstate coverage, so the UI describes this as
    evidence coverage, never fact completeness. Suggestions do not count as facts.
    """
    intervals = []
    quotes = {q for facts in sections.values() for fact in facts for q in fact['evidence'] if q}
    for quote in quotes:
        start = 0
        while (found := source.find(quote, start)) != -1:
            intervals.append((found, found + len(quote)))
            start = found + len(quote)
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    gaps, cursor = [], 0
    for start, end in [*merged, (len(source), len(source))]:
        text = source[cursor:start].strip()
        # Headings provide structure, not facts that need a second entry.
        for part in text.splitlines():
            part = part.strip()
            if re.fullmatch(r'(?:SITUATION(?:\s*\([^)]*\))?|IMPACT|AGENCIES CONTACTED(?:\s*\([^)]*\))?|ACTION|PLAN)\s*:', part, re.I):
                continue
            if re.search(r'\w', part):
                gaps.append(part)
        cursor = end
    return {'source_characters': len(source),
            'characters_in_fact_evidence': sum(end-start for start,end in merged),
            'unquoted_spans': gaps,
            'interpretation': 'Literal quote coverage only. It does not establish correct meaning, field placement, or completeness.'}


def add_source_coverage(result, source):
    coverage = evidence_coverage(source, result['sections'])
    result['source_coverage'] = coverage
    excerpts = result.setdefault('review_excerpts', [])
    visible = '\n'.join(f['text'] for f in excerpts)
    added = 0
    for text in coverage['unquoted_spans']:
        if text in visible:
            continue
        # Keep exact continuous spans; avoid chopping a decimal or an identifier.
        while text:
            cut = len(text) if len(text) <= 1200 else text.rfind(' ', 0, 1200)
            if cut <= 0:
                cut = min(1200, len(text))
            span = text[:cut].strip()
            if span:
                excerpts.append({'text': span, 'evidence': [span]})
                visible += '\n' + span
                added += 1
            text = text[cut:].strip()
    if added:
        result['issues'].append(f'{added} source passage(s) were not covered by accepted factual evidence. They are preserved below for review, including details without dates or reference numbers.')
        if result['status'] != 'incomplete_draft':
            result['status'] = 'needs_confirmation'
    return result
