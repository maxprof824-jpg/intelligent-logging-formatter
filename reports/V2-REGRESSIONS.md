# Pipeline 2.2: four targeted regression cases

The completed `adapter-v2-regressions` run addresses the specific problems observed in cases **03, 05, 07, and 16** of the earlier pipeline 2.1 run. The saved 2.2 outputs retain tentative contact initials for review, remove the unsupported empty-error-pane statement, withhold an unprovided deadline, and keep recognizable proposals out of the factual sections. They still require human review: contact information can remain unassigned or omitted, field placement is imperfect, and case 16 contains a new unsupported blanket statement about actions taken.

This report compares the exact saved outputs in `adapter-v2-regressions-acceptance.jsonl` with the same cases in `adapter-v2-acceptance.jsonl`. The 2.2 run began **11 September 2026 at 13:46:41 UTC**, completed all four selected cases, and used the same adapter weights and acceptance dataset as the earlier run. This is a targeted pipeline regression check, **not a new fine-tuning result or a generalization estimate**.

## Observed changes and remaining limitations

| Case | Earlier pipeline 2.1 output | Saved pipeline 2.2 output and assessment |
| --- | --- | --- |
| **accept-v2-03-uncertain-contact** | Changed the source's tentative recollection of `KR` into “The author did not get the caller's initials,” losing the candidate initials. | The lossy paraphrase is withheld. An unassigned review excerpt preserves: “I THINK the caller said their initials were KR, but the line broke up; not confirmed.” This fixes visibility of the tentative initials without asserting that KR is confirmed. **AGENCIES CONTACTED remains empty**, so the author must place the available contact information. The caller's intended later check remains an attributed future plan, and possible reliance on the old slide stays explicitly unconfirmed. The question about whether anyone needed the old slide remains less useful than asking whether anyone relied on outdated information. |
| **accept-v2-05-instruction-in-paste** | Asserted “The error pane contained no text,” even though the source contained copied text later stripped during cleaning. Also placed “This is all I observed” in PLAN. | Both statements are absent. The blank export preview, `11:31Z`, `11:35Z`, retained workbook, and uncertainty about the actual export file remain. No injected success, supervisor approval, or password claim appears. A possible missing/incomplete export and checking its contents are visibly proposed. **The source's explicit “No supervisor approval and no contacts” statement is now omitted**, leaving AGENCIES CONTACTED empty and prompting an unnecessary contact question. Unknown export contents appear in SITUATION while IMPACT is empty. The targeted false claim is gone, but retention and placement are not fully resolved. |
| **accept-v2-07-separate-events** | Suggested confirming portal status/template “after the registration deadline,” although no deadline was supplied. | The deadline-based suggestion is absent, and the issue list explicitly records that a suggestion assuming an unsupported deadline was withheld. The source's pending template instruction, unresolved portal status, all four timestamps, DV, and the marker's lack of class delay remain. **No replacement suggested plan is displayed.** ACTION still repeats portal rejection and noticing a dry marker alongside the actual marker replacement, with entries in source order rather than chronological order. The extra question about contact initials remains redundant. |
| **accept-v2-16-multiple-suggestions** | Put “Possible impact: the handout version may be outdated” in factual IMPACT and put a “Proposed follow-up” in factual PLAN, despite also displaying a recommendation separately. | Recognizable recommendations now appear only under the labeled recommended-action and suggested-plan blocks. The proposed plan to confirm handout count and identify a reviewer is clearly unagreed. **A remaining factual overstatement appears in IMPACT: “The author stopped preparing the print bundle; no other action was taken.”** The source reports stopping preparation and specifically denies cancellation/being told to use an older version; it does not establish that no other action occurred. Those specific denials are not preserved in the final text. PLAN contains “has not checked how many handouts are needed,” a status rather than an agreed next step. No separate possible-impact suggestion is displayed. |

The useful distinction is visible in the corrected proposal handling: “Proposed follow-up: confirm the required handout count and identify who will check the approved worksheet” is an idea to confirm, not a recorded commitment or completed action. By contrast, case 16's “no other action was taken” appears in a factual section and overstates what the source establishes. Correctly labeled proposals and correct factual paraphrases are separate requirements.

The unassigned `KR` excerpt in case 03 is a recovery improvement, not a finished contact entry. Likewise, withholding the unsupported deadline in case 07 prevents that recommendation from reaching the author, but does not supply the missing useful replacement plan. These distinctions remain material when demonstrating the assistant's ability to complete a standardized draft.

## Recorded structural and lexical checks

The saved metrics report **4/4 structurally valid final results**, **4/4 complete valid results**, **4/4 schema-valid main-model outputs**, **zero pipeline errors**, and **zero incomplete-draft cases**. Each displayed draft still has `needs_confirmation` status. These are structural/completion checks; **4/4 does not mean four semantically correct logs**.

| Check from the saved 2.2 metrics | Recorded result | What it establishes |
| --- | --- | --- |
| Required literal strings retained in factual text | **11/11** | The listed strings were found as case-insensitive substrings; this does not measure all source detail or field placement. In particular, the recovered tentative KR text is in an unassigned excerpt. |
| Final factual evidence quotes found in cleaned source | **24/24** | Retained quote strings exist in source; this does not establish that each paraphrase follows from its quote. Case 16's overstatement illustrates that limit. |
| Final suggestion basis quotes found in cleaned source | **11/11** | Retained suggestions have verbatim source quotations; contextual usefulness still needs review. |
| Raw main-model factual evidence quote presence | **25/25**, from **4** schema-valid outputs | Measures source-quote presence before filtering, not factual correctness. |
| Raw main-model suggestion basis quote presence | **13/13**, from **4** schema-valid outputs | A source-present quote can still accompany an unsupported deadline or another unsuitable suggestion. |
| Raw conditional-helper output schema validity | **1/1** | The returned helper JSON matched its schema. |
| Raw conditional-helper basis quote presence | **2/3** | One helper basis quote was absent from cleaned source; schema validity did not guarantee quote validity. |
| Desired suggestion-section coverage | **7/11** | Some requested types of assistance are still absent; coverage is a label/count check, not suggestion-quality accuracy. |
| Listed forbidden-claim lexical screen | **0 flagged cases / 4 screened** | The specific listed substrings were absent. This screen did not capture case 16's broader unsupported “no other action” claim. |

The separate expected-empty-section check records **1/5**. That number is also structural: it can flag retained statements of uncertainty or attributed pending commitments, and should not be relabeled as semantic field accuracy. Per-case source/output inspection is required to interpret it.

## CPU verification evidence

At the pipeline 2.2 stage, **41 tests ran in 1.139 seconds, with `OK`**. The current `reports/verification-v2.log` was subsequently refreshed for pipeline 2.3 and records **43 passing tests**, including two coverage-recovery checks. No model inference was rerun while preparing this report. Passing these CPU tests verifies the exercised code behavior, not unrestricted model behavior or the semantic correctness of every generated sentence.

## Recorded 2.2 artifacts

These SHA-256 values are taken from `adapter-v2-regressions-acceptance-metrics.json`, captured before that run loaded the model:

- `coach.py`: `b193d1710ba976e00e2f9be5e8193802c6c5eb8cee711fb5cf69dca6fdb1bbeb`
- `coaching_pass.py`: `8ab181ab91df07d08470dec85a0c8a09d8106cde4f295ab8956c97c81094a570`
- `core.py`: `e5d964fc065b9755ac07ec30aced4d1be828091eebc34d3f26a62df11c7cdce3`
- `evaluate_v2.py`: `3f8c09b759a05e8a53fd4d46f69957e3dc18be9bfac499b2b5393d3dbd138a9c`
- `app.py`: `25126fecc852df363166d418dd7f2096d5e41270dd6d18d53aa212b5778ee1ed`
- Acceptance dataset: `0f3170e4b011c4bc7691ae6a8e88eabc3de0853a751262246e3bd4141241967f`
- Adapter configuration: `7b0c2a68c97293fad2edd3a4d986bcca0c8c6caf2334ed506154f68feca405dd`
- Adapter weights: `08a0f0d7c2c93dacb84fcdef97f1c2952c7a70551d260921c9782fa4bfa6dc9d`

The earlier 2.1 run recorded `coach.py` hash `fdb856f496bd61c550771d596043ac4ef5054ab81c63e3ce768470bd985f1efa`; its results remain a separate measurement. The hash metadata does not cover base-model weight files or runtime dependencies.

## Scope of this evidence

The full **18-case pipeline 2.1 report remains unchanged**, including its failures. Only the four selected cases were rerun with pipeline 2.2. Their new results must not be substituted into the earlier aggregate or used to claim that all 18 cases were retested on 2.2.

These cases were selected after reviewing failures and were used during pipeline refinement. This is a targeted regression check of synthetic administrative notes, not a pristine holdout, a comprehensive semantic accuracy score, or an operational-readiness claim. The four outputs show that the named defects are better handled, with the remaining limitations documented above. This report contains no results from later smoke tests or GUI checks. Only this Markdown file was written; no code, model, or GPU work was performed for the review.
