"""Check evaluation-v3 structure and split integrity without running a model.

Reports IDs, counts, and hashes only. Reserved note contents are never printed.
Lexical expectations are review aids, not semantic accuracy labels.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
DOMAINS = ('maintenance_paperwork', 'it_support', 'facilities',
           'administrative_tracking', 'shift_handover')
SECTIONS = ('situation', 'impact', 'agencies_contacted', 'action', 'plan')
HEADING = re.compile(r'^\s*EVENT:\s*(\S[^\r\n]*?)\s*$', re.MULTILINE | re.IGNORECASE)
NONEMPTY_STRING = {'type': 'string', 'minLength': 1, 'pattern': r'\S'}
CHECK_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['event_label', 'section', 'required_fragments', 'forbidden_fragments', 'review_note'],
    'properties': {
        'event_label': {'anyOf': [NONEMPTY_STRING, {'type': 'null'}]},
        'section': {'enum': list(SECTIONS)},
        'required_fragments': {'type': 'array', 'uniqueItems': True, 'items': NONEMPTY_STRING},
        'forbidden_fragments': {'type': 'array', 'uniqueItems': True, 'items': NONEMPTY_STRING},
        'review_note': NONEMPTY_STRING,
    },
}
ROW_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['id', 'domain', 'mode', 'assist', 'source_text', 'expectations'],
    'properties': {
        'id': {'type': 'string', 'pattern': r'^(dev|reserved)-v3-[a-z]+-[0-9]{2}$'},
        'domain': {'enum': list(DOMAINS)}, 'mode': {'enum': ['draft', 'review']},
        'assist': {'type': 'boolean'}, 'source_text': NONEMPTY_STRING,
        'expectations': {
            'type': 'object', 'additionalProperties': False,
            'required': ['event_count', 'expected_event_labels', 'checks'],
            'properties': {
                'event_count': {'anyOf': [{'type': 'integer', 'minimum': 1}, {'type': 'null'}]},
                'expected_event_labels': {'type': 'array', 'uniqueItems': True, 'items': NONEMPTY_STRING},
                'checks': {'type': 'array', 'minItems': 1, 'items': CHECK_SCHEMA},
            },
        },
    },
}


def normalize(text):
    return ' '.join(text.casefold().split())


def event_sources(source):
    """Group exact normalized heading labels; repeated headings revisit an event.

    Preamble is deliberately excluded: it must not be silently copied to events.
    This helper validates expectations and does not infer unlabeled events.
    """
    found = list(HEADING.finditer(source))
    groups = {}
    labels = []
    for index, match in enumerate(found):
        label = match.group(1).strip()
        key = normalize(label)
        if key not in groups:
            labels.append(label)
            groups[key] = []
        end = found[index + 1].start() if index + 1 < len(found) else len(source)
        groups[key].append(source[match.end():end])
    return labels, {key: '\n'.join(parts) for key, parts in groups.items()}, len(found)


def validate_rows(rows, split, expected_count=None):
    from jsonschema import Draft202012Validator

    problems = []
    validator = Draft202012Validator(ROW_SCHEMA)
    valid_rows = []
    ids = set()
    sources = set()
    for index, row in enumerate(rows):
        identifier = row.get('id', f'row-{index + 1}') if isinstance(row, dict) else f'row-{index + 1}'
        errors = list(validator.iter_errors(row))
        if errors:
            # Do not print failing values: reserved contents remain opaque.
            paths = sorted({'.'.join(str(piece) for piece in error.absolute_path) or 'row' for error in errors})
            problems.append(f'{identifier}: schema error at {", ".join(paths)}')
            continue
        valid_rows.append(row)
        if row['id'] in ids:
            problems.append(f'{identifier}: duplicate id')
        ids.add(row['id'])
        wanted_prefix = 'dev-' if split == 'development' else 'reserved-'
        if not row['id'].startswith(wanted_prefix):
            problems.append(f'{identifier}: id prefix does not match split')
        source_key = normalize(row['source_text'])
        if source_key in sources:
            problems.append(f'{identifier}: duplicate normalized source')
        sources.add(source_key)
        labels, groups, _ = event_sources(row['source_text'])
        expectation = row['expectations']
        if expectation['expected_event_labels'] != labels:
            problems.append(f'{identifier}: expected labels differ from first-occurrence source headings')
        if expectation['event_count'] != (len(labels) or None):
            problems.append(f'{identifier}: event_count must count unique explicit labels, or be null without labels')
        for check_index, check in enumerate(expectation['checks']):
            key = normalize(check['event_label']) if check['event_label'] is not None else None
            if (labels and key not in groups) or (not labels and key is not None):
                problems.append(f'{identifier}: check {check_index} has an invalid event_label')
                continue
            if not check['required_fragments'] and not check['forbidden_fragments']:
                problems.append(f'{identifier}: check {check_index} has no lexical expectation')
            required = {normalize(fragment) for fragment in check['required_fragments']}
            forbidden = {normalize(fragment) for fragment in check['forbidden_fragments']}
            if required & forbidden:
                problems.append(f'{identifier}: check {check_index} has conflicting fragments')
            source = normalize(groups[key] if key is not None else row['source_text'])
            if any(fragment not in source for fragment in required):
                problems.append(f'{identifier}: check {check_index} requires a fragment absent from its event source')
    if expected_count is not None and len(rows) != expected_count:
        problems.append(f'{split}: expected {expected_count} rows, found {len(rows)}')
    counts = Counter(row['domain'] for row in valid_rows)
    per_domain = 4 if split == 'development' else 2
    for domain in DOMAINS:
        domain_rows = [row for row in valid_rows if row['domain'] == domain]
        if counts[domain] != per_domain:
            problems.append(f'{split}: {domain} needs {per_domain} rows')
        combinations = {(row['mode'], row['assist']) for row in domain_rows}
        if split == 'development' and combinations != {('draft', True), ('draft', False), ('review', True), ('review', False)}:
            problems.append(f'{split}: {domain} must cover all four mode/assistance combinations')
        if split == 'reserved' and ({row['mode'] for row in domain_rows} != {'draft', 'review'}
                                    or {row['assist'] for row in domain_rows} != {True, False}):
            problems.append(f'{split}: {domain} must include both modes and both assistance settings')
    long_rows = [row for row in valid_rows if len(row['source_text'].split()) >= 1700]
    heading_stats = [event_sources(row['source_text']) for row in valid_rows]
    if split == 'development':
        if len(long_rows) < 2:
            problems.append('development: need at least two substantive notes of at least 1700 words')
        if not any(not labels for labels, _, _ in heading_stats):
            problems.append('development: missing an unlabeled ambiguous case')
        if not any(headings > len(labels) for labels, _, headings in heading_stats):
            problems.append('development: missing a revisited explicit event label')
    return problems, {
        'rows': len(rows), 'ids': [row['id'] for row in valid_rows], 'domains': dict(sorted(counts.items())),
        'mode_assistance_counts': dict(sorted(Counter(f"{row['mode']}/assist={str(row['assist']).lower()}" for row in valid_rows).items())),
        'explicit_label_cases': sum(bool(labels) for labels, _, _ in heading_stats),
        'unlabeled_cases': sum(not labels for labels, _, _ in heading_stats),
        'revisited_label_cases': sum(headings > len(labels) for labels, _, headings in heading_stats),
        'long_notes': [{'id': row['id'], 'words': len(row['source_text'].split())} for row in long_rows],
    }


def validate_corpus(directory):
    problems = []
    all_rows = {}
    stats = {}
    for split, count in [('development', 20), ('reserved', 10)]:
        path = directory / f'{split}.jsonl'
        payload = path.read_bytes()
        rows = [json.loads(line) for line in payload.decode('utf-8').splitlines() if line.strip()]
        all_rows[split] = [row for row in rows if isinstance(row, dict)
                           and isinstance(row.get('id'), str) and isinstance(row.get('source_text'), str)]
        issues, split_stats = validate_rows(rows, split, count)
        problems.extend(issues)
        stats[split] = {**split_stats, 'sha256': hashlib.sha256(payload).hexdigest()}
    seen_ids = {row['id'] for row in all_rows['development']}
    seen_sources = {normalize(row['source_text']) for row in all_rows['development']}
    for row in all_rows['reserved']:
        if row['id'] in seen_ids:
            problems.append(f"{row['id']}: id overlaps development")
        if normalize(row['source_text']) in seen_sources:
            problems.append(f"{row['id']}: source overlaps development")
    return {'valid': not problems, 'problems': problems, 'splits': stats,
            'interpretation': 'Corpus integrity only; no model inference or semantic accuracy measurement.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'evaluation-v3')
    args = parser.parse_args()
    result = validate_corpus(args.directory)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['valid'] else 1)


if __name__ == '__main__':
    main()
