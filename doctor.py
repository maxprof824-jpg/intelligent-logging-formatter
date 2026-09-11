"""Check the local CUDA stack and save a diagnostic report, including failures."""
import json
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def probe_gpu(report):
    import torch
    report.update(cuda_available=torch.cuda.is_available(), torch_cuda=torch.version.cuda)
    if not report['cuda_available']:
        raise RuntimeError('CUDA is unavailable. Check the NVIDIA driver and the installed CUDA build of PyTorch.')
    report.update(gpu=torch.cuda.get_device_name(0), capability=torch.cuda.get_device_capability(0),
                  vram_gib=round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2),
                  bf16_supported=torch.cuda.is_bf16_supported(), compiled_arches=torch.cuda.get_arch_list())
    if not report['bf16_supported']:
        raise RuntimeError('This application requires a GPU that supports BF16 compute.')
    import bitsandbytes as bnb
    x = torch.randn(2, 64, device='cuda', dtype=torch.bfloat16, requires_grad=True)
    layer = bnb.nn.Linear4bit(64, 32, bias=False, compute_dtype=torch.bfloat16, quant_type='nf4').to('cuda')
    layer(x).float().square().mean().backward()
    torch.cuda.synchronize()
    if x.grad is None or not torch.isfinite(x.grad).all():
        raise RuntimeError('NF4 forward/backward produced missing or nonfinite gradients.')
    report['nf4_forward_backward'] = 'passed'


def main():
    report = {'python': platform.python_version(), 'packages': {}}
    for package in ['torch', 'transformers', 'peft', 'accelerate', 'bitsandbytes', 'datasets', 'gradio']:
        try:
            report['packages'][package] = version(package)
        except PackageNotFoundError:
            report['packages'][package] = 'not installed'
    try:
        probe_gpu(report)
        report['status'] = 'passed'
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
    (ROOT / 'reports').mkdir(exist_ok=True)
    (ROOT / 'reports' / 'environment.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
