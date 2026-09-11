# Logging coach v2 — model card

Prepared 2026-09-11. This local proof of concept organizes fictional administrative notes into **SITUATION (with event times), IMPACT, AGENCIES CONTACTED (W/Initials), ACTION, and PLAN**. It also offers labeled possible impacts, recommended actions, suggested plans, and confirmation questions. It was trained entirely on synthetic examples; no actual UEWR logs or operating procedures were used.

## Model and runtime

The trained artifact is a separate **LoRA adapter**, not a standalone replacement for the base model. V2 was trained from the original **Qwen/Qwen3-4B-Instruct-2507** base, revision `cdbee75f17c01a7cc42f958dc650907174af0554`; it did not continue training the v1 adapter. The base weights remain in the project's `models/Qwen3-4B-Instruct-2507` directory. File hashes are recorded in [model-manifest.json](model-manifest.json).

The demo's behavior combines those adapter weights with the runtime in [coach.py](coach.py) and [coaching_pass.py](coaching_pass.py):

- Factual sections are intended to contain supplied information only. Paraphrases carry exact source quotations; missing information stays missing.
- Possible impacts and proposals remain visibly separate from reported facts. A recommendation is not a completed action, and a suggested plan is not agreed work.
- When gaps remain, an optional second pass through the **same loaded adapter** requests additional suggestions. It adds inference time, not another trained model. Disabling assistance hides suggestions and skips that extra pass.
- Long notes use overlapping chunks of about 2,200 source tokens, up to 12,000 tokens per submission. The app merges results and flags incomplete processing. Recognized author editing requests and embedded instructions are excluded from evidence.
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

## Files and reproduction

Project root: `space-logging-coach`.

| Purpose | File or directory under the project root |
|---|---|
| V2 weights and saved training configuration | `runs/adapter-v2/`; adapter weights: `adapter_model.safetensors` |
| Preserved v1 adapter | `runs/adapter/` |
| V2 data | `data-v2/train.jsonl`, `data-v2/validation.jsonl` |
| Local Python and dependency record | `.venv/Scripts/python.exe`, `requirements-lock.txt` |
| Open v2 / v1 / stop demo | `RUN-DEMO.cmd` / `RUN-V1-DEMO.cmd` / `STOP-DEMO.cmd` |
| Train / resume / evaluate v2 | `TRAIN-V2.cmd` / `RESUME-V2.cmd` / `EVALUATE-V2.cmd` |

Stop the demo before training or evaluating to free GPU memory. The training launcher protects an existing completed adapter from accidental replacement. For a fresh reproducibility run, choose a new output directory:

```powershell
$pocRoot = 'space-logging-coach'
& "$pocRoot\.venv\Scripts\python.exe" "$pocRoot\train.py" --data-dir data-v2 --max-length 4096 --output runs/adapter-v2-reproduction
& "$pocRoot\.venv\Scripts\python.exe" "$pocRoot\evaluate_v2.py" --adapter runs/adapter-v2-reproduction --name adapter-v2-reproduction
```

These commands reuse the saved base model and dataset. Seeded generation and saved hashes aid reproduction; identical weights across different hardware/software environments are not guaranteed.

## Evaluation and remaining limits

The 18-case development evaluation is complete for runtime v2.1; four targeted cases were rerun for v2.2 safeguards. Runtime v2.3 adds a deterministic coverage check that preserves omitted date/time/reference source sentences as UNASSIGNED excerpts. Its recovery was verified by replaying recorded real-model chunk outputs, without new inference. Read [V2-ACCEPTANCE.md](reports/V2-ACCEPTANCE.md), [V2-REGRESSIONS.md](reports/V2-REGRESSIONS.md), and [chunking-v2-recovery.json](reports/chunking-v2-recovery.json) for the separate measurements and limits. This card makes no semantic accuracy claim. The cases were not used to train the adapter, but their outputs were used to refine the runtime pipeline; they are development acceptance cases, **not an unbiased, untouched holdout**.

Exact quote presence does not prove that a paraphrase follows from its evidence. Field misplacement, omitted details, mistaken event associations, and unsupported implications remain possible. A plausible proposal still needs confirmation; the model cannot establish an actual impact, completed action, or agreed plan. The prototype's suggestions concern administrative documentation and coordination. Fresh fictional notes reviewed by an operator are needed to assess usefulness beyond these development cases.
