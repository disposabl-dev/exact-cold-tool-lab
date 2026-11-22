import os
from pathlib import Path
p=Path(os.environ['EXACT'])/'scripts/publisher.mjs'
s=p.read_text()
target="""    for (const file of files) {
      if (await putVerifiedBlob(origin, file) === 'written') written++;
    }"""
assert target in s
if os.environ['MODE']=='parallel':
    s=s.replace(target,"""    for (let i = 0; i < files.length; i += 6) {
      const done = await Promise.allSettled(files.slice(i, i+6).map(file => putVerifiedBlob(origin, file)));
      for (const entry of done) {
        if (entry.status === 'rejected') throw entry.reason;
        if (entry.value === 'written') written++;
      }
    }""")
p.write_text(s)
