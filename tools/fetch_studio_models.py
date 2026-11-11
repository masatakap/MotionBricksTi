"""Fetch pinned upstream ONNX files, checking the original Git LFS SHA-256."""
from pathlib import Path
import argparse, hashlib, json, urllib.request

ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true',help='Also fetch optional G1 models');args=parser.parse_args()
    manifest=json.loads(Path(__file__).with_name('studio-models.json').read_text(encoding='utf8'))
    studio=ROOT/'outputs/motionbricks-studio'
    for item in manifest['models']:
        if not args.all and '/soma/' not in item['path']:continue
        target=(studio/item['path']).resolve()
        if not target.is_relative_to(studio.resolve()):raise ValueError('Invalid destination')
        if target.exists():
            if target.stat().st_size==item['size'] and digest(target)==item['sha256']:
                print('Verified',item['path']);continue
            raise RuntimeError(f'Existing file differs; preserve it before retrying: {target}')
        target.parent.mkdir(parents=True,exist_ok=True);part=target.with_suffix('.onnx.part')
        print('Downloading',item['path'],flush=True)
        with urllib.request.urlopen(item['url'],timeout=120) as src,part.open('wb') as dst:
            while chunk:=src.read(4*1024*1024):dst.write(chunk)
        if part.stat().st_size!=item['size'] or digest(part)!=item['sha256']:raise RuntimeError('Model hash/size mismatch: '+str(part))
        part.replace(target)

if __name__=='__main__':main()
