# Keep only public Gradle dependency state and selected unsigned build-cache tasks.
import pathlib, shutil, tarfile, re, sys
root=pathlib.Path.home()/'.gradle'; out=pathlib.Path(sys.argv[1]); cache=root/'caches'; dest=out/'caches'
dest.mkdir(parents=True,exist_ok=True)
def skip(d,names):
 return [n for n in names if n.lower().endswith(('.lock','.lck','.part','.apk','.aab','.p12','.jks','.receipt.json')) or (pathlib.Path(d)/n).is_symlink()]
for rel in ['modules-2','9.8.0/transforms']:
 src=cache/rel
 if src.exists(): shutil.copytree(src,dest/rel,ignore=skip,dirs_exist_ok=True)
source=cache/'build-cache-1'; target=dest/'build-cache-1';target.mkdir(exist_ok=True)
count=0
for f in source.iterdir():
 if not f.is_file() or f.is_symlink() or not re.fullmatch('[0-9a-f]{32}',f.name): continue
 try:
  with tarfile.open(f) as t:
   members=t.getmembers(); meta=t.extractfile('METADATA').read().decode('utf-8')
   ident=next((l for l in meta.splitlines() if l.startswith('identity=')),'').replace('\\:',':')
   allowed=('ImmutableTransformExecution' in meta or ident in ('identity=:app:compileReleaseKotlin','identity=:canvas:compileReleaseKotlin'))
   forbidden=any(re.search(r'(?:\.apk|\.aab|\.so|\.p12|\.jks|receipt\.json)$',m.name,re.I) or m.issym() or m.islnk() for m in members)
   if not allowed or forbidden: continue
  shutil.copy2(f,target/f.name); count+=1
 except (tarfile.TarError,AttributeError,UnicodeError): continue
print(f'Vetted {count} public Gradle task or transform cache entries')
