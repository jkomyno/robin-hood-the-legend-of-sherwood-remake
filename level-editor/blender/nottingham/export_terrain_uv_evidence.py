"""Export approved terrain atlas geometry without rendering or modifying it."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from export_uv_atlas_evidence import export
W=ROOT/'level-editor/work/nottingham-refinement'
print(export(W/'round-27/assets/nottingham-terrain-ground',W/'coordinator-audit/terrain-texture-preparation/uv-evidence.json'))
