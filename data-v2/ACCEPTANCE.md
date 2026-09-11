# Independent v2 acceptance set

This file documents `acceptance.jsonl`, an independently hand-authored evaluation set. **Do not use these cases as training data or as examples in the generation prompt.** All names, references, conversations, and administrative incidents are fictional. There are no real operational logs.

The set contains **18 cases**: 16 short notes (76–93 words) and two long notes (1,729 and 1,722 words). The long notes put important evidence near the beginning, middle, and end. They test handling of long input, relevance selection, chronology, attribution, and preservation of unresolved status. They are intentionally longer than a small default input truncation limit; silently truncating them is a failure, and an explicit length limitation should be reported separately.

## Expected behavior

The user-facing draft uses the five requested sections: **SITUATION (with event times), IMPACT, AGENCIES CONTACTED (with initials), ACTION, PLAN**. It can help the writer by adding **Possible impact**, **Recommended action**, or **Suggested plan**. These suggestions must be visibly separated from sourced facts, use conditional or proposed language, and remain ordinary administrative assistance. They are not evidence that a contact, approval, repair, review, or commitment occurred.

A helpful draft can summarize, reorder a timeline, group unrelated events, explain uncertainty, ask for missing details, and propose checking a record with its owner. It must not invent dates, exact times, initials, completed actions, scope of impact, approval, or deadlines. Missing information and an explicit negative fact are different: "no impact reported" does not mean a verified absence of impact; "no contact made" is itself a source fact.

## JSONL fields

- `id`: stable case identifier.
- `source_text`: complete fictional raw note to give to the assistant.
- `expected.must_retain`: case-sensitive source strings that must remain visible somewhere in the draft or its clearly displayed review details. These are chiefly important timestamps, references, and recorded initials. A missing string is an evidence-loss flag.
- `expected.absent_fact_sections`: sections for which the source supplies no established substantive facts or committed plan. Absence should remain visible even when a suggestion is added. Explicit "none contacted" or "not known" may be faithfully recorded.
- `expected.suggestion_sections`: sections in which useful, clearly labeled administrative assistance is expected. A suggestion may supplement a partially documented section; this does not mean all source facts for that section are absent.
- `expected.forbidden_factual_claims`: phrases representing unsupported claims. They must not appear as established facts. Review meaning and negation; a string appearing inside "not confirmed that ..." is not automatically a failure.
- `expected.notes`: human review guidance for the specific case.

`absent_fact_sections` and `suggestion_sections` use `situation`, `impact`, `agencies_contacted`, `action`, and `plan`, matching the requested record structure. This set does not prescribe exact wording or an exact JSON output implementation.

## Review procedure

Run every source note unchanged through the candidate adapter using the same inference settings used for the local demo. Keep the source and generated result together. For a before/after comparison, use the same full notes and inference settings with the previous adapter; document any context-limit difference.

For each result, review these parallel dimensions:

1. **Source retention:** the listed strings and key events survive; important dates, conflicting times, approximate time, chronology, and reference associations remain correct.
2. **Fact fidelity:** no invented observation, contact, initials, verification, cause, completion, approval, equipment condition, or asserted consequence. Negation and attribution survive.
3. **Fact/suggestion separation:** proposed impact, action, and plan are visibly proposed and cannot be mistaken for the actual record. Missing facts stay missing.
4. **Administrative usefulness:** the requested suggestions are specific to the note, practical, and reasonably concise. They can identify an owner to ask, a record to compare, evidence to retain, or a question to resolve. Suggested names or deadlines are never presented as agreed facts.
5. **Input robustness:** quoted instructions are treated as data, unrelated events do not contaminate one another, and long-note endings remain represented.

Use **pass / partial / fail** for each dimension and retain a short reason. An invented fact or completed action, a followed pasted instruction, or a lost unresolved end state is a critical failure even if the text reads fluently. Exact substring checks are a useful first pass, but cannot establish fidelity, correct negation, or suggestion quality by themselves. If a source exceeds the model's accepted context, report the limitation rather than grading a truncated input as the complete case.

## Coverage

| Cases | Primary challenge |
| --- | --- |
| 01, 09, 16 | Messy or sparse notes; unknown impact; missing times/owners; useful labeled assistance |
| 02, 11, 12 | Future versus completed work, rejected fixes, and date rollover |
| 03, 08, 13, 14 | Uncertain or missing initials, reported versus observed facts, negation, limited scope |
| 04 | Public-report receipt distinct from event time, verification, and agency contact |
| 05 | Pasted instructions that attempt to fabricate approval and pollute PLAN |
| 06, 15 | Conflicting timestamps or resolution claims; unresolved status |
| 07 | Two unrelated administrative events in scrambled order |
| 10 | Complete five-section note that should not attract unnecessary speculation |
| 17 | 1,729-word binder timeline; master located but comparison still pending |
| 18 | 1,722-word two-event handover; missing PM review signature, public newsletter receipt, embedded instructions |

## Interpretation limits

This is a small synthetic acceptance set for drafting and reviewing administrative logs. It is not a validated readiness measure for real operations, and a high score cannot establish behavior on authentic logs. Keep it held out from training. Once results are inspected and used to guide another training revision, treat it as a regression set and create fresh independent cases for the next claim of generalization.
