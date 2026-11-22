#!/usr/bin/env python3
"""Fail-closed fresh-archive link for explicitly qualified SDK host graphs."""
import hashlib, importlib.util, json, os, re, subprocess, sys, tempfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('kit',Path(__file__).with_name('ios-link-kit.py'))
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
import argparse
p=argparse.ArgumentParser(); p.add_argument('mode'); p.add_argument('--kit',required=True); p.add_argument('--receipt',required=True); p.add_argument('--bake',required=True); p.add_argument('--out',required=True); p.add_argument('--app',default=os.getcwd()); a=p.parse_args()
if a.mode!='link': raise ValueError('link only')
kit=Path(a.kit).resolve(); app=Path(a.app).resolve(); sdk=Path(os.environ['EXACT']).resolve(); catalog=Path(os.environ['EXACT_HOST_CATALOG']).resolve()
r=b.load(a.receipt); f=b.facts(a.receipt,a.bake,app); original=b.load(kit/'kit.json')
if original['toolchain'] != b.toolchain(): raise ValueError('Toolchain mismatch')
if subprocess.check_output(['git','-C',str(sdk),'rev-parse','HEAD'],text=True).strip() != 'a55c5581c7e1a62cdee1f09367ea2909c74c7292': raise ValueError('SDK pin mismatch')
if any(b.digest(kit/n)!=h for n,h in original['digests'].items()): raise ValueError('Original kit changed')
# SDK host code and build configuration must be the reviewed stock SDK. App
# inputs are checked against the fresh receipt below rather than the seed.
def exact_files(facts): return {(x['root'],x['path']):x['sha256'] for x in facts['source']['files'] if x['root']=='exact'}
if exact_files(f)!=exact_files(original['facts']): raise ValueError('SDK source inputs differ')
for name in ('inventories','links','directories','absent'):
 def exact_rows(x): return [v for v in (x['source'].get(name) or []) if v.get('root')=='exact']
 if exact_rows(f)!=exact_rows(original['facts']): raise ValueError('SDK source inventory differs')
for item in r['binary']['sourceInputs']['files']:
 root={'exact':sdk,'app':app}.get(item['root'])
 if root is None: raise ValueError('Unsupported input root')
 rel=Path(item['path'])
 if rel.is_absolute() or '..' in rel.parts: raise ValueError('Invalid source path')
 path=root/rel
 if not path.is_file() or b.digest(path)!=item['sha256']: raise ValueError('Fresh source input changed: '+str(rel))
ci=f['compat']; linked=ci['linked']; ext=f['topology']['extensions']
seed=original['facts']['compat']
variable={'linked','grantCeiling','rustGrants','grantPurposes'}
if any(ci.get(k)!=seed.get(k) for k in (ci.keys()|seed.keys())-variable): raise ValueError('Unsupported compatibility fields')
if f['metadata'] != original['facts']['metadata']: raise ValueError('Native metadata differs')
# Restrict app native input inventory to generated shell and the exact shipped
# extension manifests for the two qualified SDK graphs. No user native code.
allowed_shell={'.exact/shells/Cargo.lock','.exact/shells/Cargo.toml','.exact/shells/apple/Cargo.toml','.exact/shells/apple/build.rs','.exact/shells/apple/src/lib.rs'}
app_items=[x for x in r['binary']['sourceInputs']['files'] if x['root']=='app']
for item in app_items:
 name=item['path']
 if name in allowed_shell: continue
 prefix='node_modules/@exact/'
 if not name.startswith(prefix): raise ValueError('Unsupported app native input')
 upstream=sdk/'packages'/name[len(prefix):]
 if not upstream.is_file() or b.digest(upstream)!=item['sha256']: raise ValueError('Extension differs from pinned SDK')
# The complete compiler feature graph is admitted only for measured graphs.
config=hashlib.sha256(json.dumps(f['configuration'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
if ci['minimumOS']!='17.0' or ci['trust']!='production' or ci['capabilities']!={'associatedDomains':None,'audioSession':None,'backgroundModes':None,'urlSchemes':None} or ci.get('nativeModules') is not None: raise ValueError('Unsupported native settings')
if linked==['markdown','io'] and ext=={}:
 kind='paper'; expected_config='6c94d888c7f7b8cbc26bf8476c924a5ad90c6fd0a1bf5efc76f38f5680b84958'; targets=['ExactCore','ExactKit','ExactUpdates','ExactMarkdown']; defines=['EXACT_LINK_MARKDOWN','EXACT_LINK_IO']
elif linked==['io','modules','native_views'] and ext=={'geolocation':'@exact/geolocation','motion':'@exact/motion','speech-synthesis':'@exact/speech-synthesis'}:
 kind='trail'; expected_config='295228074fe9946fdeba44446fa348969dff93d27c776cba2ca5b774de1edf12'; targets=['ExactCore','ExactKit','ExactUpdates','ExactFormaBinding','ExactHeavyLeaves','ExactNativeViews']; defines=['EXACT_LINK_IO','EXACT_LINK_MODULES','EXACT_LINK_NATIVE_VIEWS']
else: raise ValueError('Unsupported capability graph')
if config!=expected_config: raise ValueError('Cargo configuration differs from qualified graph')
manifest_app=b.load(app/'app.json'); actual_id=manifest_app.get('app',{}).get('id') or manifest_app.get('id')
if r['compat']['inputs']['app']!=actual_id or r['compat']['inputs']['keys']!=manifest_app.get('deploy',{}).get('signing',{}).get('keys'): raise ValueError('Fresh identity or update keys differ')
grants=ci.get('grantCeiling'); rust_grants=ci.get('rustGrants')
if grants!=rust_grants: raise ValueError('Grant ceiling differs from native grants')
if kind=='paper':
 if not isinstance(grants,str) or not re.fullmatch(r'net\.websocket wss://[A-Za-z0-9.-]+(?::[0-9]{1,5})?',grants): raise ValueError('Unsupported Markdown grants')
else:
 if grants!='device.geolocation purpose.geolocation\ndevice.motion purpose.motion' or ci.get('grantPurposes')!='3031012d4c9fc289e48260f71b17735f': raise ValueError('Unsupported Trail grants')
expected_extensions=set() if kind=='paper' else {'node_modules/@exact/geolocation/exact.json','node_modules/@exact/motion/exact.json','node_modules/@exact/motion/apple/PrivacyInfo.xcprivacy','node_modules/@exact/speech-synthesis/exact.json'}
if {x['path'] for x in app_items} != allowed_shell | expected_extensions: raise ValueError('Unsupported app native inputs')
# The real Cargo receipt must name exactly one existing, byte-verified archive.
archives=[x for x in r['products'] if x['path'].endswith('.a')]
if len(archives)!=1 or b.digest(archives[0]['path'])!=archives[0]['sha256'] or archives[0]['sha256']!=f['archive']: raise ValueError('Fresh archive mismatch')
archive=Path(archives[0]['path']).resolve()
if not archive.is_relative_to(Path(os.environ['CARGO_TARGET_DIR']).resolve()): raise ValueError('Archive outside Cargo target')
manifest=b.load(catalog/'manifest.json')
if manifest.get('ref')!='a55c5581c7e1a62cdee1f09367ea2909c74c7292' or manifest.get('toolchain')!=b.toolchain() or manifest.get('target')!='arm64-apple-ios17.0' or manifest.get('profile')!='release-balanced' or manifest.get('conditions')!={'intent_files':False,'widget_gallery':False,'watch_sync':False,'composition':'updating'}: raise ValueError('Catalog toolchain or compile conditions mismatch')
files=manifest.get('files')
if not isinstance(files,dict) or not files: raise ValueError('Missing catalog hashes')
for n,h in files.items():
 rel=Path(n)
 if rel.is_absolute() or '..' in rel.parts or rel.parts[0]!='host-objects' or rel.suffix not in ('.o','.swiftmodule','.swiftdoc','.json') or (catalog/rel).is_symlink() or not (catalog/rel).resolve().is_relative_to(catalog) or not (catalog/rel).is_file() or b.digest(catalog/rel)!=h: raise ValueError('Catalog digest mismatch')
cat=catalog/'host-objects' 
for name in targets:
 if 'host-objects/'+name+'.o' not in files or not any(n.startswith('host-objects/'+name+'.swiftmodule/') and n.endswith('.swiftmodule') for n in files): raise ValueError('Missing catalog target '+name)
out=Path(a.out).resolve()
if out.exists(): raise ValueError('Output exists')
out.parent.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='.exact-general-',dir=out.parent) as temp:
 t=Path(temp); mm=t/'CExactLaunch.modulemap'; mm.write_text('module CExactLaunch { umbrella header "'+str(sdk/'host/apple/Sources/CExactLaunch/include/CExactLaunch.h')+'" export * }\n')
 apple_sdk=subprocess.check_output(['/usr/bin/xcrun','--sdk','iphoneos','--show-sdk-path'],text=True).strip()
 composition=t/'ExactComposition.o'
 cmd=['/usr/bin/xcrun','--sdk','iphoneos','swiftc','-target','arm64-apple-ios17.0','-sdk',apple_sdk,'-module-name','ExactComposition','-emit-object','-whole-module-optimization','-O','-parse-as-library','-I',str(cat),'-I',str(sdk/'host/apple/Sources/CExact'),'-Xcc','-fmodule-map-file='+str(mm),'-D','EXACT_APP_UPDATING']
 for define in defines: cmd+=['-D',define]
 cmd += [str(sdk/'host/apple/Sources/ExactComposition/Composition.swift'),str(sdk/'host/apple/Sources/ExactComposition/LaunchHooks.swift'),'-o',str(composition)]
 subprocess.run(cmd,check=True)
 objects=[kit/'00-main.o',kit/'01-CExactLaunch.o',*(cat/(name+'.o') for name in targets),composition,kit/'12-ExactLaunchParts.o']
 filelist=t/'link.inputs'; filelist.write_text(' '.join(map(str,objects)))
 command=[]
 for x in original['commands']:
  x=x.replace('@KIT@',str(kit))
  if x=='@'+str(kit/'link.txt'): x='@'+str(filelist)
  elif x==str(kit/'ExactIOS'): x=str(out)
  elif x==str(kit/'lto.o'): x=str(t/'lto.o')
  elif x==str(kit/'dependency.dat'): x=str(t/'dependency.dat')
  elif x in [str(kit/n) for n in b.PAYLOAD]: x=str(Path(a.bake).resolve()/Path(x).name)
  elif x=='-lapps_apple': x=str(archive)
  command.append(x)
 subprocess.run(command,check=True); b.verify_sections(out,a.bake)
 marker=os.environ.get('EXACT_GENERAL_PROOF')
 if marker: Path(marker).write_text(json.dumps({'graph':linked,'archive':f['archive'],'executable':b.digest(out)}))
 print('general host: fresh archive and sections verified')
