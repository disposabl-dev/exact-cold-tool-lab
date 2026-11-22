#!/bin/bash
set -u
tool=${0##*/}
# The lab records timings for read-only host queries. Build and signing commands
# run unmodified under the system tool; no compiler output is synthesized.
case "$tool:$*" in
  "xcrun:--sdk iphoneos --show-sdk-path"|"xcrun:--sdk iphoneos --show-sdk-version"|"xcrun:--sdk iphoneos swiftc --version"|"xcrun:-sdk iphoneos metal --version"|"xcrun:-sdk macosx metal --version"|"xcodebuild:-version"|"swift:--version") ;;
  *) exec "/usr/bin/$tool" "$@" ;;
esac
dir="$RUNNER_TEMP/host-query"
mkdir -p "$dir"
# Each job is isolated and pins Xcode; SDKROOT can vary between subprocesses.
key=$(printf '%s\0' "$tool" "${DEVELOPER_DIR:-}" "${SDKROOT:-}" "${TOOLCHAINS:-}" "${PATH:-}" "$@" | shasum -a 256 | cut -c1-64)
answer="$dir/$key"
if [[ "$PROFILE_MODE" == reuse && -f "$answer/status" ]]; then
  cat "$answer/out"; cat "$answer/err" >&2; echo "HIT $tool $*" >> "$dir/calls"; exit "$(cat "$answer/status")"
fi
tmp=$(mktemp -d "$dir/build.XXXXXX")
/usr/bin/time -p -o "$tmp/time" "/usr/bin/$tool" "$@" > "$tmp/out" 2> "$tmp/err"
status=$?
cat "$tmp/out"; cat "$tmp/err" >&2
echo "$status" > "$tmp/status"
echo "RUN $tool $* $(head -1 "$tmp/time")" >> "$dir/calls"
if [[ "$PROFILE_MODE" == reuse && ! -e "$answer" ]]; then mv "$tmp" "$answer"; fi
exit "$status"
