"""Record a visually inspected support correction and preserve the prior review."""
import sys,json,shutil,os
from pathlib import Path
from texture_experiment_paths import selected_experiment
from bake_ready_textures import ROOT,sha,update_ledger
from record_texture_review import record
asset,bake_name,*notes=sys.argv[1:]
p=selected_experiment(asset);b=p/bake_name
ledger_path=ROOT/'level-editor/work/nottingham-refinement/texture-generation/static-bake-jobs.json';job=json.loads(ledger_path.read_text())['assets'].get(asset,dict(asset_id=asset,experiment=str(p),generation_review_sha256=sha(p/'generation-review.json'),status='baked-awaiting-visual-review'))
for src,name in [(p/'texture-review.json','previous-root-texture-review.json')]:
 if src.exists() and not (b/name).exists():shutil.copy2(src,b/name)
if not (b/'previous-static-job.json').exists():(b/'previous-static-job.json').write_text(json.dumps(job,indent=2)+'\n')
v=json.loads((b/'validation.json').read_text());job.update(experiment=str(p),output=str(b),model_sha256=sha(b/'worker.blend'),actual_sheet_sha256=sha(b/'actual/textured.png'),validation_sha256=sha(b/'validation.json'),geometry_verified=v['geometry_verified'],outside_objects_unchanged=v['outside_objects_unchanged'],counts=v['counts']);update_ledger(ledger_path,asset,job)
record(asset,'ready-for-user-texture-review',notes)
diagnosis=p/'repair-background-support/diagnosis.json';d=json.loads(diagnosis.read_text());g=Path(d.get('generation_directory',p/'generation-short-no-mask-with-lighting-openrouter'))
for path in [p/'texture-review.json',b/'texture-review.json']:
 r=json.loads(path.read_text());r['background_support_diagnosis']=dict(path=str(diagnosis),sha256=sha(diagnosis));r['correction_manifest']=dict(path=str(p/'repair-background-support/views.json'),sha256=sha(p/'repair-background-support/views.json'))
 if path==p/'texture-review.json':r['generation']=os.path.relpath(g,p)
 path.write_text(json.dumps(r,indent=2)+'\n')
job=json.loads(ledger_path.read_text())['assets'][asset];job['texture_review_sha256']=sha(b/'texture-review.json');job['correction_manifest']=str(p/'repair-background-support/views.json');job['correction_manifest_sha256']=sha(p/'repair-background-support/views.json');update_ledger(ledger_path,asset,job)
sys.path.insert(0,str(ROOT/'level-editor/refinement'));from build_texture_gallery import candidate
candidate(p,'Nottingham');print(asset+' gallery candidate PASS')
