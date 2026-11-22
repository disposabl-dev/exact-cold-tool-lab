import hashlib,json,pathlib,sys,zipfile
root=pathlib.Path(sys.argv[1]); rows=json.loads((root/'index.json').read_text()); assert len(rows)==42
count=0
for row in rows:
 name=row['name']; impl=row['implementation']; jar=root/(name+'.jar'); cls=impl.get('class')
 if cls:
  if not jar.is_file(): raise SystemExit('Missing JAR: '+name)
  with zipfile.ZipFile(jar) as z:
   entries=z.namelist(); expected=cls.replace('.','/')+'.class'
   if expected not in entries: raise SystemExit('Missing declared implementation class: '+name)
   if any(x.lower().endswith(('.apk','.aab','.so','.p12','.jks','.receipt.json')) for x in entries): raise SystemExit('Unexpected file in JAR: '+name)
  sha=hashlib.sha256(jar.read_bytes()).hexdigest(); count+=1
 else:
  if jar.exists(): raise SystemExit('Unexpected JAR for metadata-only '+name)
  sha=None
 (root/(name+'.json')).write_text(json.dumps({'sdk':'a55c5581c7e1a62cdee1f09367ea2909c74c7292','name':name,'sha256':sha,'implementation':impl},indent=2)+'\n')
print('Verified',count,'public class JARs and',len(rows)-count,'metadata-only package')
