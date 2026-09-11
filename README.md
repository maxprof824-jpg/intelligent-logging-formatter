# Logging Coach

**Helping people turn rough notes into logs the next person can actually use.**

In logging-heavy jobs, a log is often how people keep track of what happened, hand work over, and decide what needs attention. When a busy shift leaves behind incomplete notes, the next person has to fill in the gaps. In important environments, those gaps matter.

I built this **synthetic-data proof of concept** to explore a simple idea: could a small, locally running AI model help someone write a more useful log while they still remember the details?

The idea applies to daily information tracking in maintenance, IT support, facilities, shift operations, and other jobs that depend on good records. This version uses fictional administrative examples to explore that shared problem; it hasn't been validated for each of those settings.

[See a real output from a fictional example](EXAMPLE.md) · [Download the prototype](https://github.com/maxprof824-jpg/space-logging-coach/releases/tag/v2.3.0-poc)

## What it does

The coach organizes rough notes into five sections:

| Section | What the next reader needs to know |
|---|---|
| Situation | What happened, and when? |
| Impact | What was affected? |
| Agencies contacted (with initials) | Who was contacted? |
| Action | What has already been done? |
| Plan | What happens next? |

When information is missing, it asks follow-up questions. It can also suggest a possible impact, an action to consider, or a next step. Those suggestions are clearly labeled for confirmation, so a proposed action is kept separate from work reported as completed. The person writing the log reviews and edits the draft.

## How I built it

I designed the logging workflow and used AI-assisted development to build, train, and test the application.

- **Model:** Qwen3 4B, adapted with QLoRA—a memory-efficient way to teach an existing model a particular response style by training a small set of additional weights.
- **Training:** 480 synthetic examples and 48 validation examples. One training pass took about 12 minutes on my RTX 5060 Ti with 16 GB VRAM and 32 GB RAM.
- **Software:** Python, PyTorch, Hugging Face Transformers, PEFT, and bitsandbytes, with Gradio providing the interface.

The application also checks the output's structure and quoted evidence. Its behavior comes from both the fine-tuning and these additional checks. No real workplace logs were used for training.

## Try it

Download the **tester ZIP** from the [release page](https://github.com/maxprof824-jpg/space-logging-coach/releases/tag/v2.3.0-poc), extract it, and run **SETUP-WINDOWS.cmd**, followed by **RUN-DEMO.cmd**.

The setup targets Windows with a compatible NVIDIA GPU; my 16 GB GPU is the tested configuration. Allow roughly 25 GB of disk space and internet access for setup, including the approximately 8 GB base-model download. The model then runs locally. This GitHub page is a showcase, not a live AI service.

## What still needs work

The packaged code passes 43 automated checks, but the model can still miss details, put information in the wrong section, or suggest something unsupported. Every draft needs human review. Testing with representative users and a clean installation on another computer are still needed before broader use.

For the technical detail, see the [model and training notes](MODEL-CARD-V2.md), [evaluation results and limitations](reports/V2-ACCEPTANCE.md), [usage guide](V2-GUIDE.md), and [third-party attribution](THIRD-PARTY-NOTICES.md).
