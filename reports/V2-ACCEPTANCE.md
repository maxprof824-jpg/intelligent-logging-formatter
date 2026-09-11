# Logging coach v2 — 18-case development evaluation

V2 was trained on 480 richer fictional notes and evaluated against 48 validation notes during training. The 18 acceptance notes were authored independently and not used for model training; two are over 1,700 words. Their outputs were subsequently examined while refining the application pipeline. These are development acceptance results, not a pristine held-out estimate of generalization.

Training time: 12.2 minutes. Peak allocated VRAM: 7.48 GiB; peak reserved: 13.38 GiB.

Completed acceptance cases: 18/18. Results below describe the saved run, including conditional coaching assistance. Recorded schema: coached-five-sections-2.1. Subsequent targeted fixes are reported separately in V2-REGRESSIONS.md; they do not retroactively change these scores.

| Check | Result |
|---|---:|
| Complete, structurally valid results | 18/18 |
| Required literal strings retained in factual text | 67/80 |
| Expected absent factual sections left empty | 3/16 |
| Requested suggestion section coverage | 36/44 |
| Raw main-pass chunks matching the full output schema | 18/18 |
| Raw main-pass fact evidence found verbatim in cleaned source | 128/130 |
| Raw main-pass suggestion basis found verbatim in cleaned source | 65/67 |
| Raw second-pass outputs matching the suggestions-only schema | 7/7 |
| Raw second-pass suggestion basis found verbatim in cleaned source | 10/11 |
| Final factual evidence found verbatim in cleaned source | 109/109 |
| Final suggestion basis found verbatim in cleaned source | 66/66 |

These are structural and literal-string checks, not semantic accuracy. A paraphrase may fail a literal check; a real quote can be interpreted incorrectly. Expected-empty-section checks sometimes penalize legitimate attributed future plans. Forbidden-phrase searches can produce false positives on negation or uncertainty. Suggestions still require human judgment and confirmation. The earlier v1 exact-match score uses a different task and dataset, so it is not directly comparable.

Raw main-pass and second-pass checks are measured before source filtering and reported separately because their schemas differ. Quote denominators include quotations from schema-valid outputs only; malformed outputs are counted by schema checks but excluded from quote denominators. Final quote checks describe the retained draft after filtering and source-wording fallback. A second pass runs only when assistance is enabled and unresolved sections need suggestions; zero emitted outputs is not a perfect-score result.

## Cases to inspect

- accept-v2-01-missing-impact: factual-claim lexical screen needs contextual review.
- accept-v2-02-future-is-not-done: literal strings absent: 14:05, 14:12, PM-FIC-22.
- accept-v2-03-uncertain-contact: expected-empty sections populated: plan; suggestion sections absent: action.
- accept-v2-04-public-report-receipt: expected-empty sections populated: impact.
- accept-v2-05-instruction-in-paste: expected-empty sections populated: plan.
- accept-v2-06-conflicting-times: literal strings absent: 13:40Z, 13:47Z, 14:11Z.
- accept-v2-07-separate-events: expected-empty sections populated: plan; suggestion sections absent: impact.
- accept-v2-08-dense-negations: raw main-pass quotation not found verbatim.
- accept-v2-09-vague-no-time: expected-empty sections populated: agencies_contacted, plan.
- accept-v2-10-complete-facts: literal strings absent: 12:02Z.
- accept-v2-11-proposed-fix-rejected: expected-empty sections populated: plan.
- accept-v2-13-attribution-counts: literal strings absent: 10:05Z, 10:09Z; expected-empty sections populated: plan; suggestion sections absent: plan; raw main-pass quotation not found verbatim.
- accept-v2-14-empty-contact-initials: expected-empty sections populated: impact.
- accept-v2-15-contradictory-resolution: expected-empty sections populated: plan; suggestion sections absent: action.
- accept-v2-16-multiple-suggestions: expected-empty sections populated: impact, plan; suggestion sections absent: impact, plan.
- accept-v2-17-long-binder-timeline: literal strings absent: ORIENT-FIC-204, BINDER-FIC-204.
- accept-v2-18-long-two-paperwork-events: literal strings absent: 17:18Z, PM-OFFICE-FIC-9; expected-empty sections populated: plan; suggestion sections absent: impact, action; raw main-pass quotation not found verbatim; raw second-pass quotation not found verbatim.

## What changed in the product

The draft can reorganize and rephrase supplied facts. Items in the suggestions collection appear under separate visible labels within the five requested headings, with source-basis quotes and confirmation questions. The measured run also misclassified some proposals as factual sections; inspect the semantic reviews. A conditional second pass through the same adapter fills unresolved suggestion gaps; disabling assistance skips that additional pass. Simple numeric or initial mismatches preserve verified source wording in an UNASSIGNED review block, while unsupported source quotes are withheld. Recognized author editing requests, control lines and instruction-bearing delimited blocks are excluded. This filtering is not a complete defense against embedded instructions. Longer notes use overlapping chunks; unprocessed parts or missing source times remain visible as review issues.

Initial raw failures were examined during pipeline refinement. This report describes one completed application run, not proof that the adapter alone resolves those failures on unseen notes. Both long cases remained below the 2,200-token chunk threshold (2,005 and 2,046 tokens), so this run did not exercise multiple input chunks. The separate chunking smoke report identifies its forced threshold and scope.

## Semantic review

Read [cases 01–09](V2-SEMANTIC-REVIEW-01-09.md) and [cases 10–18](V2-SEMANTIC-REVIEW-10-18.md). Known weaknesses include unsupported paraphrases, omitted or misplaced details, attribution errors, and inconsistent suggestions. A complete JSON result is not a correct or complete operational record.

Raw main-model chunks, recorded second-pass outputs, the assembled result, every suggestion, per-case timing, errors, and the automated checks are preserved in adapter-v2-acceptance.jsonl. The full metrics file explains each denominator and limitation.
