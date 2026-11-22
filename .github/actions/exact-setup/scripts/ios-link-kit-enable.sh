#!/usr/bin/env bash
# Opt-in integration for the pinned SDK. Run after other validated SDK setup.
set -euo pipefail
: "${EXACT:?}" "${SETUP_EXACT_REF:?}"
expected_ref=a55c5581c7e1a62cdee1f09367ea2909c74c7292
original=0306f15724f34e8fd3bad29fff511ce16ae829c9625bedddc32e3a2fb684ba6a
patched=d140dc0ab3866a6572ec52c696c7724430e0ad207b1a38df225404638127c99e
script_dir=$(cd "$(dirname "$0")" && pwd)
[[ "$SETUP_EXACT_REF" == "$expected_ref" && $(git -C "$EXACT" rev-parse HEAD) == "$expected_ref" ]] || { echo 'Unsupported Exact revision for iOS link kit' >&2; exit 1; }
file="$EXACT/host/apple/build.mjs"
actual=$(shasum -a 256 "$file" | awk '{print $1}')
if [[ "$actual" == "$original" ]]; then
  git -C "$EXACT" apply --check "$script_dir/ios-link-kit-test-hook.patch"
  git -C "$EXACT" apply "$script_dir/ios-link-kit-test-hook.patch"
elif [[ "$actual" != "$patched" ]]; then
  echo 'Exact iOS linker source differs from the pinned build; not enabling kit' >&2; exit 1
fi
[[ $(shasum -a 256 "$file" | awk '{print $1}') == "$patched" ]] || { echo 'Unexpected patched SDK digest' >&2; exit 1; }
