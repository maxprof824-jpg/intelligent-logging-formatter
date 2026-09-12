"""Isolate author-labeled incidents and retain original-source evidence locations.

Grouping follows explicit EVENT headings, not inferred incident identity. The v2
model's factual and suggestion checks run independently within each group. Flat
sections exist only for compatibility/counts; event_results is authoritative for
display and evaluation. Source locations establish matching text, not entailment.
"""
import copy
from bisect import bisect_right

import coach
from core import FIELDS, QUESTIONS
from event_groups import split_events, locate_evidence


def _empty_result(source, error, partial=None):
    partial = partial or {}
    excerpts=[]
    for line in source.splitlines():
        line=line.strip()
        while line:
            cut=len(line) if len(line)<=1200 else line.rfind(' ',0,1200)
            if cut<=0:cut=min(1200,len(line))
            text=line[:cut].strip()
            if text:excerpts.append({'text':text,'evidence':[text]})
            line=line[cut:].strip()
    return {'event_type':'other','sections':{field:[] for field in FIELDS},
            'suggestions':[],'review_excerpts':excerpts,'missing_fields':list(FIELDS),
            'questions':['Review these source passages and retry this event.'],
            'issues':[str(error),*partial.get('issues',[])], 'status':'incomplete_draft',
            'human_approval_required':True,'raw_outputs':partial.get('raw_outputs',[]),
            'coaching_outputs':partial.get('coaching_outputs',[]),
            'chunk_count':partial.get('chunk_count',0),'source_tokens':partial.get('source_tokens',0)}


def _source_evidence(event, result):
    """Reject generated evidence absent from original event text; expose all matches."""
    entries=[]
    ambiguity=False
    withheld=False
    previous_missing=set(result.get('missing_fields',[]))
    def mapped(item, kind, field, index, key):
        nonlocal ambiguity,withheld
        quotes=[{'quote':quote,**locate_evidence(event,quote)} for quote in item[key]]
        if any(not quote['candidates'] for quote in quotes):
            withheld=True
            result['issues'].append(f'{field.upper()}: a {kind} could not be linked to the original source and was withheld. Compare the original event notes.')
            return False
        ambiguity |= any(quote['ambiguous'] for quote in quotes)
        entries.append({'kind':kind,'section':field,'index':index,'text':item['text'],'quotes':quotes})
        return True
    for field in FIELDS:
        kept=[]
        for item in result['sections'][field]:
            if mapped(item,'fact',field,len(kept),'evidence'):kept.append(item)
        result['sections'][field]=kept
    kept=[]
    for item in result['suggestions']:
        if mapped(item,'suggestion',item['section'],len(kept),'basis'):kept.append(item)
    result['suggestions']=kept
    review=[]
    for item in result.get('review_excerpts',[]):
        quotes=[{'quote':quote,**locate_evidence(event,quote)} for quote in item['evidence']]
        if any(not quote['candidates'] for quote in quotes):
            withheld=True
            result['issues'].append('An unassigned excerpt could not be linked to the original source and was replaced with original event passages for review.')
            continue
        review.append(item)
    if withheld:
        existing={item['text'] for item in review}
        for item in _empty_result(event['source_text'],'')['review_excerpts']:
            if item['text'] not in existing:
                review.append(item)
                existing.add(item['text'])
    result['review_excerpts']=review
    for index,item in enumerate(review):
        # Review excerpts are visibly unassigned; never substitute a guessed match.
        quotes=[{'quote':quote,**locate_evidence(event,quote)} for quote in item['evidence']]
        ambiguity |= any(quote['ambiguous'] for quote in quotes)
        entries.append({'kind':'review_excerpt','section':'unassigned','index':index,'text':item['text'],'quotes':quotes})
    if ambiguity:
        result['issues'].append('Some quoted wording occurs more than once within this event. All matching source locations are shown; confirm the intended speaker and update.')
    result['missing_fields']=[field for field in FIELDS if not result['sections'][field]]
    result['questions'].extend(QUESTIONS[field] for field in result['missing_fields'] if field not in previous_missing)
    result['questions']=list(dict.fromkeys(result['questions']))
    if result['issues'] and result['status']!='incomplete_draft':result['status']='needs_confirmation'
    return entries


def process_note(model, tokenizer, source, mode='draft', assist=True, progress=None):
    if not isinstance(source,str) or not source.strip():raise ValueError('Enter a note to organize.')
    if mode not in ('draft','review'):raise ValueError('Select draft or review.')
    if not isinstance(assist,bool):raise ValueError('Assistance must be on or off.')
    if len(source)>120000:raise ValueError('This note is too large. Split it into related groups before submitting.')
    groups=split_events(source)
    # Match the parser's definition of a line, including CRLF, bare CR and
    # Unicode separators; LF counting alone mislabels valid source locations.
    line_starts=[0]
    line_offset=0
    for line in source.splitlines(keepends=True):
        line_offset+=len(line)
        if line_offset<len(source):line_starts.append(line_offset)
    events=[]
    for index,group in enumerate(groups):
        def report(stage,part,total):
            if progress:
                phase={'Organizing notes':0,'Preparing suggestions':.6,'Checking source coverage':.98}.get(stage,0)
                fraction=(index+phase+(part-1)/max(total,1)*(.35 if phase==.6 else .6 if phase==0 else 0))/len(groups)
                progress(min(.99,fraction),f"{group['label']} · {stage.lower()} · part {part}/{total}")
        if group['grouping']=='unassigned_context':
            result=_empty_result(group['source_text'],'Text before the first EVENT heading has no event assignment. Move it under the appropriate heading.')
            result.update(status='needs_confirmation',questions=['Which event does this opening context belong to?'])
        else:
            try:
                result=coach.process_note(model,tokenizer,group['source_text'],mode,assist,progress=report)
            except Exception as error:
                result=_empty_result(group['source_text'],f'{type(error).__name__}: {coach._short_error(error)}',getattr(error,'result',None))
        result=copy.deepcopy(result)
        evidence=_source_evidence(group,result)
        for entry in evidence:
            for quote in entry['quotes']:
                for candidate in quote['candidates']:
                    for span in candidate['segments']:
                        span['line_start']=bisect_right(line_starts,span['start'])
                        span['line_end']=bisect_right(line_starts,max(span['start'],span['end']-1))
        events.append({**group,'result':result,'source_evidence':evidence})
    sections={field:[fact for event in events for fact in event['result']['sections'][field]] for field in FIELDS}
    issues=[]
    if len(groups)==1 and groups[0]['grouping']=='unseparated':
        issues.append('No EVENT headings were supplied. These notes were processed together; if they describe different incidents, add EVENT: labels and prepare the draft again.')
    for event in events:
        issues.extend(f"{event['label']}: {issue}" for issue in event['result']['issues'])
    statuses=[event['result']['status'] for event in events]
    status='incomplete_draft' if 'incomplete_draft' in statuses else 'needs_confirmation'
    if progress:progress(1,'Event drafts ready for review')
    return {'event_type':'other','schema_version':'event-five-sections-2.5','status':status,
            'human_approval_required':True,'event_results':events,'event_count':len(events),
            'grouping':'explicit' if any(e['grouping']=='explicit' for e in events) else 'unseparated',
            'sections':sections,'suggestions':[s for e in events for s in e['result']['suggestions']],
            'missing_fields':[field for field in FIELDS if not sections[field]],
            'questions':[f"{e['label']}: {q}" for e in events for q in e['result']['questions']],
            'issues':issues,'review_excerpts':[f for e in events for f in e['result']['review_excerpts']],
            'raw_outputs':[raw for e in events for raw in e['result'].get('raw_outputs',[])],
            'coaching_outputs':[raw for e in events for raw in e['result'].get('coaching_outputs',[])],
            'chunk_count':sum(e['result'].get('chunk_count',0) for e in events),
            'source_tokens':sum(e['result'].get('source_tokens',0) for e in events),
            'source_characters':len(source),'offset_units':'Python Unicode code points, zero-based, end-exclusive',
            'mode':mode,'assist':assist}


def render_coached_log(result):
    if 'event_results' not in result:return coach.render_coached_log(result)
    parts=[]
    if result['status']=='incomplete_draft':parts.append('INCOMPLETE DRAFT — one or more events could not be processed.')
    for event in result['event_results']:
        heading=f"EVENT: {event['label']}"
        if event['grouping']=='unassigned_context':heading='UNASSIGNED OPENING CONTEXT — place under an event'
        parts.append(heading+'\n\n'+coach.render_coached_log(event['result']))
    return '\n\n'.join(parts)
