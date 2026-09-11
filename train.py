"""QLoRA supervised fine-tuning with completion-only loss and offline model loading."""
import argparse
import hashlib
import json
import time
from core import ROOT, load_model

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-steps', type=int, default=-1)
    parser.add_argument('--epochs', type=float, default=1.0)
    parser.add_argument('--output', default='runs/adapter')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--accumulation', type=int, default=8)
    parser.add_argument('--data-dir', default='data')
    parser.add_argument('--max-length', type=int, default=2048)
    args = parser.parse_args()
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import Trainer, TrainingArguments, DataCollatorForSeq2Seq, set_seed
    from transformers.trainer_utils import get_last_checkpoint
    set_seed(42)
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = True
    out = ROOT / args.output
    if (out / 'adapter_model.safetensors').exists() and not args.resume:
        raise RuntimeError(f'{out} already has an adapter. Choose a new --output directory.')
    out.mkdir(parents=True, exist_ok=True)
    model, tokenizer = load_model(training=True)
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                            gradient_checkpointing_kwargs={'use_reentrant': False})
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                                           target_modules='all-linear', bias='none', task_type='CAUSAL_LM'))
    model.print_trainable_parameters()

    def tokenize_file(name):
        items = []
        for line in (ROOT / args.data_dir / name).read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            prompt = tokenizer.apply_chat_template(row['messages'][:-1], tokenize=True, add_generation_prompt=True)
            full = tokenizer.apply_chat_template(row['messages'], tokenize=True, add_generation_prompt=False)
            if full[:len(prompt)] != prompt:
                raise ValueError('Chat-template prefix mismatch: assistant masking would be wrong')
            if len(full) > args.max_length:
                raise ValueError(f"{row['id']} exceeds {args.max_length} tokens; shorten this example instead of truncating its answer")
            items.append({'input_ids': full, 'attention_mask': [1]*len(full),
                          'labels': [-100]*len(prompt) + full[len(prompt):]})
        return items

    training = tokenize_file('train.jsonl')
    validation = tokenize_file('validation.jsonl')
    class Rows(torch.utils.data.Dataset):
        def __init__(self, rows): self.rows = rows
        def __len__(self): return len(self.rows)
        def __getitem__(self, i): return self.rows[i]

    config = dict(base_model=json.loads((ROOT / 'model-manifest.json').read_text(encoding='utf-8')),
                  rank=16, alpha=32, dropout=0.05, target_modules='all-linear', quantization='NF4 double quantization',
                  max_sequence_length=args.max_length, data_dir=args.data_dir, micro_batch=1, accumulation=args.accumulation,
                  learning_rate=1e-4, epochs=args.epochs, max_steps=args.max_steps, seed=42,
                  examples=len(training), max_observed_tokens=max(len(r['input_ids']) for r in training),
                  train_sha256=hashlib.sha256((ROOT / args.data_dir / 'train.jsonl').read_bytes()).hexdigest(),
                  validation_sha256=hashlib.sha256((ROOT / args.data_dir / 'validation.jsonl').read_bytes()).hexdigest(),
                  loss='assistant completion only')
    (out / 'training-config.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    targs = TrainingArguments(
        output_dir=str(out), num_train_epochs=args.epochs, max_steps=args.max_steps,
        per_device_train_batch_size=1, per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.accumulation, learning_rate=1e-4,
        warmup_ratio=0.05, lr_scheduler_type='cosine', optim='adamw_torch',
        bf16=True, fp16=False, gradient_checkpointing=True,
        gradient_checkpointing_kwargs={'use_reentrant': False},
        logging_steps=1, save_strategy='steps', save_steps=20, save_total_limit=2,
        eval_strategy='no', prediction_loss_only=True, report_to='none',
        dataloader_num_workers=0, dataloader_pin_memory=False,
        seed=42, data_seed=42, remove_unused_columns=False, disable_tqdm=True,
        save_safetensors=True, max_grad_norm=1.0)
    trainer = Trainer(model=model, args=targs, train_dataset=Rows(training), eval_dataset=Rows(validation),
                      data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, pad_to_multiple_of=8,
                                                          label_pad_token_id=-100), processing_class=tokenizer)
    checkpoint = get_last_checkpoint(str(out)) if args.resume else None
    if args.resume and not checkpoint:
        raise RuntimeError('No checkpoint found to resume')
    start = time.perf_counter()
    result = trainer.train(resume_from_checkpoint=checkpoint)
    trainer.save_model(str(out))
    tokenizer.save_pretrained(out)
    trainer.save_state()
    metrics = dict(result.metrics, wall_seconds=time.perf_counter()-start,
                   peak_allocated_vram_gib=torch.cuda.max_memory_allocated()/1024**3,
                   peak_reserved_vram_gib=torch.cuda.max_memory_reserved()/1024**3)
    if args.max_steps != 3:
        metrics.update(trainer.evaluate())
    (out / 'metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    print('TRAINING COMPLETE', json.dumps(metrics), flush=True)

if __name__ == '__main__':
    main()
