import importlib.util,json,shutil,sys
from pathlib import Path
root,scripts=map(Path,sys.argv[1:]); out=root/'union'; target=out/'host-objects'; target.mkdir(parents=True)
spec=importlib.util.spec_from_file_location('proof',scripts/'ios-link-kit.py'); b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
for kind in ('paper','trail'):
 for source in (root/kind/'host-objects').rglob('*'):
  if not source.is_file(): continue
  rel=source.relative_to(root/kind/'host-objects'); dest=target/rel; dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists(): assert b.digest(dest)==b.digest(source),rel
  else: shutil.copyfile(source,dest)
files={str(p.relative_to(out)):b.digest(p) for p in target.rglob('*') if p.is_file()}
(out/'manifest.json').write_text(json.dumps({'ref':'a55c5581c7e1a62cdee1f09367ea2909c74c7292','toolchain':b.toolchain(),'target':'arm64-apple-ios17.0','profile':'release-balanced','conditions':{'intent_files':False,'widget_gallery':False,'watch_sync':False,'composition':'updating'},'files':files}))
