# Review and improvement roadmap

The formatter is useful as a synthetic prototype for organizing notes and prompting an author to fill gaps. Its main weakness is factual reliability: a fluent sentence and a matching quotation can still change the meaning or put an event in the wrong section. Improving that boundary matters more than making the prose more polished.

## Review findings and the 2.4 changes

| Finding | Change |
|---|---|
| Paraphrases could reverse a denial, lose uncertainty, turn planned work into completed work, or change a date/reference while quoting real source text. | Added bounded checks for these patterns. Flagged paraphrases are withheld and their original evidence is retained for review. These checks do not prove entailment. |
| Omitted details without dates or reference numbers could disappear without being flagged. | Added a check for source passages outside accepted factual evidence and preserved them in the review area. Broad quotations can still hide omissions within a paraphrase. |
| A formatting request and an event on the same semicolon-separated line could be removed together. | Retain the event clause while excluding the writing request. |
| A quote from another chunk could pass the final whole-note check. | Validate each generated record against the chunk the model actually received. |
| A dense-note model response exceeded the four-quote validation limit and both input parts failed. | Keep the prompt's four-quote target, but tolerate up to 64 literal quotes per fact or suggestion. All existing quote and paraphrase checks remain. The initial failure and separate rerun are reported individually. |
| Reviewing evidence required reading raw JSON. Empty factual output could be described as a prepared draft. | Added a readable entry/source table, clearer status for empty/partial results, and progress by processing stage and part. |
| Setup could download the model before discovering an incompatible GPU. Same-size corruption in small model files could go undetected. | Check the environment first, verify every file against the shipped hashes, and avoid network access when all files are already valid. |
| The tester's retraining launcher targeted the already-existing released adapter. | Write retraining runs to separate experiment directories and support selecting an adapter in the app. |
| Evaluation referenced a file missing from the package; reruns could replace historical evidence. Resume could overwrite training provenance before validation. | Correct evaluation fingerprints and protect saved evaluation/training records. |

The adapter weights are unchanged. Version 2.4 improves the surrounding application; it is not a newly trained model.

## What the checks can and cannot establish

CPU regressions exercise concrete failure patterns and setup behavior. Replaying the saved 18-case development run checks how new filters handle those same old responses; it is not fresh model inference.

Four short fictional cases compare the base model and adapter using the same prompts and an earlier recorded 2.4 code revision. A dense note crossing the default chunk boundary initially failed the evidence-count limit. Its adapter rerun uses a later revision with the narrow validation-limit change; the model weights and generation prompt are unchanged. These are separate measurements, identified by their recorded code hashes, rather than one run of the final code. This small comparison cannot establish general accuracy or usefulness across occupations.

See [the 2.4 validation record](reports/VALIDATION-V24.md) for measured results and the remaining failures. Historical reports remain available with their original runtime labels.

## Next improvements, in order

1. **Track events and evidence spans explicitly.** First-occurrence text matching is ambiguous when a quote repeats. One event's confirmed lack of impact can currently suppress a useful suggestion for a different event. Introduce source offsets and event identifiers, then test speaker, time, and event association before expanding automatic cross-event reasoning.
2. **Build a representative evaluation set.** Use newly authored fictional notes from maintenance records, support desks, facilities, administrative tracking, and shift handovers. Keep them separate from training. Include review/draft modes, assistance on/off, corrections, denials, uncertain attribution, and realistic long inputs. Have people familiar with the workflows assess fact retention, support, placement, useful questions, and editing effort.
3. **Improve the training curriculum around measured failures.** Balance both modes within each scenario family; the original generator ties family selection to mode. Add explicit suggestions-only examples for the optional second pass. Add longer, dense notes and difficult actor/negation examples. The current longest full training example was 1,480 tokens, while an inference chunk can contain 2,200 source tokens before prompt and output.
4. **Train and compare a separate candidate.** Use identical prompts and runtime for base/current/new-adapter comparisons. A candidate must improve supported fact placement and reduce editing effort without increasing invented or overconfident claims. Preserve the current adapter until those checks pass; do not choose a model from validation loss alone.
5. **Validate distribution and workflow.** Complete a clean install on another computer, measure long-note latency and memory, and test whether reviewers can find and correct mistakes using the evidence view. Evaluate explicit per-event drafting before increasing input limits.

Source coverage is deliberately conservative and can make long drafts verbose. The current suggestion limit also means later events may receive less help. A better event model and representative user review are the next substantial improvements; another layer of keyword rules is not a substitute.
