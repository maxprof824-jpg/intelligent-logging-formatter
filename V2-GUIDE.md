# Using Intelligent Logging Formatter

This synthetic proof of concept turns fictional notes into five sections and helps the author identify missing details. Runtime **2.5** uses the same trained v2 adapter, with separate drafts for author-labeled events and source locations for reviewing facts and suggestions.

## Run the demo

Extract the tester download, run **SETUP-WINDOWS.cmd**, then **RUN-DEMO.cmd**. Open <http://127.0.0.1:7860> if the browser does not open. Use **STOP-DEMO.cmd** before training or evaluation so the model is not competing for GPU memory.

Draft mode organizes rough notes; review mode applies the same source and completeness checks to an existing log. Neither mode approves a log.

## Separate events in your notes

Start each event with `EVENT: descriptive label` on its own line. Repeating the same label joins later updates to that event. Put dates, time zones, and other necessary context inside each relevant event; opening text before the first heading stays unassigned for your review and is not passed to the model.

```text
EVENT: Visitor register query
2026-09-12, UTC. 09:10 the register would not open. Cause unknown.

EVENT: Room notice update
2026-09-12, UTC. 09:15 Reception (AB) confirmed the new room notice was displayed.

EVENT: Visitor register query
09:25 UTC Support (CD) acknowledged the report; no fix confirmed.
```

Labels match after ignoring capitalization and extra whitespace. Without headings, the app processes the notes together and asks you to add labels if they describe separate incidents. Standalone `EVENT:` lines inside pasted material also count as headings, so check the resulting groups.

## Review the result

- Check **Situation, Impact, Agencies contacted, Action, and Plan**, including event times, who said what, and whether work was completed or merely proposed.
- Possible impacts, recommended actions, and suggested plans are labeled separately. They require confirmation.
- Read **source passages to place during review**. These include rejected paraphrase evidence and text not covered by accepted factual evidence. They have not been assigned to the right field for you.
- Open **Compare draft entries with your source** to see facts and suggestions beside their quotations and original source lines. Repeated wording shows every matching location within that event; the app does not choose which occurrence was intended. A real quote does not prove correct meaning, speaker, or placement.
- Edit the draft or add missing information to the notes and generate again. Evidence rows refer to the generated draft, so recheck them after editing.

The submission limit is 120,000 characters and eight groups in total, including any unassigned opening context. Each processed event has its own 12,000-source-token limit and uses overlapping parts of about 2,200 tokens. An oversized event is marked incomplete with its source retained for review; it is not silently truncated. Long and dense notes can still lose field placement or produce a large review area.

The model is asked for at most four concise quotes per entry, but validation allows up to 64 for dense notes. Extra quotes within that limit no longer cause a whole part to fail. They still undergo the same source and paraphrase checks; more evidence does not establish that an entry is correct.

## Train or evaluate

**TRAIN-V2.cmd** creates a new timestamped experiment and prints a command for opening that adapter. The released adapter is preserved. To select an existing experiment yourself:

```powershell
.venv\Scripts\python.exe app_v2.py --adapter runs/experiments/YOUR-RUN
```

**EVALUATE-EVENTS.cmd** runs the 20-note synthetic development set through the event formatter and compares five selected notes with the legacy flat formatter, using the same adapter. The 10 reserved notes are not selected by this launcher. **EVALUATE-V2.cmd** remains available for the older 18-case development evaluation through the legacy pipeline. Each run gets separate files; see its printed paths. For CPU checks:

```powershell
.venv\Scripts\python.exe -m unittest discover -p "test_*.py"
```

Setup verifies local model files using their saved hashes. An already complete installation can be checked without internet access:

```powershell
.venv\Scripts\python.exe download_model.py --verify-only
```

## Prepare a future training candidate

Run these commands from the installation folder after setup and local base-model verification. Replace `NEW` with a fresh report name each time; existing reports are protected. Start with the CPU curriculum audit and review its findings:

```powershell
.\.venv\Scripts\python.exe audit_curriculum.py --output reports/curriculum-v3-NEW.json
```

Stop the demo before the GPU feasibility check. This preflight performs no optimizer updates and saves no candidate weights. Passing it does not guarantee that a full training run will fit or improve the model.

```powershell
.\STOP-DEMO.cmd
.\.venv\Scripts\python.exe preflight_training.py --output reports/training-v3-NEW.json
```

This phase prepares data and checks feasibility; it does not launch candidate training. When ready for a **future training run**, replace `UNIQUE` with an unused experiment name:

```powershell
.\.venv\Scripts\python.exe train.py --data-dir data-v3 --max-length 4096 --epochs 1 --accumulation 8 --output runs/experiments/v3-candidate-UNIQUE
```

That command initializes a new adapter from the pinned base model. It preserves the released adapter and refuses an existing training-run directory. The candidate must be evaluated separately before replacing the model used in the demo. `TRAIN-V2.cmd` continues to reproduce the original v2 curriculum.

The released adapter was trained on the original 480 synthetic examples and 48 validation examples. The separate [new curriculum](data-v3/DATASET_CARD.md) is preparation for a future candidate, not a newly trained model. Read the [model card](MODEL-CARD-V2.md), [roadmap](REVIEW-AND-ROADMAP.md), and [2.5 validation record](reports/VALIDATION-V25.md) for measured results and limitations. No claim of readiness for real operational use is made.
