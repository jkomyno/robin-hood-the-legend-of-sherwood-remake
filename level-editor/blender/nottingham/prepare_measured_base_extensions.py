"""Freeze measured per-face connected basal extensions without widening other faces."""
import json,sys,math,hashlib,shutil
from pathlib import Path
from texture_experiment_paths import selected_experiment
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for asset in sys.argv[1:]:
 p=selected_experiment(asset);old=p/'repair-measured-base-v1';out=p/'repair-measured-base-v2';b=p/'bake-background-support-001'
 proof=b/'residual-physical-provenance-band-12.json';r=json.loads(proof.read_text())
 if r['model_sha256']!=sha(b/'worker.blend'):raise ValueError('Stale measurement')
 m=json.loads((old/'views.json').read_text());policy=m['texture_inferred_gap_repair'];bands={};evidence=[]
 for o in r['objects']:
  if o['object'] not in policy['receiver_objects']:continue
  for f in o['faces']:
   d=f.get('band_nearest_generated');extent=f['zmax']-o['minimum_world_z']
   if f.get('abs_normal_z',1)>.05 or not d or not 4<extent<=12 or f['class0_texels']/f['interior_texels']>.05 or d['max_texels']>16 or d['max_world']>8:continue
   bands.setdefault(o['object'],{})[str(f['face'])]=min(12,math.ceil(extent*10)/10)
   policy['max_distance_texels']=max(policy['max_distance_texels'],min(16,math.ceil(d['max_texels']*10)/10))
   policy['max_distance_world']=max(policy['max_distance_world'],min(8,math.ceil(d['max_world']*10)/10))
   evidence.append(dict(object=o['object'],face=f))
 if bands:policy['face_bottom_bands']=bands
 shutil.copytree(old,out,symlinks=True);(out/'views.json').write_text(json.dumps(m,indent=2)+'\n')
 c=json.loads((out/'repair-contract.json').read_text());c.update(policy=policy,manifest_sha256=sha(out/'views.json'),extension_measurement=str(proof),extension_measurement_sha256=sha(proof),per_face_extension_evidence=evidence)
 c['limitations'].append('Unmeasured faces retain the original band4 and distance caps. Remaining visible gaps are not approved by this candidate.')
 (out/'repair-contract.json').write_text(json.dumps(c,indent=2)+'\n');print(asset,len(evidence))
