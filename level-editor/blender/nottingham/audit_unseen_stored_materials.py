"""Read-only actual-material render batch for previously unreviewed assets."""
import json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
from audit_stored_materials import run
for w in json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text()):
 w=Path(w);out=w/'inspection/unseen-stored-material'
 if out.exists():continue
 print(run(w,out,render=True,export=False)['status'],w,flush=True)
