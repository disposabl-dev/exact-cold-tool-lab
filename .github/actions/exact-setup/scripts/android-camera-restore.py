#!/usr/bin/env python3
"""Restore only allowlisted public Gradle cache files, never overwrite the base."""
import os, pathlib, shutil, subprocess, sys, tarfile, tempfile
archive, destination = map(pathlib.Path, sys.argv[1:])
allowed = ('caches/modules-2/', 'caches/9.8.0/transforms/', 'caches/build-cache-1/')
with tempfile.TemporaryDirectory() as work:
    tarpath = pathlib.Path(work)/'overlay.tar'
    proc = subprocess.Popen(['zstd', '-dc', str(archive)], stdout=subprocess.PIPE)
    try:
        with tarpath.open('wb') as output:
            remaining = 256*1024*1024
            while chunk := proc.stdout.read(min(1024*1024, remaining + 1)):
                if len(chunk) > remaining: raise ValueError('Feature cache exceeds size limit')
                output.write(chunk); remaining -= len(chunk)
        if proc.wait() != 0: raise ValueError('Invalid compressed feature cache')
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()
    with tarfile.open(tarpath) as tar:
        members = tar.getmembers()
        if len(members)>200000: raise ValueError('Too many feature cache entries')
        for item in members:
            name=item.name.removeprefix('./').rstrip('/')
            if not name or name == 'caches': continue
            path=pathlib.PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or not (item.isfile() or item.isdir()):
                raise ValueError('Invalid feature cache entry')
            # Parent directories are harmless; all files are under the allowlist.
            if item.isfile() and (not name.startswith(allowed) or item.size > 64*1024*1024):
                raise ValueError('Unexpected feature cache file')
        for item in members:
            if not item.isfile(): continue
            name=item.name.removeprefix('./'); target=destination/name
            parent=destination
            for part in pathlib.PurePosixPath(name).parts[:-1]:
                parent=parent/part
                if parent.is_symlink(): raise ValueError('Symlink in cache path')
                parent.mkdir(exist_ok=True)
            try:
                with target.open('xb') as out, tar.extractfile(item) as source:
                    shutil.copyfileobj(source, out)
            except FileExistsError:
                pass
