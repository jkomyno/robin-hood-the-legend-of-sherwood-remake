"""Withdraw only visually confirmed background-spill candidates, preserving old reviews."""
import json,shutil,sys
from pathlib import Path
from texture_experiment_paths import selected_experiment
from bake_ready_textures import ROOT,update_ledger
r=ROOT/'level-editor/work/nottingham-refinement/texture-generation'
for asset in sys.argv[1:]:
 p=selected_experiment(asset);f=p/'texture-review.json'
 if f.exists():
  history=p/'texture-review-before-background-hold.json'
  if not history.exists():shutil.copy2(f,history)
  review=json.loads(f.read_text())
 else:review={}
 review['status']='fix-needed';review.setdefault('notes',[]).append('Independent visual classification confirmed generated silhouette truncation. Held pending support correction and actual eight-view review.')
 f.write_text(json.dumps(review,indent=2)+'\n');job=json.loads((r/'static-bake-jobs.json').read_text())['assets'].get(asset)
 if job:job['status']='needs-refinement';update_ledger(r/'static-bake-jobs.json',asset,job)
 print('HELD '+asset)
