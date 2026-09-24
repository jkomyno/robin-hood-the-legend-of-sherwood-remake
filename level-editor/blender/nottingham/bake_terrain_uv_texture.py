"""Bake the guarded nonplanar Nottingham terrain atlas in a separate worker."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from bake_uv_atlas_texture import bake_uv
W=ROOT/'level-editor/work/nottingham-refinement/texture-generation/nottingham-terrain-ground-uv-atlas-v1'
print(bake_uv(W,W/'generation-short-no-mask-with-lighting-openrouter/generated-preserved.png',W/'bake-uv-v1'))
