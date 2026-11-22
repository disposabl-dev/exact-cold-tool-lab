import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('ios-cargo-precalculated.py')

class PrecalculatedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.sdk, self.target, self.bin = (self.root / x for x in ('sdk', 'target', 'bin'))
        (self.sdk / 'crate/build').mkdir(parents=True)
        self.bin.mkdir()
        for name, data in [('Cargo.toml','[package]\nname="fixture"\nversion="0.1.0"\n'), ('build.rs','fn main() {}\n'), ('build/codec.rs','pub fn codec() {}\n')]:
            (self.sdk / 'crate' / name).write_text(data)
        subprocess.run(['git','init','-q',str(self.sdk)],check=True)
        subprocess.run(['git','-C',str(self.sdk),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.sdk),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture'],check=True)
        self.ref=subprocess.check_output(['git','-C',str(self.sdk),'rev-parse','HEAD'],text=True).strip()
        self.metadata=self.root/'metadata.json'
        self.metadata.write_text(json.dumps({'packages':[{'name':'fixture','source':None,'manifest_path':str(self.sdk/'crate/Cargo.toml')}]}))
        cargo=self.bin/'cargo'
        cargo.write_text('#!/bin/sh\ncat "$IOS_TEST_METADATA"\n')
        cargo.chmod(0o755)
        self.manifest=self.root/'times.json'
        self.manifest.write_text(json.dumps({'version':1,'exactRef':self.ref,'sdkPath':str(self.sdk),'files':[{'root':'sdk','path':'crate/Cargo.toml','mtimeNs':'1577836800000000000','sha256':'x'}]}))
        fp=self.target/'aarch64-apple-ios/balanced/.fingerprint/fixture-abcdef/run-build-script-build-script-build.json'
        fp.parent.mkdir(parents=True)
        fp.write_text(json.dumps({'local':[{'Precalculated':'1577836800.000000000s (Cargo.toml)'},{'RerunIfChanged':{'paths':['build']}}]}))
        self.env={**os.environ,'PATH':str(self.bin)+os.pathsep+os.environ['PATH'],'SETUP_EXACT_REF':self.ref,'IOS_TEST_METADATA':str(self.metadata)}
    def tearDown(self): self.tmp.cleanup()
    def run_tool(self):
        return subprocess.run(['python3',str(SCRIPT),str(self.sdk),str(self.root/'app/Cargo.toml'),str(self.target),str(self.manifest)],env=self.env,text=True,capture_output=True)
    def test_normalizes_unique_max(self):
        result=self.run_tool()
        self.assertEqual(result.returncode,0,result.stderr)
        chosen=(self.sdk/'crate/Cargo.toml').stat().st_mtime_ns
        self.assertEqual(chosen,1577836800000000000)
        self.assertLess((self.sdk/'crate/build.rs').stat().st_mtime_ns,chosen)
        self.assertLess((self.sdk/'crate/build').stat().st_mtime_ns,chosen)
    def test_tamper_or_untracked_refuses_before_touch(self):
        path=self.sdk/'crate/build.rs'
        path.write_text('changed native code')
        before=path.stat().st_mtime_ns
        self.assertNotEqual(self.run_tool().returncode,0)
        self.assertEqual(path.stat().st_mtime_ns,before)
        subprocess.run(['git','-C',str(self.sdk),'checkout','--','crate/build.rs'],check=True)
        (self.sdk/'crate/build/new.rs').write_text('unknown')
        self.assertNotEqual(self.run_tool().returncode,0)

if __name__ == '__main__': unittest.main()
