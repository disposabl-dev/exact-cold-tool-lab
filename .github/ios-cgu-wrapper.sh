#!/usr/bin/env bash
set -euo pipefail
args=("$@")
if [[ ${IOS_TEST_CGU:-0} == 16 && ${1:-} == rustc ]]; then
  pkg='' profile='' archive=0
  for ((i=0;i<${#args[@]};i++)); do
    [[ ${args[i]} != -p ]] || pkg=${args[i+1]}
    [[ ${args[i]} != --profile ]] || profile=${args[i+1]}
    [[ ${args[i]} != staticlib ]] || archive=1
  done
  if [[ $archive == 1 && $profile == balanced && $pkg =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Testing package-specific codegen units for $pkg" >&2
    args+=(--config "profile.balanced.package.\"$pkg\".codegen-units=16")
  fi
fi
exec "$IOS_REAL_CARGO" "${args[@]}"
