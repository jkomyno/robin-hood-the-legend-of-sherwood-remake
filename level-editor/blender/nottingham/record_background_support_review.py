"""Record a visually inspected support correction and preserve the prior review."""
import sys,json,shutil,os,argparse
from pathlib import Path
from texture_experiment_paths import selected_experiment
from bake_ready_textures import ROOT,sha,update_ledger
from record_texture_review import record
parser=argparse.ArgumentParser();parser.add_argument('--actual-sheet',default='actual/textured.png');parser.add_argument('--coverage',default='coverage/coverage.json');parser.add_argument('asset');parser.add_argument('bake_name');parser.add_argument('notes',nargs='+');args=parser.parse_args()
asset,bake_name,notes=args.asset,args.bake_name,args.notes
p=selected_experiment(asset);b=p/bake_name
if Path(bake_name).name!=bake_name:raise ValueError('Local bake name required')
v=json.loads((b/'validation.json').read_text())
manifest_entries=[(Path(k),digest) for k,digest in v['evidence_sha256'].items() if Path(k).name=='views.json']
if len(manifest_entries)!=1:raise ValueError('Unique guarded correction manifest required')
manifest,digest=manifest_entries[0]
if sha(manifest)!=digest or not manifest.resolve().is_relative_to(p.resolve()):raise ValueError('Correction manifest drift/escape')
from texture_actual_evidence import actual_sheet
actual=actual_sheet(b,dict(actual_sheet_path=args.actual_sheet,actual_sheet_sha256=sha(b/args.actual_sheet)))
coverage=b/args.coverage
if Path(args.coverage).is_absolute() or '..' in Path(args.coverage).parts or not coverage.resolve().is_relative_to(b.resolve()):raise ValueError('Coverage path escape')
c=json.loads(coverage.read_text())
if c['model_sha256']!=sha(b/'worker.blend') or c['manifest_sha256']!=sha(manifest):raise ValueError('Coverage evidence drift')
ledger_path=ROOT/'level-editor/work/nottingham-refinement/texture-generation/static-bake-jobs.json';job=json.loads(ledger_path.read_text())['assets'].get(asset,dict(asset_id=asset,experiment=str(p),generation_review_sha256=sha(p/'generation-review.json'),status='baked-awaiting-visual-review'))
for src,name in [(p/'texture-review.json','previous-root-texture-review.json')]:
 if src.exists() and not (b/name).exists():shutil.copy2(src,b/name)
if not (b/'previous-static-job.json').exists():(b/'previous-static-job.json').write_text(json.dumps(job,indent=2)+'\n')
v=json.loads((b/'validation.json').read_text());job.update(experiment=str(p),output=str(b),model_sha256=sha(b/'worker.blend'),actual_sheet_sha256=sha(actual),actual_sheet_path=args.actual_sheet,validation_sha256=sha(b/'validation.json'),geometry_verified=v['geometry_verified'],outside_objects_unchanged=v['outside_objects_unchanged'],counts=v['counts']);update_ledger(ledger_path,asset,job)
record(asset,'ready-for-user-texture-review',notes)
diagnosis=manifest.parent/'diagnosis.json';d=json.loads(diagnosis.read_text());g=Path(d.get('generation_directory',p/'generation-short-no-mask-with-lighting-openrouter'))
for path in [p/'texture-review.json',b/'texture-review.json']:
 r=json.loads(path.read_text());r['background_support_diagnosis']=dict(path=str(diagnosis),sha256=sha(diagnosis));r['correction_manifest']=dict(path=str(manifest),sha256=sha(manifest))
 if path==p/'texture-review.json':r['generation']=os.path.relpath(g,p)
 if coverage.exists():
  if json.loads(coverage.read_text())['model_sha256']!=sha(b/'worker.blend'):raise ValueError('Coverage diagnostic model drift')
  r['coverage_diagnostic']=dict(path=str(coverage),sha256=sha(coverage))
 path.write_text(json.dumps(r,indent=2)+'\n')
job=json.loads(ledger_path.read_text())['assets'][asset];job['texture_review_sha256']=sha(b/'texture-review.json');job['correction_manifest']=str(manifest);job['correction_manifest_sha256']=sha(manifest);update_ledger(ledger_path,asset,job)
sys.path.insert(0,str(ROOT/'level-editor/refinement'));from build_texture_gallery import candidate
candidate(p,'Nottingham');print(asset+' gallery candidate PASS')
