# Intelligent Logging Formatter — v3 training experiment

This release adds a separately trained adapter and a complete comparison of the base model, current v2 adapter and v3 candidate on 20 synthetic notes. The project explores daily information tracking in logging-heavy jobs using fictional records.

The candidate placed more checked details and needed fewer corrections overall, but introduced new errors about causes and promised follow-ups. It did not pass the promotion criteria. **The usual launcher still uses v2.** See the [comparison](reports/V3-COMPARISON.md) for results and the [model card](MODEL-CARD-V3-CANDIDATE.md) for training details.

- **Tester ZIP:** application, current v2 weights and optional v3 weights. Extract, run `SETUP-WINDOWS.cmd`, then `RUN-DEMO.cmd`.
- **Source ZIP:** code, synthetic data and reports; no model weights.
- **Candidate ZIP:** optional adapter for an existing installation; it is not a complete application.

To try v3 from the tester package, stop the demo and run `RUN-DEMO.cmd --adapter runs/adapter-v3-experimental`. The footer identifies the selected adapter. Windows with a compatible NVIDIA GPU is required; initial setup downloads dependencies and the approximately 8 GB base model. See the [usage guide](V2-GUIDE.md).

Training completed on 720 synthetic examples with 144 validation examples. The comparison retained all 60 attempts, including failures, and all 20 notes received AI-assisted source review. Ten reserved notes remain unused for inference and semantic review. The exported candidate passed a local startup check; a clean installation on another computer and representative-user testing remain outstanding. This is an experimental local prototype, with human review required for every draft.
