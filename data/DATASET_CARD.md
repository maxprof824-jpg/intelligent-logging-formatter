# Synthetic five-section administrative logs

Created for this local proof of concept on September 11, 2026. No real logs, organizational records, operational manuals, or remote datasets were used. Every agency, initial, asset, reference, event, and scenario is fictional. Any resemblance to an actual identifier is coincidental.

**Contract:** source note plus mode → JSON containing an internal event category and `situation`, `impact`, `agencies_contacted`, `action`, `plan`. Field values are exact source spans or null. Situation preserves supplied chronology and uncertainty. A separate checker asks for missing details and renders the user's five headings.

**Splits:** 480 generated training cases, 60 generated validation cases with different scenario IDs and heading aliases, and 24 hand-authored test cases. Source hashes are checked for exact duplication across all splits. The generator shares semantic templates across training and validation; validation loss is not a generalization benchmark. Train and validation vary field order, note layout, chronology, heading aliases, and missing information. Some notes contain irrelevant pasted instructions that targets ignore.

**Scope:** administrative receipt of public launch reports, generic training/office equipment errors, conversations, preventive maintenance documentation, and other office administration. This is not a source of operational knowledge or an approved UEWR log standard.

**Limitations:** small template vocabulary, synthetic distribution, English-only training, limited contact-initial patterns, basic date/time patterns, few adversarial cases, no real operator shorthand, no adjudicated real-world outcome labels. Test exact-match scores may penalize harmless quote-boundary differences. Cases encountered during development are no longer pristine for the next experiment.

**Improve next:** ask operators to author and review fresh fictional notes that reflect realistic writing habits, while keeping all source data approved for this environment. Split by incident/scenario before making variants. Do not put the test targets in training. Record reviewer decisions, schema version, scenario ID, and data provenance.

Run `build_data.py` to reproduce the original generated corpus. It overwrites the JSONL files; save manually curated additions elsewhere before regenerating. Edit the authoritative schema in `core.py`, then regenerate data and retrain if the target contract changes.
