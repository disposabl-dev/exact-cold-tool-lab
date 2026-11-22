#!/usr/bin/env bash
# Build a public synthetic iOS fixture at the same paths used by the consumer.
# Run only on a disposable publisher machine, before the real app is staged.
set -euo pipefail
: "${EXACT:?}" "${RUNNER_TEMP:?}" "${HOME:?}"
app="${IOS_CACHE_ROOT:-$HOME/exact-native}/apps/apps"
target="${IOS_CACHE_TARGET:-$HOME/.cache/exact-native/cargo}"
[[ "$app" == /* && "$target" == /* ]] || { echo "Seed paths must be absolute" >&2; exit 1; }
bake="$RUNNER_TEMP/ios-artifacts/bake"
[[ "$(uname -s):$(uname -m)" == Darwin:arm64 ]] || { echo 'Requires an Apple Silicon Mac' >&2; exit 1; }
[[ ! -e "$app" && ! -e "$target" && ! -e "$bake" ]] || { echo 'Seed app, target and bake paths must be absent' >&2; exit 1; }
mkdir -p "$(dirname "$app")" "$(dirname "$target")" "$(dirname "$bake")"
# Optionally retain the real JSON emitted by Cargo for the public seed.
# Consumers must validate the captured graph and source inputs before reuse.
if [[ "${IOS_CAPTURE_EVIDENCE:-0}" == 1 ]]; then
  real_cargo=$(command -v cargo)
  wrapper_dir="$RUNNER_TEMP/ios-cargo-capture-bin"
  [[ ! -e "$wrapper_dir" ]] || { echo 'Cargo capture directory already exists' >&2; exit 1; }
  mkdir -p "$wrapper_dir"
  ln -s "$(cd "$(dirname "$0")" && pwd)/ios-cargo-capture.sh" "$wrapper_dir/cargo"
  export PATH="$wrapper_dir:$PATH" IOS_REAL_CARGO="$real_cargo" IOS_EVIDENCE_DIR="${IOS_EVIDENCE_DIR:-$RUNNER_TEMP/ios-evidence}" IOS_EVIDENCE_PUBLIC_SEED=1
fi
# A fixed, public key and endpoint only. No app or account secrets enter this process.
clean=(env -i "HOME=$HOME" "PATH=$PATH" "TMPDIR=${TMPDIR:-/tmp}" "EXACT=$EXACT" "CARGO_TARGET_DIR=$target" "EXACT_BAKE_OUTPUT=$bake" "EXACT_UPDATE_TRUST=production" "EXACT_UPDATE_GENESIS=1" "CONVEX_ORIGIN=wss://seed.invalid")
[[ -z "${DEVELOPER_DIR:-}" ]] || clean+=("DEVELOPER_DIR=$DEVELOPER_DIR")
if [[ -n "${EXACT_IOS_BAKER_PATH:-}" || -n "${EXACT_IOS_BAKER_SHA256:-}" ]]; then
  : "${EXACT_IOS_BAKER_PATH:?}" "${EXACT_IOS_BAKER_SHA256:?}"
  clean+=("EXACT_IOS_BAKER_PATH=$EXACT_IOS_BAKER_PATH" "EXACT_IOS_BAKER_SHA256=$EXACT_IOS_BAKER_SHA256")
fi
[[ "${IOS_CAPTURE_EVIDENCE:-0}" != 1 ]] || clean+=("IOS_REAL_CARGO=$IOS_REAL_CARGO" "IOS_EVIDENCE_DIR=$IOS_EVIDENCE_DIR" "IOS_EVIDENCE_PUBLIC_SEED=1")
# The consumer must use the identical profile setting to reuse Cargo products.
[[ "${IOS_CACHE_NO_LTO:-0}" != 1 ]] || clean+=("CARGO_PROFILE_BALANCED_LTO=off")
"${clean[@]}" bun "$EXACT/scripts/exact.mjs" new "$app" --name Apps --bundle-id dev.disposabl.publicseed --with ios
mkdir -p "$app/assets"
cp "${GITHUB_WORKSPACE:?}/apps/apps/assets/icon.png" "$app/assets/icon.png"
"${clean[@]}" "APP=$app" bun -e '
  const path = `${process.env.APP}/app.json`;
  const app = await Bun.file(path).json();
  app.env = ["CONVEX_ORIGIN"];
  app.icons = [{src:"assets/icon.png",type:"image/png",sizes:"1024x1024",purpose:"any"}];
  app.deploy.store.ios = "A";
  app.deploy.signing = {key:"mobile",keys:{mobile:"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="}};
  app.deploy.channel = "base-1";
  app.deploy.channels = {"base-1":"appdrop"};
  await Bun.write(path, JSON.stringify(app, null, 2) + "\n");
  const ts = `${process.env.APP}/app.ts`;
  const source = await Bun.file(ts).text();
  await Bun.write(ts, source.replace(/export const grants = [^;]+;/, "const origin = import.meta.env.CONVEX_ORIGIN;\nexport const grants = `net.websocket ${origin}`;"));
'
(cd "$app" && "${clean[@]}" bun install --frozen-lockfile && "${clean[@]}" bun exact.mjs ios --device --release --unsigned --archive "$RUNNER_TEMP/ios-seed.ipa" --json > "$RUNNER_TEMP/ios-seed-build.json")
# The receipt and IPA describe the synthetic app and are never cache inputs.
# The archive builder must select compiled products only; in particular, exclude
# bake/, clients/, Apple SDKs, Swift/Clang module caches and all *.pcm files.
echo "iOS seed built; compiled target is $target"
