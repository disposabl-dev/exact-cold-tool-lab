#!/bin/bash
set -euo pipefail
kit=$1
python3 - "$kit" <<'PY'
import hashlib,json,sys
from pathlib import Path
k=Path(sys.argv[1]); rec=json.loads((k/'kit.json').read_text()); facts=rec['facts']['compat']
assert facts['linked']==['router','share','effects','io','modules','svg','images','native_views','navigation']
assert facts['trust']=='production' and 'device.camera cameraPurpose' in facts['grantCeiling']
modules=json.loads((k/'swift-modules.json').read_text()); assert modules
for name,sha in modules.items():
 p=k/name; assert p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==sha
assert hashlib.sha256((k/'14-ExactComposition.o').read_bytes()).hexdigest()==rec['digests']['14-ExactComposition.o']
PY
map="$RUNNER_TEMP/CExactLaunch.modulemap"
printf 'module CExactLaunch { umbrella header "%s/host/apple/Sources/CExactLaunch/include/CExactLaunch.h" export * }\n' "$EXACT" > "$map"
out="$RUNNER_TEMP/recompiled-composition.o"
xcrun --sdk iphoneos swiftc -target arm64-apple-ios17.0 -sdk "$(xcrun --sdk iphoneos --show-sdk-path)" -module-name ExactComposition -emit-object -whole-module-optimization -O -parse-as-library -I "$kit/swift-modules" -I "$EXACT/host/apple/Sources/CExact" -Xcc "-fmodule-map-file=$map" -D EXACT_APP_UPDATING -D EXACT_LINK_ROUTER -D EXACT_LINK_SHARE -D EXACT_LINK_EFFECTS -D EXACT_LINK_IO -D EXACT_LINK_MODULES -D EXACT_LINK_SVG -D EXACT_LINK_IMAGES -D EXACT_LINK_NATIVE_VIEWS -D EXACT_LINK_NAVIGATION "$EXACT/host/apple/Sources/ExactComposition/Composition.swift" "$EXACT/host/apple/Sources/ExactComposition/LaunchHooks.swift" -o "$out"
nm -u "$kit/14-ExactComposition.o" | sort > "$RUNNER_TEMP/original.symbols"
nm -u "$out" | sort > "$RUNNER_TEMP/recompiled.symbols"
diff -u "$RUNNER_TEMP/original.symbols" "$RUNNER_TEMP/recompiled.symbols"
nm -gU "$kit/14-ExactComposition.o" | awk '{print $NF}' | grep -F '_$s16ExactCompositionAAO' | sort > "$RUNNER_TEMP/original-defined.symbols"
nm -gU "$out" | awk '{print $NF}' | grep -F '_$s16ExactCompositionAAO' | sort > "$RUNNER_TEMP/recompiled-defined.symbols"
diff -u "$RUNNER_TEMP/original-defined.symbols" "$RUNNER_TEMP/recompiled-defined.symbols"
cp "$out" "$kit/14-ExactComposition.o"
python3 - "$kit" <<'PY'
import hashlib,json,sys
from pathlib import Path
k=Path(sys.argv[1]); p=k/'kit.json'; rec=json.loads(p.read_text()); rec['digests']['14-ExactComposition.o']=hashlib.sha256((k/'14-ExactComposition.o').read_bytes()).hexdigest(); p.write_text(json.dumps(rec,sort_keys=True,indent=2))
PY
echo 'Recompiled camera composition: original defined and undefined symbols match'
