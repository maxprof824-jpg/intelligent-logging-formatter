"""CPU replay of recorded real-model chunks to verify the deterministic coverage fix."""
import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import patch

import coach
from core import ROOT
from evaluate_v2 import validate_result
from smoke_chunks_v2 import retention_checks


def main():
    from transformers import AutoTokenizer

    original_path = ROOT / 'reports/chunking-v2-smoke.json'
    original = json.loads(original_path.read_text(encoding='utf-8'))
    tokenizer = AutoTokenizer.from_pretrained(ROOT / 'models/Qwen3-4B-Instruct-2507', local_files_only=True)
    original_split = coach.split_source
    index = 0

    def split(source, tok):
        chunks, count = original_split(source, tok, chunk_tokens=150, overlap_tokens=40)
        assert chunks == original['chunks'], 'Input chunks changed; recorded generations cannot be reused.'
        return chunks, count

    def replay(model, tok, source, mode):
        nonlocal index
        assert mode == 'draft' and source == original['chunks'][index]
        raw = original['raw_outputs'][index]
        index += 1
        return raw

    with patch('coach.split_source', side_effect=split), patch('coach.generate_coached', side_effect=replay):
        result = coach.process_note(None, tokenizer, original['source'], mode='draft', assist=False)
    assert index == len(original['raw_outputs'])
    rendered = coach.render_coached_log(result)
    retention = retention_checks(result, rendered)
    errors = validate_result(result)
    passed = not errors and not retention['missing_from_all_rendered_text'] and result['chunk_count'] > 1
    report = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'method': 'CPU replay of unchanged recorded real-model responses through the new deterministic coverage check; no fresh inference.',
        'original_report': str(original_path),
        'original_report_sha256': hashlib.sha256(original_path.read_bytes()).hexdigest(),
        'coach_sha256': hashlib.sha256((ROOT / 'coach.py').read_bytes()).hexdigest(),
        'unchanged_input_chunks_verified': True,
        'recorded_real_model_generations_replayed': index,
        'original_real_model_runtime': original['runtime'],
        'result': result, 'rendered_draft': rendered,
        'retention': retention, 'validation_errors': errors, 'passed_recovery_check': passed,
        'limitation': 'Recovered excerpts are UNASSIGNED, not correct field placement. This does not establish semantic correctness, long-input accuracy/performance, or coaching quality. The original generation failures remain in the original report.',
    }
    (ROOT / 'reports/chunking-v2-recovery.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Recovery {'PASS' if passed else 'FAIL'}: {result['chunk_count']} recorded chunks, "
          f"{len(retention['all_rendered_text_retained'])}/6 anchors visible; "
          f"{len(retention['unassigned_only'])} remain unassigned. No fresh inference.")
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
