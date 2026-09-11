# Logging coach v2

The new default demo organizes messy notes into the same five sections and helps the author develop missing content. RUN-DEMO.cmd opens v2; RUN-V1-DEMO.cmd preserves the earlier extract-only model. Stop the current demo with STOP-DEMO.cmd before switching models or training.

## How it helps

- **Reported details:** cleans up shorthand, combines related fragments, and preserves source evidence, dates, times, initials, references, negation and uncertainty.
- **Possible impact:** when an impact is missing or uncertain, proposes a plausible administrative effect for the author to confirm. A frozen classroom console might have interrupted a practice session; the model must not assert that it did.
- **Recommended action:** proposes a documentation or coordination step, such as confirming who was affected or whether a support request exists. This is never presented as an action already performed.
- **Suggested plan:** proposes follow-up, such as identifying an owner and agreeing a review point. It does not invent a deadline or turn a proposed plan into an approved one.
- **Questions:** asks for the actual missing details, plus questions tied to the suggested content.

These additions appear inside your five headings with visible labels: **POSSIBLE IMPACT — CONFIRM**, **RECOMMENDED ACTION — NOT RECORDED AS DONE**, and **SUGGESTED PLAN — NOT YET AGREED**. If the first pass leaves an unresolved impact, action or plan without useful assistance, a conditional second pass through the same adapter requests suggestions for those gaps. The second pass adds suggestions, not factual claims. Turning off the assistance checkbox skips that additional pass and leaves the factual draft without suggestions. Edit the draft for your use or add confirmed answers to the source and prepare it again. Editing a draft does not itself establish that a suggestion is true.

## Longer notes

The app accepts up to 12,000 source tokens, roughly 7,000–9,000 English words depending on the content. It processes overlapping sections of about 2,200 tokens and merges the results, keeping evidence for each fact. Separate events can remain identifiable in the wording of the draft. It does not silently truncate oversized submissions. If a section fails, the result is explicitly marked incomplete. Missing source times are listed for review.

The runtime also checks recognizable dates, times and reference identifiers against the draft. When one is omitted, its exact source sentence is preserved in the UNASSIGNED review block. This keeps important anchors visible without claiming correct field placement or complete coverage of every detail. Source-span grouping and deduplication are heuristics; they do not prove event relationships or chronology. Long, dense submissions take longer and may need to be split into related incidents.

## Model change

A separate rank-16 QLoRA adapter was trained from the original Qwen3-4B-Instruct-2507 model on **480 synthetic training examples**, with **48 validation examples**. Training took **12.2 minutes**, with peak allocated VRAM of **7.48 GiB** and peak reserved VRAM of **13.38 GiB**. Allocated and reserved memory are different measurements, not amounts to add together.

The richer output contract contains five arrays of factual sentences with evidence, plus separate suggestions with source basis and a confirmation question. Training uses assistant-response-only loss, BF16 compute, NF4 base weights, gradient checkpointing and a microbatch of one. The old adapter and old evaluation remain intact.

Training data and generation code: `data-v2/` and `build_data_v2.py`. The **18 acceptance examples were authored independently and were not used for model training**. They contain short messy notes and two longer notes, including contradictory times, proposed versus completed actions, uncertain paperwork and pasted instructions. Their outputs have since been examined to refine the application's filtering and coaching pipeline. They are therefore development acceptance cases, not a pristine held-out estimate of generalization. Initial raw outputs exposed problems including copied editing requests, an embedded instruction, inaccurate paraphrases and missing useful suggestions. Final pipeline results must be read from the completed acceptance report; these changes alone do not establish that every case passes.

## Reproduce

```powershell
.\.venv\Scripts\python.exe train.py --data-dir data-v2 --max-length 4096 --output runs/adapter-v2
.\.venv\Scripts\python.exe evaluate_v2.py
.\.venv\Scripts\python.exe app_v2.py
```

TRAIN-V2.cmd and RESUME-V2.cmd provide the same workflow. Choose a new `--output` path for additional experiments so the trained adapter is not overwritten.

## What still needs review

Quote checks verify that evidence appears in the note. When a simple check finds an unsupported number or contact initial in a factual paraphrase, the app preserves its exact verified source excerpts in an **UNASSIGNED** review block below the five sections. The error can also indicate that the model chose the wrong section, so the author must assign those excerpts during review. They are not automatically placed in ACTION, PLAN or another factual section, and the draft remains marked as needing confirmation. Evidence quotations that are not present in the source are still withheld. These checks cannot prove that a paraphrase or possible impact is logically supported.

The source filter excludes recognized requests to rewrite the log, recognized control lines, and delimited blocks that contain instructions directed at the model. It does not recognize every possible embedded instruction. Suggestions concern administrative documentation and coordination; the model does not establish operational impact or prescribe radar or maintenance procedures.

Acceptance metrics separately show the final draft's structure and literal retention, raw main-pass schema and quote checks, and raw second-pass schema and quote checks when available. Literal retention counts only the five factual sections: a time or reference visible in the UNASSIGNED review block can still fail that check because it has not been assigned to the log. These are not semantic accuracy scores. Expected-empty-section checks can penalize legitimate, attributed future plans, and forbidden-phrase searches can flag negated statements. Inspect those cases in context. A valid JSON object and a real source quote do not by themselves establish a correct interpretation.

All data remain fictional in this proof of concept. The useful next evaluation is independent operator review of fresh fictional notes, assessing retained facts, sensible questions, useful suggestions and mistaken implications. See STATUS.md and the v2 acceptance report for the actual measured results.
