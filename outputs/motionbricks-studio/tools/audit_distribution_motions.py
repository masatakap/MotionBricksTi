"""Check deployed data for the identified removed evaluation-only motions.

This detects known names, exact raw-data copies and saved source references;
it is not a general license certification of unrelated data or dependencies.
"""
from pathlib import Path
import argparse,csv,gzip,hashlib,json,re

SOURCE_FIELDS=re.compile(r'"(?:source|path|seed_source|clip|source_file)"\s*:\s*("(?:\\.|[^"\\])*")')

def restricted_references(data,names):
    if data[:2]==b'\x1f\x8b':data=gzip.decompress(data)
    result=[]
    for token in SOURCE_FIELDS.findall(data.decode('utf8')):
        value=json.loads(token);normalized=value.replace('\\','/').lower()
        if normalized.split('/')[-1] in names or '/assets/motions/' in normalized or normalized.startswith('assets/motions/'):
            result.append(value)
    return sorted(set(result))

def scan(root):
    root=Path(root).resolve();names=set();hashes=set();issues=[];checked=0
    inventory=root/'MOTION_LICENSE_INVENTORY_20261031.csv'
    if inventory.exists():
        with inventory.open(encoding='utf-8-sig') as f:names.update(Path(r['file']).name.lower() for r in csv.DictReader(f))
    marker=root/'assets/motions/REMOVED_SAMPLES.json'
    if marker.exists():
        policy=json.loads(marker.read_text(encoding='utf8'))
        for item in policy['restricted_samples']:names.add(Path(item['file']).name.lower());hashes.add(item['sha256'])
    if not names:raise ValueError('Missing removed-sample inventory; refusing an unverifiable distribution check')
    for folder in (root/'assets',root/'user_data'):
        for path in folder.rglob('*'):
            if not path.is_file():continue
            checked+=1
            if path.name.lower() in names:
                issues.append(dict(file=path.relative_to(root).as_posix(),reason='known_restricted_sample_name'));continue
            if path.suffix.lower() not in ('.bvh','.csv','.json','.npz','.npy','.fbx','.zip'):continue
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest() in hashes:
                issues.append(dict(file=path.relative_to(root).as_posix(),reason='exact_copy_of_restricted_sample'));continue
            if path.suffix.lower()=='.json':
                try:refs=restricted_references(data,names)
                except (ValueError,OSError,UnicodeError) as exc:
                    issues.append(dict(file=path.relative_to(root).as_posix(),reason='unreadable_data_document',detail=str(exc)));continue
                if refs:issues.append(dict(file=path.relative_to(root).as_posix(),reason='saved_reference_to_removed_sample',references=refs))
    for digest in hashes:
        cached=root/'.git/lfs/objects'/digest[:2]/digest[2:4]/digest
        if cached.is_file():issues.append(dict(file=cached.relative_to(root).as_posix(),reason='known_restricted_lfs_cache_object'))
    return dict(schema='motionbricks-ti-distribution-motion-audit',files_checked=checked,known_restricted_sample_names=len(names),issues=issues,passed=not issues,scope='Known evaluation-only sample motions, traceable copies/derivatives in assets and user_data, and known local Git LFS sample objects; excludes Git history, external private backups, models and unrelated dependency licenses')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--report',type=Path);args=parser.parse_args();result=scan(args.root);body=json.dumps(result,ensure_ascii=False,indent=2)
    if args.report:args.report.write_text(body,encoding='utf8')
    print(body)
    raise SystemExit(0 if result['passed'] else 1)

if __name__=='__main__':main()
