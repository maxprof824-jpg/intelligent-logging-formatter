# V3 candidate evaluation and promotion protocol

Frozen before reviewing candidate outputs. This is a synthetic development comparison, not an operational acceptance test. The protocol author inspected development metadata and runtime settings, not new candidate outputs, training examples, or reserved notes. Existing v2.5 development findings informed the criteria below.

## Fixed candidate and comparison

Train one new rank-16 adapter from the verified local base using the prepared 720 training / 144 validation examples: one epoch, learning rate `1e-4`, maximum sequence length `4096`, gradient accumulation `8`. Save it separately from the released adapter. Record the complete training configuration, data hashes, base identity, exported checkpoint, and candidate weight hash. Do not choose checkpoints using development or reserved evaluation results.

Compare three variants under the same runtime 2.5: base without an adapter, released v2 adapter, and this candidate. Freeze code/prompt hashes, tokenizer, model-loading settings, generation settings, and evaluator revision before the first comparison. Use the same 4-bit NF4/double-quantized loading, BF16 computation, SDPA attention, deterministic generation (`do_sample=False`), main-output limit `2600`, and helper-output limit `1100`. Preserve explicit-heading grouping, eight-group maximum, 120,000-character submission limit, 12,000 source tokens per processed group, and 2,200-token chunks with 160-token overlap. Keep each row's mode and assistance setting.

Use all 20 development IDs in `evaluation-v3/development.jsonl`, SHA-256:

`2dea24c5016a739076b0d4e30829b3385e9c1097f55e00ef9b40c898dcd5672a`

An initial diagnostic subset may detect execution problems, but cannot justify promotion. Complete all 20 for every variant before selecting a candidate. Preserve original failures and every rerun; do not select the best response from retries. A changed prompt, runtime, candidate configuration, or generation setting creates a new experiment requiring a new matched comparison.

## Review and record

Apply the [review rubric](../evaluation-v3/REVIEW-RUBRIC.md). The fixed qualitative sample is:

- One case per domain: `dev-v3-maint-01`, `dev-v3-it-05`, `dev-v3-fac-09`, `dev-v3-admin-13`, `dev-v3-shift-17`. This includes both long cases.
- Additional mode/assistance coverage: `dev-v3-maint-02`, `dev-v3-it-07`, `dev-v3-fac-12`.
- Add every case with a newly failed group, new structural failure, or apparent regression in any variant. Review all three outputs for each added case, including failures.

Prepare a source-only checklist before comparing each case's variants. Identify the important claims, correct event/field, speaker, time, uncertainty, corrections, completed actions, and agreed follow-up. Count a supported claim once only when correctly placed in the draft. Evidence quotations and unassigned excerpts preserve information but do not count as placed facts. Record material omissions and duplicate work separately.

For every reviewed output, record critical errors and the substantive edits needed: removing an unsupported claim, correcting meaning/attribution/status, placing an omitted important fact, moving it to the correct event/field, or removing unnecessary advice. Apply the same edit-counting method across variants; record reconstruction work for failed groups instead of treating empty output as effortless. Track useful versus redundant/contradictory suggestions. If no human timed review occurs, label this an AI-assisted estimate of editing burden, not measured time saved. Hide model labels during review where practical and disclose prior familiarity with released outputs.

Critical errors include invented facts or approvals, changed speakers/times, reversed negation, unsupported impact certainty, proposed work presented as completed, stale status after an explicit correction, and material cross-event misattribution. Substring matches, quote validity, schema success, and validation loss remain separate diagnostics, not semantic accuracy scores.

## Development decision gate

Advance the candidate only when the completed comparison shows all of the following:

1. More important supported facts correctly placed and fewer substantive edits than the released adapter across the fixed qualitative sample. Inspect per-case results so gains cannot hide a material domain regression.
2. No increase in unsupported factual or falsely completed claims, and no unresolved new correctness-critical regression in reviewed cases. A gain in formatting does not offset such a regression.
3. No increase in failed cases or failed groups relative to the released adapter, no silent source loss, and clear incomplete-status handling. Investigate differently affected cases before advancing.

An equal, mixed, or insufficiently reviewed result does not justify replacing the released adapter. Retain the candidate as an experiment and document the reason. Report the base comparison separately; claim adapter value over base only when supported. These relative criteria do not demand perfect outputs or establish broad accuracy. Do not relax them after seeing results.

## Reserved check and release

Keep the 10 reserved cases unread and unused unless the candidate passes the development gate and the configuration is frozen. If it clearly regresses, leave them unused and explain why. If advanced, run all three variants under that same frozen setup on the reserved set and review every case using the same criteria. Any new critical regression or contradictory result holds promotion for investigation; this small set cannot establish generalization or operational readiness.

If reserved findings guide changes, relabel those cases as development and replace the reserved set. Publish hashes, failures, review limitations, and the selection rationale. Keep the existing release until an explicitly recorded promotion decision; successful training alone is not promotion.
