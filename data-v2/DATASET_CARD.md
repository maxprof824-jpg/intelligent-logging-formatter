# Synthetic logging coach dataset v2

This dataset contains 480 training and 48 validation examples authored specifically
for a local proof of concept. Every event, person, office, reference and timestamp is
fictional. No actual UEWR logs, internal records or operating procedures were used.
The examples cover office equipment errors, administrative receipt of public launch
notices, conversations about office/training arrangements, maintenance paperwork and
visits for office equipment, and other clerical records.

## Target behavior

The five fact sections retain supplied details and chronology. A fact may clean up
shorthand or combine fragments, but always carries one or more exact contiguous
source quotations as evidence. Missing sections are empty arrays. Uncertain times,
unverified outcomes, explicit no impact/no action/no follow-up, and planned versus
completed work remain distinct.

Suggestions are separately marked possible impacts, proposed administrative actions,
or proposed follow-up plans. Every suggestion quotes its source basis and asks a
confirmation question. They help the author clarify affected activities, verify
receipt or records, obtain missing documentation, and choose a follow-up owner or
review point. They never prescribe radar operation or tactical action and never
invent initials, IDs, dates, outcomes or approvals.

## Construction and split

- Training: 456 detailed examples from 24 scenario families, plus 24 deliberately
  vague examples whose correct output has no speculative suggestions.
- Validation: 44 detailed examples from 11 separately written families and a
  disjoint office-name/initials/month pool, plus four vague examples.
- Both draft and review modes use the same evidence-bearing contract.
- Examples vary fragment ordering, shorthand, duplicates, punctuation and unrelated
  administrative clutter. Many contain two or three timestamped related events;
  45 longer training notes contain five related events including a documentation
  review sequence. Reviewing the note is never treated as resolving its event.
- Pasted instructions to fabricate identity, approval, times or resolution are
  ignored, including some sources with instructions but no actual event facts.
- Generation is seeded and deterministic. The generator performs JSON Schema,
  exact source-span, confirmation-question and exact-source duplication checks.
- CPU tokenization checks each full chat example against the 4,096-token training
  limit; the token counts below include the system instruction and target JSON.
- Exact duplicate source texts within or between training and validation: **0**.
- The independently authored acceptance file is never read by this generator and
  is not used to create training targets.

The source frames and scenario families differ by split, but the target contract,
administrative skills and some linguistic patterns intentionally overlap. This is a
small programmatically expanded demonstration dataset, not evidence of broad
operational reliability. Template expansion limits diversity; fresh human-authored
fictional examples and human review remain necessary. Exact source-span validation
checks quote existence, not whether the surrounding fact or suggestion is a sound
interpretation. The application must preserve suggestion labels and confirmation.

## Verified generation statistics

```json
{
  "train": {
    "rows": 480,
    "facts": 1546,
    "suggestions": 798,
    "equipment_error": 95,
    "draft": 240,
    "no_suggestions": 119,
    "multiple_evidence_facts": 216,
    "review": 240,
    "launch_report": 76,
    "conversation": 76,
    "preventive_maintenance": 95,
    "other": 138,
    "total_chat_tokens": {
      "min": 609,
      "median": 961,
      "p95": 1412,
      "max": 1480
    },
    "sha256": "221b20b72c07abf1e65c5fea96e7467f2337c8fb9ebcbc652280a2e340efefba"
  },
  "validation": {
    "rows": 48,
    "facts": 140,
    "suggestions": 68,
    "equipment_error": 8,
    "draft": 24,
    "no_suggestions": 16,
    "multiple_evidence_facts": 16,
    "review": 24,
    "launch_report": 8,
    "conversation": 8,
    "preventive_maintenance": 8,
    "other": 16,
    "total_chat_tokens": {
      "min": 610,
      "median": 926,
      "p95": 1065,
      "max": 1125
    },
    "sha256": "68c166cba26037d1165210aa10cb049d9c5cb6b5f955b47b0b73dd424082741e"
  }
}
```

Regenerate with the project's Python environment: `python build_data_v2.py`.
The command writes only train.jsonl, validation.jsonl and this card under data-v2.
