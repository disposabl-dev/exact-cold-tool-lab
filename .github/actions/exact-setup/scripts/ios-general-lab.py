#!/usr/bin/env python3
"""Lab-only fresh-archive link for two explicitly qualified public sample graphs."""
import importlib.util, json, os, subprocess, sys, tempfile
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
for item in r['binary']['sourceInputs']['files']:
 root={'exact':sdk,'app':app}.get(item['root'])
 if root is None: raise ValueError('Unsupported input root')
 rel=Path(item['path'])
 if rel.is_absolute() or '..' in rel.parts: raise ValueError('Invalid source path')
 path=root/rel
 if not path.is_file() or b.digest(path)!=item['sha256']: raise ValueError('Fresh source input changed: '+str(rel))
ci=f['compat']; linked=ci['linked']; ext=f['topology']['extensions']
if ci['minimumOS']!='17.0' or ci['trust']!='production' or ci['capabilities']!={'associatedDomains':None,'audioSession':None,'backgroundModes':None,'urlSchemes':None} or ci.get('nativeModules') is not None: raise ValueError('Unsupported native settings')
if linked==['markdown','io'] and ext=={}:
 kind='paper'; targets=['ExactCore','ExactKit','ExactUpdates','ExactMarkdown']; defines=['EXACT_LINK_MARKDOWN','EXACT_LINK_IO']
elif linked==['io','modules','native_views'] and ext=={'geolocation':'@exact/geolocation','motion':'@exact/motion','speech-synthesis':'@exact/speech-synthesis'}:
 kind='trail'; targets=['ExactCore','ExactKit','ExactUpdates','ExactFormaBinding','ExactHeavyLeaves','ExactNativeViews']; defines=['EXACT_LINK_IO','EXACT_LINK_MODULES','EXACT_LINK_NATIVE_VIEWS']
else: raise ValueError('Unsupported capability graph')
# The real Cargo receipt must name exactly one existing, byte-verified archive.
archives=[x for x in r['products'] if x['path'].endswith('/libapps_apple.a')]
if len(archives)!=1 or b.digest(archives[0]['path'])!=archives[0]['sha256'] or archives[0]['sha256']!=f['archive']: raise ValueError('Fresh archive mismatch')
archive=Path(archives[0]['path']).resolve(); cat=catalog/kind/'host-objects'
for name in targets:
 if not (cat/(name+'.o')).is_file() or not (cat/(name+'.swiftmodule')).is_dir(): raise ValueError('Missing catalog target '+name)
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
 print('general lab: fresh archive and sections verified')
