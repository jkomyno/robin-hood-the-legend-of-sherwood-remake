"""Audit only canonical ready texture bakes, preserving every reviewed artifact."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';OUT=WORK/'coordinator-audit/final-texture-coverage'
DELEGATED={'nottingham-castle-east-courtyard-wall','nottingham-south-gate-house','nottingham-south-gate-east-tower','nottingham-south-curtain-wall-3'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inventory():
 gallery=json.loads((WORK/'texture-review/texture-candidates.json').read_text())
 paths={Path(i['review']).resolve() for i in gallery['items']}
 paths.update(p/'texture-review.json' for p in (WORK/'texture-generation/experiments').iterdir() if p.is_dir() and (p/'texture-review.json').is_file())
 jobs=[];skips=[];seen=set()
 def add(path,state=None,parent=None):
  path=path.resolve()
  if path in seen:return
  seen.add(path);r=json.loads(path.read_text());exp=path.parent
  if r.get('status')!=('supplemental' if state else 'ready-for-user'):
   skips.append(dict(review=str(path),status='not-ready',review_status=r.get('status')));return
  b=(exp/r['bake']).resolve();v=json.loads((b/'validation.json').read_text());asset=v['asset_id'];identity=asset+('--'+state if state else '')
  for child in r.get('texture_states',[]):add(exp/child['experiment']/'texture-review.json',child['id'],identity)
  for child in r.get('material_states',[]):skips.append(dict(asset_id=identity+'--'+child['id'],status='material-state-needs-explicit-provenance-binding',review=str(path)))
  if asset in DELEGATED:skips.append(dict(asset_id=identity,status='delegated-to-walls-market'));return
  row=dict(asset_id=identity,review=str(path),review_sha256=sha(path),bake=str(b),model_sha256=sha(b/'worker.blend'),validation_sha256=sha(b/'validation.json'))
  if r.get('baked_model_sha256')!=row['model_sha256']:skips.append({**row,'status':'model-changed'});return
  provenance=[(f,o['texel_provenance']) for f in b.glob('layer-*.json') for o in json.loads(f.read_text()).get('objects',[]) if o.get('texel_provenance')]
  if not provenance:skips.append({**row,'status':'missing-explicit-provenance'});return
  if any(not p.get('packed_image_sha256') for _,p in provenance):skips.append({**row,'status':'legacy-provenance-needs-exact-replay'});return
  manifests=[Path(p).resolve() for p in v.get('evidence_sha256',{}) if Path(p).name=='views.json']
  if len(manifests)!=1:raise ValueError(('Ambiguous exact bake manifest',identity,manifests))
  manifest=manifests[0];expected=next(d for p,d in v['evidence_sha256'].items() if Path(p).resolve()==manifest)
  if sha(manifest)!=expected:raise ValueError(('Bake manifest changed',manifest))
  row.update(manifest=str(manifest),manifest_sha256=expected,output=str(OUT/identity),provenance=[dict(report=str(f),report_sha256=sha(f),**p) for f,p in provenance],status='queued')
  jobs.append(row)
 for p in sorted(paths):add(p)
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'jobs.json').write_text(json.dumps(dict(jobs=jobs,skips=skips),indent=2)+'\n');print('queued',len(jobs),'skipped',len(skips),flush=True)
def run():
 sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'));sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire,release
 from render_texture_coverage import inspect
 data=json.loads((OUT/'jobs.json').read_text());results=[]
 for row in data['jobs']:
  acquire()
  try:
   review=Path(row['review']);b=Path(row['bake']);manifest=Path(row['manifest']);out=Path(row['output'])
   if sha(review)!=row['review_sha256'] or sha(b/'worker.blend')!=row['model_sha256'] or sha(manifest)!=row['manifest_sha256']:
    result={**row,'status':'changed-since-inventory'}
   elif out.exists():
    report=json.loads((out/'coverage.json').read_text())
    if report['model_sha256']!=row['model_sha256'] or report['manifest_sha256']!=row['manifest_sha256']:raise ValueError('Existing diagnostic binds different bake')
    result={**row,'status':'diagnostic-existing','views':report['views'],'unverified_materials':report['unverified_materials']}
   else:
    report=inspect(manifest,b,out)
    result={**row,'status':'diagnostic-ready','views':report['views'],'unverified_materials':report['unverified_materials'],'coverage_report_sha256':sha(out/'coverage.json')}
   results.append(result);(OUT/'results.json').write_text(json.dumps(dict(results=results,skips=data['skips']),indent=2)+'\n')
   print(json.dumps({k:result[k] for k in ['asset_id','status','views','unverified_materials'] if k in result}),flush=True)
  finally:release()
  time.sleep(1.1)
if __name__=='__main__':
 if '--run' in sys.argv:run()
 else:inventory()
