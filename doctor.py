import json
import platform
from importlib.metadata import version
from core import ROOT

def main():
    import torch
    import bitsandbytes as bnb
    report = {'python': platform.python_version(), 'packages': {p: version(p) for p in
              ['torch', 'transformers', 'peft', 'accelerate', 'bitsandbytes', 'datasets', 'gradio']},
              'cuda_available': torch.cuda.is_available(), 'torch_cuda': torch.version.cuda}
    if not report['cuda_available']:
        raise RuntimeError('CUDA is unavailable: ' + json.dumps(report))
    report.update(gpu=torch.cuda.get_device_name(0), capability=torch.cuda.get_device_capability(0),
                  vram_gib=round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2),
                  bf16_supported=torch.cuda.is_bf16_supported(), compiled_arches=torch.cuda.get_arch_list())
    x = torch.randn(2, 64, device='cuda', dtype=torch.bfloat16, requires_grad=True)
    layer = bnb.nn.Linear4bit(64, 32, bias=False, compute_dtype=torch.bfloat16, quant_type='nf4').to('cuda')
    layer(x).float().square().mean().backward()
    torch.cuda.synchronize()
    assert x.grad is not None and torch.isfinite(x.grad).all()
    report['nf4_forward_backward'] = 'passed'
    (ROOT / 'reports').mkdir(exist_ok=True)
    (ROOT / 'reports' / 'environment.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
