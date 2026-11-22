import hashlib, json, os, sys, tempfile, time, urllib.request
from pathlib import Path
from subprocess import run
repo = os.environ['GITHUB_REPOSITORY']
assert repo == 'disposabl-dev/exact-cold-tool-lab'
source = f'https://github.com/{repo}/releases/download/delivery-benchmark-45019838035-1/android-production.apk'
expected = '6122e4f6d368def5aa36a8fdaf0e9cc1f0472bae0d980d9c3edafbc0b6885a7d'
now = lambda: round(time.monotonic_ns() / 1e6)
def read_public(url):
    with urllib.request.urlopen(url) as reply:
        return reply.read()
def request(url, body, mime):
    assert url.startswith(('https://api.github.com/repos/'+repo+'/releases','https://uploads.github.com/repos/'+repo+'/releases/'))
    req=urllib.request.Request(url, data=body, method='POST', headers={
        'Authorization':'Bearer '+os.environ['GH_TOKEN'], 'Content-Type':mime,
        'Accept':'application/vnd.github+json','User-Agent':'disposabl-public-fixture'})
    with urllib.request.urlopen(req) as res: return json.load(res)
data=read_public(source)
assert hashlib.sha256(data).hexdigest() == expected
for variant in ('a','b','c'):
    tag=f'delivery-direct-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}-{variant}'
    start=now()
    release=request(f'https://api.github.com/repos/{repo}/releases',json.dumps({'tag_name':tag,'target_commitish':os.environ['GITHUB_SHA'],'name':tag,'prerelease':True,'make_latest':'false','body':'Public synthetic signed APK transfer benchmark'}).encode(),'application/json')
    created=now()
    up=release['upload_url'].split('{')[0]+'?name=android-production.apk'
    asset=request(up,data,'application/vnd.android.package-archive')
    done=now()
    assert asset['state']=='uploaded' and asset['size']==len(data) and asset['digest']=='sha256:'+expected
    assert hashlib.sha256(read_public(asset['browser_download_url'])).hexdigest()==expected
    print('DIRECT_RELEASE_MS',variant, 'create',created-start,'upload',done-created,'download_verify',now()-done,asset['browser_download_url'],flush=True)
