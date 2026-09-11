# Logging Coach v2.3 — proof-of-concept preview

Windows tester package containing application code, synthetic datasets, evaluation evidence, and the trained LoRA adapter. Extract the tester ZIP, run SETUP-WINDOWS.cmd, then RUN-DEMO.cmd. Setup downloads Python, dependencies, and the pinned approximately 8 GB base model. Tested locally on RTX 5060 Ti 16 GB / 32 GB RAM; recipient clean-install testing remains pending.

Runtime v2.3 uses the same trained v2 adapter plus improved evidence and source-excerpt recovery checks. All outputs require human review. This release does not provide an online inference endpoint.
