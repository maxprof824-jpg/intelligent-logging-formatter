"""Small, conservative screens for risky factual paraphrases.

This is not an entailment model. A passing sentence can still be inaccurate.
Flagged paraphrases should be withheld and their original evidence shown for
human placement; these checks must never rewrite a claim into a new fact.
"""
import re


_WORDS = re.compile(r"[a-z]+")
_SPACE = re.compile(r"\s+")
_STOP = set("a an the i we me us my our author operator person was were is are be been being has have had do does did to of for at on in with by and or but that this it its their his her they them he she as from then there said says stated states".split())
_FORMS = {
    "sent": "send", "sending": "send", "took": "take", "taken": "take",
    "done": "do", "made": "make", "got": "get", "told": "tell",
    "cancelled": "cancel", "canceled": "cancel", "cancelling": "cancel",
    "received": "receive", "receiving": "receive",
    "prepared": "prepare", "preparing": "prepare", "required": "require",
    "stopped": "stop", "stopping": "stop", "planned": "plan", "planning": "plan",
    "filed": "file", "filing": "file", "completed": "complete",
    "completing": "complete", "resolved": "resolve", "resolving": "resolve",
    "closed": "close", "closing": "close", "saved": "save", "saving": "save",
    "notified": "notify", "notifying": "notify", "delayed": "delay",
}
_QUALIFIER = re.compile(
    r"\b(?:unknown|unclear|uncertain|unconfirmed|unsure|maybe|possibly|reportedly|"
    r"apparently|allegedly|preliminary|estimated|may|might|could|"
    r"seems?|appears?|believes?|thinks?|not sure|not know|not known|not specify|not yet assessed|"
    r"not assessed|not yet confirmed|not confirmed|not verified|"
    r"no impact (?:was )?reported|has not been (?:assessed|confirmed|verified)|"
    r"can not (?:be identified|identify|tell)|could not tell)\b",
    re.I,
)
_PROSPECTIVE = re.compile(
    r"\b(?:planned|planning|plans? to|intends? to|intended|will|would|should|"
    r"must|needs? to|awaiting|pending|proposed|suggested|recommended|"
    r"(?:asked|requested|instructed)\b[^.;!?]{0,100}\bto|to be)\b", re.I,
)
_COMPLETED = re.compile(
    r"\b(?:sent|checked|contacted|called|emailed|filed|submitted|approved|received|"
    r"cancelled|canceled|resolved|completed|prepared|saved|updated|reviewed|"
    r"assigned|acknowledged|finished|closed|opened|confirmed|loaded|cleared|"
    r"escalated|restored|notified|done|taken)\b", re.I,
)
_IMPERATIVE = re.compile(
    r"^(?:confirm|ask|check|identify|record|contact|review|clarify|arrange|follow up|"
    r"await|wait|complete|update|send|save|prepare|file|notify|submit)\b", re.I,
)
_NEGATIVE = re.compile(r"\b(?:not|no|never|neither|nobody|nothing|without)\b", re.I)
_NEGATIVE_QUALIFIER = re.compile(
    r"\b(?:not (?:yet )?(?:sure|know|known|specify|assessed|confirmed|verified|clear|certain)|"
    r"has not been (?:assessed|confirmed|verified)|not (?:only|just))\b", re.I,
)
_BLANKET_ACTION = re.compile(
    r"\b(?:no (?:(?:other|further|additional) )?(?:actions?|work|steps?)\b"
    r"[^.;!?]{0,32}\b(?:taken|done|performed|carried out)|"
    r"nothing (?:else )?(?:was |has been )?(?:done|taken))\b", re.I,
)
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_REFERENCE = re.compile(r"(?<!\w)[A-Z][A-Z0-9]{0,24}(?:[-_][A-Z0-9]{1,24})+(?!\w)")
_CONTACT = re.compile(r"\b(?:contacts?|contacted|calls?|called|caller|replied|reply|"
                      r"responded|spoke|emailed|notified|initials?)\b", re.I)


def _normal(text):
    # Contractions need the same polarity treatment as their expanded forms.
    text = text.casefold().replace("\u2019", "'")
    text = re.sub(r"\b(can't|cannot)\b", "can not", text)
    text = re.sub(r"\bwon't\b", "will not", text)
    text = re.sub(r"n't\b", " not", text)
    return _SPACE.sub(" ", text).strip()


def _tokens(text):
    result = set()
    for word in _WORDS.findall(_normal(text)):
        if word in _STOP:
            continue
        if word in _FORMS:
            word = _FORMS[word]
        elif word.endswith("ing") and len(word) > 5:
            word = word[:-3]
        elif word.endswith("ed") and len(word) > 4:
            word = word[:-2]
        elif word.endswith("s") and len(word) > 3:
            word = word[:-1]
        result.add(word)
    return result


def _clauses(text):
    # Keep punctuation within a time/date out of this modest sentence splitter.
    # Coordinated statements often carry different polarity: "saved the file,
    # but did not send it" must not make saving look negated.
    return [part.strip() for part in re.split(
        r"[;!?\n]+|\.(?:\s|$)|\s+(?:but|and|while)\s+|(?=\s+without\b)|"
        r",\s+(?=(?:i|we|he|she|they|it|the author|the source)\b)", text
    ) if part.strip()]


def _negative(text):
    return bool(_NEGATIVE.search(_NEGATIVE_QUALIFIER.sub("", text)))


def _related(left, right):
    """Require overlap before comparing polarity in different source clauses."""
    a, b = _tokens(left), _tokens(right)
    overlap = a & b
    # One generic shared word such as 'action' cannot associate two events.
    return len(overlap) >= 2 and len(overlap) / max(1, min(len(a), len(b))) >= 0.6


def factual_risk(text, evidence_quotes):
    """Return a concise reason for a recognized risky paraphrase, or None.

    Call only after verifying that every evidence quote exists in the source.
    Exact whole-quote wording bypasses this paraphrase screen. Related clauses
    are compared for dropped uncertainty, reversed negation, and conversion of
    requested/planned work into completed work. Lexical matching is deliberately
    bounded and cannot establish general semantic correctness or event identity.
    """
    candidate = _normal(text)
    evidence = [_normal(quote) for quote in evidence_quotes]
    if any(candidate == quote for quote in evidence):
        return None
    # Compare dates as complete values: their component numbers can all be in
    # the source even after the model swaps the month and day.
    source_dates = {date for quote in evidence for date in _ISO_DATE.findall(quote)}
    if any(date not in source_dates for date in _ISO_DATE.findall(candidate)):
        return "a calendar date absent from its evidence"
    source_references = {reference.casefold() for quote in evidence_quotes
                         for reference in _REFERENCE.findall(quote)}
    if any(reference.casefold() not in source_references for reference in _REFERENCE.findall(text)):
        return "a reference identifier absent from its evidence"
    source_initials = {initial.casefold() for quote in evidence_quotes
                       for initial in re.findall(r"\(([A-Z]{2,4})\)", quote)}
    if _BLANKET_ACTION.search(candidate) and not any(_BLANKET_ACTION.search(q) for q in evidence):
        return "a blanket no-action claim absent from its evidence"
    # 'No impact reported' is not equivalent to a confirmed absence of impact.
    if (re.search(r"\bno impact\b", candidate)
            and not _QUALIFIER.search(candidate)
            and any(re.search(r"\bno impact (?:was )?reported\b", q) for q in evidence)):
        return "a confirmed absence of impact from an absence of impact reports"
    for claim in _clauses(candidate):
        comparable = [clause for quote in evidence for clause in _clauses(quote)
                      if _related(claim, clause)]
        if not comparable:
            continue
        # An exactly quoted complete clause is not a model-added paraphrase.
        if any(claim == clause for clause in comparable):
            continue
        # Prefer the closest lexical match instead of an unrelated clause with
        # one overlapping noun. Ties remain ambiguous and are reviewed below.
        scored = [(len(_tokens(claim) & _tokens(clause)) /
                   max(1, len(_tokens(claim) | _tokens(clause))), clause)
                  for clause in comparable]
        best = max(score for score, _ in scored)
        matched = [clause for score, clause in scored if score == best]
        if _CONTACT.search(claim):
            # Matching clauses avoid requiring every contact in a long source
            # quotation to appear in an unrelated situation sentence.
            initials = {initial for clause in matched
                        for initial in re.findall(r"\(([a-z]{2,4})\)", clause)
                        if initial in source_initials}
            if any(not re.search(r"\b" + re.escape(initial) + r"\b", claim)
                   for initial in initials):
                return "an omission of contact initials stated in its evidence"
        if any(_QUALIFIER.search(clause) for clause in matched) and not _QUALIFIER.search(claim):
            return "a loss of uncertainty stated in its evidence"
        if any(_negative(clause) != _negative(claim) for clause in matched):
            return "a change in negation compared with its evidence"
        if (any(_PROSPECTIVE.search(clause) for clause in matched)
                and not _PROSPECTIVE.search(claim) and not _QUALIFIER.search(claim)
                and not _IMPERATIVE.match(claim)
                and any(_tokens(verb.group()) & _tokens(clause)
                        for verb in _COMPLETED.finditer(claim) for clause in matched)):
            return "requested or planned work presented as completed"
    return None
