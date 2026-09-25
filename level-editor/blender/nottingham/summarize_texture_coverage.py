"""Summarize immutable coverage diagnostics without treating pending as approved."""
import json,hashlib
from pathlib import Path
from audit_ready_texture_coverage import OUT
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 inventory=json.loads((OUT/'jobs.json').read_text());rows=[]
 for r in inventory['jobs']+inventory['skips']:
  a=r.get('asset_id');row={k:r[k]for k in ('asset_id','review','bake','model_sha256')if k in r}
  if not a or not r.get('bake'):row['status']='outside-current-audit';row['reason']=r['status'];rows.append(row);continue
  candidates=[OUT/a/'coverage.json',OUT/'legacy-replay'/a/'coverage-transfer/coverage.json',OUT/'legacy-replay'/a/'coverage/coverage.json']
  if a=='nottingham-terrain-ground':candidates.insert(0,OUT/'terrain-uv/coverage/coverage.json')
  p=next((p for p in candidates if p.exists()),None)
  if p is None:row['status']='pending';row['reason']=r['status'];rows.append(row);continue
  current=json.loads(Path(r['review']).read_text());current_model=Path(r['review']).parent/current['bake']/'worker.blend'
  if sha(current_model)!=r['model_sha256']:
   row['status']='pending';row['reason']='Canonical saved model changed after diagnostic inventory.';rows.append(row);continue
  d=json.loads(p.read_text());row.update(coverage_report=str(p),coverage_report_sha256=sha(p),model_sha256=d['model_sha256'],manifest_sha256=d['manifest_sha256'],rendered_red_pixels=sum(v['unfilled_visible_pixels']for v in d['views']))
  center=p.with_name('center-ray-classification.json')
  if d['unverified_materials']:row['status']='pending';row['reason']='unverified-materials'
  elif not row['rendered_red_pixels']:row['status']='PASS';row['reason']='All eight explicit-provenance views contain zero unfilled visible pixels; every displayed material verified.'
  elif center.exists():
   c=json.loads(center.read_text());assert c['coverage_report_sha256']==sha(p);row['center_ray_report']=str(center);row['center_ray_sha256']=sha(center);row['unfilled_center_hits']=sum(v['counts'].get('center-class-0',0)for v in c['views']);row['status']='real-gap'if row['unfilled_center_hits']else'PASS';row['reason']='Exact center rays hit unfilled saved surface texels.'if row['unfilled_center_hits']else'Rendered red pixels have no unfilled center-ray surface hits; raster silhouette/occlusion distinction recorded.'
  else:row['status']='pending';row['reason']='Red pixels require center-ray classification.'
  rows.append(row)
 result=dict(scope='Canonical ready candidates captured by jobs.json. PASS means eight-camera saved-atlas coverage only, not aesthetic quality or unseen undersides. Original reviews/models remain authoritative; stale-model evidence must never activate a candidate.',inventory_sha256=sha(OUT/'jobs.json'),counts={s:sum(r['status']==s for r in rows)for s in ['PASS','real-gap','pending','outside-current-audit']},assets=rows)
 (OUT/'inventory-verdict.json').write_text(json.dumps(result,indent=2)+'\n');print(result['counts'])
if __name__=='__main__':main()
