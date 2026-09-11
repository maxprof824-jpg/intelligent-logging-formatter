# Runtime 2.5: qualitative development review

This is an AI-assisted review of synthetic development outputs, not representative user validation or an accuracy estimate. It compares explicit-event processing with legacy flat processing using the same released v2 adapter. It does not compare base versus fine-tuned models. Sources, drafts, accepted facts, suggestions, and processing issues were examined using the [review rubric](../evaluation-v3/REVIEW-RUBRIC.md). Review/editing effort was not timed. Reserved notes were not used.

Source outputs: [development report](events-v25-development.json). Five paired cases are reviewed below. Failed generations remain part of the review; malformed output is not treated as an accepted draft. Findings must be read with the report's code hashes and completion status.

## Maintenance paperwork — dev-v3-maint-01

Grouping keeps the later copier callback with its original event and correctly places the cabinet labels' no-delay outcome, completed paperwork, and unknown application owner. Legacy processing leaves much of that information in review excerpts.

Both versions can turn a completed telephone exchange awaiting technical confirmation into an unanswered call. The unsigned copier-service context remains outside SITUATION after a validation screen. Helpers also introduce assumptions: “preventive maintenance” in the event version and a “missing” record in legacy, although the note establishes an existing unsigned service form.

## IT support — dev-v3-it-05

Both versions are incomplete after a long chunk fails JSON parsing. Most access chronology survives as excerpts, requiring substantial reconstruction. Grouping separates the contact-card work and retains some late access-handover facts.

The separated card IMPACT incorrectly turns a card-only scope limitation into a definite statement that replacement had no effect on workshop access or preparation. A literal supporting quotation did not prevent this unsupported interpretation. The access PLAN is empty despite FR's stated follow-up agreement. Helpers ask for an owner already supplied and a status already recorded.

## Facilities — dev-v3-fac-09

The separated draft preserves room/sign timelines and puts reception's explicit no-wait outcome under the sign event. Legacy withholds SITUATION and leaves those times and the sign outcome in excerpts.

The event draft loses the stale notice's “yesterday” context and Reception as recipient of the photograph-retention request. Legacy weakens the explicit no-permission-to-remove-or-use restriction into “not an action.” Event helpers shift unknown booking impact into possibly unconfirmed booking status and add a display-review task without establishing its need.

## Administrative tracking — dev-v3-admin-13

The event version visibly fails the short booking group because generated objects contain unexpected properties. It preserves that source for review and successfully processes the separate receipt group, including the distinction between a documentation request and rejected reimbursement. Some receipt timing and uncertainty remain outside placed facts.

Legacy is structurally valid but says the organizer acknowledged the booking correction and that no reply was received. Its helper requests an already received booking reply and invokes an absent “documented review point.” Visible failure and valid structure therefore require separate correctness judgments.

## Shift handover — dev-v3-shift-17

The event output is incomplete: the key-register group fails JSON parsing while noticeboard and courier groups survive. Legacy's two chunks both fail JSON parsing, leaving no accepted draft for a meaning comparison. This pair demonstrates useful failure isolation, not a complete handover.

The event draft retains board completion but withholds its limited no-delay report. Helpers request the already supplied display-change time and add checking to completed work. Courier output retains unknown impact and the expected update deadline, but leaves the corrected envelope number and later completed caller conversations outside placed facts. A helper proposes a receipt check already reflected in the later correction.

## Priorities before another training run

Grouping improves organization and some field placement in these examples; it does not establish reliable prevention of cross-event meaning errors. Prioritize correction-aware chronology, named speakers and recipients, narrow impact scope, supported field placement, and suggestions that recognize completed work. Improve structured generation on both short and long inputs. Keep failed groups and unplaced source visible.

Evaluate any future candidate under identical runtime/settings. Promotion should require better supported fact placement and less editing without more unsupported or falsely completed claims. These observations do not establish measured effort savings or operational readiness.
