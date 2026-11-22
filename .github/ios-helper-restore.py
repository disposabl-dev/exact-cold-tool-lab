#!/usr/bin/env python3
# The SDK independently verifies checked-<inputs> against current source bytes.
import hashlib,json,re,shutil,sys
from pathlib import Path
target,sdk,source=map(lambda x:Path(x).resolve(),sys.argv[1:])
m=json.loads((source/'manifest.json').read_text())
key=hashlib.sha256(str(sdk).encode()).hexdigest()[:24]
assert m['version']==1 and m['sdk']==str(sdk) and m['target']==str(target) and m['rootKey']==key
out=target/'exact-filesystem-tool'/key
out.mkdir(parents=True,exist_ok=True)
for r in m['records']:
    assert re.fullmatch(r'checked-[0-9a-f]{32}',r['check'])
    assert re.fullmatch(r'exact-filesystem-[0-9a-f]{64}',r['binary'])
    assert r['binary']=='exact-filesystem-'+r['sha256']
    check=source/r['check'];binary=source/r['binary']
    assert not check.is_symlink() and not binary.is_symlink() and check.read_text().strip()==r['binary']
    assert hashlib.sha256(binary.read_bytes()).hexdigest()==r['sha256']
    for p in (check,binary):
        dst=out/p.name
        assert not dst.exists()
        shutil.copy2(p,dst)
        dst.chmod(0o755 if p == binary else 0o644)
print('Restored',len(m['records']),'verified helper records')
