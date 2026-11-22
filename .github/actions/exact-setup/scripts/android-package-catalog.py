#!/usr/bin/env python3
"""Create and check Android package compilation evidence.

The consuming app's normal Gradle graph and manifest remain authoritative.
A failed or absent check must retain the original Kotlin source compilation.
"""
import hashlib, json, os, pathlib, subprocess, sys, zipfile

SDK_REF = 'a55c5581c7e1a62cdee1f09367ea2909c74c7292'
HOST_PATHS = ('host/android/build.gradle.kts', 'host/android/settings.gradle.kts',
              'host/android/gradle', 'host/android/canvas', 'vendor/ibex/crates/ibex2/android')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def file_digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def tree_digest(sdk, paths):
    """Bind every tracked host input, rejecting altered, missing or added source."""
    raw = subprocess.check_output(['git', '-C', str(sdk), 'ls-files', '-z', '--', *paths])
    files = [os.fsdecode(p) for p in raw.split(b'\0') if p]
    if not files:
        raise ValueError('No SDK source inputs')
    # Untracked source can be picked up by Gradle source sets and must not be ignored.
    changed = subprocess.check_output(['git', '-C', str(sdk), 'status', '--porcelain', '--untracked-files=all', '--', *paths])
    # Exact temporarily places the consuming app's strict verification file
    # here during Gradle. It is not a compiler input and is checked by Gradle.
    changes = changed.splitlines()
    allowed = b'?? host/android/gradle/verification-metadata.xml'
    if any(line != allowed for line in changes):
        raise ValueError('SDK inputs differ from the pinned checkout')
    h = hashlib.sha256()
    for name in sorted(files):
        path = sdk / name
        if path.is_symlink():
            data = os.readlink(path).encode()
        else:
            data = path.read_bytes()
        h.update(name.encode()+b'\0'+str(len(data)).encode()+b'\0'+data)
    return h.hexdigest()

def evidence(sdk, android_home):
    actual = subprocess.check_output(['git','-C',str(sdk),'rev-parse','HEAD'],text=True).strip()
    if actual != SDK_REF:
        raise ValueError('Unsupported Exact revision')
    sdk_jar = android_home/'platforms/android-37.2/android.jar'
    java = subprocess.check_output(['java','-version'],stderr=subprocess.STDOUT,text=True).strip()
    return {'sdk': actual, 'hostSha256': tree_digest(sdk, HOST_PATHS),
            'androidJarSha256': file_digest(sdk_jar), 'javaVersion': java}

def artifact_set(rows):
    result = set()
    for row in rows:
        if set(row) != {'group','name','version','sha256'} or not all(isinstance(v,str) and v for v in row.values()) or len(row['sha256'])!=64:
            raise ValueError('Invalid dependency evidence')
        result.add((row['group'],row['name'],row['version'],row['sha256']))
    return result

def compatible(record, candidate, graph, module_sha, jar_sha):
    try:
        if record['evidence'] != candidate or record['sourceSha256'] != module_sha or record['jarSha256'] != jar_sha:
            return False
        return artifact_set(record['dependencies']).issubset(artifact_set(graph))
    except (KeyError, TypeError, ValueError):
        return False

def main(argv):
    command=argv[0]; sdk=pathlib.Path(os.environ['EXACT']).resolve(); android=pathlib.Path(os.environ['ANDROID_HOME']).resolve()
    if command=='fingerprint':
        pathlib.Path(argv[1]).write_text(json.dumps(evidence(sdk,android),sort_keys=True)+'\n')
    elif command=='seal':
        work=pathlib.Path(argv[1]); baseline=json.loads(pathlib.Path(argv[2]).read_text()); out=pathlib.Path(argv[3]); out.mkdir(parents=True,exist_ok=True)
        rows=json.loads((work/'packages.json').read_text());
        if len(rows)!=42 or baseline['sdk']!=SDK_REF: raise ValueError('Incomplete SDK catalog')
        index={}
        for row in rows:
            name=row['name']; impl=row['implementation']; cls=impl.get('class')
            source=tree_digest(sdk, ('packages/'+name+'/android',)); jar=work/'jars'/(name+'.jar')
            if cls:
                with zipfile.ZipFile(jar) as z:
                    if cls.replace('.','/')+'.class' not in z.namelist(): raise ValueError('Missing class: '+name)
                graph=json.loads((work/'jars'/(name+'-graph.json')).read_text()); artifact_set(graph)
                record={'name':name,'evidence':baseline,'sourceSha256':source,'jarSha256':file_digest(jar),'dependencies':graph,'implementation':impl}
            else:
                record={'name':name,'evidence':baseline,'sourceSha256':source,'jarSha256':None,'dependencies':[],'implementation':impl}
            (out/(name+'.json')).write_text(json.dumps(record,sort_keys=True)+'\n'); index[name]=record['jarSha256']
        (out/'index.json').write_text(json.dumps(index,sort_keys=True)+'\n')
        print('Sealed',len(rows),'package records')
    elif command=='select':
        catalog=pathlib.Path(argv[1]); graph=json.loads(pathlib.Path(argv[2]).read_text()); candidate=evidence(sdk,android)
        selected=[]
        for name in argv[3:]:
            # Every unrecognized, absent or mismatched package remains source-built.
            if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in name): continue
            try:
                record=json.loads((catalog/(name+'.json')).read_text()); jar=catalog/(name+'.jar')
                source=tree_digest(sdk,('packages/'+name+'/android',))
                if record.get('name')==name and compatible(record,candidate,graph,source,file_digest(jar)):
                    selected.append(name)
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        print(json.dumps(selected))
    else:
        raise ValueError('Expected fingerprint, seal, or select')

if __name__=='__main__':
    main(sys.argv[1:])
