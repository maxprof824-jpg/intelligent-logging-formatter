# Using Intelligent Logging Formatter

This synthetic proof of concept turns fictional notes into five sections and helps the author identify missing details. Runtime **2.4** uses the same trained v2 adapter, with improved checks and a clearer review interface.

## Run the demo

Extract the tester download, run **SETUP-WINDOWS.cmd**, then **RUN-DEMO.cmd**. Open <http://127.0.0.1:7860> if the browser does not open. Use **STOP-DEMO.cmd** before training or evaluation so the model is not competing for GPU memory.

Draft mode organizes rough notes; review mode applies the same source and completeness checks to an existing log. Neither mode approves a log. Keep separate incidents in separate submissions when possible.

## Review the result

- Check **Situation, Impact, Agencies contacted, Action, and Plan**, including event times, who said what, and whether work was completed or merely proposed.
- Possible impacts, recommended actions, and suggested plans are labeled separately. They require confirmation.
- Read **source passages to place during review**. These include rejected paraphrase evidence and text not covered by accepted factual evidence. They have not been assigned to the right field for you.
- Open **Compare draft entries with your source** to see each generated entry beside its quotations. A real quote does not prove that the entry's meaning or placement is correct.
- Edit the draft or add missing information to the notes and generate again. Evidence rows refer to the generated draft, so recheck them after editing.

The formatter accepts up to 12,000 source tokens and processes long notes in overlapping parts. It rejects oversized input rather than silently cutting it. Failed parts are marked incomplete. Long and dense notes can still lose field placement or produce a large review area; progress now identifies the current stage and part.

The model is asked for at most four concise quotes per entry, but validation allows up to 64 for dense notes. Extra quotes within that limit no longer cause a whole part to fail. They still undergo the same source and paraphrase checks; more evidence does not establish that an entry is correct.

## Train or evaluate

**TRAIN-V2.cmd** creates a new timestamped experiment and prints a command for opening that adapter. The released adapter is preserved. To select an existing experiment yourself:

```powershell
.venv\Scripts\python.exe app_v2.py --adapter runs/experiments/YOUR-RUN
```

**EVALUATE-V2.cmd** runs the synthetic development evaluation. Each run gets separate files; see its printed paths. For CPU checks:

```powershell
.venv\Scripts\python.exe -m unittest discover -p "test_*.py"
```

Setup verifies local model files using their saved hashes. An already complete installation can be checked without internet access:

```powershell
.venv\Scripts\python.exe download_model.py --verify-only
```

The training data remain the original 480 synthetic examples and 48 validation examples. Read the [model card](MODEL-CARD-V2.md), [review and roadmap](REVIEW-AND-ROADMAP.md), and [2.4 validation record](reports/VALIDATION-V24.md) for evidence and limitations. No claim of readiness for real operational use is made.
