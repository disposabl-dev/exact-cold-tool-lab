#!/usr/bin/env bash
set -euo pipefail
lane=$1
scripts="$GITHUB_WORKSPACE/.github/actions/exact-setup/scripts"
cd "$NATIVE_APP_DIR"
export SETUP_EXACT_REF="$EXACT_REF" EXACT_BAKE_OUTPUT="$RUNNER_TEMP/ios-artifacts/bake"
export EXACT_VERSION=0.1.0
if [[ $lane == producer ]]; then
  export APP_ID=dev.disposabl.publicseed PUBLIC_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= CONVEX_ORIGIN=wss://public-seed.invalid
  unset EXACT_LINK_KIT_PROOF EXACT_LINK_KIT
else
  export APP_ID=dev.disposabl.independentcamera CONVEX_ORIGIN=wss://different-camera.invalid
  PUBLIC_KEY=$(bun -e "import {generateKeyPairSync} from 'node:crypto'; console.log(generateKeyPairSync('ed25519').publicKey.export({type:'spki',format:'der'}).subarray(-32).toString('base64'))")
  export PUBLIC_KEY EXACT_LINK_KIT="$RUNNER_TEMP/camera-kit"
  tar -xf "$RUNNER_TEMP/camera-kit.tar" -C "$RUNNER_TEMP"
  export EXACT_LINK_KIT_PROOF="$scripts/ios-selective-link.py"
  sed -i '' 's/Capture a moment/Independent camera capture/' app.contract
fi
bun -e 'const p="app.json",a=await Bun.file(p).json(); a.id=a.app.id=process.env.APP_ID; a.deploy.store.ios="A"; a.deploy.signing={key:"mobile",keys:{mobile:process.env.PUBLIC_KEY}}; a.deploy.channel="base-1"; a.deploy.channels={"base-1":"appdrop"}; await Bun.write(p,JSON.stringify(a,null,2)+"\n")'
bash "$scripts/native-build.sh" ios 2>&1 | tee "$RUNNER_TEMP/$lane-build.log"
python3 - <<'PY'
import json,os,plistlib,zipfile
from pathlib import Path
ipa=Path(os.environ['RUNNER_TEMP'])/'ios-artifacts/apps.ipa'
with zipfile.ZipFile(ipa) as z:
 name=next(f for f in z.namelist() if f.endswith('.app/Info.plist') and f.count('/')==2)
 info=plistlib.loads(z.read(name)); assert info['CFBundleIdentifier']==os.environ['APP_ID'] and info['NSCameraUsageDescription']
 receipt=json.loads(z.read(name.rsplit('/',1)[0]+'/receipt.json'))['build']
 assert receipt['trust']=='production' and receipt['compat']['inputs']['keys']=={'mobile':os.environ['PUBLIC_KEY']}
 assert os.environ['CONVEX_ORIGIN'] in receipt['compat']['inputs']['grantCeiling'] and 'device.camera cameraPurpose' in receipt['compat']['inputs']['grantCeiling']
PY
if [[ $lane == producer ]]; then
  bash "$scripts/ios-link-kit-publish.sh"
  cp -R "$HOME/.cache/exact/ios-link-kit/$EXACT_REF" "$RUNNER_TEMP/camera-kit"
  bash "$scripts/ios-selective-capture.sh" "$RUNNER_TEMP/camera-kit"
  tar -C "$RUNNER_TEMP" -cf "$RUNNER_TEMP/camera-kit.tar" camera-kit
else
  grep -F 'compiled verified camera composition' "$RUNNER_TEMP/$lane-build.log"
  grep -F 'new production executable linked from verified inputs' "$RUNNER_TEMP/$lane-build.log"
fi
