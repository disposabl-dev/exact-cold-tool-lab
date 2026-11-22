#!/usr/bin/env bash
# Run Cargo in the same absolute layout as the public compiler-input build.
set -euo pipefail
platform=$1
case "$platform" in android|ios) ;; *) exit 2 ;; esac
fixed="$HOME/exact-native"
target="$HOME/.cache/exact-native/cargo"
git worktree add --quiet --detach "$fixed" HEAD
mkdir -p "$target" "$fixed/apps/apps/.exact"
ln -s "$EXACT" "$fixed/apps/apps/.exact/checkout"
(cd "$fixed/apps/apps" && bun install --frozen-lockfile)
{
  echo "NATIVE_APP_DIR=$fixed/apps/apps"
  echo "CARGO_TARGET_DIR=$target"
  echo 'CARGO_PROFILE_RELEASE_LTO=off'
  echo 'CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16'
  echo 'CARGO_PROFILE_BALANCED_LTO=off'
  echo 'CARGO_PROFILE_SIZE_LTO=off'
} >> "$GITHUB_ENV"

# A fresh git checkout gives immutable SDK sources today's mtime. Cargo uses
# mtimes for local crates; only normalize files from the known pinned SDK.
[[ $(git -C "$EXACT" rev-parse HEAD) == "$EXACT_REF" ]]
if [[ $platform == android ]]; then
  python3 - "$EXACT/scripts/cargo-check.mjs" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text()
before = "return ['apple','ios','macos','tvos','android'].includes(kind) && profile === 'release'"
after = """if (kind === 'android' && profile === 'release') return ['--config','profile.release.lto="off"','--config','profile.release.codegen-units=16'];
  """ + before
if text.count(before) != 1:
    raise SystemExit("Unsupported Exact revision for cached Android release linking")
path.write_text(text.replace(before, after))
PY
fi
# Frozen Cargo inputs come only from the public fixture release.
archive="cargo-$platform.zst"
work=$(mktemp -d "$RUNNER_TEMP/native-cache.XXXXXX")
trap 'rm -rf "$work"' EXIT
base="$NATIVE_CACHE_RELEASE"
restore() (
  archive=$1
  output=$2
  mkdir -p "$output"
  cd "$work"
  curl -fsSL --retry 3 "$base/$archive.sha256" -o "$archive.sha256"
  curl -fsSL --retry 3 "$base/$archive" -o "$archive"
  shasum -a 256 -c "$archive.sha256"
  zstd -dc "$archive" | tar -xf - -C "$output"
)
restore "$archive" "$target" &
cargo_pid=$!
if [[ $platform == android ]]; then
  restore cargo-gradle.zst "$HOME/.gradle" &
  gradle_pid=$!
fi
# Cargo watches some directories as well as the individual SDK sources.
(cd "$EXACT" && git ls-files -z | xargs -0 touch -t 202001010000)
find "$EXACT" -type d -not -path '*/.git*' -exec touch -t 202001010000 {} +
wait "$cargo_pid"
if [[ $platform == android ]]; then
  wait "$gradle_pid"
  python3 - "$target" "$EXACT" <<'PYTIME'
import json, os, re, sys
from pathlib import Path
target, sdk = map(Path, sys.argv[1:])
for name, sub in [('wgpu-hal', 'vendor/wgpu-hal'), ('exact-logic', 'logic')]:
    package = sdk / sub
    for path in target.glob('**/.fingerprint/' + name + '-*/run-build-script-*.json'):
        locals = json.loads(path.read_text()).get('local', [])
        for fact in locals:
            if 'Precalculated' not in fact: continue
            value = fact['Precalculated']; print(name, value)
            match = re.fullmatch(r'(\d+)\.(\d+) \(([^)]+)\)', value)
            if not match: continue
            file = (package / match[3]).resolve()
            if not file.is_relative_to(package) or not file.is_file(): continue
            ns = int(match[1])*10**9 + int(match[2].ljust(9, '0'))
            for item in package.rglob('*'):
                if item.is_file() and not item.is_symlink(): os.utime(item, ns=(ns-10**9,ns-10**9))
            os.utime(file, ns=(ns, ns))
PYTIME
  echo 'org.gradle.caching=true' >> "$HOME/.gradle/gradle.properties"
fi
if [[ "$platform" == ios && -z "${EXACT_PUBLISH_TOOLS:-}" ]]; then
  publisher="$RUNNER_TEMP/ios-publisher"
  mkdir -p "$publisher"
  (cd "$work" &&
    curl -fsSL --retry 3 "$base/ios-publisher.tar.zst.sha256" -o ios-publisher.tar.zst.sha256 &&
    curl -fsSL --retry 3 "$base/ios-publisher.tar.zst" -o ios-publisher.tar.zst &&
    shasum -a 256 -c ios-publisher.tar.zst.sha256 &&
    zstd -dc ios-publisher.tar.zst | tar -xf - -C "$publisher")
  echo "EXACT_PUBLISH_TOOLS=$publisher" >> "$GITHUB_ENV"
fi
