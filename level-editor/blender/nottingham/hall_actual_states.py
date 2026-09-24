"""Render saved hall materials in every authored covered and revealed state."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9');sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from audit_stored_materials import run
args=sys.argv[sys.argv.index('--')+1:];w=Path(args[0]).resolve();dest=w/'inspection'/args[1];states=Path(json.loads((w/'state-packet.json').read_text())['directory'])
for s in json.loads((states/'states.json').read_text())['states']:
 selected=w/'inspection/state-models'/s['state'] if (w/'material-states.json').exists() else w
 r=run(selected,dest/s['state'],render=True,render_object_names=s['object_names'],frame_manifest=Path(s['path'])/'views.json');assert not r['problems'],r['problems']
