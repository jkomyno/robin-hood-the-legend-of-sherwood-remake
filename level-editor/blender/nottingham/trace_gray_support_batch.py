"""Read-only exact-gray receiver/facing diagnostics for completed support models."""
import sys,runpy
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from texture_experiment_paths import selected_experiment
assets=sys.argv[sys.argv.index('--')+1:]
for asset in assets:
 p=selected_experiment(asset);b=p/'bake-background-support-001'
 sys.argv=['trace_visible_texture_gaps.py','--','--actual-gray',str(p/'repair-background-support/views.json'),str(b),str(b/'actual')]
 runpy.run_path(str(HERE/'trace_visible_texture_gaps.py'),run_name='__main__')
 print('GRAY RECEIVER AUDIT '+asset,flush=True)
