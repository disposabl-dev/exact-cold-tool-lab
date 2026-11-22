#!/bin/bash
set -euo pipefail
kit=$1
target=${IOS_CACHE_TARGET:-$HOME/.cache/exact-native/cargo}
products="$target/apple-swift/ios-17.0-balanced/out/Products/Release-iphoneos"
mkdir "$kit/swift-modules"
for module in ExactCore ExactKit ExactUpdates ExactEffects ExactAnimations ExactSvg ExactImages ExactFormaBinding ExactHeavyLeaves ExactNativeViews ExactNavigation ExactSharing; do
  test -d "$products/$module.swiftmodule"
  cp -R "$products/$module.swiftmodule" "$kit/swift-modules/"
done
python3 - "$kit" <<'PY'
import hashlib,json,sys
from pathlib import Path
k=Path(sys.argv[1]); files=sorted(p for p in (k/'swift-modules').rglob('*') if p.is_file())
assert files and all(not p.is_symlink() and p.suffix in ('.swiftmodule','.swiftdoc','.json') for p in files)
(k/'swift-modules.json').write_text(json.dumps({str(p.relative_to(k)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},sort_keys=True))
PY
