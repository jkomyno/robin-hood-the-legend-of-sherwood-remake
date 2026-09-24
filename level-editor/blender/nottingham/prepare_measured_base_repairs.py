"""Prepare explicit bounded base repairs from hash-bound same-face measurements."""
import json,sys,math,hashlib
from pathlib import Path
from texture_experiment_paths import selected_experiment
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for asset in sys.argv[1:]:
 p=selected_experiment(asset);b=p/'bake-background-support-001';source=p/'repair-background-support'
 proof=b/'residual-physical-provenance.json';r=json.loads(proof.read_text())
 if r['model_sha256']!=sha(b/'worker.blend') or r['validation_sha256']!=sha(b/'validation.json'):raise ValueError('Stale measurement')
 minimum=min(o['minimum_world_z'] for o in r['objects']);selected=[];evidence=[]
 for o in r['objects']:
  if o['minimum_world_z']>minimum+4:continue
  faces=[f for f in o['faces'] if f.get('abs_normal_z',1)<=.05 and f.get('bottom4_nearest_generated') and f['class0_bottom4_texels']/f['interior_texels']<=.05 and f['bottom4_nearest_generated']['max_texels']<=16 and f['bottom4_nearest_generated']['max_world']<=8]
  if faces:selected.append(o['object']);evidence.append(dict(object=o['object'],faces=faces))
 if not selected:raise ValueError('No measured bounded targets: '+asset)
 distances=[f['bottom4_nearest_generated'] for o in evidence for f in o['faces']]
 policy=dict(version=1,receiver_objects=selected,max_distance_texels=min(16,math.ceil(max(d['max_texels'] for d in distances)*10)/10),max_distance_world=min(8,math.ceil(max(d['max_world'] for d in distances)*10)/10),bottom_band_world=4,max_face_fraction=.05,max_total_texels=10000,max_abs_normal_z=.05)
 out=p/'repair-measured-base-v1'
 if out.exists():raise ValueError('Fresh output required')
 out.mkdir()
 for f in source.iterdir():
  if f.name!='views.json':(out/f.name).symlink_to(f.resolve())
 m=json.loads((source/'views.json').read_text());m['texture_inferred_gap_repair']=policy
 (out/'views.json').write_text(json.dumps(m,indent=2)+'\n')
 (out/'repair-contract.json').write_text(json.dumps(dict(status='PREPARED-NOT-APPROVED',previous_bake=str(b),previous_model_sha256=sha(b/'worker.blend'),measurement=str(proof),measurement_sha256=sha(proof),manifest_sha256=sha(out/'views.json'),policy=policy,measured_targets=evidence,limitations=['Only narrow same-face base gaps are eligible. Targets outside these bounds remain unfilled and require subsequent review.','Per-face and total repair budget guards remain mandatory; no source, alpha, geometry, UV or other materials may change.']),indent=2)+'\n')
 print(asset,len(selected),policy['max_distance_texels'],policy['max_distance_world'])
