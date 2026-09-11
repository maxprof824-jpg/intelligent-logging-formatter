# Runtime 2.4 validation

These checks were completed for the Intelligent Logging Formatter update. The existing v2 adapter weights were not changed.

## Automated and interface checks

- **110 CPU tests passed.** They cover the original behavior plus new paraphrase-risk, source-coverage, UI status, download-integrity, evaluation-record, resume-provenance, and bounded extra-evidence regressions. This count is not a model accuracy score.
- Every existing base-model file passed offline verification against its recorded SHA256. New tests include same-size corruption, bad downloads, and no-network verification of complete files.
- The updated GPU diagnostic passed on the RTX 5060 Ti, including BF16 support and an NF4 forward/backward check. See [environment-v24.json](environment-v24.json). This uses the existing installation.
- PowerShell setup/training scripts parsed successfully. A clean installation on another computer and an actual resumed training run were not performed.
- The Gradio interface was exercised in a browser using a saved synthetic model result: generation display, the entry/source table, and clearing the draft and evidence worked. This interface check did not run a second model inference.

## Fresh model comparison

Four short synthetic notes were passed through the earlier recorded 2.4 pipeline with the adapter enabled and with it disabled on the same loaded model. They cover draft/review, assistance on/off, a mixed writing request and event, pending work, unanchored details, and a complete record. These are newly authored development smoke cases, not a representative or untouched accuracy benchmark.

The adapter produced structured results on **4/4 short cases**, compared with **2/4 for the base model**. The two base failures put factual-section names into suggestion section labels and were rejected. This supports only a narrow observation about the output contract on these cases.

The first long-case run failed because otherwise valid responses included more than four evidence quotes per item. The validator now accepts up to 64 while retaining the four-quote prompt target and all literal-source checks. A separate fresh long-case rerun exercises that fix. Prompts and weights stayed unchanged; the two report files record different code hashes. The four short cases were not regenerated after this narrow validation change.

| Case | Model | Elapsed | Result | Source chunks |
|---|---|---:|---|---:|
| mixed-request-and-event | adapter | 48.75 s | needs_confirmation | 1 |
| mixed-request-and-event | base | 31.23 s | Error: invalid output contract | 1 |
| planned-not-completed | adapter | 49.67 s | needs_confirmation | 1 |
| planned-not-completed | base | 38.47 s | needs_confirmation | 1 |
| unanchored-details | adapter | 30.64 s | needs_confirmation | 1 |
| unanchored-details | base | 21.17 s | needs_confirmation | 1 |
| complete-record-control | adapter | 55.89 s | needs_confirmation | 1 |
| complete-record-control | base | 37.66 s | Error: invalid output contract | 1 |
| actual-default-multichunk | adapter | 299.11 s | Error: invalid output contract | 2 |
| actual-default-multichunk (after limit fix) | adapter | 297.75 s | needs_confirmation | 2 |

The deliberately dense long case contained **2330 source tokens**, crossing the production 2,200-token split boundary. It used **2 chunks**. Of **52** literal references, **4** appeared in factual entries and **52** appeared somewhere in the factual entries plus the review area. Those counts do not establish correct meaning or placement. It produced **49** review excerpts; long-note usability remains limited.

### Qualitative findings

- **Mixed request/event:** the adapter retained the event after “Need a clear log;”, including its date, time, contact and reference. It placed the saved confirmation in Situation and left Action empty. The possible impact was generic rather than evidence of an actual consequence.
- **Pending work:** the adapter preserved the later statement that the check had not started and the unsent document. The initial wording can still make the time of the call sound like the planned check time. The record requires review for attribution and placement.
- **Untimed details, assistance off:** the adapter retained the paper register, no contact, no settings change, unknown delay, and missing owner. The base model put most of these details only in the recovered review area and added interpretations such as “backup record.”
- **Complete record:** the adapter retained the supplied times, contact and stock-update plan, but placed a no-additional-action statement under Impact and suggested recording details already supplied. The helper can still be unnecessary when a record is complete.

Read [quality-v24.json](quality-v24.json) for the paired short cases and original long-case failure, and [quality-v24-long.json](quality-v24-long.json) for the fresh rerun after the fix. Both include the exact source, raw responses, final drafts, timing and code/weight hashes. No semantic accuracy percentage is claimed.

## Saved-response replay

All **18 saved v2.1 development cases** were reprocessed with current filters, without new model inference. This tests reactions to previously recorded outputs; it does not regenerate the helper or prove current generation behavior. Flagged paraphrases and unquoted text are preserved for review. On dense notes, that conservative recovery can make the review area very long.

The final replay and its input/code fingerprints are in [replay-v24-final.json](replay-v24-final.json). It applies the final filters and whole-note assembly to saved responses; it does not exercise the live chunk-local validation or helper generation. The earlier [replay-v24.json](replay-v24.json) is retained as an intermediate development artifact without code fingerprints and should not be used to identify the final runtime. Historical evaluation files retain their original results and version labels. Future evaluation runs use distinct filenames by default.

## Remaining risks

Source quotations and lexical coverage do not prove factual correctness. The model can omit facts inside broad quotes, confuse events or speakers, misplace work between sections, and make weak or unnecessary suggestions. Repeated source text is matched heuristically, and one event's known impact can affect another event's suggestions. These limitations are the priority for the next event-aware design and representative evaluation described in the [review and roadmap](../REVIEW-AND-ROADMAP.md).
