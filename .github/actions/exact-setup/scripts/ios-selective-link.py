#!/usr/bin/env python3
"""Compile a camera composition after the standard kit's full eligibility checks."""
import importlib.util, os, subprocess
from pathlib import Path
spec=importlib.util.spec_from_file_location('exact_ios_link_kit',Path(__file__).with_name('ios-link-kit.py'))
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
digest,load=base.digest,base.load

# This first implementation admits only the exact public camera closure. Extend
# only from a reviewed producer and a fresh receipt; any other graph falls back.
CAMERA_LINKED = ['router', 'share', 'effects', 'io', 'modules', 'svg', 'images', 'native_views', 'navigation']
CAMERA_DEFINES = ['EXACT_APP_UPDATING', 'EXACT_LINK_ROUTER', 'EXACT_LINK_SHARE', 'EXACT_LINK_EFFECTS', 'EXACT_LINK_IO', 'EXACT_LINK_MODULES', 'EXACT_LINK_SVG', 'EXACT_LINK_IMAGES', 'EXACT_LINK_NATIVE_VIEWS', 'EXACT_LINK_NAVIGATION']
CAMERA_MODULES = {'ExactCore', 'ExactKit', 'ExactUpdates', 'ExactEffects', 'ExactAnimations', 'ExactSvg', 'ExactImages', 'ExactFormaBinding', 'ExactHeavyLeaves', 'ExactNativeViews', 'ExactNavigation', 'ExactSharing'}

def compile_composition(kit, current, scratch):
    compat=current['compat']
    if compat.get('linked') != CAMERA_LINKED or compat.get('trust') != 'production' or 'device.camera cameraPurpose' not in compat.get('grantCeiling', ''):
        raise ValueError('Unsupported composition; use normal Exact build')
    root=Path(os.environ['EXACT']).resolve()
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip() != 'a55c5581c7e1a62cdee1f09367ea2909c74c7292':
        raise ValueError('SDK pin mismatch')
    modules=load(kit/'swift-modules.json')
    if not isinstance(modules,dict) or not modules: raise ValueError('Missing module hashes')
    seen=set()
    for name, expected in modules.items():
        rel=Path(name)
        if len(rel.parts)!=3 or rel.parts[0]!='swift-modules' or not rel.parts[1].endswith('.swiftmodule') or rel.parts[1][:-12] not in CAMERA_MODULES or rel.suffix not in ('.swiftmodule','.swiftdoc','.json'):
            raise ValueError('Unexpected module input')
        p=kit/rel
        if p.is_symlink() or not p.is_file() or digest(p)!=expected: raise ValueError('Module digest mismatch')
        seen.add(rel.parts[1][:-12])
    if seen!=CAMERA_MODULES: raise ValueError('Incomplete first-party modules')
    mm=scratch/'CExactLaunch.modulemap'
    mm.write_text('module CExactLaunch { umbrella header "'+str(root/'host/apple/Sources/CExactLaunch/include/CExactLaunch.h')+'" export * }\n')
    sdk=subprocess.check_output(['/usr/bin/xcrun','--sdk','iphoneos','--show-sdk-path'],text=True).strip()
    output=scratch/'ExactComposition.o'
    command=['/usr/bin/xcrun','--sdk','iphoneos','swiftc','-target','arm64-apple-ios17.0','-sdk',sdk,'-module-name','ExactComposition','-emit-object','-whole-module-optimization','-O','-parse-as-library','-I',str(kit/'swift-modules'),'-I',str(root/'host/apple/Sources/CExact'),'-Xcc','-fmodule-map-file='+str(mm)]
    for define in CAMERA_DEFINES: command.extend(['-D',define])
    command.extend([str(root/'host/apple/Sources/ExactComposition/Composition.swift'),str(root/'host/apple/Sources/ExactComposition/LaunchHooks.swift'),'-o',str(output)])
    subprocess.run(command,check=True)
    original=kit/'14-ExactComposition.o'
    def symbols(path, flags):
        return set(subprocess.check_output(['/usr/bin/nm',*flags,str(path)],text=True).splitlines())
    if symbols(original,['-u']) != symbols(output,['-u']): raise ValueError('Composition dependency symbols differ')
    def api(path):
        lines=subprocess.check_output(['/usr/bin/nm','-gU',str(path)],text=True).splitlines()
        return {line.split()[-1] for line in lines if '_$s16ExactCompositionAAO' in line}
    if not api(original) or api(original)!=api(output): raise ValueError('Composition exports differ')
    print('link kit: compiled verified camera composition')
    return output


if __name__=='__main__': base.main(compile_composition)
