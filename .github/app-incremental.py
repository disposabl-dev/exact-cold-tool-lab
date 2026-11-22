#!/usr/bin/env python3
import os
import sys
from pathlib import Path
args = sys.argv[2:]
def val(option):
    return args[args.index(option)+1] if option in args else None
if val('--crate-name') == 'apps_android' and val('--target') == 'aarch64-linux-android':
    root = Path(os.environ['CARGO_TARGET_DIR'])/'app-release-incremental'
    root.mkdir(parents=True,exist_ok=True)
    args += ['-C','incremental='+str(root)]
    print('Measuring generated Android release crate compiler units', file=sys.stderr)
os.execv(sys.argv[1], [sys.argv[1], *args])
