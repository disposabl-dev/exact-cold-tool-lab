#!/usr/bin/env python3
"""Try the verified camera capsule, then the existing stock capsule."""
import os, subprocess, sys
from pathlib import Path
args=sys.argv[1:]
if not args or args[0] != 'link': raise SystemExit('link only')
scripts=Path(__file__).resolve().parent
camera=os.environ.get('EXACT_CAMERA_LINK_KIT')
if camera and '--kit' in args:
    selected=list(args); selected[selected.index('--kit')+1]=camera
    result=subprocess.run([sys.executable,str(scripts/'ios-selective-link.py'),*selected],capture_output=True,text=True)
    if result.returncode==0:
        print('camera capsule: verified selective link')
        raise SystemExit(0)
    print('camera capsule refused; trying stock kit',file=sys.stderr)
    # A failed link must never leave an output that the next attempt can use.
    if '--out' in args: Path(args[args.index('--out')+1]).unlink(missing_ok=True)
result=subprocess.run([sys.executable,str(scripts/'ios-link-kit.py'),*args])
raise SystemExit(result.returncode)
