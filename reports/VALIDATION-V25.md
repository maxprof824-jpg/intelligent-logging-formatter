# Runtime 2.5 validation and retraining preparation

This update separates author-labeled events and prepares a broader synthetic curriculum. **The released v2 adapter is unchanged. No candidate training was performed.** All examples and logs in these measurements are fictional.

## What was checked

- **194 CPU tests passed.** Coverage includes event isolation, repeated updates, exact source locations, Unicode and discontinuous spans, failure recovery, malformed evaluation outputs, scoring-only report revisions, curriculum integrity, and preflight gradient failures, alongside earlier regressions. See [verification-v25.log](verification-v25.log). This is not a model accuracy score.
- Existing base-model files passed offline SHA-256 verification before GPU evaluation. These checks used the existing Windows installation and RTX 5060 Ti; a clean installation on another computer remains untested.
- The Gradio interface was exercised with a saved synthetic two-event result: draft display, separate event labels, fact and suggestion evidence, original line references, full-screen table review, and clearing the results worked. This browser fixture did not run additional model inference.
- The PowerShell scripts parsed successfully. Model weights, the environment, and the original training data were preserved.

## Broader development evaluation

Twenty notes cover five domains and all four combinations of draft/review mode and assistance enabled/disabled within each domain. Fifteen notes supply explicit event labels, five leave boundaries ambiguous, and five revisit earlier labels. Two are substantive long notes. The [corpus card](../evaluation-v3/DATASET-CARD.md) records contents, construction, hashes and limits.

**16/20 event-formatter outputs completed the structural and source-location checks without an incomplete status.** Completion does not mean the facts, field placement, or suggestions are correct. The incomplete/failed cases were: `dev-v3-it-05`, `dev-v3-admin-13`, `dev-v3-shift-17`, `dev-v3-shift-19`.

| Domain | Notes run | Complete structure |
|---|---:|---:|
| Maintenance paperwork | 4 | 4 |
| IT support | 4 | 3 |
| Facilities | 4 | 4 |
| Administrative tracking | 4 | 3 |
| Shift handover | 4 | 2 |

The event parser reproduced the expected explicit labels with **0 mismatches**. That measures following the author's headings, not discovering unlabeled incidents. The final scorer found **0 cases with quotes absent from their event**. Exact matching text still does not establish the meaning of a generated claim.

Limited lexical screens flagged missing or forbidden fragments in the expected event/section on **13/20 cases**; **10/20** lacked at least one required fragment anywhere in the factual draft. These are review cues: paraphrases, denials and historical corrections can trigger them. No semantic accuracy percentage is inferred.

### Matched comparison with the earlier application

Five selected notes, one per domain, were also run through the unchanged legacy flat formatter. The same loaded base model, v2 adapter, prompt templates and generation settings were used; the event formatter intentionally supplies each event's own source context. This compares application behavior; it is not a base-versus-adapter or new-training comparison. Event-specific placement checks are not applied to legacy output because it has no corresponding event groups.

| Case | Event formatter | Time | Legacy formatter | Time |
|---|---|---:|---|---:|
| `dev-v3-maint-01` | Complete structure | 113.11 s | Complete structure | 101.25 s |
| `dev-v3-it-05` | Incomplete / failed checks | 434.74 s | Incomplete / failed checks | 377.41 s |
| `dev-v3-fac-09` | Complete structure | 135.45 s | Complete structure | 93.99 s |
| `dev-v3-admin-13` | Incomplete / failed checks | 129.73 s | Complete structure | 133.33 s |
| `dev-v3-shift-17` | Incomplete / failed checks | 537.69 s | Incomplete / failed checks | 456.11 s |

For the 18 shorter event-formatter notes, the median was **67.88 seconds**, ranging from **39.25 to 135.45 seconds**. Times include extraction, optional assistance and application checks, but exclude initial model loading. They are measurements on this installation, not performance guarantees.

| Long case | Total processed chunks | Unassigned review passages | Time |
|---|---:|---:|---:|
| `dev-v3-it-05` | 3 | 68 | 434.74 s |
| `dev-v3-shift-17` | 3 | 44 | 537.69 s |

The long IT event crosses the 2,200-source-token chunk boundary; the long handover is split into smaller author-labeled events. Source retained in an unassigned review area is not a finished log. Large review areas, incomplete output, attribution and field placement remain important limitations.

Read the [five-domain qualitative review](QUALITATIVE-V25.md) for concrete successes and errors. This is an AI-assisted development review, not testing by representative users. Examples include changing a pending answer into an unanswered call and turning a statement limited to a contact card into an unsupported no-effect claim about workshop preparation. Event separation improves organization but does not resolve those meaning errors. Helper suggestions can also be generic or repeat information already provided.

### Reproducibility and the final optimization

The [original generation report](events-v25-development.json) records exact inputs, raw outputs, drafts, failures, adapter hash and generation-code fingerprints. Its initial code is retained in commit `dacb6869ecc38456dc006bf979aed0c03d00d438`. After that run started, the scorer was strengthened to validate authoritative nested results and all original source locations. The [scoring-only revision](events-v25-rescored.json) preserves every generated result and draft, verifies the dataset and ordered case selection, and identifies both original and final code hashes. It does not regenerate responses or conceal failures.

Elapsed measurements use a monotonic timer. The host wall clock changed during this session, so recorded UTC timestamps do not establish the order of these reports.

A final application optimization deduplicates identical fallback excerpts, caches repeated quote lookups, and avoids scanning unrelated source segments. It does not change the model prompts or factual entries. In a CPU-only failure reproduction with 200 repeated updates, the previous wrapper produced 200 identical excerpt rows and 40,000 candidate instances; the final wrapper produced one row with all 200 matching locations. Both retain identical unique source spans and ambiguity flags. See [the regression measurement](event-location-regression-v25.json). This is a postprocessing measurement, not inference speed or model quality. The GPU generation report predates this optimization; final source-location code is exercised by rescoring and CPU regressions.

## Candidate curriculum, not newly trained weights

The [new curriculum](../data-v3/DATASET_CARD.md) contains **720 training rows** (600 full responses, 120 suggestions-only tasks) and **144 validation rows** (120 full responses, 24 suggestions-only tasks). Draft/review are balanced within task and scenario families. It includes attribution, negation, corrections, planned versus completed work, unknown impact, long context and explicit empty suggestion targets.

All **864 targets** pass schema, literal-source, prompt and construction checks; the current runtime screens withheld none of them. The [final audit](curriculum-v3-final-audit.json) found no exact or identity-stripped exact source overlap with either evaluation split. A six-row qualitative spot check prompted clearer action placement and less leading uncertainty wording before the dataset was frozen. It was not a semantic review of every row.

Training and validation use different scenario families, but shared form-guide text remains a limitation: 48 validation rows have nearest-training trigram similarity at or above 0.5. Programmatic variation and zero exact overlap do not establish generalization. The longest full training chat is **3,527 tokens**, and the longest validation chat is **3,451**, both below the proposed 4,096-token limit.

## Hardware preflight

The longest training example completed one forward/backward pass on **NVIDIA GeForce RTX 5060 Ti**, using 4-bit NF4, BF16 compute, rank-16 all-linear LoRA, gradient checkpointing and a microbatch of one. Two buffers per trainable parameter reserved approximate AdamW-state memory.

- Example: `train-v3-main-facilities_booking_long-004`; **3,527 chat tokens**, padded to 3,528.
- Peak allocated GPU memory: **11.562 GiB**; peak reserved: **13.484 GiB** during the pass and gradient checks. Setup peaks are recorded separately.
- All 504 trainable parameter tensors had finite gradients; 252 had nonzero gradients. Some zero gradients are expected for a freshly initialized LoRA branch.
- **Zero optimizer steps; no weights saved.** See [training-v3-preflight.json](training-v3-preflight.json) for settings, hashes and memory scope.

This supports trying the proposed training configuration on this hardware. It does not guarantee that a full training run fits, finishes, or improves the model; the preflight does not execute optimizer updates, checkpointing, accumulation or validation.

## Next candidate decision

The ten reserved notes remain unused for inference and training. Automated integrity and overlap checks inspected them without exposing their text to development reviewers. They are stored publicly with the project, so they are not an independently administered benchmark.

Next, review the current semantic failures, train a separate candidate from the base model using the prepared curriculum, and compare base/current/candidate under one fixed runtime. Use the [human review rubric](../evaluation-v3/REVIEW-RUBRIC.md) to assess supported fact placement, serious errors and editing effort. Run reserved evaluation only after design choices are frozen. Preserve the current adapter until a candidate improves usefulness without increasing unsupported or overconfident claims. Commands are in the [usage guide](../V2-GUIDE.md); the [roadmap](../REVIEW-AND-ROADMAP.md) describes remaining workflow and distribution testing.
