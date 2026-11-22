import json, os, sys
from pathlib import Path
_, command, target, output = sys.argv
assert command == "record"
root = Path(target)
stats = {}
for directory in ("balanced", "aarch64-apple-darwin/balanced", "aarch64-apple-ios/balanced", "bake-compiled"):
    for base, _, names in os.walk(root / directory, followlinks=False):
        for n in names:
            p = Path(base) / n
            if not p.is_symlink() and p.is_file():
                st = p.stat()
                stats[str(p.relative_to(root))] = [st.st_size, st.st_mtime_ns]
Path(output).write_text(json.dumps(stats))
