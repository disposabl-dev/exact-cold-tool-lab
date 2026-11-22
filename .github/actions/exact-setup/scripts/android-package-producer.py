#!/usr/bin/env python3
"""Generate isolated Gradle library projects for pinned first-party modules.

Lab prototype: classes are compiled against each implementation's own Maven
coordinates and the pinned Canvas host. It does not change the consuming app.
"""
import hashlib, json, pathlib, sys
sdk=pathlib.Path(sys.argv[1]).resolve(); out=pathlib.Path(sys.argv[2]).resolve(); names=set(sys.argv[3:])
packages=[]
for meta in sorted((sdk/'packages').glob('*/android/exact.json')):
    data=json.loads(meta.read_text()); name=meta.parent.parent.name
    if names and name not in names: continue
    packages.append((name, meta, data))
if names and names!={n for n,_,_ in packages}: raise SystemExit('Unknown requested package')
settings=sdk/'host/android/settings.gradle.kts'
with settings.open('a') as f:
    f.write('\n// Public catalog lab projects.\n')
    for name,_,data in packages:
        if not data.get('class'): continue
        stem=name.replace('-','_'); directory=out/'projects'/name
        f.write(f'include(":catalog_{stem}")\nproject(":catalog_{stem}").projectDir = file({json.dumps(str(directory))})\n')
for name,meta,data in packages:
    if not data.get('class'): continue
    stem=name.replace('-','_'); directory=out/'projects'/name
    (directory/'src/main').mkdir(parents=True,exist_ok=True)
    (directory/'src/main/AndroidManifest.xml').write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" />\n')
    deps=['androidx.browser:browser:1.9.0','androidx.activity:activity:1.9.0','androidx.webkit:webkit:1.16.0']+data.get('maven',[])
    kt='''import org.gradle.api.artifacts.component.ProjectComponentIdentifier
import org.gradle.api.artifacts.component.ModuleComponentIdentifier
import org.gradle.api.artifacts.type.ArtifactTypeDefinition
import java.security.MessageDigest
import groovy.json.JsonOutput
plugins { id("com.android.library") }
android {
  namespace = "dev.exact.catalog.STEM"
  compileSdk { version = release(37) { minorApiLevel = 2 } }
  defaultConfig { minSdk = 29 }
  compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
  sourceSets { getByName("main").kotlin.directories.add(SOURCES) }
}
dependencies {
  implementation(project(":canvas"))
DEPENDENCIES
}
tasks.register<Jar>("catalogJar") {
  val compile = tasks.named("compileReleaseKotlin")
  dependsOn(compile)
  from(compile.map { it.outputs.files }) { include("exact/**", "META-INF/*.kotlin_module") }
  archiveFileName = "NAME.jar"
  destinationDirectory = file(OUTPUT)
  doLast {
    val digest = MessageDigest.getInstance("SHA-256")
    val view = configurations.getByName("releaseCompileClasspath").incoming.artifactView {
      componentFilter { it !is ProjectComponentIdentifier }
      attributes.attribute(ArtifactTypeDefinition.ARTIFACT_TYPE_ATTRIBUTE, "android-classes-jar")
    }
    val artifacts = view.artifacts.artifacts.map { a ->
        val id = a.id.componentIdentifier as ModuleComponentIdentifier
        val bytes = a.file.readBytes()
        mapOf("group" to id.group, "name" to id.module, "version" to id.version,
          "sha256" to digest.digest(bytes).joinToString("") { "%02x".format(it) })
      }.sortedBy { it.toString() }
    file(OUTPUT + "/NAME-graph.json").writeText(JsonOutput.toJson(artifacts))
  }
}
'''
    kt=kt.replace('STEM',stem).replace('NAME',name).replace('SOURCES',json.dumps(str(meta.parent))).replace('OUTPUT',json.dumps(str(out/'jars'))).replace('DEPENDENCIES','\n'.join('  implementation('+json.dumps(d)+')' for d in sorted(set(deps))))
    (directory/'build.gradle.kts').write_text(kt)
(out/'packages.json').write_text(json.dumps([{'name':n,'implementation':x} for n,_,x in packages],indent=2)+'\n')
print('Generated',len(packages),'package records')
