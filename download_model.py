"""Download the pinned model and verify every file against the shipped manifest."""
import argparse
import hashlib
import json
import re
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'models' / 'Qwen3-4B-Instruct-2507'
REPO = 'Qwen/Qwen3-4B-Instruct-2507'


def fetch(url):
    import certifi
    return urllib.request.urlopen(
        url, context=ssl.create_default_context(cafile=certifi.where()), timeout=120)


def load_manifest(path):
    """Treat the committed hashes as expected values, never replace them on download."""
    manifest = json.loads(Path(path).read_text(encoding='utf-8'))
    if manifest.get('repo') != REPO or not re.fullmatch(r'[0-9a-f]{40}', manifest.get('revision', '')):
        raise ValueError('Model manifest must identify the expected repository and an exact revision')
    if not isinstance(manifest.get('files'), list) or not manifest['files']:
        raise ValueError('Model manifest must contain a nonempty file list')
    seen = set()
    for record in manifest['files']:
        name = record.get('file', '')
        relative = PurePosixPath(name)
        if (not name or relative.is_absolute() or '..' in relative.parts or
                '\\' in name or ':' in name or str(relative) != name or name.casefold() in seen):
            raise ValueError(f'Unsafe or duplicate model filename: {name!r}')
        seen.add(name.casefold())
        if (type(record.get('bytes')) is not int or record['bytes'] < 0 or
                not re.fullmatch(r'[0-9a-f]{64}', record.get('sha256', ''))):
            raise ValueError(f'Missing size or SHA256 for {name}')
    return manifest


def verified(path, record):
    if not path.is_file() or path.stat().st_size != record['bytes']:
        return False
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest() == record['sha256']


def download(record, revision, destination, opener=fetch, attempts=4):
    name = record['file']
    dest = destination / name
    if verified(dest, record):
        print('Verified existing', name, flush=True)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.partial')
    url = f'https://huggingface.co/{REPO}/resolve/{revision}/{quote(name, safe="/")}'
    for attempt in range(attempts):
        try:
            print('Downloading', name, record['bytes'], flush=True)
            digest = hashlib.sha256()
            total = 0
            last = time.monotonic()
            with opener(url) as response, tmp.open('wb') as output:
                while chunk := response.read(8 * 1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
                    total += len(chunk)
                    if time.monotonic() - last > 30:
                        print(name, round(total / 1e9, 2), 'GB', flush=True)
                        last = time.monotonic()
            if total != record['bytes']:
                raise ValueError(f'Size mismatch for {name}: {total} != {record["bytes"]}')
            if digest.hexdigest() != record['sha256']:
                raise ValueError('SHA256 mismatch: ' + name)
            tmp.replace(dest)
            print('Complete', name, total, flush=True)
            return
        except Exception as error:
            # Never promote a partial or corrupt response to a model file.
            tmp.unlink(missing_ok=True)
            if attempt == attempts - 1:
                raise
            print('Retry', name, attempt + 1, repr(error), flush=True)
            time.sleep(2 ** attempt)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Check local files without any network requests')
    parser.add_argument('--destination', type=Path, default=DEST, help='Model directory (defaults to this project)')
    args = parser.parse_args(argv)
    manifest = load_manifest(ROOT / 'model-manifest.json')
    print('Pinned model revision:', manifest['revision'], flush=True)
    if args.verify_only:
        invalid = [record['file'] for record in manifest['files']
                   if not verified(args.destination / record['file'], record)]
        if invalid:
            parser.exit(1, 'Missing or checksum-mismatched files: ' + ', '.join(invalid) + '\n')
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda record: download(record, manifest['revision'], args.destination),
                          manifest['files']))
    print('MODEL FILES VERIFIED', flush=True)


if __name__ == '__main__':
    main()
