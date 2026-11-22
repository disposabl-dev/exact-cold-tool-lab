import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, realpathSync, mkdirSync, writeFileSync, existsSync, cpSync, rmSync } from 'node:fs';
import { resolve, dirname, basename, join } from 'node:path';

const sdk = process.env.EXACT, appDir = process.env.NATIVE_APP_DIR, temp = process.env.RUNNER_TEMP;
const catalog = resolve(sdk,'packages'), deps = JSON.parse(readFileSync(resolve(appDir,'package.json'),'utf8'));
const names = readdirSync(catalog).filter(name => {
  const declaration = resolve(catalog,name,'apple/exact.json');
  return existsSync(declaration) && JSON.parse(readFileSync(declaration)).targets.includes('ios');
});
for (const name of names) deps.dependencies['@exact/'+name] = 'file:.exact/checkout/packages/'+name;
writeFileSync(resolve(appDir,'package.json'),JSON.stringify(deps));
execFileSync('bun',['install'],{cwd:appDir,stdio:'inherit'});
const {appleImplementations} = await import(resolve(sdk,'js/bake/src/typescript.mjs'));
const {packageCompiler} = await import(resolve(sdk,'host/apple/compose.mjs'));
const manifest = JSON.parse(readFileSync(resolve(appDir,'app.json')));
const app = {dir:appDir,manifest};
const sdkName = 'iphoneos';
const xcrun = (...args) => execFileSync('xcrun',args,{encoding:'utf8'});
const swiftc = xcrun('--sdk',sdkName,'swiftc','--version');
const iphoneSDK = xcrun('--sdk',sdkName,'--show-sdk-path').trim();
const packagesRoot = resolve(process.env.CARGO_TARGET_DIR,'apple-swift/ios-17.0-balanced');
const seam = resolve(sdk,'host/apple/modules/ExactPackage.swift');
const results = {};
for (const name of names) {
  try {
    const extensions = {[name]:'@exact/'+name};
    const packages=appleImplementations(appDir,'ios',extensions);
    if (packages.length!==1) throw Error('Expected one Swift implementation, found '+packages.length);
    const p=packages[0];
    if (p.activity==='alarmkit') p.sources=[...p.sources,resolve(sdk,'host/apple/widget/AlarmAttributes.swift')];
    const packageDir=resolve(temp,'catalog-build',name,'packages');
    mkdirSync(packageDir,{recursive:true});
    const packageCopies=[p.sources.map((source,i)=>{
      const file=resolve(packageDir,'src-'+p.module,i+'-'+basename(source));
      mkdirSync(dirname(file),{recursive:true});
      writeFileSync(file,'#sourceLocation(file: '+JSON.stringify(realpathSync(source))+', line: 1)\n'+readFileSync(source,'utf8'));
      return file;
    })];
    const target=['-target','arm64-apple-ios17.0','-sdk',iphoneSDK];
    packageCompiler({packages,packageDir,packageTargets:new Map([[packageDir,[sdkName,target]]]),packageCopies,
      seam,packagesRoot,swiftc,production:true,distribution:true,ios:true,tv:false,app,extensions,minimum:{ios:'17.0',macos:'14.0'}}).place(packageDir);
    const binary=resolve(packageDir,p.module+'.dylib');
    xcrun('lipo','-verify_arch','arm64',binary);
    if (!/platform\s+(ios|2)\b/i.test(xcrun('vtool','-show-build',binary))) throw Error('unexpected Mach-O platform');
    results[name]={module:p.module,sha256:createHash('sha256').update(readFileSync(binary)).digest('hex')};
    console.log('PASS',name);
  } catch(e) { results[name]={error:String(e.message)}; console.log('FAILED',name,String(e.message).slice(-1800)); }
}
const output=resolve(temp,'catalog-output');
mkdirSync(output,{recursive:true});
const kept=resolve(packagesRoot,'packages-kept');
const sizes={};
for (const d of readdirSync(kept)) {
  if (!/^(ExactPackage|ExactPkg_\w+)-[0-9a-f]{20}$/.test(d))continue;
  const path=resolve(output,d+'.tar.zst');
  execFileSync('tar',['--zstd','-cf',path,'-C',kept,d]);
  sizes[d]=Bun.file(path).size;
}
writeFileSync(resolve(output,'index.json'),JSON.stringify({exact:process.env.EXACT_REF,swiftc,results,sizes},null,2));
const passed=Object.values(results).filter(r=>r.sha256).length;
console.log('Catalog result',passed,'/',names.length,'on arm64 iOS 17');
if (passed!==names.length) process.exitCode=1;
