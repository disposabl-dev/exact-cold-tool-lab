#!/usr/bin/env bash
set -euo pipefail
script="$GITHUB_WORKSPACE/.github/actions/exact-setup/scripts"
assets="$GITHUB_WORKSPACE/.github/snapshot-assets.json"
url="https://github.com/disposabl-dev/disposabl-exact/releases/download/v9-exact-$EXACT_REF-bun-1.4.5"
build_home="$HOME"
sdk="$HOME/work/_temp/exact-sdk"
file="$RUNNER_TEMP/android.squashfs"
image="$RUNNER_TEMP/public-image"
mountpoint="$RUNNER_TEMP/shared-tools"
case "$1" in
build)
  mkdir -p "$image/home" "$image/gradle" "$image/cargo" "$sdk"
  extract_asset() {
    local name=$1 dest=$2
    shift 2
    python3 "$script/fetch-input.py" "$url" "$assets" "$name" "$RUNNER_TEMP/$name"
    zstd -dc "$RUNNER_TEMP/$name" | tar -xf - -C "$dest" "$@"
  }
  base="exact-$EXACT_REF"
  extract_asset "$base-android-Linux-X64-bun-1.4.5.tar.zst" "$image/home" & ids=($!)
  extract_asset "$base-web-Linux-X64-bun-1.4.5.tar.zst" "$image/home" ".cache/exact/publisher/$EXACT_REF" & ids+=($!)
  extract_asset cargo-gradle.zst "$image/gradle" & ids+=($!)
  extract_asset cargo-android.zst "$image/cargo" & ids+=($!)
  extract_asset sdk.tar.zst "$sdk" & ids+=($!)
  for pid in "${ids[@]}"; do wait "$pid"; done
  git -C "$sdk" reset --hard -q HEAD
  (cd "$sdk" && bun install --frozen-lockfile)
  EXACT="$sdk" bash "$script/android-fast-profile.sh"
  mv "$sdk" "$image/sdk"
  mksquashfs "$image" "$file" -noappend -comp zstd -Xcompression-level 3 -b 262144 -no-progress
  ls -lh "$file"
  sha256sum "$file" | cut -d' ' -f1 > "$file.sha256"
  ;;
mount)
  mkdir -p "$mountpoint" "$RUNNER_TEMP/overlays"
  sudo mount -t squashfs -o loop,ro,nodev,nosuid "$file" "$mountpoint"
  overlay() {
    local lower=$1 dest=$2 n=$3
    local base="$RUNNER_TEMP/overlays/$n"
    mkdir -p "$base/upper" "$base/work" "$dest"
    sudo mount -t overlay overlay -o "lowerdir=$lower,upperdir=$base/upper,workdir=$base/work" "$dest"
  }
  overlay "$mountpoint/sdk" "$sdk" sdk
  overlay "$mountpoint/cargo" "$HOME/.cache/exact-native/cargo" native
  overlay "$mountpoint/gradle" "$HOME/.gradle" gradle
  idx=0
  for rel in .rustup/toolchains/* .cargo/hermes-lean-sys .cargo/registry/cache .cargo/registry/index .cargo/git/db; do
    if [[ "$rel" == ".rustup/toolchains/"* ]]; then continue; fi
    [[ -d "$mountpoint/home/$rel" ]] || continue
    overlay "$mountpoint/home/$rel" "$HOME/$rel" "leaf$((++idx))"
  done
  # Keep the runner's installed components and rustup's temp and toolchain directories on one filesystem.
  original="$RUNNER_TEMP/runner-rustup"
  mkdir -p "$original"
  sudo mount --bind "$HOME/.rustup" "$original"
  overlay "$mountpoint/home/.rustup:$original" "$HOME/.rustup" rust
  overlay "$mountpoint/home/.cache/exact/publisher" "$HOME/.cache/exact/publisher" publisher
  [[ $(git -C "$sdk" rev-parse HEAD) == "$EXACT_REF" ]]
  app="$HOME/exact-native/apps/apps"
  git worktree add --quiet --detach "$HOME/exact-native" HEAD
  mkdir -p "$app/.exact"
  ln -s "$sdk" "$app/.exact/checkout"
  (cd "$app" && bun install --frozen-lockfile)
  printf 'org.gradle.caching=true\n' >> "$HOME/.gradle/gradle.properties"
  for path in "$ANDROID_HOME/build-tools/37.0.0" "$ANDROID_HOME/platforms/android-37.2" "$ANDROID_HOME/ndk/27.3.13750724"; do test -s "$path/source.properties"; done
  {
    echo "EXACT=$sdk"
    echo "NATIVE_APP_DIR=$app"
    echo "CARGO_TARGET_DIR=$HOME/.cache/exact-native/cargo"
    echo "EXACT_PUBLISH_TOOLS=$HOME/.cache/exact/publisher/$EXACT_REF"
    echo "ANDROID_NDK_HOME=$ANDROID_HOME/ndk/27.3.13750724"
    echo "ANDROID_BUILD_TOOLS_VERSION=37.0.0"
    echo 'CARGO_PROFILE_RELEASE_LTO=off'
    echo 'CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16'
  } >> "$GITHUB_ENV"
  ;;
esac
