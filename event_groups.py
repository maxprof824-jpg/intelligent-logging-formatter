"""Explicit author-supplied event groups and exact source locations.

Only a complete line of the form ``EVENT: descriptive label`` starts a group.
Blank lines and timestamps do not establish event identity. Labels that match
after whitespace normalization and case folding group later updates together;
this is an author instruction, not a conclusion that the incidents are related.
Text before the first heading remains separate unassigned context. The parser
does not identify quoted blocks: a standalone EVENT heading inside pasted text
is still a heading, so authors should inspect the resulting groups.

Every offset is a half-open Python Unicode codepoint index, NOT a UTF-16 code
unit offset or a byte offset. Original body slices remain unchanged. A single
synthetic newline joins disjoint slices of the same event; that separator has
no original location. Evidence that crosses such a join maps to multiple source
spans, never to a fabricated continuous span. Multiple occurrences are returned
without choosing which occurrence the author meant. Locations establish text
presence, not entailment, correct chronology, or correct event attribution.
"""
import re


MAX_GROUPS = 8
MAX_LABEL_LENGTH = 100
_HEADING = re.compile(r"[ \t]*EVENT[ \t]*:[ \t]*(.*)", re.IGNORECASE)


def _new_group(index, label, grouping):
    return {
        "event_id": f"event-{index}",
        "label": label,
        "grouping": grouping,
        "source_text": "",
        "source_segments": [],
    }


def _append_segment(event, source, start, end):
    """Append one unchanged source slice, recording the join separately."""
    if event["source_segments"]:
        event["source_text"] += "\n"
    local_start = len(event["source_text"])
    event["source_text"] += source[start:end]
    event["source_segments"].append({
        "local_start": local_start,
        "local_end": len(event["source_text"]),
        "start": start,
        "end": end,
    })


def split_events(source):
    """Return at most eight explicit event groups with original source mappings.

    IDs follow first appearance, including an optional unassigned-context group.
    The first trimmed spelling of a repeated label is retained for display.
    Without headings, one ``unseparated`` group contains the complete input.
    Empty labels, empty heading bodies, oversized labels, and more than eight
    output groups raise ValueError with an actionable explanation.
    """
    if not isinstance(source, str):
        raise TypeError("Source notes must be text.")
    if not source.strip():
        raise ValueError("Enter notes before separating events.")

    headings, offset = [], 0
    for line_number, line in enumerate(source.splitlines(keepends=True), 1):
        match = _HEADING.fullmatch(line.rstrip("\r\n"))
        if match:
            label = match.group(1).strip()
            if not label:
                raise ValueError(f"EVENT heading on line {line_number} needs a descriptive label.")
            if len(label) > MAX_LABEL_LENGTH:
                raise ValueError(
                    f"EVENT label on line {line_number} exceeds {MAX_LABEL_LENGTH} characters; shorten it."
                )
            headings.append({
                "label": label,
                "key": " ".join(label.split()).casefold(),
                "start": offset,
                "body_start": offset + len(line),
                "line_number": line_number,
            })
        offset += len(line)

    if not headings:
        event = _new_group(1, "Supplied notes", "unseparated")
        _append_segment(event, source, 0, len(source))
        return [event]

    events, labels = [], {}

    def add_group(label, grouping):
        if len(events) >= MAX_GROUPS:
            raise ValueError(
                f"These notes contain more than {MAX_GROUPS} event groups, including any unassigned "
                "context. Split the submission into smaller sets or combine updates under the same EVENT label."
            )
        event = _new_group(len(events) + 1, label, grouping)
        events.append(event)
        return event

    preamble_end = headings[0]["start"]
    if source[:preamble_end].strip():
        preamble = add_group("Unassigned context", "unassigned_context")
        _append_segment(preamble, source, 0, preamble_end)

    for index, heading in enumerate(headings):
        start = heading["body_start"]
        end = headings[index + 1]["start"] if index + 1 < len(headings) else len(source)
        if not source[start:end].strip():
            raise ValueError(
                f"EVENT '{heading['label']}' on line {heading['line_number']} has no notes. "
                "Add event details below the heading or remove the empty heading."
            )
        if heading["key"] not in labels:
            labels[heading["key"]] = add_group(heading["label"], "explicit")
        _append_segment(labels[heading["key"]], source, start, end)
    return events


def locate_evidence(event, quote):
    """Locate every exact occurrence in one event, preserving discontinuity.

    Returns ``{"candidates": [{"segments": [{"start": int, "end": int}]}],
    "ambiguous": bool}``. An absent quote returns no candidates. Empty quotes
    are invalid; occurrences made entirely of synthetic join characters have
    no source location and are omitted. Overlapping occurrences are included.
    Event identity scopes the lookup: occurrences in other groups do not make
    an otherwise unique occurrence in this event ambiguous.
    """
    if not isinstance(quote, str):
        raise TypeError("Evidence quotes must be text.")
    if not quote:
        raise ValueError("Provide a nonempty evidence quote to locate.")
    text = event["source_text"]
    candidates, seen, search_start = [], set(), 0
    while True:
        local_start = text.find(quote, search_start)
        if local_start < 0:
            break
        local_end = local_start + len(quote)
        segments = []
        for mapping in event["source_segments"]:
            left = max(local_start, mapping["local_start"])
            right = min(local_end, mapping["local_end"])
            if left < right:
                segments.append({
                    "start": mapping["start"] + left - mapping["local_start"],
                    "end": mapping["start"] + right - mapping["local_start"],
                })
        key = tuple((segment["start"], segment["end"]) for segment in segments)
        if segments and key not in seen:
            candidates.append({"segments": segments})
            seen.add(key)
        search_start = local_start + 1
    return {"candidates": candidates, "ambiguous": len(candidates) > 1}
