#!/usr/bin/env bash
set -euo pipefail
scripts="$GITHUB_WORKSPACE/.github/actions/exact-setup/scripts"
export SETUP_EXACT_REF="$EXACT_REF" CARGO_TARGET_DIR="$HOME/.cache/exact-native/cargo"
export EXACT_BAKE_OUTPUT="$RUNNER_TEMP/ios-artifacts/bake" EXACT_MOBILE_CHANNEL=base-1 EXACT_BUILD_NUMBER=1 EXACT_VERSION=0.1.0
export CONVEX_ORIGIN=wss://consumer-seed.invalid
app="$HOME/exact-native/apps/apps"
kitout="$RUNNER_TEMP/ios-verified"
mkdir -p "$kitout" "$HOME/.cache/exact/publisher/$EXACT_REF"
gh release download ios-verified-v1 -R disposabl-dev/exact-cold-tool-lab --dir "$kitout"
(cd "$kitout" && for checksum in *.sha256; do shasum -a 256 -c "$checksum"; done)
curl -fsSL --retry 3 https://github.com/disposabl-dev/exact-cold-tool-lab/releases/download/compiled-inputs-v2/ios-publisher.tar.zst -o "$RUNNER_TEMP/publisher.zst"
echo "2bfa76b5d45615b58a97bd0c87d7591e59a4aecec1ccfd93d2aeeea8ed01a7f0  $RUNNER_TEMP/publisher.zst" | shasum -a 256 -c -
zstd -dc "$RUNNER_TEMP/publisher.zst" | tar -xf - -C "$HOME/.cache/exact/publisher/$EXACT_REF"
bun "$scripts/ios-baker.mjs" enable "$kitout/ios-baker.json"
export EXACT_IOS_BAKER_PATH="$HOME/.cache/exact/publisher/$EXACT_REF/exact-js-bake" EXACT_IOS_BAKER_SHA256="$(shasum -a 256 "$HOME/.cache/exact/publisher/$EXACT_REF/exact-js-bake" | cut -d ' ' -f1)"
bash "$scripts/ios-link-kit-enable.sh"
python3 "$scripts/ios-cache-restore.py" "$kitout/cargo-ios.zst" "$CARGO_TARGET_DIR" "$(cut -d ' ' -f1 "$kitout/cargo-ios.zst.sha256")"
export EXACT_LINK_KIT="$HOME/.cache/exact/ios-link-kit/$EXACT_REF" EXACT_LINK_KIT_PROOF="$scripts/ios-link-kit.py"
mkdir -p "$EXACT_LINK_KIT"
zstd -dc "$kitout/ios-link-kit.zst" | tar -xf - -C "$EXACT_LINK_KIT"
git worktree add --quiet --detach "$HOME/exact-native" HEAD
cd "$app"
mkdir -p .exact
ln -s "$EXACT" .exact/checkout
bun install --frozen-lockfile
# Preserve the real template and its Convex grant; change only public fixtures.
bun -e '
  const p="app.json", app=await Bun.file(p).json();
  app.id="dev.disposabl.publicconsumer"; app.name="Public Consumer"; app.app.id=app.id; app.app.name=app.name;
  app.deploy.store.ios="A"; app.deploy.signing={key:"mobile",keys:{mobile:"AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="}};
  app.deploy.channel="base-1"; app.deploy.channels={"base-1":"appdrop"};
  await Bun.write(p,JSON.stringify(app,null,2)+"\n");
  const c="app.contract", text=await Bun.file(c).text(); await Bun.write(c,text.replace("text \"App\" role=", "text \"Consumer\" role="));
  const t="app.ts", source=await Bun.file(t).text(); await Bun.write(t,source.replace("Hello from ${name}.","Greetings from ${name}."));
'
# Generate the stock app workspace, then unpack vendored dependency sources.
APP_DIR="$app" bun -e 'const {resolveApp}=await import(`${process.env.EXACT}/scripts/app.mjs`); resolveApp(process.env.APP_DIR).rust();'
cargo fetch --locked --manifest-path "$app/.exact/shells/Cargo.toml"
IOS_RESTORE_CARGO_SOURCE_MTIMES=1 bun "$scripts/ios-source-times.mjs" apply "$kitout/ios-source-times.json" "$app"
# Capture Cargo's raw fingerprint diagnostics before Exact's progress filter.
mkdir -p "$RUNNER_TEMP/cargo-trace-bin"
export IOS_TRACE_REAL_CARGO=$(command -v cargo)
cat > "$RUNNER_TEMP/cargo-trace-bin/cargo" <<'TRACE'
#!/usr/bin/env bash
set -o pipefail
export CARGO_LOG=cargo::core::compiler::fingerprint=info
printf 'command: cargo %s\n' "$*" >> "$RUNNER_TEMP/cargo-fingerprint.raw"
"$IOS_TRACE_REAL_CARGO" "$@" 2> >(tee -a "$RUNNER_TEMP/cargo-fingerprint.raw" >&2)
TRACE
chmod +x "$RUNNER_TEMP/cargo-trace-bin/cargo"
export PATH="$RUNNER_TEMP/cargo-trace-bin:$PATH"
{ rustc -vV; cargo -V; xcodebuild -version; env | LC_ALL=C sort | grep -E '^(CARGO_|RUST|EXACT_|MACOSX_|IPHONEOS_|DEVELOPER_DIR|HOME=|TMPDIR=)' | sed '/TOKEN/d;/SECRET/d;/KEYSTORE/d;/PASSWORD/d'; } > "$RUNNER_TEMP/cargo-env.log"
start=$(date +%s)
bun exact.mjs ios --device --release --unsigned --archive "$RUNNER_TEMP/consumer.ipa" --json 2>&1 | tee "$RUNNER_TEMP/consumer-build.log"
echo "consumer build wall: $(($(date +%s)-start))s" | tee -a "$GITHUB_STEP_SUMMARY"
unzip -tq "$RUNNER_TEMP/consumer.ipa"
grep -F 'link kit: new production executable linked from verified inputs' "$RUNNER_TEMP/consumer-build.log"
jq -e '.platform=="ios" and .build.trust=="production" and .build.compat.inputs.app=="dev.disposabl.publicconsumer"' "$RUNNER_TEMP/consumer.receipt.json" >/dev/null
