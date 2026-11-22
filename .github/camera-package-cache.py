"""Carry two individually keyed public Exact modules; the fixture has no user modules."""
from pathlib import Path
import re,sys,tarfile
mode,root,output=sys.argv[1:]
root=Path(root)
files={}
for d in (root/'apple-swift').rglob('packages-kept'):
    for entry in d.iterdir():
        m=re.fullmatch(r'(ExactPackage|ExactPkg_camera)-[0-9a-f]{20}',entry.name)
        if not m or entry.is_symlink(): continue
        name=m[1]
        for p in entry.iterdir():
            if p.is_symlink() or p.name not in {name+'.'+ext for ext in ('o','swiftmodule','swiftdoc','swiftsourceinfo','tbd','dylib','abi.json')}: continue
            if p.is_file(): files[str(p.relative_to(root))]=p
if not any('/ExactPkg_camera-' in f and f.endswith('.dylib') for f in files): raise ValueError('No compiled public camera package')
if mode=='capture':
    with tarfile.open(output,'x') as t:
        for name,p in files.items(): t.add(p,arcname=name,recursive=False)
    print('Cached module files',len(files))
else:
    with tarfile.open(output) as t:
        expected=set(t.getnames())
        if set(files)!=expected: raise ValueError('Consumer used a different package key: '+str(sorted(set(files)-expected)))
        for name,p in files.items():
            if p.read_bytes()!=t.extractfile(name).read(): raise ValueError('Cache bytes changed '+name)
    print('Consumer kept the same public camera package keys and outputs')
