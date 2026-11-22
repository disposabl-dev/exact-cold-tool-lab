#!/usr/bin/env bash
set -euo pipefail
scripts="$GITHUB_WORKSPACE/.github/actions/exact-setup/scripts"
export SETUP_EXACT_REF="$EXACT_REF"
export CARGO_TARGET_DIR="$HOME/.cache/exact-native/cargo"
export EXACT_BAKE_OUTPUT="$RUNNER_TEMP/ios-artifacts/bake"
export EXACT_MOBILE_CHANNEL=base-1 EXACT_BUILD_NUMBER=1
app="$HOME/exact-native/apps/apps"
git worktree add --quiet --detach "$HOME/exact-native" HEAD
cd "$app"
mkdir -p ".exact" "$RUNNER_TEMP/kit-out" "$RUNNER_TEMP/evidence" "$RUNNER_TEMP/capturebin"
ln -s "$EXACT" .exact/checkout
bun install --frozen-lockfile
# The public canonical template is the fixture. No deployment credentials are used.
export CONVEX_ORIGIN=wss://public-seed.invalid
export EXACT_UPDATE_SEED=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
sed -i '' 's/dev.disposabl.exact/dev.disposabl.publicseed/g;s/com.example.apps-8d662a/dev.disposabl.publicseed/g' app.json
bun "$scripts/mobile-updates.mjs" configure ios
unset EXACT_UPDATE_SEED
bundle="$HOME/.cache/exact/publisher/$EXACT_REF"
mkdir -p "$bundle"
curl -fsSL --retry 3 https://github.com/disposabl-dev/exact-cold-tool-lab/releases/download/compiled-inputs-v2/ios-publisher.tar.zst -o "$RUNNER_TEMP/publisher.zst"
echo "2bfa76b5d45615b58a97bd0c87d7591e59a4aecec1ccfd93d2aeeea8ed01a7f0  $RUNNER_TEMP/publisher.zst" | shasum -a 256 -c -
zstd -dc "$RUNNER_TEMP/publisher.zst" | tar -xf - -C "$bundle"
bun "$scripts/ios-baker.mjs" record "$bundle/exact-js-bake" "$RUNNER_TEMP/kit-out/ios-baker.json"
bun "$scripts/ios-baker.mjs" enable "$RUNNER_TEMP/kit-out/ios-baker.json"
bash "$scripts/ios-link-kit-enable.sh"
(cd "$EXACT" && git ls-files -z | xargs -0 touch -t 202001010000)
find "$EXACT" -type d -not -path '*/.git*' -exec touch -t 202001010000 {} +
export IOS_REAL_CARGO=$(command -v cargo)
export IOS_EVIDENCE_PUBLIC_SEED=1 IOS_EVIDENCE_DIR="$RUNNER_TEMP/evidence"
ln -s "$scripts/ios-cargo-capture.sh" "$RUNNER_TEMP/capturebin/cargo"
export PATH="$RUNNER_TEMP/capturebin:$PATH"
bun exact.mjs ios --device --release --unsigned --archive "$RUNNER_TEMP/public-seed.ipa" --json > "$RUNNER_TEMP/public-seed.json"
captures=("$RUNNER_TEMP"/evidence/cargo-ios.*)
[[ ${#captures[@]} == 1 ]]
bash "$scripts/ios-cache-archive.sh" "$CARGO_TARGET_DIR" "$RUNNER_TEMP/kit-out/cargo-ios.zst" "${captures[0]}"
bash "$scripts/ios-link-kit-publish.sh"
tar -C "$HOME/.cache/exact/ios-link-kit/$EXACT_REF" -cf - . | zstd -T0 -3 -o "$RUNNER_TEMP/kit-out/ios-link-kit.zst"
