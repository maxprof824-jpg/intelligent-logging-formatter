"""Audit candidate-data construction and source overlap without model inference.

Reserved evaluation text is read only by deterministic integrity/overlap checks;
this command emits aggregate scores and IDs, never reserved source or targets.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import coach
from core import ROOT,FIELDS
from build_data_v3 import validate_target,validate_splits,identity_stripped


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
def grams(text):
    words=identity_stripped(text).split()
    return set(zip(words,words[1:],words[2:]))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Choose a new audit output; earlier reports are preserved.')
    splits={split:load(ROOT/'data-v3'/f'{split}.jsonl') for split in ('train','validation')}
    validate_splits(splits)
    screened=[]
    for split,rows in splits.items():
        for row in rows:
            validate_target(row)
            record=row['expected'] if row['task']=='main' else {'event_type':'other','sections':{f:[] for f in FIELDS},'suggestions':row['expected']['suggestions']}
            checked=coach.check_record(record,row['source_text'])
            if checked['sections']!=record['sections'] or checked['suggestions']!=record['suggestions']:
                screened.append({'split':split,'id':row['id'],'task':row['task'],'issues':checked['issues']})
    combined=[row for rows in splits.values() for row in rows]
    source_set={row['source_text'] for row in combined}
    normalized={identity_stripped(row['source_text']) for row in combined}
    training_grams=[grams(row['source_text']) for row in splits['train']]
    evaluation={}
    for split in ('development','reserved'):
        path=ROOT/'evaluation-v3'/f'{split}.jsonl'
        rows=load(path)
        overlap=[row['id'] for row in rows if row['source_text'] in source_set]
        normalized_overlap=[row['id'] for row in rows if identity_stripped(row['source_text']) in normalized]
        nearest=[]
        for row in rows:
            candidate=grams(row['source_text'])
            nearest.append(max((len(candidate&other)/len(candidate|other) if candidate|other else 1) for other in training_grams))
        evaluation[split]={'rows':len(rows),'sha256':digest(path),'exact_source_overlap_ids':overlap,
                           'identity_stripped_exact_overlap_ids':normalized_overlap,
                           'maximum_nearest_training_trigram_jaccard':round(max(nearest),6),
                           'cases_at_or_above_0_5':sum(score>=.5 for score in nearest)}
    report={'audit_code_sha256':digest(__file__),
            'candidate_data_sha256':{split:digest(ROOT/'data-v3'/f'{split}.jsonl') for split in splits},
            'candidate_rows':sum(map(len,splits.values())),'target_contract_checks':'passed',
            'runtime_screened_target_count':len(screened),'runtime_screened_targets':screened,
            'evaluation_overlap':evaluation,'model_inference_performed':False,
            'interpretation':'Construction and lexical overlap checks only. Runtime screens are heuristics, not a semantic teacher. A low overlap score does not prove independent reasoning patterns or useful trained behavior. Reserved source/targets were not exposed or used for training/inference.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as out:json.dump(report,out,indent=2)
    print(json.dumps(report,indent=2))
    if any(value['exact_source_overlap_ids'] or value['identity_stripped_exact_overlap_ids'] for value in evaluation.values()):raise SystemExit(1)


if __name__=='__main__':main()
