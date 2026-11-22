#!/usr/bin/env bash
set -euo pipefail
mode=$1
[[ $mode == seed || $mode == fresh ]]
cd "$NATIVE_APP_DIR"
if [[ ${LAB_APERTURE:-0} == 1 ]]; then cp "$GITHUB_WORKSPACE/.github/aperture-public.contract" app.contract; fi
export EXACT_UPDATE_TRUST=production EXACT_UPDATE_GENESIS=1 EXACT_BUILD_NUMBER=1 EXACT_VERSION=0.1.0
export EXACT_MOBILE_CHANNEL=base-1 EXACT_BAKE_OUTPUT="$RUNNER_TEMP/camera-bake"
if [[ $mode == seed ]]; then id=dev.example.publiccameraseed; else id=dev.example.freshcameranotes; fi
export CONVEX_ORIGIN="wss://$mode-camera-fixture.invalid"
python3 - "$id" <<'PY'
import json,sys
p='app.json'; x=json.load(open(p)); x['id']=sys.argv[1]; x['app']['id']=sys.argv[1]; x['host']['android']['id']=sys.argv[1]
open(p,'w').write(json.dumps(x,indent=2)+'\n')
PY
export EXACT_UPDATE_SEED="$(openssl rand -base64 32)"
bun "$GITHUB_WORKSPACE/.github/actions/exact-setup/scripts/mobile-updates.mjs" configure android
unset EXACT_UPDATE_SEED
export EXACT_KEYSTORE="$RUNNER_TEMP/camera-test.p12" EXACT_KEY_ALIAS=android
export EXACT_KEYSTORE_PASSWORD="$(openssl rand -hex 24)"
export EXACT_KEY_PASSWORD="$EXACT_KEYSTORE_PASSWORD"
trap 'rm -f "$EXACT_KEYSTORE"' EXIT
keytool -genkeypair -noprompt -storetype PKCS12 -keystore "$EXACT_KEYSTORE" -storepass:env EXACT_KEYSTORE_PASSWORD -keypass:env EXACT_KEY_PASSWORD -alias android -keyalg RSA -dname "CN=Synthetic $mode Camera Notes" -validity 2 >/dev/null 2>&1
start=$(date +%s%N)
bun exact.mjs android --release --no-install --json > "$RUNNER_TEMP/camera-result.json"
end=$(date +%s%N)
apk=$(jq -er .path "$RUNNER_TEMP/camera-result.json")
"$ANDROID_HOME/build-tools/$ANDROID_BUILD_TOOLS_VERSION/apksigner" verify --print-certs "$apk" > "$RUNNER_TEMP/apk-certificate.txt"
python3 - "$RUNNER_TEMP/apk-certificate.txt" "$EXACT_KEYSTORE" <<'PY'
import re,subprocess,sys,os
lines=open(sys.argv[1]).read().splitlines(); matches=[re.search(r'certificate SHA-256 digest:\s*([0-9a-fA-F]{64})\s*$',x) for x in lines if 'certificate SHA-256 digest:' in x]
key=subprocess.check_output(['keytool','-list','-v','-keystore',sys.argv[2],'-storepass:env','EXACT_KEYSTORE_PASSWORD','-alias','android'],text=True)
expected=re.search(r'^\s*SHA256:\s*([0-9A-F:]+)',key,re.M).group(1).replace(':','').lower()
if not matches or any(m is None or m.group(1).lower()!=expected for m in matches): raise SystemExit('Wrong APK signer')
print('Verified APK certificate SHA-256:',expected)
PY
jq -e --arg id "$id" '.trust=="production" and .compat.inputs.platform=="android" and .compat.inputs.app==$id' "$EXACT_BAKE_OUTPUT"/android-*.build.json >/dev/null
"$ANDROID_HOME/build-tools/$ANDROID_BUILD_TOOLS_VERSION/aapt" dump badging "$apk" | head -1
printf '%s native build: %s ms\n' "$mode" "$(((end-start)/1000000))" | tee -a "$GITHUB_STEP_SUMMARY"
if [[ $mode == fresh ]]; then cp "$apk" "$RUNNER_TEMP/fresh-cameranotes.apk"; fi
