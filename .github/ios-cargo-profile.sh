#!/usr/bin/env bash
set -euo pipefail
scripts="$GITHUB_WORKSPACE/.github/actions/exact-setup/scripts"
export EXACT_BAKE_OUTPUT="$RUNNER_TEMP/ios-artifacts/bake"
mkdir -p "$EXACT_BAKE_OUTPUT"
cd "$NATIVE_APP_DIR"
bun -e '
const m=await Bun.file("app.json").json();m.id=m.app.id=process.env.IOS_PROFILE_ID;m.name=m.app.name=m.short_name=process.env.IOS_PROFILE_NAME;m.deploy.store.ios="A";m.deploy.signing={key:"mobile",keys:{mobile:"AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="}};m.deploy.channel="base-1";m.deploy.channels={"base-1":"appdrop"};await Bun.write("app.json",JSON.stringify(m,null,2)+"\n");'
IOS_PROFILE_SOURCE_TIMES=1 SETUP_EXACT_REF="$EXACT_REF" IOS_RESTORE_CARGO_SOURCE_MTIMES=1 bun "$scripts/ios-source-times.mjs" apply "$EXACT_IOS_SOURCE_TIMES" "$PWD"
mkdir -p "$RUNNER_TEMP/ios-profbin"
for command in cargo xcrun swift rustc git; do
  real=$(command -v "$command")
  cat > "$RUNNER_TEMP/ios-profbin/$command" <<WRAPPER
#!/bin/bash
start=\$(python3 -c 'import time; print(time.time_ns())')
"$real" "\$@"
result=\$?
end=\$(python3 -c 'import time; print(time.time_ns())')
printf '%s %s %s %s %s\\n' "$command" "\$start" "\$end" "\$result" "\$*" >> "$RUNNER_TEMP/ios-profile.log"
exit "\$result"
WRAPPER
  chmod +x "$RUNNER_TEMP/ios-profbin/$command"
done
export PATH="$RUNNER_TEMP/ios-profbin:$PATH" EXACT_BUILD_STEPS=1
bun exact.mjs ios --device --release --unsigned --archive "$RUNNER_TEMP/ios-profile.ipa" --json 2>&1 | tee "$RUNNER_TEMP/ios-profile-build.log"
unzip -tq "$RUNNER_TEMP/ios-profile.ipa"
