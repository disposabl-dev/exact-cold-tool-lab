#!/usr/bin/env bash
# Extend the public template cache using only a tracked synthetic camera app.
set -euo pipefail
: "${EXACT:?}" "${RUNNER_TEMP:?}" "${GITHUB_WORKSPACE:?}" "${GRADLE_USER_HOME:?}" "${EXACT_KEYSTORE:?}"
scripts=$(cd "$(dirname "$0")" && pwd)
fixture="$scripts/../fixtures/android-camera"
app="$HOME/exact-native/apps/apps"
out="$RUNNER_TEMP/kit-out"
mkdir -p "$out"
[[ ${GITHUB_REPOSITORY:-} == disposabl-dev/exact-cold-tool-lab && -d "$app/.exact" ]] || exit 1
(cd "$GRADLE_USER_HOME" && find caches -type f -print | LC_ALL=C sort > "$RUNNER_TEMP/android-camera-before.txt")
cp -R "$fixture"/. "$app/"
cd "$app"
python3 - <<'PY_ID'
import json
p='app.json'; x=json.load(open(p)); x['id']='dev.example.publiccameraseed'; x['app']['id']=x['id']; x['host']['android']['id']=x['id']; open(p,'w').write(json.dumps(x,indent=2)+'\n')
PY_ID
bun install --frozen-lockfile
export CONVEX_ORIGIN=wss://public-camera-fixture.invalid EXACT_UPDATE_TRUST=production EXACT_UPDATE_GENESIS=1
export EXACT_MOBILE_CHANNEL=base-1 EXACT_BUILD_NUMBER=1 EXACT_VERSION=0.1.0
export EXACT_BAKE_OUTPUT="$RUNNER_TEMP/public-camera-bake"
export EXACT_UPDATE_SEED="$(openssl rand -base64 32)"
bun "$scripts/mobile-updates.mjs" configure android
unset EXACT_UPDATE_SEED
bun exact.mjs android --release --no-install --json > "$RUNNER_TEMP/public-camera-result.json"
python3 "$scripts/android-camera-vet.py" "$RUNNER_TEMP/android-camera-vetted"
python3 - "$RUNNER_TEMP/android-camera-vetted" "$RUNNER_TEMP/android-camera-before.txt" <<'PY'
import pathlib, sys
root=pathlib.Path(sys.argv[1]); old=set(pathlib.Path(sys.argv[2]).read_text().splitlines())
for path in root.rglob('*'):
    if path.is_file() and path.relative_to(root).as_posix() in old:
        path.unlink()
PY
tar -cf - -C "$RUNNER_TEMP/android-camera-vetted" caches | zstd -T0 -3 -o "$out/cargo-gradle-camera.zst"
