# Generate a synthetic all-first-party compilation from pinned SDK metadata.
import json, pathlib, sys
root=pathlib.Path(sys.argv[1]); out=pathlib.Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
rows=[]; dependencies=set(); paths=[]
for p in sorted((root/'packages').glob('*/android/exact.json')):
 x=json.loads(p.read_text()); name=p.parent.parent.name; cls=x.get('class'); namespace=cls.rsplit('.',1)[0] if cls else None
 rows.append(dict(name=name, namespace=namespace, implementation=x))
 if namespace: paths.append(str(p.parent))
 dependencies.update(x.get('maven',[]))
(out/'index.json').write_text(json.dumps(rows,indent=2)+'\n')
gradle=root/'host/android/app/build.gradle.kts'; text=gradle.read_text();
text+='\n// Public all-package lab only.\nandroid.sourceSets["main"].kotlin.srcDirs('+','.join(json.dumps(x) for x in paths)+')\n'
text+='dependencies {\n'+''.join('  implementation('+json.dumps(x)+')\n' for x in sorted(dependencies))+'}\n'
gradle.write_text(text)
print('Catalog metadata:',len(rows),'implementations,',len(paths),'Kotlin namespaces,',len(dependencies),'declared Maven coordinates')
