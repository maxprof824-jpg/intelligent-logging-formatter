"""Local intelligent logging formatter demo: source details and suggestions stay distinct."""
import argparse
import html
import threading

from core import ROOT, load_model
from event_formatter import process_note, render_coached_log


EXAMPLES = [
    [
        "2026-09-11 09:15 UTC training terminal T-7 froze, error DEMO-42. "
        "screen stopped updating. happened during the practice session. "
        "09:22 UTC still showing the same error. don't know what happened next."
    ],
    [
        "PM paperwork came in for the training room printer exterior cleaning, "
        "2026-09-11 11:05 UTC. form says completed but signature blank. "
        "11:12 UTC spoke to Training Support (AB), they said they'd check. "
        "I filed a copy under DEMO-PM-18. unsure if work really done."
    ],
    [
        "EVENT: Briefing room change\n2026-09-11 UTC / 13:10 Training Coordination (JK) called: fictional "
        "briefing moved from room A to room B. I updated the practice calendar "
        "at 13:14.\n\nEVENT: Room C projector\n2026-09-11 UTC / 13:25 Training Support (LM) called about a projector "
        "issue in room C; picture flickering, no fix confirmed.\n\nEVENT: Briefing room change\n"
        "2026-09-11 UTC / 13:40 JK called back, room B now confirmed. At 13:45 I sent the "
        "updated briefing location to the fictional participants. Need the "
        "projector issue kept separate from the room change."
    ],
]


def _plain_markdown(value):
    """Display model-written questions as text, without links or markup."""
    text = html.escape(str(value))
    for character in "\\`*_{}[]()#+-.!|":
        text = text.replace(character, "\\" + character)
    return text.replace("\n", " ")


def format_followup(result):
    questions = result.get("questions") or []
    issues = result.get("issues") or []
    parts = []
    if questions:
        parts.append("**Questions to complete your log**\n\n" + "\n".join(
            f"{index}. {_plain_markdown(question)}"
            for index, question in enumerate(questions, 1)
        ))
    else:
        parts.append("No additional questions were generated. Check the draft against your notes.")
    if issues:
        parts.append("**Details to check**\n\n" + "\n".join(
            "- " + _plain_markdown(issue) for issue in issues
        ))
    return "\n\n".join(parts)


def format_raw(raw_outputs, coaching_outputs=None):
    def format_group(outputs, label):
        if isinstance(outputs, str):
            outputs = [outputs] if outputs else []
        return "\n\n".join(
            f"{label} {index}\n{output}"
            for index, output in enumerate(outputs or [], 1)
        )
    groups = [format_group(raw_outputs, "EXTRACTION RESPONSE"),
              format_group(coaching_outputs, "ADDITIONAL SUGGESTION RESPONSE")]
    return "\n\n".join(group for group in groups if group)


def evidence_rows(result):
    """A direct, readable comparison for human review; quotes are not correctness scores."""
    if 'event_results' in result:
        rows=[]
        for event in result['event_results']:
            for entry in event['source_evidence']:
                if entry['kind']=='review_excerpt':continue
                locations=[]
                for quote in entry['quotes']:
                    candidates=quote['candidates']
                    label='Multiple possible matches: ' if quote['ambiguous'] else ''
                    label+=' | '.join(', '.join(f"lines {span['line_start']}–{span['line_end']}" for span in candidate['segments']) for candidate in candidates)
                    locations.append(label or 'No original source match')
                field=entry['section'].replace('_',' ').upper()
                if entry['kind']=='suggestion':field+=' (SUGGESTION — CONFIRM)'
                rows.append([event['label'],field,entry['text'],'\n\n'.join(q['quote'] for q in entry['quotes']),'\n\n'.join(locations)])
        return rows
    return [['Supplied notes',field.replace('_', ' ').upper(), fact['text'], '\n\n'.join(fact['evidence']),'Not recorded in this saved result']
            for field, facts in result.get('sections', {}).items() for fact in facts]


def draft_status(result):
    count = sum(len(facts) for facts in result.get('sections', {}).values())
    if result.get('status') == 'incomplete_draft':
        if not count:return 'Draft not completed: no supported entries were organized. Your source notes remain available for review.'
        return 'Partial draft: some notes could not be processed. Check the source and review details.'
    if not count:
        return 'No supported entries were organized. Review the preserved source passages and try a shorter related group.'
    unassigned = len(result.get('review_excerpts', []))
    message = f'{count} draft entries prepared for review.'
    if result.get('event_count',0)>1:message+=f" Kept in {result['event_count']} separate groups."
    if unassigned:
        message += f' {unassigned} source passage(s) still need placement or checking.'
    return message + ' Confirm suggestions before using them.'


def build_demo(model, tokenizer, model_name):
    """Build the UI around an already-loaded model; inference is serialized."""
    import gradio as gr

    inference_lock = threading.Lock()

    def process(source, mode, assist, progress=gr.Progress()):
        result = {}
        try:
            if not source or not source.strip():
                return "", "Enter fictional notes above to prepare a draft.", "", {}, "", []
            progress(0, desc="Organizing notes and checking suggested next steps…" if assist else "Organizing your notes…")
            with inference_lock:
                def update_progress(fraction, description):
                    progress(fraction, desc=description)
                result = process_note(model, tokenizer, source, mode=mode, assist=assist, progress=update_progress)
            draft = render_coached_log(result)
            followup = format_followup(result)
            status = draft_status(result)
            long_events = [event for event in result.get('event_results',[]) if event['result'].get('chunk_count',0)>1]
            if long_events:
                status += f" {len(long_events)} event group(s) needed multiple processing parts; check their full sequence."
            diagnostics = {key: value for key, value in result.items()
                           if key not in ("raw_outputs", "coaching_outputs")}
            progress(1, desc="Partial draft ready" if result.get("status") == "incomplete_draft" else "Draft ready")
            return draft, followup, status, diagnostics, format_raw(result.get("raw_outputs"), result.get("coaching_outputs")), evidence_rows(result)
        except Exception as error:
            # If the extraction layer attaches partial output, retain it for diagnosis.
            partial_result = getattr(error, "result", None)
            if isinstance(partial_result, dict):
                result = partial_result
            raw_outputs = result.get("raw_outputs") or getattr(error, "raw_outputs", [])
            coaching_outputs = result.get("coaching_outputs") or getattr(error, "coaching_outputs", [])
            diagnostics = {key: value for key, value in result.items()
                           if key not in ("raw_outputs", "coaching_outputs")}
            diagnostics["error"] = str(error)
            message = "Could not finish this draft. Your notes remain above."
            if isinstance(error, ValueError):
                message += " " + _plain_markdown(str(error))
            else:
                message += " Try a shorter section, or check the details in the accordion below."
            return "", message, "Draft not completed.", diagnostics, format_raw(raw_outputs, coaching_outputs), []

    with gr.Blocks(
        title="Intelligent Logging Formatter",
        analytics_enabled=False,
        theme=gr.themes.Soft(),
        css=".gradio-container {max-width: 1200px !important;} #draft textarea {line-height: 1.6;}",
    ) as demo:
        gr.Markdown(
            "# Intelligent Logging Formatter\n"
            "Turn messy notes into a standard draft, find missing details, and explore possible next steps. "
            "**Synthetic proof of concept · fictional administrative notes only.**\n\n"
            "Reported details from your notes and inferred suggestions appear separately in the draft. "
            "**Possible impacts, recommended actions, and suggested plans need your confirmation; "
            "they are not recorded actions.**"
        )
        with gr.Row():
            mode = gr.Radio(
                choices=[("Draft from notes", "draft"), ("Review an existing log", "review")],
                value="draft", label="Task", scale=1,
            )
            assist = gr.Checkbox(
                value=True, label="Include possible impacts and suggested next steps", scale=2,
            )
        gr.Markdown(
            "For different incidents, start each group with **EVENT: a short name** on its own line. "
            "Repeat the same heading for later updates to that event. Put its date and context inside that group. "
            "Without headings, notes are processed together. Long notes and optional suggestions take more time."
        )
        source = gr.Textbox(
            lines=12, max_lines=24, label="Fictional notes or existing log",
            placeholder="Paste rough notes, several updates, or an existing draft. Include any times and uncertainties you have.",
        )
        gr.Examples(
            examples=EXAMPLES, inputs=[source],
            label="Try an example", example_labels=[
                "Terminal issue with missing details", "Uncertain PM paperwork", "Two events with later updates",
            ],
        )
        with gr.Row():
            button = gr.Button("Prepare draft and follow-up questions", variant="primary", scale=3)
            clear = gr.Button("Clear", scale=1)
        status = gr.Markdown()
        draft = gr.Textbox(
            lines=24, max_lines=45, label="Standardized draft · edit and confirm before use",
            interactive=True, show_copy_button=True, elem_id="draft",
        )
        followup = gr.Markdown()
        with gr.Accordion('Compare draft entries with your source', open=False):
            gr.Markdown('Check meaning, uncertainty, and who did what—not just matching words. '
                        'These quotes relate to the generated draft; check them again after editing. '
                        'Line numbers refer to your original notes. '
                        'Multiple matches are shown when the wording repeats; the intended occurrence still needs confirmation.')
            evidence = gr.Dataframe(headers=['Event', 'Section', 'Generated entry', 'Quoted source', 'Source locations'],
                                    datatype=['str']*5, type='array', interactive=False, wrap=True)
        gr.Markdown(
            "Add answers to your notes and prepare the draft again, or edit the draft above. "
            "Keep suggestions labeled until you confirm them."
        )
        with gr.Accordion("Source evidence and processing details", open=False):
            checked = gr.JSON(label="Source details, suggestions, and checks")
            raw = gr.Textbox(lines=8, max_lines=20, label="Raw extraction and suggestion responses", interactive=False)
        gr.Markdown(f"Running locally · {model_name}. Processing stays on this computer.")
        button.click(
            process, inputs=[source, mode, assist], outputs=[draft, followup, status, checked, raw, evidence],
            concurrency_limit=1, concurrency_id="logging-model", api_name="process_note",
        )
        clear.click(
            lambda: ("", "", "", "", {}, "", []),
            outputs=[source, draft, followup, status, checked, raw, evidence], queue=False,
        )
    return demo.queue(default_concurrency_limit=1)


def main():
    parser = argparse.ArgumentParser(description="Run the local intelligent logging formatter demo.")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--base", action="store_true", help="Use the original model without an adapter")
    selection.add_argument("--adapter", help="Path to a trained adapter directory, relative to the project or absolute")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--no-browser", action="store_true", help="Start without opening a browser")
    args = parser.parse_args()
    import torch
    torch.set_num_threads(4)
    adapter = None if args.base else ROOT / (args.adapter or "runs/adapter-v2")
    if adapter and not (adapter / "adapter_model.safetensors").exists():
        raise RuntimeError(
            "The v2 adapter is not ready. Finish v2 training, or run python app_v2.py --base to use the base model."
        )
    model, tokenizer = load_model(adapter)
    model_name = "Original base model · formatter runtime 2.5" if args.base else f"Local adapter: {adapter.name} · formatter runtime 2.5"
    demo = build_demo(model, tokenizer, model_name)
    demo.launch(
        server_name="127.0.0.1", server_port=args.port,
        share=False, inbrowser=not args.no_browser, show_error=False,
    )


if __name__ == "__main__":
    main()
