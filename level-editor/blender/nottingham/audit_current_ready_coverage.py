"""Render missing saved-atlas coverage for the current immutable ready snapshot."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'level-editor/refinement/blender'),str(Path(__file__).parent)]
from audit_ready_texture_coverage import OUT,sha

def run():
 from render_slots import acquire,release
 from render_texture_coverage import inspect
 rows=json.loads((OUT/'current-ready-preliminary.json').read_text())
 results=[]
 for row in rows:
  if row['coverage']:continue
  bake=Path(row['bake']);review=Path(row['review'])
  reports=list(bake.glob('layer-*.json'))
  proofs=[o.get('texel_provenance') for f in reports for o in json.loads(f.read_text()).get('objects',[])]
  if not proofs or not all(p and p.get('packed_image_sha256') for p in proofs):
   results.append({**row,'status':'external-provenance-required'});continue
  before=sha(review);validation=json.loads((bake/'validation.json').read_text())
  manifests=[Path(p)for p in validation.get('evidence_sha256',{})if Path(p).name=='views.json']
  if len(manifests)!=1:raise ValueError(('Ambiguous camera binding',row['asset_id']))
  manifest=manifests[0]
  assert sha(manifest)==validation['evidence_sha256'][str(manifest)]
  out=OUT/'current-ready'/row['asset_id']/row['model_sha256'][:16]
  acquire()
  try:
   if sha(bake/'worker.blend')!=row['model_sha256'] or json.loads(review.read_text()).get('status')!='ready-for-user':
    result={**row,'status':'changed-before-audit'}
   else:
    if (out/'coverage.json').exists():
     d=json.loads((out/'coverage.json').read_text());assert d['model_sha256']==row['model_sha256'] and d['manifest_sha256']==sha(manifest)
    else:d=inspect(manifest,bake,out)
    assert sha(bake/'worker.blend')==row['model_sha256'] and sha(review)==before
    result={**row,'status':'diagnostic-complete','coverage_report':str(out/'coverage.json'),'coverage_report_sha256':sha(out/'coverage.json'),'red':sum(v['unfilled_visible_pixels']for v in d['views']),'unverified':len(d['unverified_materials'])}
   results.append(result);print(json.dumps({k:result[k]for k in ('asset_id','status','red','unverified')if k in result}),flush=True)
  except Exception as error:
   results.append({**row,'status':'fail-closed','reason':str(error)})
  finally:release()
  (OUT/'current-ready-results.json').write_text(json.dumps(results,indent=2)+'\n')
  time.sleep(1.1)
 (OUT/'current-ready-results.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':run()
