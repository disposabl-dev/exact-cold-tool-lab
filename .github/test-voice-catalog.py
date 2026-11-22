import importlib.util, json, os
from pathlib import Path
s=importlib.util.spec_from_file_location('kit',Path(os.environ['GITHUB_WORKSPACE'])/'.github/actions/exact-setup/scripts/ios-link-kit.py'); kit=importlib.util.module_from_spec(s);s.loader.exec_module(kit)
source=kit.load('host-objects/manifest.json')
assert source['exact_ref']==os.environ['EXACT_REF']
files={'host-objects/'+k:h for k,h in source['files'].items()}
assert all(kit.digest(k)==h for k,h in files.items())
manifest={'ref':source['exact_ref'],'toolchain':kit.toolchain(),'target':'arm64-apple-ios17.0','profile':'release-balanced','conditions':{'intent_files':False,'widget_gallery':False,'watch_sync':False,'composition':'updating'},'files':files,'targets':kit.load('graph.json')['targets']}
Path('manifest.json').write_text(json.dumps(manifest))
