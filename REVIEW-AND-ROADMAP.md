# Review and improvement roadmap

The formatter explores a useful role for a small local model: organize rough notes and help an author identify gaps. The main challenge is preserving meaning. A fluent sentence and a matching quotation can still change who did something, turn a plan into completed work, or attach an outcome to the wrong event.

Runtime 2.5 addresses event boundaries and reviewability while keeping the existing trained adapter. It also broadens evaluation and prepares better training examples. These are three distinct improvements; preparing data or changing the application does not create a newly fine-tuned model.

## Three improvements implemented, with limits

| Area | What is in place | What remains limited |
|---|---|---|
| Event separation and source locations | Standalone `EVENT:` headings create separate drafts. Repeated labels join later updates. Facts and suggestions are checked within their event, and the review table shows original source lines and all matching locations for repeated quotes. | Authors supply the boundaries. Unlabeled notes stay together; opening context stays unassigned. Matching locations do not resolve speaker, chronology, or meaning. |
| Broader synthetic evaluation | Twenty development notes cover five logging domains, both modes, both assistance settings, explicit and ambiguous event boundaries, and realistic long notes. The launcher includes five comparisons with the legacy flat formatter using the same adapter. Ten separate notes remain reserved and unused for inference. | These are fictional development cases, not representative-user validation. Lexical checks and correct heading counts are not semantic accuracy. Consult the validation record for actual run completion and failures. |
| Preparatory training curriculum | A separate curriculum contains 720 training rows and 144 validation rows, including full responses and suggestions-only tasks. Modes are balanced within families and tasks, with longer notes and difficult attribution, negation, and pending-action cases. | The examples are programmatically expanded and share some reference patterns. Target integrity checks do not prove correctness. The released adapter has not been retrained on these rows. |

The event parser accepts at most eight groups, including any opening context. Put date/time context inside each relevant event. Standalone `EVENT:` lines in pasted quotations also create groups, so authors must check the labels. Within a group, dense notes can still be incomplete, repetitive, or misinterpreted.

Source excerpts keep information available for review; they do not finish its placement in the log. Likewise, multiple matching quote locations are displayed as alternatives rather than silently choosing one. Suggestions still require confirmation even when their evidence is easy to locate.

## Evidence and training status

Read the [2.5 validation record](reports/VALIDATION-V25.md), [evaluation corpus card](evaluation-v3/DATASET-CARD.md), and [preparatory curriculum card](data-v3/DATASET_CARD.md). The released adapter remains the one trained on 480 synthetic examples with 48 validation examples. A feasibility preflight uses zero optimizer updates and saves no candidate weights; its result must not be described as completed training.

The event-versus-legacy evaluation compares application behavior with unchanged prompts and weights. It does not establish an improvement from new training. Development examples may guide fixes; if reserved examples are used for tuning, they must be relabeled as development and replaced for the later reserved comparison.

Earlier work added bounded paraphrase screens, source-coverage review, per-chunk evidence checks, broader quote-count tolerance, and setup/evaluation protections. Its separate measurements remain in the [2.4 validation record](reports/VALIDATION-V24.md) and earlier reports. New results do not replace or retroactively improve those measurements.

## Next work, in order

1. **Review the current outputs with people familiar with the workflows.** Assess retained facts, correct actors and times, field placement, unnecessary questions, and useful suggestions. Record editing effort and the mistakes that matter most. Correctly reproducing an author's event labels is only a boundary check.
2. **Train a separate candidate after the data and feasibility checks are reviewed.** Preserve the released adapter and record exact data, code, configuration, and weight hashes. Do not choose a candidate from validation loss alone.
3. **Compare base, current, and candidate models under the same runtime.** Use matched prompts and inputs to separate model effects from application effects. Evaluate the reserved notes only after design choices are frozen. Promotion should require better supported placement and lower editing effort without more invented or overconfident claims.
4. **Validate distribution and everyday use.** Complete a clean installation on another computer and measure latency, memory, and usability on realistic long notes. Test whether reviewers can find errors and distinguish completed work from suggestions before expanding the intended use.

Automatic discovery of unlabeled incidents remains future work. Reliable human review and representative testing take priority over adding more rules or accepting larger submissions.
