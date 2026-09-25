"""Recover diagnostic provenance only when replay equals the existing saved atlas."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'level-editor/refinement/blender'),str(Path(__file__).parent)]
from audit_ready_texture_coverage import OUT,sha

def run(limit=None):
 import bpy
 from render_slots import acquire,release
 from project_reviewed_texture import apply
 from render_texture_coverage import inspect
 rows=json.loads((OUT/'jobs.json').read_text())['skips']
 rows=[r for r in rows if r['status'] in ('missing-explicit-provenance','legacy-provenance-needs-exact-replay')]
 root=OUT/'legacy-replay';root.mkdir(exist_ok=True);summary=root/'results.json';results=json.loads(summary.read_text()) if summary.exists() else []
 completed={r['asset_id'] for r in results if r['status']=='exact-replay-diagnostic-ready'}
 rows=[r for r in rows if r['asset_id'] not in completed]
 for row in rows[:limit]:
  base=root/row['asset_id'];base.mkdir(exist_ok=True);result={**row,'status':'pending'}
  acquire()
  try:
   review=Path(row['review']);bake=Path(row['bake']);validation=json.loads((bake/'validation.json').read_text())
   if sha(review)!=row['review_sha256'] or sha(bake/'worker.blend')!=row['model_sha256'] or sha(bake/'validation.json')!=row['validation_sha256']:
    raise ValueError('Canonical ready bake changed since inventory')
   manifests=[Path(p) for p in validation.get('evidence_sha256',{}) if Path(p).name=='views.json']
   if len(manifests)!=1:raise ValueError('No unique exact manifest in bake evidence')
   manifest=manifests[0];data=json.loads(manifest.read_text())
   if data.get('projection_kind')=='planar-atlas':raise ValueError('Planar atlas needs its own provenance method')
   for p,digest in validation['evidence_sha256'].items():
    if sha(p)!=digest:raise ValueError('Original bake evidence changed: '+p)
   experiment=review.parent;approved=experiment/'approved-model.blend';approval=json.loads((experiment/'approval.json').read_text())
   if sha(approved)!=approval['saved_model_sha256']:raise ValueError('Approved preparation model changed')
   replay=base/'replay'
   if not (replay/'report.json').exists():
    if replay.exists():
     # Preserve the interrupted diagnostic exactly and use a fresh output.
     n=1
     while (base/f'replay-resume-{n}').exists():n+=1
     replay=base/f'replay-resume-{n}'
    bpy.ops.wm.open_mainfile(filepath=str(approved));bpy.context.window.scene=bpy.data.scenes[data['scene_name']];bpy.context.view_layer.update()
    apply(manifest,validation['generated_image'],replay,texels_per_unit=2,reconciliation_reference=validation.get('reconciliation_reference'))
   record=json.loads((replay/'report.json').read_text())
   for key in ('generated_sha256','input_sha256'):
    if record[key]!=validation[key]:raise ValueError('Replay input differs: '+key)
   # inspect opens the OLD worker and requires exact packed-PNG and UV hashes
   # for every replay record before any coverage image is rendered.
   reports=sorted(replay.glob('layer-*.json'));output=base/'coverage'
   if output.exists():
    coverage=json.loads((output/'coverage.json').read_text())
    if coverage['model_sha256']!=row['model_sha256'] or coverage['manifest_sha256']!=sha(manifest):raise ValueError('Stale coverage')
   else:coverage=inspect(manifest,bake,output,provenance_reports=reports)
   if sha(bake/'worker.blend')!=row['model_sha256'] or sha(review)!=row['review_sha256']:raise ValueError('Canonical bake changed during audit')
   result.update(status='exact-replay-diagnostic-ready',manifest=str(manifest),manifest_sha256=sha(manifest),replay_report_sha256=sha(replay/'report.json'),coverage_report=str(output/'coverage.json'),coverage_report_sha256=sha(output/'coverage.json'),views=coverage['views'],unverified_materials=coverage['unverified_materials'])
  except Exception as error:
   result.update(status='fail-closed',reason=str(error));print('Replay held:',row['asset_id'],error,flush=True)
  finally:release()
  (base/'result.json').write_text(json.dumps(result,indent=2)+'\n');results.append(result)
  (root/'results.json').write_text(json.dumps(results,indent=2)+'\n');time.sleep(1.1)
if __name__=='__main__':
 args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
 run(int(args[0]) if args else None)
