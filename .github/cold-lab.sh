set -euo pipefail
fixed="$HOME/exact-native"
git clone -q --local "$GITHUB_WORKSPACE" "$fixed"
cd "$fixed/apps/apps"
mkdir -p .exact
ln -s "$EXACT" .exact/checkout
bun install --frozen-lockfile
export CARGO_TARGET_DIR="$HOME/.cache/exact-native/cargo"
export EXACT_KEYSTORE="$RUNNER_TEMP/study.p12" EXACT_KEY_ALIAS=android EXACT_KEYSTORE_PASSWORD=fixture-test-key EXACT_KEY_PASSWORD=fixture-test-key
if [[ $PLATFORM == android ]]; then
  keytool -genkeypair -noprompt -storetype PKCS12 -keystore "$EXACT_KEYSTORE" -storepass:env EXACT_KEYSTORE_PASSWORD -keypass:env EXACT_KEY_PASSWORD -alias android -keyalg RSA -dname CN=PublicFixture -validity 2
  # Gradle starts with its dependency cache from the runner image.
  mkdir -p "$HOME/.gradle"
  echo 'org.gradle.caching=true' >> "$HOME/.gradle/gradle.properties"
fi
for version in first second; do
  git restore app.json
  export CONVEX_ORIGIN="wss://$version-fixture-123.convex.cloud" EXACT_BAKE_OUTPUT="$RUNNER_TEMP/$version-bake" EXACT_MOBILE_CHANNEL=base-1
  export EXACT_UPDATE_SEED=$(openssl rand -base64 32)
  sed -i.bak "s/com.example.apps-8d662a/dev.example.$version/g;s/dev.disposabl.exact/dev.example.$version/g" app.json
  rm -f app.json.bak
  bun "$fixed/.github/actions/exact-setup/scripts/mobile-updates.mjs" configure "$PLATFORM"
  unset EXACT_UPDATE_SEED
  export EXACT_VERSION=0.1.0
  start=$(date +%s)
  if [[ $PLATFORM == ios ]]; then
    bun exact.mjs ios --device --release --unsigned --archive "$RUNNER_TEMP/$version.ipa" --json > "$RUNNER_TEMP/result.json"
  else
    bun exact.mjs android --release --no-install --json > "$RUNNER_TEMP/result.json"
  fi
  echo "$PLATFORM $version production build in $(($(date +%s)-start))s" | tee -a "$GITHUB_STEP_SUMMARY"
  du -sh "$CARGO_TARGET_DIR" "$CARGO_TARGET_DIR"/* | sort -h | tail -24
  if [[ $version == first && $PLATFORM == android ]]; then
    # Store compiled dependencies only. Never cache keystores or a deployment's output.
    cd "$CARGO_TARGET_DIR"
    shopt -s nullglob
    targets=(release aarch64-linux-android/release)
    tar -cf - --exclude='incremental' --exclude='apps-android-*' --exclude='libapps_android*' --exclude='apps_android-*' "${targets[@]}" | zstd -T0 -3 -o "$RUNNER_TEMP/cargo-android.zst"
    du -h "$RUNNER_TEMP/cargo-android.zst"
    cd "$fixed/apps/apps"
  fi
done
