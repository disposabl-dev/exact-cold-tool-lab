#!/usr/bin/env python3
# Only the content-addressed, upstream-checked Exact filesystem helper.
import hashlib,json,os,re,shutil,sys
from pathlib import Path
target,sdk,out=map(lambda x:Path(x).resolve(),sys.argv[1:])
rootkey=hashlib.sha256(str(sdk).encode()).hexdigest()[:24]
src=target/'exact-filesystem-tool'/rootkey
assert src.is_dir() and not out.exists()
out.mkdir(parents=True)
records=[]
for check in src.glob('checked-*'):
    if not re.fullmatch(r'checked-[0-9a-f]{32}',check.name) or check.is_symlink(): continue
    name=check.read_text().strip()
    match=re.fullmatch(r'exact-filesystem-([0-9a-f]{64})',name)
    if not match: continue
    binary=src/name
    if binary.is_symlink() or not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest()!=match.group(1): continue
    shutil.copy2(check,out/check.name);shutil.copy2(binary,out/binary.name)
    records.append({'check':check.name,'binary':name,'sha256':match.group(1)})
if not records: raise SystemExit('No upstream checked filesystem helper captured')
(out/'manifest.json').write_text(json.dumps({'version':1,'sdk':str(sdk),'target':str(target),'rootKey':rootkey,'records':records})+'\n')
print('Captured',len(records),'verified helper records')
