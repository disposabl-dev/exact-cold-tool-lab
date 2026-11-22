import importlib.util, json, os, tempfile
from pathlib import Path
from unittest.mock import patch
p=Path(__file__).with_name('ios-selective-link.py')
s=importlib.util.spec_from_file_location('selective',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
with tempfile.TemporaryDirectory() as d:
 k=Path(d); (k/'swift-modules.json').write_text('{}'); os.environ['EXACT']=d
 try: m.compile_composition(k,{'compat':{'linked':[], 'trust':'production'}},k)
 except ValueError as e: assert 'Unsupported composition' in str(e)
 else: raise AssertionError('different graph accepted')
 record={}
 for name in m.CAMERA_MODULES:
  f=k/'swift-modules'/(name+'.swiftmodule')/'arm64-apple-ios.swiftmodule'; f.parent.mkdir(parents=True); f.write_bytes(b'module'); record[str(f.relative_to(k))]=m.digest(f)
 (k/'swift-modules.json').write_text(json.dumps(record)); f.write_bytes(b'tampered')
 with patch.object(m.subprocess,'check_output',return_value='a55c5581c7e1a62cdee1f09367ea2909c74c7292'):
  try: m.compile_composition(k,{'compat':{'linked':m.CAMERA_LINKED, 'trust':'production','grantCeiling':'device.camera cameraPurpose'}},k)
  except ValueError as e: assert 'Module digest mismatch' in str(e)
  else: raise AssertionError('tampered module accepted')
print('unsupported graph and tampered module rejected')
