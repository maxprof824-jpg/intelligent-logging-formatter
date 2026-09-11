"""Measure a candidate-data forward/backward pass without updating or saving weights.

This is a memory/gradient preflight, not a training run or an accuracy evaluation.
Two zero buffers per trainable parameter approximate AdamW state memory. There
are no optimizer steps. A full training run can still have higher peaks.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time

import core


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_gradients(named_parameters,torch):
    """Require gradients for every trainable adapter parameter, allowing zeros.

    A freshly initialized LoRA branch can legitimately give some zero gradients;
    at least one gradient must be nonzero, and every gradient must be finite.
    This helper also accepts CPU parameters for a GPU-free regression check.
    """
    if not named_parameters:raise RuntimeError('No trainable LoRA parameters were found.')
    missing=[name for name,parameter in named_parameters if parameter.grad is None]
    if missing:raise RuntimeError(f'{len(missing)} trainable LoRA parameter(s) have no gradient: '+', '.join(missing[:3]))
    gradients=[parameter.grad for _,parameter in named_parameters]
    if not all(torch.isfinite(gradient).all().item() for gradient in gradients):
        raise RuntimeError('Nonfinite LoRA gradients in memory preflight.')
    nonzero=sum(bool(torch.count_nonzero(gradient).item()) for gradient in gradients)
    if not nonzero:raise RuntimeError('All LoRA gradients were zero.')
    return {'parameters_with_gradients':len(gradients),'parameters_with_nonzero_gradients':nonzero}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model-dir',type=Path,default=core.MODEL_DIR)
    parser.add_argument('--data-dir',type=Path,default=core.ROOT/'data-v3')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'optimizer_steps':0,'weights_saved':False,
             'purpose':'Longest candidate training example: completion-only forward/backward with memory reserved for AdamW states; not full training.',
             'preflight_code_sha256':digest(__file__),'core_sha256':digest(core.ROOT/'core.py'),
             'training_code_sha256':digest(core.ROOT/'train.py'),
             'training_data_sha256':digest(args.data_dir/'train.jsonl'),
             'model_identifier':args.model_dir.name,
             'model_metadata_sha256':{name:digest(args.model_dir/name) for name in
                                     ('config.json','tokenizer_config.json','tokenizer.json','model.safetensors.index.json')
                                     if (args.model_dir/name).is_file()},
             'training_settings':{'quantization':'4-bit NF4 with double quantization','compute_dtype':'bfloat16',
                                  'rank':16,'alpha':32,'dropout':.05,'target_modules':'all-linear',
                                  'max_sequence_length':4096,'micro_batch':1,'gradient_checkpointing':True,
                                  'use_reentrant':False,'seed':42,'allow_tf32':True,
                                  'optimizer_state_approximation':'Two zeros_like buffers for every trainable parameter; no optimizer execution.',
                                  'gradient_accumulation_executed':False},
             'status':'started','complete':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as out:json.dump(report,out,indent=2)
    torch=None
    measurement_scope='model setup, batch and approximate optimizer-state allocation'
    try:
        import torch
        from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
        from transformers import set_seed
        torch.set_num_threads(4);set_seed(42)
        torch.backends.cuda.matmul.allow_tf32=True
        core.MODEL_DIR=args.model_dir
        model,tokenizer=core.load_model(training=True)
        report.update(gpu=torch.cuda.get_device_name(0),vram_gib=round(torch.cuda.get_device_properties(0).total_memory/1024**3,2))
        rows=[json.loads(line) for line in (args.data_dir/'train.jsonl').read_text(encoding='utf-8').splitlines()]
        if not rows:raise ValueError('The candidate training file has no examples.')
        selected=max(rows,key=lambda row:len(tokenizer.apply_chat_template(row['messages'],tokenize=True,add_generation_prompt=False)))
        prompt=tokenizer.apply_chat_template(selected['messages'][:-1],tokenize=True,add_generation_prompt=True)
        tokens=tokenizer.apply_chat_template(selected['messages'],tokenize=True,add_generation_prompt=False)
        if tokens[:len(prompt)]!=prompt:raise ValueError('Assistant masking prefix does not match the full chat.')
        if len(tokens)>4096:raise ValueError('Candidate example exceeds the configured 4096-token training limit.')
        labels=[-100]*len(prompt)+tokens[len(prompt):]
        if not any(label!=-100 for label in labels):raise ValueError('The selected example has no assistant target.')
        padding=(-len(tokens))%8
        batch={'input_ids':torch.tensor([tokens+[tokenizer.pad_token_id]*padding],device='cuda'),
               'attention_mask':torch.tensor([[1]*len(tokens)+[0]*padding],device='cuda'),
               'labels':torch.tensor([labels+[-100]*padding],device='cuda')}
        model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False})
        model=get_peft_model(model,LoraConfig(r=16,lora_alpha=32,lora_dropout=.05,target_modules='all-linear',bias='none',task_type='CAUSAL_LM'))
        model.train()
        named_parameters=[(name,parameter) for name,parameter in model.named_parameters() if parameter.requires_grad]
        parameters=[parameter for _,parameter in named_parameters]
        report.update(example_id=selected['id'],task=selected.get('task'),chat_tokens=len(tokens),padded_tokens=len(tokens)+padding,
                      trainable_parameters=sum(parameter.numel() for parameter in parameters),
                      trainable_parameter_dtypes=sorted({str(parameter.dtype) for parameter in parameters}))
        state_buffers=[torch.zeros_like(parameter) for parameter in parameters for _ in range(2)]
        report.update(optimizer_state_reserve_bytes=sum(buffer.numel()*buffer.element_size() for buffer in state_buffers),
                      setup_peak_allocated_gib=round(torch.cuda.max_memory_allocated()/1024**3,3),
                      setup_peak_reserved_gib=round(torch.cuda.max_memory_reserved()/1024**3,3))
        torch.cuda.reset_peak_memory_stats()
        measurement_scope='forward/backward and gradient checks, including live model, batch and approximate optimizer-state buffers'
        started=time.monotonic()
        with torch.autocast('cuda',dtype=torch.bfloat16):loss=model(**batch).loss
        if not torch.isfinite(loss):raise RuntimeError('Nonfinite loss in memory preflight.')
        loss.backward();torch.cuda.synchronize()
        report.update(validate_gradients(named_parameters,torch))
        report.update(status='passed',loss=float(loss.detach()),seconds=round(time.monotonic()-started,2),
                      peak_allocated_gib=round(torch.cuda.max_memory_allocated()/1024**3,3),
                      peak_reserved_gib=round(torch.cuda.max_memory_reserved()/1024**3,3),
                      interpretation='One example passed with finite gradients and approximate optimizer-state memory reserved. No optimizer was run or weights saved. This does not guarantee an entire training run will fit or improve quality.')
    except Exception as error:
        report.update(status='failed',error=f'{type(error).__name__}: {error}')
    if torch is not None and torch.cuda.is_initialized():
        report.update(peak_allocated_gib=round(torch.cuda.max_memory_allocated()/1024**3,3),
                      peak_reserved_gib=round(torch.cuda.max_memory_reserved()/1024**3,3),
                      peak_measurement_scope=measurement_scope)
    report['complete']=True
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
