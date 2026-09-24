"""Reopen the hut candidate and audit stored materials at all review cameras."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire(slots=2)
from audit_stored_materials import run
w=Path(sys.argv[sys.argv.index('--')+1]).resolve()
run(w,w/'inspection/stored-material',render=True)
from audit_small_hut_source_materials import main
main()
