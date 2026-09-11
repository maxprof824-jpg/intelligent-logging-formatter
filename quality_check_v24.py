"""Fresh synthetic model smoke cases. No operational accuracy claim or training use."""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import core
import coach


CASES = [
    {'id':'mixed-request-and-event','mode':'draft','assist':True,
     'source':'Need a clear log; 2026-09-11 10:30Z Records Desk (KR) confirmed receipt of FORM-27. I saved the confirmation. No follow-up has been agreed.',
     'review':'Preserve the event after the writing request. Do not invent an agreed plan.'},
    {'id':'planned-not-completed','mode':'review','assist':True,
     'source':'Fictional office note, 2026-09-11 UTC. At 09:00 Support (LM) said they would check the missing attachment on REQ-12. At 09:20 LM said the check had not started. The document was not sent. Nobody has assessed the effect on the meeting. I saved a copy of the request.',
     'review':'The check is pending and the document was not sent. Preserve who said what and both times.'},
    {'id':'unanchored-details','mode':'draft','assist':False,
     'source':'Fictional reception note. The visitor list would not open. I kept the paper register beside the desk. Nobody was contacted. I did not change the computer settings. Whether arrivals were delayed is unknown. There is no agreed follow-up owner.',
     'review':'Keep the paper register, explicit no contact, no settings change, unknown impact, and missing owner visible despite no date/reference anchors.'},
    {'id':'complete-record-control','mode':'review','assist':True,
     'source':'Fictional office record, 2026-09-11 UTC. 12:02 Room B printer displayed PAPER EMPTY. 12:04 I loaded one ream of office paper. 12:06 the queued handouts printed and the instructor confirmed class began on time with all handouts. At 12:08 Office Support (NH) acknowledged the paper use. NH agreed to update the stock sheet by 15:00 today. No additional action was needed for the printing issue.',
     'review':'Preserve completed printing, no class delay, NH and the supplied future stock update. Do not manufacture an additional problem.'},
]


def run():
    p=argparse.ArgumentParser()
    p.add_argument('--model-dir',type=Path,default=core.MODEL_DIR)
    p.add_argument('--adapter',type=Path,default=core.ROOT/'runs/adapter-v2')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--compare-base',action='store_true')
    p.add_argument('--include-long',action='store_true')
    p.add_argument('--only',help='Run one case by its id, preserving other recorded runs.')
    args=p.parse_args()
    if args.output.exists(): raise SystemExit('Choose a new output path; existing evaluations are preserved.')
    core.MODEL_DIR=args.model_dir
    model,tokenizer=core.load_model(args.adapter)
    cases=list(CASES)
    if args.include_long:
        paragraphs=[]
        i=0
        while len(tokenizer('\n'.join(paragraphs),add_special_tokens=False)['input_ids'])<=2300:
            paragraphs.append(f'Fictional inventory note {i}: the classroom supply sheet lists box DEMO-{i+100}. The label was readable, but no physical count or restock was confirmed. The note remains open for later review.')
            i+=1
        cases.append({'id':'actual-default-multichunk','mode':'draft','assist':False,'source':'\n'.join(paragraphs),
                      'review':'A deliberately dense fictional inventory note exceeding the default 2200-token chunk boundary. Check incomplete processing, reference retention, and excessive unassigned text; this is not a realistic-user accuracy benchmark.'})
    if args.only:
        cases=[case for case in cases if case['id']==args.only]
        if not cases: raise SystemExit('Unknown case id; use --include-long to enable the dense-note case.')
    code_files=['coach.py','coaching_pass.py','evidence_checks.py','source_coverage.py','core.py','quality_check_v24.py']
    meta={'runtime':'2.4','weights_changed':False,'created_utc':datetime.now(timezone.utc).isoformat(),
          'code_sha256':{n:hashlib.sha256((core.ROOT/n).read_bytes()).hexdigest() for n in code_files},
          'adapter_sha256':hashlib.sha256((args.adapter/'adapter_model.safetensors').read_bytes()).hexdigest(),
          'limitations':'Small synthetic development smoke set authored for this review; not an untouched holdout or semantic accuracy score.', 'outputs':[],'complete':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def save(): args.output.write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    save()
    for case in cases:
        variants=['adapter','base'] if args.compare_base and case['id']!='actual-default-multichunk' else ['adapter']
        for variant in variants:
            started=time.monotonic(); row={**case,'variant':variant}
            print('RUN',case['id'],variant,flush=True)
            try:
                if variant=='base':
                    with model.disable_adapter(): result=coach.process_note(model,tokenizer,case['source'],case['mode'],case['assist'])
                else: result=coach.process_note(model,tokenizer,case['source'],case['mode'],case['assist'])
                row.update(result=result,draft=coach.render_coached_log(result),error=None)
            except Exception as error:
                row.update(result=getattr(error,'result',{}),error=f'{type(error).__name__}: {error}')
            row['seconds']=round(time.monotonic()-started,2)
            meta['outputs'].append(row); save()
            print('DONE',case['id'],variant,row['seconds'],'seconds',row['error'] or row['result']['status'],flush=True)
    meta['complete']=True; save()
    print('Model checks complete.',flush=True)


if __name__=='__main__': run()
