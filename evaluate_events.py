"""Record synthetic event-group development runs; lexical checks are not accuracy.

Reserved examples are deliberately not selectable by this command. Keep those
for a separately specified candidate evaluation after training is frozen.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
import uuid

import coach
import core
import event_formatter
from evaluate_v2 import validate_result


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def label_key(label):return ' '.join(label.split()).casefold()


def inspect_case(row,result,variant,error=None):
    failures=validate_result(result)
    sections=result.get('sections',{})
    all_facts='\n'.join(fact['text'] for facts in sections.values() for fact in facts)
    expected=row['expectations']
    explicit=[event for event in result.get('event_results',[]) if event['grouping']=='explicit']
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
                selected=matches[0]['result'] if len(matches)==1 else {}
        text='\n'.join(fact['text'] for fact in selected.get('sections',{}).get(check['section'],[]))
        required=check.get('required_fragments',[])
        forbidden=check.get('forbidden_fragments',[])
        checks.append({'event_label':wanted_label,'section':check['section'],'applicable':applicable,
                       'required_fragments':required,'missing_fragments':[term for term in required if term.casefold() not in text.casefold()] if applicable else None,
                       'forbidden_hits':[term for term in forbidden if term.casefold() in text.casefold()] if applicable else None,
                       'global_missing_fragments':[term for term in required if term.casefold() not in all_facts.casefold()],
                       'review_note':check.get('review_note','')})
    quote_issues=[]
    for event in result.get('event_results',[]):
        for field,facts in event['result']['sections'].items():
            for item in facts:
                for quote in item['evidence']:
                    if quote not in event['source_text']:quote_issues.append(f"{event['label']}: {field} quote absent from that event")
        for item in event['result']['suggestions']:
            if any(quote not in event['source_text'] for quote in item['basis']):quote_issues.append(f"{event['label']}: suggestion basis absent from that event")
    return {'complete_structured_output':not error and not failures and result.get('status')!='incomplete_draft',
            'structure_errors':failures,'explicit_labels_match':labels_match,'explicit_event_count_match':event_count_match,
            'checks':checks,'event_quote_issues':quote_issues,
            'unassigned_passages':len(result.get('review_excerpts',[])),
            'suggestions':len(result.get('suggestions',[])),
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


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model-dir',type=Path,default=core.MODEL_DIR)
    parser.add_argument('--adapter',type=Path,default=core.ROOT/'runs/adapter-v2')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--legacy-per-domain',action='store_true',help='Also evaluate the first explicitly grouped development case per domain with the unchanged v2.4 pipeline.')
    parser.add_argument('--case',action='append',help='Select development case ids; repeat this option for multiple cases.')
    args=parser.parse_args()
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
    code_files=['event_formatter.py','event_groups.py','coach.py','coaching_pass.py','evidence_checks.py','source_coverage.py','core.py','evaluate_events.py']
    report={'runtime':'2.5','training_performed_by_this_command':False,'created_utc':datetime.now(timezone.utc).isoformat(),
            'dataset':'evaluation-v3/development.jsonl','dataset_sha256':digest(dataset),
            'code_sha256':{name:digest(core.ROOT/name) for name in code_files},
            'model_manifest_sha256':digest(core.ROOT/'model-manifest.json'),
            'adapter_sha256':digest(args.adapter/'adapter_model.safetensors'),
            'selected_ids':[row['id'] for row in rows],'legacy_ids':sorted(legacy_ids),
            'dataset_usage':'Newly authored synthetic development cases, used for runtime review. No human workflow validation or generalization claim. Reserved examples were not loaded.',
            'complete':False,'outputs':[]}
    with output.open('x',encoding='utf-8') as handle:json.dump(report,handle,indent=2)
    core.MODEL_DIR=args.model_dir
    import torch
    torch.set_num_threads(4)
    model,tokenizer=core.load_model(args.adapter)
    for row in rows:
        for variant in ['events','legacy'] if row['id'] in legacy_ids else ['events']:
            print('RUN',row['id'],variant,flush=True)
            started=time.monotonic();error=None;result={}
            try:
                function=event_formatter.process_note if variant=='events' else coach.process_note
                result=function(model,tokenizer,row['source_text'],row['mode'],row['assist'])
            except Exception as exc:
                error=f'{type(exc).__name__}: {coach._short_error(exc)}';result=getattr(exc,'result',{})
            checks=inspect_case(row,result,variant,error)
            record={'id':row['id'],'domain':row['domain'],'variant':variant,'mode':row['mode'],'assist':row['assist'],
                    'seconds':round(time.monotonic()-started,2),'source_text':row['source_text'],'error':error,
                    'result':result,'checks':checks}
            if not checks['structure_errors']:
                record['draft']=event_formatter.render_coached_log(result) if variant=='events' else coach.render_coached_log(result)
            report['outputs'].append(record);report['summary']=summarize(report)
            output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
            print('DONE',row['id'],variant,record['seconds'],'seconds; complete structure:',checks['complete_structured_output'],flush=True)
    report['complete']=True
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Evaluation complete:',json.dumps(report['summary']),flush=True)
    print('Saved report:',output.name,flush=True)


if __name__=='__main__':main()
