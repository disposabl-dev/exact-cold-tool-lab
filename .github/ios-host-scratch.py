#!/usr/bin/env python3
"""Lab-only: copy first-party host outputs; never package Xcode state or app inputs."""
import hashlib, json, os, shutil, sys
from pathlib import Path
mode, src_arg, dst_arg = sys.argv[1:]
src, dst = Path(src_arg), Path(dst_arg)
allowed = {'ExactCore','ExactKit','ExactUpdates','ExactEffects','ExactAnimations','ExactSvg','ExactImages','ExactFormaBinding','ExactHeavyLeaves','ExactNativeViews','ExactNavigation','ExactSharing'}
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
if mode == 'capture':
  records={}
  for name in sorted(allowed):
    product=src/'out/Products/Release-iphoneos'
    for p in [product/(name+'.o'), *(product/(name+'.swiftmodule')).glob('*')]:
      if not p.is_file() or p.is_symlink() or p.suffix not in ('.o','.swiftmodule','.swiftdoc','.json'): continue
      rel=p.relative_to(src); dest=dst/rel; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,dest); records[str(rel)]=h(p)
    folder=src/'out/Intermediates.noindex/Exact.build/Release-iphoneos'/(name+'-t.build')/'Objects-normal/arm64'
    if folder.exists():
      for p in folder.iterdir():
        if not p.is_file() or p.is_symlink() or p.suffix not in ('.o','.swiftmodule','.swiftdoc','.json','.d','.swiftdeps'): continue
        rel=p.relative_to(src); dest=dst/rel; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,dest); records[str(rel)]=h(p)
  assert records and all('ExactComposition' not in n and 'ExactIOS' not in n for n in records)
  (dst/'host-inputs.json').write_text(json.dumps(records,sort_keys=True))
  print('Captured',len(records),'first-party host files,',sum((dst/n).stat().st_size for n in records),'bytes')
elif mode=='restore':
  records=json.loads((src/'host-inputs.json').read_text()); assert records
  for n,digest in records.items():
    rel=Path(n); assert not rel.is_absolute() and '..' not in rel.parts and 'ExactComposition' not in n and 'ExactIOS' not in n
    p=src/rel; assert p.is_file() and not p.is_symlink() and h(p)==digest
    out=dst/rel; out.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,out)
  print('Restored',len(records),'verified first-party host files')
else: raise SystemExit('mode')
