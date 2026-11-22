#!/usr/bin/env python3
"""Restore Cargo's package-wide Precalculated inputs only after content checks.

Run after ios-source-times apply. This adjusts no application files. Git-tracked
SDK bytes must match their pinned blob or a recorded, SHA-checked SDK input.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

if len(sys.argv) != 5:
    raise SystemExit('usage: ios-cargo-precalculated.py SDK APP_CARGO_TOML TARGET SOURCE_TIMES')
sdk, app_manifest, target, source_manifest = map(lambda x: Path(x).resolve(), sys.argv[1:])
ref = os.environ.get('SETUP_EXACT_REF', '')
if not re.fullmatch(r'[0-9a-f]{40}', ref) or subprocess.check_output(['git','-C',str(sdk),'rev-parse','HEAD'], text=True).strip() != ref:
    raise SystemExit('Exact checkout does not match pin')
seed = json.loads(source_manifest.read_text())
if seed.get('version') != 1 or seed.get('exactRef') != ref or seed.get('sdkPath') != str(sdk):
    raise SystemExit('source manifest does not match Exact checkout')
recorded = {e['path']: e['sha256'] for e in seed['files'] if e.get('root') == 'sdk'}
metadata = json.loads(subprocess.check_output(['cargo','metadata','--locked','--offline','--format-version','1','--manifest-path',str(app_manifest)]))
packages = []
for p in metadata['packages']:
    if p.get('source') is not None:
        continue
    directory = Path(p['manifest_path']).resolve().parent
    try:
        directory.relative_to(sdk)
    except ValueError:
        continue
    packages.append((p['name'], directory))
plans = {}
for f in target.glob('**/.fingerprint/*/run-build-script-*.json'):
    try:
        info = json.loads(f.read_text())
    except (ValueError, OSError) as e:
        raise SystemExit(f'bad Cargo fingerprint {f}: {e}')
    for local in info.get('local', []):
        value = local.get('Precalculated') if isinstance(local, dict) else None
        if not isinstance(value, str):
            continue
        match = re.fullmatch(r'(\d+)\.(\d{1,9})s \((.+)\)', value)
        if not match:
            continue # registry packages identify by version, not a file timestamp
        candidates = [(name, path) for name, path in packages if f.parent.name.startswith(name + '-')]
        if not candidates:
            continue # not an SDK package, e.g. the generated app
        longest = max(len(name) for name, _ in candidates)
        candidates = [(name, path) for name, path in candidates if len(name) == longest]
        if len(candidates) != 1:
            raise SystemExit(f'ambiguous SDK fingerprint {f.parent.name}')
        name, package = candidates[0]
        rel = Path(match.group(3))
        if rel.is_absolute() or '..' in rel.parts:
            raise SystemExit(f'unsafe Cargo fingerprint path: {rel}')
        item = package / rel
        if not item.is_file() or item.is_symlink() or not item.resolve().is_relative_to(package):
            raise SystemExit(f'missing or unsafe Cargo fingerprint input: {item}')
        ns = int(match.group(1)) * 1_000_000_000 + int(match.group(2).ljust(9, '0'))
        old = plans.setdefault(package, (name, item, ns))
        if old[1:] != (item, ns):
            raise SystemExit(f'conflicting Cargo fingerprints for {name}')
if not plans:
    print('No SDK package-wide Cargo fingerprints found')
    raise SystemExit(0)
# A package's chosen max cannot be tied with or outranked by a nested package.
for package, (name, item, ns) in plans.items():
    for other, (_, other_item, other_ns) in plans.items():
        if other != package and other_item.is_relative_to(package) and other_ns >= ns:
            raise SystemExit(f'overlapping Cargo fingerprints for {name}')

# Validate all tracked SDK files in affected packages before changing any time.
# Git's object ID verifies pinned bytes, and recorded compiler SHA-256 permits
# the reviewed deterministic hooks and generated SDK sources in the receipt.
raw = subprocess.check_output(['git','-C',str(sdk),'ls-files','--stage','-z'])
files = {}
for row in raw.split(b'\0'):
    if not row:
        continue
    header, raw_path = row.split(b'\t', 1)
    mode, oid, stage = header.decode('ascii').split(' ')
    if stage != '0' or mode not in ('100644','100755'):
        continue
    rel = os.fsdecode(raw_path)
    path = sdk / rel
    if not any(path.is_relative_to(package) for package in plans):
        continue
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(sdk):
        raise SystemExit(f'unsafe or missing tracked SDK file {rel}')
    data = path.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if blob != oid and hashlib.sha256(data).hexdigest() != recorded.get(rel):
        raise SystemExit(f'SDK source differs from pin and seed: {rel}')
    files[path] = rel
# Recorded ignored/generated SDK files may participate in a package's scan.
for rel, expected in recorded.items():
    path = sdk / rel
    if not any(path.is_relative_to(package) for package in plans) or path in files:
        continue
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(sdk) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit(f'generated SDK input differs from seed: {rel}')
    files[path] = rel
# Check every file Cargo could see, including ignored files: a package's
# explicit include list can admit files ignored by Git. Unknown inputs refuse
# the optimization before any timestamp is changed.
for package in plans:
    for base, directories, names in os.walk(package, followlinks=False):
        directories[:] = [d for d in directories if d not in ('.git', 'target')]
        for name in directories:
            if (Path(base) / name).is_symlink():
                raise SystemExit(f'unverified SDK source directory symlink: {Path(base) / name}')
        for name in names:
            path = Path(base) / name
            if path.is_symlink() or not path.is_file() or path not in files:
                raise SystemExit(f'unverified SDK package input: {path}')
# A nonignored untracked file could change Cargo's package-wide scan.
untracked = subprocess.check_output(['git','-C',str(sdk),'ls-files','--others','--exclude-standard','-z'])
for raw_path in untracked.split(b'\0'):
    if not raw_path:
        continue
    path = sdk / os.fsdecode(raw_path)
    if any(path.is_relative_to(package) for package in plans) and path not in files:
        raise SystemExit(f'unverified untracked SDK source: {path}')
for _, item, _ in plans.values():
    if item not in files:
        raise SystemExit(f'Cargo fingerprint input is not verified: {item}')
# Make all competing verified package files older than every selected max.
floor = min(ns for _, _, ns in plans.values()) - 1_000_000_000
if floor <= 0:
    raise SystemExit('invalid Cargo fingerprint timestamp')
for path in files:
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, floor))
# Directory mtimes can participate in package discovery; normalize only
# verified file ancestors, never roots outside the affected SDK packages.
directories = set()
for path in files:
    directory = path.parent
    while directory != sdk and any(directory.is_relative_to(package) for package in plans):
        directories.add(directory)
        directory = directory.parent
for directory in directories:
    st = directory.stat()
    os.utime(directory, ns=(st.st_atime_ns, floor))
for _, item, ns in plans.values():
    st = item.stat()
    os.utime(item, ns=(st.st_atime_ns, ns))
print(f'Normalized {len(files)} SHA-verified SDK files for {len(plans)} Cargo package fingerprints')
