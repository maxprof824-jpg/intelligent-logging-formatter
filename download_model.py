import hashlib
import json
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import certifi

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'models' / 'Qwen3-4B-Instruct-2507'
DEST.mkdir(parents=True, exist_ok=True)
CTX = ssl.create_default_context(cafile=certifi.where())
REPO = 'Qwen/Qwen3-4B-Instruct-2507'

def fetch(url):
    return urllib.request.urlopen(url, context=CTX, timeout=120)

manifest_path = ROOT / 'model-manifest.json'
prior_manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else None
api = 'https://huggingface.co/api/models/' + REPO
if prior_manifest:
    api += '/revision/' + prior_manifest['revision']
info = json.load(fetch(api + '?blobs=true'))
revision = info['sha']
files = [f for f in info['siblings'] if f['rfilename'].endswith(('.json', '.safetensors', '.txt', '.jinja')) or f['rfilename'] in ('LICENSE', 'README.md')]
print('Pinned model revision:', revision, flush=True)

def download(f):
    name = f['rfilename']
    dest = DEST / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    expected = f.get('lfs', {}).get('sha256')
    expected_size = f.get('size')
    if dest.exists() and (not expected_size or dest.stat().st_size == expected_size):
        digest = hashlib.file_digest(dest.open('rb'), 'sha256').hexdigest()
        if not expected or digest == expected:
            print('Verified existing', name, flush=True)
            return dict(file=name, bytes=dest.stat().st_size, sha256=digest, upstream_sha256=expected)
    tmp = dest.with_suffix(dest.suffix + '.partial')
    for attempt in range(4):
        try:
            print('Downloading', name, expected_size, flush=True)
            h = hashlib.sha256()
            with fetch(f'https://huggingface.co/{REPO}/resolve/{revision}/{name}') as response, tmp.open('wb') as output:
                total = 0
                last = time.monotonic()
                while chunk := response.read(8 * 1024 * 1024):
                    output.write(chunk)
                    h.update(chunk)
                    total += len(chunk)
                    if time.monotonic() - last > 30:
                        print(name, round(total / 1e9, 2), 'GB', flush=True)
                        last = time.monotonic()
            if expected_size and total != expected_size:
                raise ValueError(f'Size mismatch for {name}: {total} != {expected_size}')
            if expected and h.hexdigest() != expected:
                raise ValueError('SHA256 mismatch: ' + name)
            tmp.replace(dest)
            print('Complete', name, total, flush=True)
            return dict(file=name, bytes=total, sha256=h.hexdigest(), upstream_sha256=expected)
        except Exception as error:
            print('Retry', name, attempt, repr(error), flush=True)
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)

with ThreadPoolExecutor(max_workers=2) as pool:
    records = list(pool.map(download, files))
(ROOT / 'model-manifest.json').write_text(json.dumps(dict(repo=REPO, revision=revision, files=records), indent=2), encoding='utf-8')
print('MODEL DOWNLOAD VERIFIED', flush=True)
