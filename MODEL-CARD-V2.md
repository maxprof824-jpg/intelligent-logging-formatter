# Intelligent Logging Formatter v2 — model card

Prepared 2026-09-11. This local proof of concept organizes fictional administrative notes into **SITUATION (with event times), IMPACT, AGENCIES CONTACTED (W/Initials), ACTION, and PLAN**. It also offers labeled possible impacts, recommended actions, suggested plans, and confirmation questions. It was trained entirely on synthetic examples; no actual UEWR logs or operating procedures were used.

## Current runtime 2.5

The adapter weights and training measurements below are unchanged. Runtime 2.5 processes explicit author-labeled events separately and maps evidence to original source locations. It retains the bounded paraphrase checks, source coverage, and setup/evaluation protections introduced in 2.4. Review [VALIDATION-V25.md](reports/VALIDATION-V25.md) for measured results. Historical v2.1–2.4 evidence remains labeled by its actual version.

## Model and runtime

The trained artifact is a separate **LoRA adapter**, not a standalone replacement for the base model. V2 was trained from the original **Qwen/Qwen3-4B-Instruct-2507** base, revision `cdbee75f17c01a7cc42f958dc650907174af0554`; it did not continue training the v1 adapter. The base weights remain in the project's `models/Qwen3-4B-Instruct-2507` directory. File hashes are recorded in [model-manifest.json](model-manifest.json).

The demo combines those adapter weights with [event grouping](event_groups.py), the [event formatter](event_formatter.py), and the existing [factual pipeline](coach.py) and [suggestion pass](coaching_pass.py):

- Factual sections are intended to contain supplied information only. Paraphrases carry exact source quotations; missing information stays missing.
- Only standalone `EVENT: descriptive label` headings establish separate groups. Repeated normalized labels join later updates to that event. Unlabeled notes remain one group with a warning; no automatic incident identification is claimed. Opening context stays unassigned and bypasses inference, so date/time context belongs inside each relevant event.
- Possible impacts and proposals remain visibly separate from reported facts. A recommendation is not a completed action, and a suggested plan is not agreed work.
- Factual checks and optional suggestions run independently for each event, using the unchanged model prompts. The optional second pass uses the **same loaded adapter**. Disabling assistance hides suggestions and skips that pass.
- The whole submission is limited to 120,000 characters and eight groups, including unassigned opening context. Each processed event is limited to 12,000 cleaned source tokens, using overlapping chunks of about 2,200 tokens. Failed or oversized events retain their source for review and mark the draft incomplete. Recognized author requests and embedded instructions remain excluded from evidence.
- Evidence for facts, suggestions, and review excerpts maps to original source offsets and line numbers. All exact matches within the event are retained; disjoint updates map to separate spans rather than an invented continuous location. JSON offsets are zero-based, end-exclusive Python Unicode code-point indices. Matching text does not establish the intended speaker, time, or meaning.
- The main generation prompt still requests at most four concise evidence/basis quotations per item. The current validator accepts up to 64 per fact or suggestion so extra evidence in a dense note does not alone invalidate an entire chunk. Every quote must still occur literally in that input chunk, and the same downstream evidence and paraphrase checks apply. This increases structural tolerance, not semantic confidence.
- Quote checks and simple number/initial checks reject some unsupported text. Verified excerpts from a rejected paraphrase can appear in an **UNASSIGNED** review block for the author to place; they are not silently assigned to a factual section.

The [loader](core.py) uses local files, a 4-bit NF4 base with double quantization, and BF16 compute. The demo listens on `127.0.0.1:7860` and processes notes locally.

## Training record

| Setting | Recorded value |
|---|---|
| Data | 480 training examples; 48 validation examples; synthetic only |
| Adapter | Rank 16; alpha 32; dropout 0.05; linear attention/MLP projections |
| Optimization | One epoch; learning rate 0.0001; microbatch 1; accumulation 8; seed 42 |
| Objective | Assistant-completion-only loss; gradient checkpointing |
| Sequence limit | 4,096 tokens; longest observed training example 1,480 tokens |
| Measured training/saving wall time | 731.49 seconds, approximately **12.2 minutes** |
| Peak allocated / reserved VRAM | **7.48 GiB / 13.38 GiB** |

The memory figures are separate PyTorch allocator measurements, not quantities to add together or total system memory usage. Post-training validation took another 20.64 seconds. Configuration, dataset hashes, and measurements are recorded in [training-config.json](runs/adapter-v2/training-config.json), [adapter_config.json](runs/adapter-v2/adapter_config.json), and [metrics.json](runs/adapter-v2/metrics.json).

The [dataset card](data-v2/DATASET_CARD.md) describes scenario families, split construction, token counts, and limitations of the small, programmatically expanded dataset. Its generator does not read the acceptance cases.

The [new synthetic curriculum](data-v3/DATASET_CARD.md) contains 720 training rows and 144 validation rows for a future candidate, including main-response and suggestions-only tasks. It has not been used to update the released adapter. The curriculum's template reuse and validation limits are documented separately. A training preflight exercises feasibility without optimizer updates or saved candidate weights; consult the current validation record for its result. It is not a completed fine-tuning run.

## Files and reproduction

Project root: `intelligent-logging-formatter`.

| Purpose | File or directory under the project root |
|---|---|
| V2 weights and saved training configuration | `runs/adapter-v2/`; adapter weights: `adapter_model.safetensors` |
| V2 data | `data-v2/train.jsonl`, `data-v2/validation.jsonl` |
| Preparatory curriculum / broader evaluation | `data-v3/` / `evaluation-v3/` |
| Local Python and dependency record | `.venv/Scripts/python.exe`, `requirements-lock.txt` |
| Open / stop demo | `RUN-DEMO.cmd` / `STOP-DEMO.cmd` |
| Reproduce v2 training | `TRAIN-V2.cmd` |
| Event evaluation / legacy evaluation | `EVALUATE-EVENTS.cmd` / `EVALUATE-V2.cmd` |

Stop the demo before training or evaluating to free GPU memory. The training launcher protects an existing completed adapter from accidental replacement. For a fresh reproducibility run, choose a new output directory:

```powershell
$pocRoot = 'intelligent-logging-formatter'
& "$pocRoot\.venv\Scripts\python.exe" "$pocRoot\train.py" --data-dir data-v2 --max-length 4096 --output runs/adapter-v2-reproduction
& "$pocRoot\.venv\Scripts\python.exe" "$pocRoot\evaluate_v2.py" --adapter runs/adapter-v2-reproduction --name adapter-v2-reproduction
```

These commands reuse the saved base model and dataset. Seeded generation and saved hashes aid reproduction; identical weights across different hardware/software environments are not guaranteed.

## Evaluation and remaining limits

Runtime 2.5 has a [20-note development corpus](evaluation-v3/DATASET-CARD.md) spanning five logging domains, both modes, both assistance settings, and realistic long notes. The event-evaluation launcher also compares five selected notes with the legacy flat pipeline using the same adapter. This compares application behavior, not new model weights. Ten separate reserved examples remain unused for inference. See [VALIDATION-V25.md](reports/VALIDATION-V25.md) for completion, failures, timings, and exact code/data identities; corpus size alone is not evidence that the tool passed.

The 18-case development evaluation is complete for runtime v2.1; four targeted cases were rerun for v2.2 safeguards. Runtime v2.3 adds a deterministic coverage check that preserves omitted date/time/reference source sentences as UNASSIGNED excerpts. Its recovery was verified by replaying recorded real-model chunk outputs, without new inference. Read [V2-ACCEPTANCE.md](reports/V2-ACCEPTANCE.md), [V2-REGRESSIONS.md](reports/V2-REGRESSIONS.md), and [chunking-v2-recovery.json](reports/chunking-v2-recovery.json) for the separate measurements and limits. This card makes no semantic accuracy claim. The cases were not used to train the adapter, but their outputs were used to refine the runtime pipeline; they are development acceptance cases, **not an unbiased, untouched holdout**.

Exact quote presence does not prove that a paraphrase follows from its evidence. Field misplacement, omitted details, mistaken event associations, and unsupported implications remain possible. A plausible proposal still needs confirmation; the model cannot establish an actual impact, completed action, or agreed plan. The prototype's suggestions concern administrative documentation and coordination. Fresh fictional notes reviewed by an operator are needed to assess usefulness beyond these development cases.
