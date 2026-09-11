# Synthetic formatter curriculum v3

Every record is invented. No workplace logs, operational procedures, reserved evaluation cases, or external model-generated examples are used.

Training contains **600 main-call and 120 helper-call examples** across 20 scenario families. Validation contains **120 main and 24 helper examples** across 6 different families. Every family/task has equal draft and review counts. Main and helper calls use distinct source records; source text is unique across tasks and splits.

Main targets follow the current five-section prompt and schema. Helper targets follow the current suggestions-only contract, including requested sections and existing factual context. Empty helper targets teach restraint when context or supplied completed/denied facts make a suggestion unnecessary. Helpers do not repeat an agreed next step as a new recommendation.

The invented stories cover offices, facilities, warehouses, libraries, education, laboratory administration, volunteer work, museums, and permit administration. Difficult cases distinguish speakers, promises from completion, partial receipt from full receipt, explicit denials from missing information, corrections from competing accounts, and paperwork checks from technical work. Suggestions concern documentation and coordination, not technical repairs or operational decisions.

Long examples describe one incident and contain substantial related form-guide context. They train separation of event evidence from accompanying reference material. Complete paragraphs are included only while the full chat stays within 4,096 tokens and source text within 2,200 tokens. No answer or evidence quote is truncated. These examples do not substitute for diverse long user narratives.

Generation checks schema, literal quote/basis presence, proposal framing, per-family mode balance, distinct split families, unique source text, and full-chat token length with the pinned base tokenizer. These checks verify construction properties; they do not prove semantic correctness or model quality. BUILD-REPORT.json records counts, lengths, and hashes.

## Diversity limits

This is a small hand-designed template curriculum. Names, times, IDs, ordering, and framing vary inside a family, while its causal pattern stays similar. Shorthand cleanup is deliberately limited to known equivalent phrases. Validation families differ but share author, contracts, code, and administrative vocabulary. Neither split independently measures broad generalization. Long reference paragraphs recur across long families. Domain coverage is illustrative, not validation for those professions.

## Rebuild

```powershell
.venv\Scripts\python.exe build_data_v3.py --model-dir models/Qwen3-4B-Instruct-2507 --output data-v3
```

The generator reads local runtime contracts and tokenizer files only. It does not load model weights, use a GPU, train an adapter, or read reserved evaluation data.

## Measured build

- Train: 720 rows; longest full chat 3,527 tokens; 144 long rows with 2,161-2,184 source tokens.
- Validation: 144 rows; longest full chat 3,451 tokens; 48 long rows with 2,168-2,185 source tokens.

Identity-stripped exact source overlap across splits: 0. Maximum nearest training/validation word-trigram Jaccard similarity: 0.812. Shared long form-guide text contributes to this similarity; see the full diagnostic and limitations in BUILD-REPORT.json. These are development splits, not reserved evaluation data.
