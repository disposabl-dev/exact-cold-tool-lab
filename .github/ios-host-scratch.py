#!/usr/bin/env python3
"""Lab-only: copy first-party host outputs; never package Xcode state or app inputs."""
import hashlib, json, os, shutil, sqlite3, sys
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
  dbrel=Path('out/Intermediates.noindex/XCBuildData/build.db')
  source_db=src/dbrel
  if source_db.exists():
    dest=dst/dbrel; dest.parent.mkdir(parents=True,exist_ok=True)
    source=sqlite3.connect(f'file:{source_db}?mode=ro',uri=True); out=sqlite3.connect(dest); source.backup(out); source.close(); out.text_factory=bytes
    bad=[b'/exact-native/apps/',b'/clients/',b'publicseed',b'ExactComposition',b'ExactIOS',b'app.plan',b'compat.json',b'app.hbc',b'libapps_apple',b'linked-plan']
    rows=out.execute('select k.id,k.key,r.value,r.dependencies from key_names k left join rule_results r on r.key_id=k.id').fetchall()
    drop=[]
    for ident,key,value,deps in rows:
      blobs=[key.encode() if isinstance(key,str) else key,bytes(value or b''),bytes(deps or b'')]
      if any(token.lower() in blob.lower() for blob in blobs for token in bad if blob): drop.append((ident,))
    out.executemany('delete from rule_results where key_id=?',drop); out.executemany('delete from key_names where id=?',drop); out.commit(); out.execute('vacuum'); out.close()
    data=dest.read_bytes(); assert not any(token.lower() in data.lower() for token in bad)
    records[str(dbrel)]=h(dest)
    print('Sanitized genuine XCBuild metadata:',len(rows),'rows, removed',len(drop))
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
