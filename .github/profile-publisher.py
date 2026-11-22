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
# This experiment uses a unique private directory and a fresh stream per build.
if os.environ['MODE']=='parallel':
    s=s.replace('  const base = streamPath(stream);\n  const recordPath',"""  const gate = process.env.DELIVERY_GATE;
  const verified = new Map();
  const {existsSync,writeFileSync} = await import('node:fs');
  const base = streamPath(stream);
  const recordPath""")
    s=s.replace('  return origin.withLock(stream, async () => {\n    if (await origin.get(recordPath))', '  const publish = async (prepare) => origin.withLock(stream, async () => {\n    if (await origin.get(recordPath))')
    s=s.replace('file => putVerifiedBlob(origin, file)',"""async file => {
        if (sha256(file.bytes) !== file.sha256) throw Error('staged blob changed');
        if (verified.has(file.sha256)) return 'present';
        const result = await putVerifiedBlob(origin, file);
        verified.set(file.sha256, true);
        return result;
      }""")
    s=s.replace('    const originDigest = sha256(bytes);','''    if (prepare) return;
    const originDigest = sha256(bytes);''')
    t='''  });
}

async function putVerifiedBlob'''
    assert s.count(t)==1
    s=s.replace(t,'''  });
  if (gate) {
    await publish(true);
    writeFileSync(gate+'/staged','');
    console.log('STAGED',Date.now());
    while (!existsSync(gate+'/installer-verified')) await new Promise(r=>setTimeout(r,25));
  }
  return publish(false);
}

async function putVerifiedBlob''')
    p.write_text(s)
    a=Path(os.environ['EXACT'])/'scripts/agent-android.mjs'
    src=a.read_text()
    mark="  const started = new Date().toISOString(), uses = planUses(out);"
    assert src.count(mark)==1
    a.write_text(src.replace(mark,"  if(process.env.DELIVERY_GATE) writeFileSync(process.env.DELIVERY_GATE+'/baked','');\n"+mark))
