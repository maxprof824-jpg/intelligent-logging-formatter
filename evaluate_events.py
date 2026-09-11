"""Record synthetic event-group development runs; lexical checks are not accuracy.

Reserved examples are deliberately not selectable by this command. Keep those
for a separately specified candidate evaluation after training is frozen.
"""
import argparse
from bisect import bisect_right
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
import uuid

import coach
import core
import event_formatter
from event_groups import split_events,locate_evidence
from evaluate_v2 import validate_result


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def label_key(label):return ' '.join(label.split()).casefold()


SCORING_FILES=('evaluate_events.py','evaluate_v2.py','event_groups.py','coach.py','core.py')
GENERATION_FILES=('event_formatter.py','event_groups.py','coach.py','coaching_pass.py','evidence_checks.py','source_coverage.py','core.py')


def scoring_fingerprints():return {name:digest(core.ROOT/name) for name in SCORING_FILES}


def cli_progress(case_id,variant):
    """Adapt the two existing progress contracts to flushed CLI stage updates."""
    if variant=='events':
        def event_progress(fraction,description):
            print('PROGRESS',case_id,variant,f'{fraction:.0%}',description,flush=True)
        return event_progress
    def legacy_progress(stage,part,total):
        print('PROGRESS',case_id,variant,stage,f'part {part}/{total}',flush=True)
    return legacy_progress


def _dictionary(value):return value if isinstance(value,dict) else {}
def _list(value):return value if isinstance(value,list) else []


def _facts(result,field=None):
    sections=_dictionary(_dictionary(result).get('sections'))
    fields=[field] if field else core.FIELDS
    return [fact for name in fields for fact in _list(sections.get(name))
            if isinstance(fact,dict) and isinstance(fact.get('text'),str)]


def _structure_errors(result):
    try:return validate_result(result)
    except Exception as error:return ['Malformed result structure: '+coach._short_error(error)]


def _expected_evidence(group,nested,source):
    """Rebuild location metadata from the original input, independently of saved spans."""
    starts=[0];offset=0
    for line in source.splitlines(keepends=True):
        offset+=len(line)
        if offset<len(source):starts.append(offset)
    entries=[];problems=[]
    def entry(item,kind,section,index,key):
        item=_dictionary(item)
        values=item.get(key)
        if not isinstance(values,list) or not values or any(not isinstance(q,str) or not q for q in values):
            problems.append(f'{section}: invalid {key} quote collection')
            return
        quotes=[]
        for quote in values:
            located=locate_evidence(group,quote)
            if not located['candidates']:problems.append(f'{section}: quote absent from that event')
            for candidate in located['candidates']:
                for span in candidate['segments']:
                    span['line_start']=bisect_right(starts,span['start'])
                    span['line_end']=bisect_right(starts,max(span['start'],span['end']-1))
            quotes.append({'quote':quote,**located})
        entries.append({'kind':kind,'section':section,'index':index,'text':item.get('text'),'quotes':quotes})
    sections=_dictionary(nested.get('sections'))
    for field in core.FIELDS:
        for index,item in enumerate(_list(sections.get(field))):entry(item,'fact',field,index,'evidence')
    for index,item in enumerate(_list(nested.get('suggestions'))):entry(item,'suggestion',_dictionary(item).get('section','invalid'),index,'basis')
    for index,item in enumerate(_list(nested.get('review_excerpts'))):entry(item,'review_excerpt','unassigned',index,'evidence')
    return entries,problems


def _event_validation(row,result):
    from jsonschema import validate
    errors=[];quote_issues=[]
    try:groups=split_events(row['source_text'])
    except Exception as error:return ['Cannot validate source groups: '+coach._short_error(error)],[],[]
    events=result.get('event_results')
    if not isinstance(events,list) or not events:
        return ['event_results must be a nonempty list for the event-aware variant.'],[],[]
    if len(events)!=len(groups):errors.append('event_results count differs from the original source groups.')
    if result.get('event_count')!=len(groups):errors.append('event_count differs from the original source groups.')
    valid_events=[]
    for index,event in enumerate(events):
        prefix=f'event_results[{index}]'
        if not isinstance(event,dict):errors.append(prefix+' is not an object.');continue
        valid_events.append(event)
        nested=_dictionary(event.get('result'))
        errors.extend(prefix+': '+error for error in _structure_errors(event.get('result')))
        if index>=len(groups):continue
        expected=groups[index]
        for key in ('event_id','label','grouping','source_text','source_segments'):
            if event.get(key)!=expected[key]:errors.append(prefix+f': {key} differs from original-source grouping metadata.')
        expected_evidence,problems=_expected_evidence(expected,nested,row['source_text'])
        quote_issues.extend(expected['label']+': '+problem for problem in problems)
        if event.get('source_evidence')!=expected_evidence:
            errors.append(prefix+': source_evidence does not match all original-source occurrences and spans.')
        if not isinstance(nested.get('review_excerpts'),list):errors.append(prefix+': review_excerpts is not a list.')
        for item_index,item in enumerate(_list(nested.get('review_excerpts'))):
            try:validate(item,coach.FACT)
            except Exception as error:errors.append(prefix+f': invalid review excerpt {item_index}: '+coach._short_error(error))
    return errors,quote_issues,valid_events


def inspect_case(row,result,variant,error=None):
    failures=_structure_errors(result)
    result=_dictionary(result)
    quote_issues=[];events=[]
    if variant=='events':
        nested_errors,quote_issues,events=_event_validation(row,result)
        failures.extend(nested_errors)
        all_facts='\n'.join(fact['text'] for event in events for fact in _facts(event.get('result')))
    else:all_facts='\n'.join(fact['text'] for fact in _facts(result))
    expected=row['expectations']
    explicit=[event for event in events if event.get('grouping')=='explicit' and isinstance(event.get('label'),str)]
    actual_labels=[label_key(event['label']) for event in explicit]
    expected_labels=[label_key(label) for label in expected.get('expected_event_labels',[])]
    labels_match=actual_labels==expected_labels if variant=='events' else None
    event_count_match=(len(explicit)==expected['event_count']) if variant=='events' and expected.get('event_count') is not None else None
    checks=[]
    for check in expected['checks']:
        wanted_label=check.get('event_label')
        selected=result
        applicable=True
        if wanted_label is not None:
            if variant!='events':applicable=False
            else:
                matches=[event for event in explicit if label_key(event['label'])==label_key(wanted_label)]
                selected=matches[0].get('result') if len(matches)==1 else {}
        if variant=='events' and wanted_label is None:
            text='\n'.join(fact['text'] for event in events for fact in _facts(event.get('result'),check['section']))
        else:text='\n'.join(fact['text'] for fact in _facts(selected,check['section']))
        required=check.get('required_fragments',[])
        forbidden=check.get('forbidden_fragments',[])
        checks.append({'event_label':wanted_label,'section':check['section'],'applicable':applicable,
                       'required_fragments':required,'missing_fragments':[term for term in required if term.casefold() not in text.casefold()] if applicable else None,
                       'forbidden_hits':[term for term in forbidden if term.casefold() in text.casefold()] if applicable else None,
                       'global_missing_fragments':[term for term in required if term.casefold() not in all_facts.casefold()],
                       'review_note':check.get('review_note','')})
    nested_incomplete=any(_dictionary(event.get('result')).get('status')=='incomplete_draft' for event in events)
    return {'complete_structured_output':not error and not failures and not quote_issues and not nested_incomplete and result.get('status')!='incomplete_draft',
            'structure_errors':failures,'explicit_labels_match':labels_match,'explicit_event_count_match':event_count_match,
            'checks':checks,'event_quote_issues':quote_issues,
            'unassigned_passages':sum(len(_list(_dictionary(event.get('result')).get('review_excerpts'))) for event in events) if variant=='events' else len(_list(result.get('review_excerpts'))),
            'suggestions':sum(len(_list(_dictionary(event.get('result')).get('suggestions'))) for event in events) if variant=='events' else len(_list(result.get('suggestions'))),
            'limitations':'Substring screens of factual entries only. Negation can create false positives, paraphrases can miss, and matching fragments do not establish support, speaker attribution, usefulness, or correct placement. Legacy flat output is not scored for event-specific placement.'}


def summarize(report):
    summary={}
    for variant in sorted({row['variant'] for row in report['outputs']}):
        rows=[row for row in report['outputs'] if row['variant']==variant]
        summary[variant]={'attempted':len(rows),'complete_structured_outputs':sum(row['checks']['complete_structured_output'] for row in rows),
                          'explicit_label_mismatches':sum(row['checks']['explicit_labels_match'] is False for row in rows),
                          'cases_with_event_quote_issues':sum(bool(row['checks']['event_quote_issues']) for row in rows),
                          'cases_with_missing_global_fragments':sum(any(check['global_missing_fragments'] for check in row['checks']['checks']) for row in rows),
                          'cases_with_missing_or_forbidden_scoped_fragments':sum(any(check['applicable'] and (check['missing_fragments'] or check['forbidden_hits']) for check in row['checks']['checks']) for row in rows),
                          'seconds':round(sum(row['seconds'] for row in rows),2)}
    return summary


def score_safely(row,result,variant,error=None):
    """A scoring bug must not erase completed inference or stop a batch run."""
    try:return inspect_case(row,result,variant,error),None
    except Exception as exception:
        problem=f'{type(exception).__name__}: {coach._short_error(exception)}'
        return {'complete_structured_output':False,'structure_errors':['Scoring failed: '+problem],
                'explicit_labels_match':None,'explicit_event_count_match':None,'checks':[],
                'event_quote_issues':[],'unassigned_passages':0,'suggestions':0,
                'limitations':'Scoring failed; this case has no lexical scores.'},problem


def rescore_saved_report(input_path,output_path,dataset_path=None):
    """Re-score a complete saved run without model loading or changing its outputs.

    The generation report, current development dataset hash, exact ordered case
    selection, source text, metadata and expected case/variant pairs must agree.
    Reserved data is never read. Existing reports are never overwritten.
    """
    input_path=Path(input_path);output_path=Path(output_path)
    dataset_path=Path(dataset_path) if dataset_path is not None else core.ROOT/'evaluation-v3/development.jsonl'
    if output_path.exists():raise FileExistsError('Choose a new output path; rescoring never overwrites an existing report.')
    payload=input_path.read_bytes()
    original=json.loads(payload)
    if not isinstance(original,dict) or original.get('complete') is not True:
        raise ValueError('Rescoring requires a complete saved generation report.')
    if original.get('dataset')!='evaluation-v3/development.jsonl':
        raise ValueError('Only the recorded development dataset can be rescored by this command.')
    dataset_bytes=dataset_path.read_bytes()
    if original.get('dataset_sha256')!=hashlib.sha256(dataset_bytes).hexdigest():
        raise ValueError('Development dataset SHA-256 differs from the saved run; no scores were changed.')
    rows=[json.loads(line) for line in dataset_bytes.decode('utf-8').splitlines()]
    by_id={row['id']:row for row in rows}
    if len(by_id)!=len(rows):raise ValueError('Development dataset contains duplicate case IDs.')
    selected=original.get('selected_ids')
    if (not isinstance(selected,list) or not selected or any(not isinstance(value,str) for value in selected)
            or len(set(selected))!=len(selected) or any(value not in by_id for value in selected)):
        raise ValueError('Saved selected_ids must contain unique IDs from the unchanged development dataset.')
    if selected!=[row['id'] for row in rows if row['id'] in set(selected)]:
        raise ValueError('Saved selected_ids order differs from the frozen development selection.')
    legacy_ids=original.get('legacy_ids',[])
    if (not isinstance(legacy_ids,list) or any(not isinstance(value,str) for value in legacy_ids)
            or len(set(legacy_ids))!=len(legacy_ids) or not set(legacy_ids).issubset(selected)):
        raise ValueError('Saved legacy_ids do not match the recorded selection.')
    expected_pairs=[(case_id,variant) for case_id in selected
                    for variant in (['events','legacy'] if case_id in legacy_ids else ['events'])]
    outputs=original.get('outputs')
    if not isinstance(outputs,list) or any(not isinstance(item,dict) for item in outputs):
        raise ValueError('Saved outputs must be a list of case records.')
    if [(item.get('id'),item.get('variant')) for item in outputs]!=expected_pairs:
        raise ValueError('Saved output IDs/variants do not exactly match the selected cases; no rescoring was performed.')
    for item in outputs:
        row=by_id[item['id']]
        for field in ('source_text','domain','mode','assist'):
            if item.get(field)!=row[field]:
                raise ValueError(f"Saved {item['id']} {field} differs from the unchanged development case.")
    recorded_hashes=original.get('generation_code_sha256',original.get('code_sha256'))
    if not isinstance(recorded_hashes,dict) or not recorded_hashes:
        raise ValueError('The saved report has no recorded generation code fingerprints.')
    report=copy.deepcopy(original)
    report.update(scoring_only_revision=True,inference_performed_by_this_command=False,
                  training_performed_by_this_command=False,source_report_name=input_path.name,
                  source_report_sha256=hashlib.sha256(payload).hexdigest(),
                  recorded_generation_code_sha256=copy.deepcopy(recorded_hashes),
                  prior_scoring_code_sha256=copy.deepcopy(original.get('scoring_code_sha256',original.get('code_sha256',{}))),
                  scoring_code_sha256=scoring_fingerprints(),
                  rescored_utc=datetime.now(timezone.utc).isoformat(),generation_run_complete=True,complete=False)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with output_path.open('x',encoding='utf-8') as handle:json.dump(report,handle,indent=2,ensure_ascii=False)
    for item in report['outputs']:
        item.setdefault('generation_checks',copy.deepcopy(item.get('checks')))
        item['checks'],scoring_error=score_safely(by_id[item['id']],item.get('result'),item['variant'],item.get('error'))
        if scoring_error:item['scoring_error']=scoring_error
        else:item.pop('scoring_error',None)
    report['summary']=summarize(report);report['complete']=True
    output_path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model-dir',type=Path,default=core.MODEL_DIR)
    parser.add_argument('--adapter',type=Path,default=core.ROOT/'runs/adapter-v2')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--rescore',type=Path,help='Re-score a complete saved development run without loading a model; requires a new --output path.')
    parser.add_argument('--legacy-per-domain',action='store_true',help='Also evaluate the first explicitly grouped development case per domain with the unchanged v2.4 pipeline.')
    parser.add_argument('--case',action='append',help='Select development case ids; repeat this option for multiple cases.')
    args=parser.parse_args()
    if args.rescore:
        if not args.output:parser.error('--rescore requires a new --output path.')
        if args.case or args.legacy_per_domain:parser.error('--rescore uses the exact case/variant selection already recorded in the input report.')
        report=rescore_saved_report(args.rescore,args.output)
        print('Scoring-only revision complete:',json.dumps(report['summary']),flush=True)
        print('Saved report:',args.output.name,flush=True)
        return
    dataset=core.ROOT/'evaluation-v3/development.jsonl'
    rows=[json.loads(line) for line in dataset.read_text(encoding='utf-8').splitlines()]
    if args.case:
        unknown=set(args.case)-{row['id'] for row in rows}
        if unknown:raise SystemExit('Unknown development case ids: '+', '.join(sorted(unknown)))
        rows=[row for row in rows if row['id'] in args.case]
    legacy_ids=set();domains=set()
    if args.legacy_per_domain:
        for row in rows:
            if row['expectations'].get('expected_event_labels') and row['domain'] not in domains:
                legacy_ids.add(row['id']);domains.add(row['domain'])
    output=args.output or core.ROOT/'reports'/('events-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    code_files=list(dict.fromkeys((*GENERATION_FILES,*SCORING_FILES)))
    report={'runtime':'2.5','training_performed_by_this_command':False,'created_utc':datetime.now(timezone.utc).isoformat(),
            'dataset':'evaluation-v3/development.jsonl','dataset_sha256':digest(dataset),
             'code_sha256':{name:digest(core.ROOT/name) for name in code_files},
             'generation_code_sha256':{name:digest(core.ROOT/name) for name in GENERATION_FILES},
             'scoring_code_sha256':scoring_fingerprints(),'inference_performed_by_this_command':True,
             'model_manifest_sha256':digest(core.ROOT/'model-manifest.json'),
             'adapter_sha256':digest(args.adapter/'adapter_model.safetensors'),
             'adapter_config_sha256':digest(args.adapter/'adapter_config.json'),
             'model_metadata_sha256':{name:digest(args.model_dir/name) for name in ('config.json','tokenizer_config.json','tokenizer.json') if (args.model_dir/name).is_file()},
            'selected_ids':[row['id'] for row in rows],'legacy_ids':sorted(legacy_ids),
            'dataset_usage':'Newly authored synthetic development cases, used for runtime review. No human workflow validation or generalization claim. Reserved examples were not loaded.',
            'complete':False,'outputs':[]}
    with output.open('x',encoding='utf-8') as handle:json.dump(report,handle,indent=2)
    core.MODEL_DIR=args.model_dir
    import torch
    torch.set_num_threads(4)
    try:model,tokenizer=core.load_model(args.adapter)
    except Exception as exception:
        report['run_error']=f'Model loading failed: {type(exception).__name__}: {coach._short_error(exception)}'
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        raise
    for row in rows:
        for variant in ['events','legacy'] if row['id'] in legacy_ids else ['events']:
            print('RUN',row['id'],variant,flush=True)
            started=time.monotonic();error=None;result={}
            try:
                function=event_formatter.process_note if variant=='events' else coach.process_note
                result=function(model,tokenizer,row['source_text'],row['mode'],row['assist'],
                                progress=cli_progress(row['id'],variant))
            except Exception as exc:
                error=f'{type(exc).__name__}: {coach._short_error(exc)}';result=getattr(exc,'result',{})
            checks,scoring_error=score_safely(row,result,variant,error)
            record={'id':row['id'],'domain':row['domain'],'variant':variant,'mode':row['mode'],'assist':row['assist'],
                    'seconds':round(time.monotonic()-started,2),'source_text':row['source_text'],'error':error,
                     'result':result,'checks':checks}
            if scoring_error:record['scoring_error']=scoring_error
            if not checks['structure_errors']:
                try:record['draft']=event_formatter.render_coached_log(result) if variant=='events' else coach.render_coached_log(result)
                except Exception as exception:record['rendering_error']=f'{type(exception).__name__}: {coach._short_error(exception)}'
            report['outputs'].append(record);report['summary']=summarize(report)
            output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
            print('DONE',row['id'],variant,record['seconds'],'seconds; complete structure:',checks['complete_structured_output'],flush=True)
    report['complete']=True
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Evaluation complete:',json.dumps(report['summary']),flush=True)
    print('Saved report:',output.name,flush=True)


if __name__=='__main__':main()
