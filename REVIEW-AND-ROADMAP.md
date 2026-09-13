# Review and improvement roadmap

The formatter's job is to make rough notes easier for the next person to use. The hard part is preserving meaning: who did what, which event it belongs to, and whether it happened, was proposed, or remains uncertain.

## What is in place

- **Separate event drafts.** Authors use `EVENT: short name` headings; repeated labels join later updates. Each event gets its own five sections. Unlabeled notes stay together, because the app does not yet reliably discover incident boundaries.
- **Source comparison.** Facts and suggestions appear beside their quoted source lines. Repeated wording shows every matching location. A matching quotation helps review; it does not prove that the model interpreted it correctly.
- **Broader synthetic tests.** Twenty development notes cover maintenance paperwork, IT support, facilities, administrative tracking and shift handovers. They include corrections, mixed outcomes, incomplete contacts, ambiguous boundaries and dense timelines. Ten additional notes are reserved for a later check.
- **A separately trained and evaluated candidate.** The v3 curriculum has 720 training examples and 144 validation examples, including formatting and suggestions-only tasks. The candidate placed more checked facts and needed fewer repairs overall, but new cause/commitment errors prevented promotion. The [completed comparison](reports/V3-COMPARISON.md) keeps the gains and failures visible; v2 remains the default.

The application accepts up to eight groups, including any unassigned opening context. Put necessary date and time-zone context inside each event. A failed event retains its source for review, but the author must still place missing details into the draft.

## How improvement is judged

The [frozen comparison protocol](reports/V3-CANDIDATE-PROTOCOL.md) uses the same inputs, prompts and runtime for base, current and candidate models. Reviewers check supported facts in the correct fields, substantive corrections, and invented or overconfident claims. Retained source excerpts are not counted as completed draft placement.

The candidate must improve supported placement and require fewer corrections without introducing new critical errors or more failed outputs. Training loss and valid JSON alone do not meet that standard. The ten reserved notes are used only if the candidate passes development review. These are AI-assisted synthetic reviews, not measured time savings or independent user validation.

## Next priorities

1. Address cause and commitment errors with contrasting examples: a requested update, an expected update and an agreed commitment must stay distinct. Suggestions need the same factual discipline as the main draft.
2. Diagnose malformed or overlong model responses before another training run. Test smaller extraction tasks and field assembly on development data; retain every failure and rerun all variants after changing the runtime.
3. Expand long training examples with varied, information-dense timelines. The current long examples contain repeated form-guide text, which limits what they teach about narrative complexity.
4. Test drafts with people familiar with the workflows and measure their actual corrections. Also complete a clean installation on another computer and profile physical/shared memory and uninterrupted long-note latency.

Automatic separation of unlabeled incidents remains future work. The [candidate model card](MODEL-CARD-V3-CANDIDATE.md), [curriculum card](data-v3/DATASET_CARD.md) and [2.5 runtime validation](reports/VALIDATION-V25.md) give the evidence and limits behind this plan. Earlier measurements remain historical records; new training does not retroactively improve them.
