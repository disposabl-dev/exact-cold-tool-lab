import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

p = argparse.ArgumentParser()
p.add_argument("mode", choices=["index", "fetch"])
p.add_argument("image", type=Path)
p.add_argument("index", type=Path)
p.add_argument("--url")
args = p.parse_args()
chunk_size = 32 * 1024**2
if args.mode == "index":
    with args.image.open("rb") as image:
        hashes = [hashlib.sha256(chunk).hexdigest() for chunk in iter(lambda: image.read(chunk_size), b"")]
    args.index.write_text(json.dumps({"size": args.image.stat().st_size, "chunk": chunk_size, "hashes": hashes})+"\n")
else:
    record = json.loads(args.index.read_text())
    size, hashes = record["size"], record["hashes"]
    assert 0 < size < 2**31 and record["chunk"] == chunk_size and len(hashes) == (size + chunk_size - 1)//chunk_size
    with urllib.request.urlopen(urllib.request.Request(args.url,method="HEAD"), timeout=15) as response:
        location = response.geturl()
    with tempfile.NamedTemporaryFile(dir=args.image.parent, delete=False) as tmp:
        name = tmp.name
        try:
            tmp.truncate(size)
            def fetch(index):
                start = index*chunk_size
                end = min(start+chunk_size,size)
                for attempt in range(3):
                    try:
                        req = urllib.request.Request(location,headers={"Range": f"bytes={start}-{end-1}", "Accept-Encoding":"identity"})
                        with urllib.request.urlopen(req,timeout=30) as response:
                            assert response.status==206 and response.headers.get("Content-Range")==f"bytes {start}-{end-1}/{size}"
                            data = response.read(end-start+1)
                        if len(data)!=end-start or hashlib.sha256(data).hexdigest()!=hashes[index]:
                            raise ValueError("Incorrect public tool chunk")
                        if os.pwrite(tmp.fileno(),data,start)!=len(data): raise OSError("Short write")
                        return
                    except OSError:
                        if attempt == 2: raise
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool: list(pool.map(fetch,range(len(hashes))))
            os.replace(name,args.image)
        finally:
            Path(name).unlink(missing_ok=True)
