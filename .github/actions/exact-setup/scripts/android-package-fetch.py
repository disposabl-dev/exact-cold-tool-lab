#!/usr/bin/env python3
"""Fetch only requested, digest-pinned public Android package assets."""
import io, pathlib, re, subprocess, sys, tarfile
base, manifest, dest, scripts, *names = sys.argv[1:]
dest=pathlib.Path(dest); dest.mkdir(parents=True,exist_ok=True)
for name in names:
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name):
        continue
    asset='android-package-'+name+'.zst'; archive=dest/asset
    try:
        subprocess.run([sys.executable,str(pathlib.Path(scripts)/'fetch-input.py'),base,manifest,asset,str(archive)],check=True,stdout=sys.stderr)
        data=subprocess.check_output(['zstd','-dc',str(archive)])
        if len(data)>8*1024*1024: raise ValueError('Package archive is too large')
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            members=tar.getmembers(); expected={name+'.json',name+'.jar'}
            if len(members)!=2 or {m.name for m in members}!=expected or any(not m.isfile() or m.size>4*1024*1024 for m in members):
                raise ValueError('Unexpected package archive contents')
            for member in members:
                data=tar.extractfile(member).read()
                (dest/member.name).write_bytes(data)
    except (OSError,ValueError,subprocess.CalledProcessError,tarfile.TarError) as error:
        print('Android package '+name+' unavailable; using sources ('+type(error).__name__+')',file=sys.stderr)
