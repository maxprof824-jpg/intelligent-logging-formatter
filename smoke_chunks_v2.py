"""Real-model chunk/merge smoke with an intentionally reduced split threshold.

Run this script only after other GPU jobs finish. Importing it does not load a model.
This checks execution and literal retention, not long-input accuracy or performance.
"""
import json
import time
from datetime import datetime, timezone

import coach
from core import FIELDS, ROOT, load_model
from evaluate_v2 import validate_result


SOURCE = """Fictional administrative office record for 2026-09-11; all event times are UTC.
At 08:10 UTC, the training desk found two printed copies of the room-calendar notice DEMO-ROOM-71 beside the classroom door. The headings were identical, but one copy was inside a clear folder and the other was loose. At 08:18 UTC, Training Coordination (JN) confirmed the loose copy was a spare print, not a second booking. The room reservation and attendance were checked and were unaffected. I filed the spare copy with the notice. Training Coordination confirmed no further action was needed for this duplicate print.

A separate office-supply question arose at 10:05 UTC. The classroom marker inventory sheet DEMO-STOCK-84 listed four sealed packages, while the cabinet count showed three packages. The counter did not know whether another package had already been issued to a class. At 10:12 UTC, I saved the count note and sent it to Office Supplies (RC). The effect on the afternoon class was not yet assessed. Office Supplies had not replied, and no replacement delivery or follow-up owner had been confirmed. The cabinet was left as found, and the count note remained open for review."""

CHUNK_TOKENS = 150
OVERLAP_TOKENS = 40
REQUIRED_ITEMS = ["08:10", "08:18", "10:05", "10:12", "DEMO-ROOM-71", "DEMO-STOCK-84"]
LIMITATION = (
    "This deliberately forces a short fictional note across a 150-token split threshold. "
    "It checks real-model chunk execution, merge structure, and literal time/reference retention. "
    "It does not establish long-input accuracy, long-input performance, semantic correctness, "
    "or assistance quality; assistance is disabled."
)


def retention_checks(result, rendered):
    sections = result.get("sections", {}) if isinstance(result, dict) else {}
    factual_text = "\n".join(
        item.get("text", "")
        for field in FIELDS
        for item in sections.get(field, [])
        if isinstance(item, dict)
    )
    unassigned_text = "\n".join(
        item.get("text", "")
        for item in (result.get("review_excerpts", []) if isinstance(result, dict) else [])
        if isinstance(item, dict)
    )
    factual = [item for item in REQUIRED_ITEMS if item.lower() in factual_text.lower()]
    unassigned = [item for item in REQUIRED_ITEMS if item.lower() in unassigned_text.lower()]
    combined = [item for item in REQUIRED_ITEMS if item in factual or item in unassigned]
    rendered_retained = [item for item in REQUIRED_ITEMS if item.lower() in rendered.lower()]
    return {
        "method": "Case-insensitive literal substring checks; not semantic or section-accuracy judgments.",
        "expected": REQUIRED_ITEMS,
        "factual_sections_retained": factual,
        "unassigned_review_retained": unassigned,
        "unassigned_only": [item for item in unassigned if item not in factual],
        "factual_plus_unassigned_retained": combined,
        "missing_from_factual_plus_unassigned": [item for item in REQUIRED_ITEMS if item not in combined],
        "all_rendered_text_retained": rendered_retained,
        "missing_from_all_rendered_text": [item for item in REQUIRED_ITEMS if item not in rendered_retained],
    }


def main():
    import torch

    torch.set_num_threads(4)
    adapter = ROOT / "runs" / "adapter-v2"
    report_path = ROOT / "reports" / "chunking-v2-smoke.json"
    original_split = coach.split_source
    observed_chunks = []

    def forced_split(source, tokenizer, **kwargs):
        kwargs.update(chunk_tokens=CHUNK_TOKENS, overlap_tokens=OVERLAP_TOKENS)
        chunks, token_count = original_split(source, tokenizer, **kwargs)
        observed_chunks[:] = chunks
        return chunks, token_count

    result, error, rendered = None, None, ""
    model_load_seconds, process_seconds = None, None
    started = time.perf_counter()
    try:
        load_started = time.perf_counter()
        model, tokenizer = load_model(adapter)
        model_load_seconds = time.perf_counter() - load_started
        coach.split_source = forced_split
        process_started = time.perf_counter()
        try:
            result = coach.process_note(model, tokenizer, SOURCE, mode="draft", assist=False)
        finally:
            process_seconds = time.perf_counter() - process_started
        rendered = coach.render_coached_log(result)
    except Exception as exception:
        error = {"type": type(exception).__name__, "message": str(exception)}
        partial = getattr(exception, "result", None)
        if isinstance(partial, dict):
            result = partial
    finally:
        coach.split_source = original_split
    runtime_seconds = time.perf_counter() - started

    validation_errors = validate_result(result)
    raw_outputs = result.get("raw_outputs", []) if isinstance(result, dict) else []
    chunk_count = result.get("chunk_count", 0) if isinstance(result, dict) else 0
    status = result.get("status") if isinstance(result, dict) else None
    retention = retention_checks(result, rendered)
    checks = {
        "multiple_chunks_split": len(observed_chunks) > 1,
        "multiple_chunks_generated": chunk_count > 1 and len(raw_outputs) > 1,
        "pipeline_error": error is not None,
        "incomplete_draft": status == "incomplete_draft",
        "valid_structure": not validation_errors,
        "validation_errors": validation_errors,
        "no_suggestions_with_assistance_disabled": isinstance(result, dict) and not result.get("suggestions"),
        "retention": retention,
    }
    passed = (
        checks["multiple_chunks_split"]
        and checks["multiple_chunks_generated"]
        and not checks["pipeline_error"]
        and not checks["incomplete_draft"]
        and checks["valid_structure"]
        and checks["no_suggestions_with_assistance_disabled"]
        and not retention["missing_from_all_rendered_text"]
    )
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Real-model forced chunk-and-merge smoke test",
        "limitation": LIMITATION,
        "adapter": str(adapter),
        "source": SOURCE,
        "source_word_count": len(SOURCE.split()),
        "forced_threshold": {
            "chunk_tokens": CHUNK_TOKENS,
            "overlap_tokens": OVERLAP_TOKENS,
            "production_threshold_unchanged": True,
            "other_split_arguments": "Original split_source defaults preserved.",
        },
        "assist": False,
        "chunks": observed_chunks,
        "result": result,
        "raw_outputs": raw_outputs,
        "rendered_draft": rendered,
        "error": error,
        "runtime": {"total_seconds": runtime_seconds, "model_load_seconds": model_load_seconds,
                    "process_seconds": process_seconds},
        "checks": checks,
        "passed": passed,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"CHUNK SMOKE {'PASS' if passed else 'FAIL'} | chunks={chunk_count} "
        f"| structure={'valid' if not validation_errors else 'invalid'} "
        f"| retained={len(retention['all_rendered_text_retained'])}/{len(REQUIRED_ITEMS)} "
        f"| unassigned-only={len(retention['unassigned_only'])} | total={runtime_seconds:.1f}s",
        flush=True,
    )
    if not passed:
        print(json.dumps({"error": error, "checks": checks}, ensure_ascii=False), flush=True)
    print(f"Report: {report_path}", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
