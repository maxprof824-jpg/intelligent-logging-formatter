# V3 training experiment: gains, regressions and release decision

**Keep v2 as the default; release v3 as an optional experiment.** The new adapter put more checked details into the right fields and needed fewer corrections overall. It also introduced unsupported explanations and commitments. Those regressions fail the criteria set before evaluation, so the ten reserved notes were not used for inference or semantic review.

## What was compared

One fresh QLoRA adapter completed 90 optimizer updates on 720 synthetic examples, with 144 validation examples. Training took 46.37 minutes, followed by 177.4 seconds of validation. The [model card](../MODEL-CARD-V3-CANDIDATE.md) records settings, dataset limits and the GPU memory caveat.

The base model, released v2 adapter and candidate v3 adapter processed the same 20 development notes through runtime 2.5: **60 attempts, all retained, including failures**. Notes span maintenance paperwork, IT support, facilities, administrative tracking and shift handovers. Inputs, event labels, modes, assistance settings, generation limits and quantized base were held constant. No checkpoint was selected from these results and no retry replaced a failed response.

## Results

The primary eight-case checklist was fixed before outputs were reviewed. It contains 103 units, each requiring the important detail to be supported and in the correct field/event.

| Primary eight cases | Base | Current v2 | Candidate v3 |
|---|---:|---:|---:|
| Supported units correctly placed / 103 | 8 | 38 | 46 |
| Substantive repair operations | 95 | 68 | 59 |
| Critical correctness errors | 2 | 2 | 3 |

All 20 cases were reviewed, including the additional 12 cases with 92 checklist units. The larger result does not replace the primary decision criteria.

| All 20 cases | Base | Current v2 | Candidate v3 |
|---|---:|---:|---:|
| Supported units correctly placed / 195 | 17 | 97 | 117 |
| Substantive repair operations | 180 | 104 | 83 |
| All correctness errors / critical subset | 3 / 3 | 6 / 4 | 4 / 3 |
| Structurally complete cases / 20 | 3 | 16 | 17 |
| Failed or incomplete event groups | 23 | 4 | 4 |

These are checklist counts and reviewer-assessed repairs, **not accuracy percentages or measured editing time**. A quotation retained below an unfinished draft does not count as a correctly placed fact. Reconstructing failed output still counts as work. Optional reasonable advice is not charged as a required repair merely because its usefulness is uncertain.

## Why it was not promoted

The candidate improves the primary placement/repair totals, but its primary critical errors rise from two to three. Its three critical findings concern unsupported factual premises:

- **Maintenance 01:** it attributes no delay to label delivery and quantity verification. The source instead explains that the labels were for a future filing change.
- **IT 05:** it calls an expected investigation update a promised update.
- **IT 07:** it describes a requested other-user check result as promised. The current adapter has no recorded correctness error on this case. The candidate's factual PLAN keeps the direction correct; the unsupported commitment appears in its suggestion.

These are cause/commitment errors, not claims that the proposed work was completed. Neither adapter had a recorded false-completion error in this review. Lower pooled error counts cannot excuse a new critical regression. The [audit](review-audit/README.md) retains severity disagreements and their adjudications, including a noncritical alternative for IT07; the decision also rests on the other cause/commitment findings and changed failures.

Failures moved between cases. The candidate fixes the current adapter's failed booking group in Administrative13 and loan-folder group in Shift19, but newly fails IT06 and the courier group in the dense Shift17 timeline. Both adapters retain four failed groups overall. IT failed groups increase from one to two; the primary administrative case also drops from three placed units to two and rises from seven repairs to eight. These changes require investigation despite the aggregate gains. Failed groups are marked incomplete and retain their source; no malformed, missing or unexpected output groups were reported.

Both adapters improve structural compatibility and supported placement substantially over the base under this application protocol. That does not establish general superiority, and sparse base output is not evidence of safety: it produces less usable material and therefore fewer opportunities for displayed errors.

## Limits and next work

Review was AI-assisted, with A/B/C identities hidden where practical. Reviewers had prior familiarity with some released outputs; the coordinator saw labeled execution progress, and one IT07 peer check incidentally exposed raw text. This was not an independent blinded study. All 20 canonical reviews were completed before the aggregate unmasked identities. Exact judgments, repairs and peer qualifications are published for inspection.

The comparison spans a long session gap. Current-v2 Shift17 recorded 34,975.937 elapsed seconds, which cannot be interpreted as active model latency. The original timer and output remain unchanged; this report makes no speed claim. See [run notes](V3-RUN-NOTES.json).

The next experiment should target distinctions between requests, expectations and commitments, investigate malformed/overlong responses, and add denser varied timelines rather than repeated guidance. Changes require a new matched development comparison. Reserved notes remain unused for inference and semantic review; earlier automated integrity checks inspected their bytes. Representative-user testing and a clean installation on another computer remain outstanding.

Evidence: [all attempts and runtime hashes](V3-COMPARISON-DEVELOPMENT.json), [all qualitative judgments and domain totals](V3-QUALITATIVE-REVIEW.json), [frozen protocol](V3-CANDIDATE-PROTOCOL.md), [training provenance](V3-TRAINING-PROVENANCE.json), [233 CPU checks](V3-CPU-VALIDATION.json), [export startup check](V3-EXPORT-SMOKE.json), and [release decision](V3-RELEASE-DECISION.json).
