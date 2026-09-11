"""Recheck saved model responses with current filters; no model inference occurs."""
import argparse
import hashlib
import json
from pathlib import Path
import coach
from source_coverage import add_source_coverage
from core import FIELDS, ROOT
from jsonschema import ValidationError


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,default=ROOT/'reports/adapter-v2-acceptance.jsonl')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists(): raise SystemExit('Choose a new output path.')
    rows=[]
    for line in args.input.read_text(encoding='utf-8').splitlines():
        original=json.loads(line); source,_=coach.clean_source(original['source_text'])
        records=[]
        invalid_responses = 0
        for raw in original['raw_result'].get('raw_outputs',[]):
            try: records.append(coach.parse_coached_output(raw))
            except (ValueError, ValidationError):
                invalid_responses += 1
        for raw in original['raw_result'].get('coaching_outputs',[]):
            extra=json.loads(raw)
            records.append({'event_type':'other','sections':{f:[] for f in FIELDS},'suggestions':extra['suggestions']})
        result=add_source_coverage(coach.assemble_results(records,source),source)
        oldcount=sum(len(v) for v in original['raw_result']['sections'].values())
        rows.append({'id':original['id'],'original_fact_entries':oldcount,
                     'invalid_saved_responses':invalid_responses,
                     'current_fact_entries':sum(len(v) for v in result['sections'].values()),
                     'result':result,'draft':coach.render_coached_log(result)})
    report={'description':'Replay of saved v2.1 model responses with current postprocessing; no fresh inference, helper regeneration, or model accuracy claim.',
            'runtime':'2.4','input_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(),
            'code_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                           ['replay_saved_outputs.py','coach.py','coaching_pass.py','evidence_checks.py','source_coverage.py','core.py']},
            'cases':rows}
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Replayed',len(rows),'saved cases without inference.')


if __name__=='__main__':main()
