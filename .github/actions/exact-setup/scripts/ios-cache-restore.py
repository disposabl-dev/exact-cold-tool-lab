#!/usr/bin/env python3
"""Restore a verified public iOS Cargo seed without extracting arbitrary paths."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile

if len(sys.argv) != 4:
    raise SystemExit('usage: ios-cache-restore.py ARCHIVE TARGET SHA256')
archive, target = (Path(x) for x in sys.argv[1:3])
expected = sys.argv[3]
if not archive.is_absolute() or not target.is_absolute() or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
    raise SystemExit('expected absolute paths and a lowercase SHA-256')
if target.exists() or target.is_symlink():
    raise SystemExit('restore target must not already exist')
digest = hashlib.sha256()
with archive.open('rb') as source:
    for chunk in iter(lambda: source.read(1024 * 1024), b''):
        digest.update(chunk)
actual = digest.hexdigest()
if actual != expected:
    raise SystemExit('iOS Cargo archive digest mismatch')
target.parent.mkdir(parents=True, exist_ok=True)
staging = Path(tempfile.mkdtemp(prefix='.ios-cargo-restore-', dir=target.parent))
profiles = (('balanced',), ('aarch64-apple-ios', 'balanced'), ('aarch64-apple-darwin', 'balanced'))
forbidden = ('.pcm', '.swiftmodule', '.tbd', '.receipt.json', '.build.json')
count = size = 0
try:
    proc = subprocess.Popen(['zstd', '-dc', str(archive)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout, mode='r|') as tar:
            for member in tar:
                path = PurePosixPath(member.name)
                parts = path.parts
                allowed = parts[:1] == ('bake-compiled',) or any(
                    parts[:len(profile)] == profile and len(parts) > len(profile)
                    and parts[len(profile)] in ('deps', '.fingerprint', 'build')
                    for profile in profiles
                ) or any(parts[:len(profile)] == profile and len(parts) == len(profile) + 1
                         and parts[-1].startswith('lib') and parts[-1].endswith('.a') for profile in profiles)
                if (not member.isfile() or path.is_absolute() or not parts or '..' in parts or '.' in parts or not allowed
                    or any(p.endswith(('.sdk', '.framework')) or 'modulecache' in p.lower() or 'module-cache' in p.lower() for p in parts)
                    or parts[-1] in ('compat.json', 'app.plan', 'app.hbc', 'receipt.json')
                    or parts[-1].endswith(forbidden)):
                    raise ValueError(f'refused archive member: {member.name}')
                count += 1
                size += member.size
                if count > 200000 or size > 8 * 1024 ** 3:
                    raise ValueError('iOS Cargo archive exceeds restore limits')
                dest = staging.joinpath(*parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                # The archive producer emits each file once; reject duplicates.
                with dest.open('xb') as out:
                    shutil.copyfileobj(tar.extractfile(member), out, 1024 * 1024)
                os.chmod(dest, stat.S_IMODE(member.mode) & 0o777)
                os.utime(dest, (member.mtime, member.mtime))
        if proc.wait() != 0:
            raise ValueError('zstd could not decompress iOS Cargo archive')
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    if not count:
        raise ValueError('iOS Cargo archive is empty')
    # Do not overwrite a target created by another process after the first check.
    if target.exists() or target.is_symlink():
        raise ValueError('restore target appeared during extraction')
    os.rename(staging, target)
    print(f'Restored {count} iOS Cargo files ({size} bytes)')
finally:
    shutil.rmtree(staging, ignore_errors=True)
