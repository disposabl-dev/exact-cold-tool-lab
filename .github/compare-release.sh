#!/usr/bin/env bash
set -euo pipefail
file=android-production.apk
tag="delivery-benchmark-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
repo="$GITHUB_REPOSITORY"
[[ "$repo" == disposabl-dev/exact-cold-tool-lab ]]
expected=$(sha256sum "$file" | cut -d' ' -f1)
testdir=$(mktemp -d)
trap 'rm -rf "$testdir"' EXIT
(cd "$testdir" && npm pack --silent appdrop@0.8.0 && tar -xzf appdrop-0.8.0.tgz)
stamp() { python3 -c 'import time;print(time.time_ns()//1000000)'; }
echo "RELEASE_CREATE_START $(stamp)"
gh release create "$tag" --target "$GITHUB_SHA" --title "Synthetic delivery fixture $GITHUB_RUN_ID" --notes 'Disposable signed Android benchmark. The backend is a synthetic example.' --prerelease > /dev/null
echo "RELEASE_CREATED $(stamp)"
gh release upload "$tag" "$file"
echo "RELEASE_UPLOADED $(stamp)"
release=$(gh api "repos/$repo/releases/tags/$tag" --jq '.assets[0]|[.state,.digest,.browser_download_url]|@tsv')
IFS=$'\t' read -r state digest url <<< "$release"
[[ "$state" == uploaded && "$digest" == "sha256:$expected" ]]
curl -qfsSL "$url" -o "$testdir/github.apk"
[[ $(sha256sum "$testdir/github.apk"|cut -d' ' -f1) == "$expected" ]]
echo "RELEASE_ANONYMOUS_DOWNLOAD_VERIFIED $(stamp) $url"
echo "APPDROP_START $(stamp)"
env -u GH_TOKEN bun --preload ../lab/.github/trace-fetch.mjs "$testdir/package/cli.mjs" "$file" --json > "$testdir/result"
echo "APPDROP_ACCEPTED $(stamp)"
id=$(python3 -c 'import json,sys; s=open(sys.argv[1]).read(); print(json.loads(s[s.index("{"):])["id"])' "$testdir/result")
[[ "$id" =~ ^[a-zA-Z0-9]+$ ]]
curl -qfsSL "https://appdrop.app/api/drops/$id/file?revision=1" -o "$testdir/appdrop.apk"
[[ $(sha256sum "$testdir/appdrop.apk"|cut -d' ' -f1) == "$expected" ]]
echo "APPDROP_ANONYMOUS_DOWNLOAD_VERIFIED $(stamp) https://appdrop.app/d/$id"
grep '^HTTP ' "$testdir/result"
echo "BOTH_SIGNED_APK_SHA256 $expected"
