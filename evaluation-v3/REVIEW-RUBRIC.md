# Human review rubric

Compare the base model, released adapter, and future candidate. Human judgments about these synthetic outputs do not establish broad accuracy.

## Keep the comparison fair

Freeze the runtime revision, case IDs and source hashes, prompts, generation settings, mode, assistance setting, and grouping/chunk limits. Change only the model variant and record its identity. Apply the same review criteria. Hide variant names during review when practical.

Use development notes for refinement. Do not inspect or run the reserved notes for model selection or tuning before design choices are frozen. Integrity checks may verify their structure and hashes. If reserved notes or outputs guide a change, relabel them as development and replace the reserved set.

## Review each case against its source

| Criterion | What to check |
|---|---|
| Source support | Every factual claim follows from the note. Preserve the speaker, reported versus personally observed information, dates, times, counts, negation, uncertainty, corrections, and chronology. A matching quotation alone is insufficient. |
| Event and field placement | Facts belong to the correct event and useful section. One event's no-impact statement must not become another event's outcome. Respect supplied headings without claiming automatic discovery of unlabeled incidents. |
| Retention | Important source details remain readable. Record omissions and duplicates. Information found only in evidence or an unassigned excerpt is recoverable, but has not been placed correctly in the draft. |
| Suggestions | Proposed impacts, actions, and plans are relevant, conditional where needed, and clearly separate from reported facts. They should not repeat completed work, assume an owner/deadline, contradict a denial, or present a proposal as agreed work. |
| Questions and effort | Questions address actual gaps rather than information already supplied. Record substantive edits, details the reviewer had to retrieve, and review/editing time using the same method for every variant. |
| Failure handling | Include failed generation, malformed structure, empty factual output, and incomplete processing. Check that limitations and unprocessed source remain visible. Do not exclude failures or treat a readable fallback as a completed log. |

## Record critical errors separately

Flag invented facts or approvals, reversed negation, changed actors or times, unconfirmed work presented as completed, unsupported certainty about impact, and material information assigned to the wrong event. Record the exact claim, supporting or conflicting source passage, affected event/section, and required correction. Distinguish these from cosmetic edits and lexical-check failures.

For each variant, retain the case ID, critical errors, supported facts correctly placed, important omissions/unassigned details, suggestion usefulness, and editing effort. Literal fragments, quote matches, and schema validity remain diagnostic checks; none substitutes for these judgments.

## Candidate release decision

A candidate should improve supported fact placement and reduce editing effort without increasing unsupported claims or falsely completed actions. Inspect regressions individually; do not promote from validation loss or a single aggregate score. After design freeze, use the small reserved set as an additional check, document every failure, and avoid claims of broad accuracy or operational readiness.
