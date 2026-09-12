# Synthetic evaluation corpus v3

This corpus tests whether a logging formatter preserves useful information while keeping unrelated events separate. Every note, person, record, office, timestamp, and outcome is fictional. It covers administrative aspects of logging-heavy work; it contains no real workplace records, internal procedures, or operational recommendations.

The notes were authored for evaluation independently of the new training curriculum. The evaluation author did not read `build_data_v3.py` or `data-v3/`, and did not provide note contents to the training author. The domains, requested format, and explicit-event contract were shared design requirements. This is separate synthetic authoring, not independent human validation or a claim that all language and scenario patterns are novel.

## Files and intended use

| Split | Notes | Per domain | Use |
|---|---:|---:|---|
| `development.jsonl` | 20 | 4 | Inspect outputs, diagnose failures, and improve the runtime. |
| `reserved.jsonl` | 10 | 2 | Reserve for a later comparison after design choices are frozen. No inference on this split was performed during authoring. |

The five domains are maintenance paperwork, IT support, facilities, administrative tracking, and shift handover. The development split includes all four combinations of draft/review mode and assistance enabled/disabled in every domain. The smaller reserved split includes both modes and both assistance settings per domain, but not every combination.

Reserved examples must not guide prompts, runtime rules, training examples, or model selection during development. If their notes or outputs are used that way, relabel them as development and create a new reserved set. Integrity tools can inspect structure and hashes without generating model outputs. The file is stored with the project, so it is not a secret or independently administered benchmark. No general accuracy claim follows from either split.

## What is exercised

Development contains 15 notes with explicit event labels, five unlabeled ambiguous notes, and five notes that revisit a previous event heading. Coverage includes repeated identical statements attached to different events, separate speakers, corrected timestamps and counts, unconfirmed initials, pending versus completed actions, limited observations, cross-midnight updates, and one event with no reported effect beside another with unknown impact. Some records and individual events are complete, allowing reviewers to notice unnecessary questions or suggested work.

Two longer notes use substantive related updates rather than repeated filler. They include reports from several people, later corrections, evidence references, limited successful checks, handover ownership, and unresolved follow-up.

| Development ID | Words | Source tokens | Largest explicit event, tokens |
|---|---:|---:|---:|
| `dev-v3-it-05` | 1,957 | 2,482 | 2,255 |
| `dev-v3-shift-17` | 2,128 | 2,715 | 1,133 |

Token counts use the locally stored Qwen3-4B-Instruct-2507 tokenizer, revision `cdbee75f17c01a7cc42f958dc650907174af0554`, without added special tokens. They exclude model prompts and generated output. The IT note includes a single event longer than the 2,200-token chunk threshold; the handover note is long in total but its individual labeled events are shorter. Only tokenization was used to obtain these counts, not model inference.

## Row contract

Each row contains `id`, `domain`, `mode`, `assist`, `source_text`, and `expectations`. Expectations contain:

- `event_count`: the number of unique explicit `EVENT: descriptive label` headings, or `null` for unlabeled notes. It does not count an unassigned preamble and does not claim how many real events an unlabeled note contains.
- `expected_event_labels`: first-occurrence labels, in source order. A later heading with the same normalized label updates that event. Headings are author-supplied boundaries; successful grouping does not establish reliable automatic discovery of events.
- `checks`: entries with `event_label` (or `null` for an unlabeled note), a standard `section`, `required_fragments`, `forbidden_fragments`, and a human `review_note`.

Fragments are deliberately limited lexical review aids. Search them in the intended event's intended factual section; a fragment found only in another section, another event, a quotation, a suggestion, or an unassigned excerpt does not establish correct placement. A correct paraphrase can fail a literal requirement, and an incorrect or negated sentence can contain every required word. Forbidden fragments can miss paraphrases or trigger on correctly preserved denials and historical corrections. Do not convert these checks into semantic accuracy or treat an exact source quote as proof of the generated claim.

Human review should assess meaning, attribution, chronology, negation, uncertainty, omitted details, field placement, and whether assistance adds useful information. A no-impact statement must remain scoped to its event. A source's suggestion or reported future action must not become completed work. Long-note success must account for both details organized into fields and details left for manual placement.

## Integrity and provenance

Run `python validate_evaluation_v3.py` from the project root. It prints IDs, counts, hashes, and integrity problems, never note contents. Run `python -m unittest test_evaluation_v3` for its CPU regression checks. The validator checks schema, unique IDs, normalized source uniqueness within and across these two splits, per-domain mode/assistance coverage, explicit labels/counts, check targets, nonempty/nonconflicting fragments, and that required fragments occur in their stated event's source. It also checks the presence of unlabeled cases, revisited headings, and two notes of at least 1,700 words. None of these checks runs the model or evaluates generated meaning.

There are zero duplicate normalized source texts within or between these two files. This is not a near-duplicate search against the training corpus. The validator does not read training data.

Frozen file SHA-256 values:

- `development.jsonl`: `2dea24c5016a739076b0d4e30829b3385e9c1097f55e00ef9b40c898dcd5672a`
- `reserved.jsonl`: `34a870aa85b7fa99b4aaa7d6832119fa9b9899e2d031860373ca9a0ab861e3ce`

Later inference reports should identify the corpus hash, selected IDs, model/adapter, code revision, mode, assistance setting, and failures. Results from different code revisions or filtered subsets must remain separate measurements. Record any change in the reserved split's use explicitly.
