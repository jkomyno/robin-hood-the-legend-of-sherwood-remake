"""Freeze final mask authority with the pre-correction geometry as comparison input."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling

def main():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from refinement_workspace import prepare
 before=WORK/'round-40/assets/nottingham-castle-main-hall';author=WORK/'round-41/assets/nottingham-castle-main-hall';out=WORK/'round-42/assets/nottingham-castle-main-hall';cfg=json.loads((author/'workspace.json').read_text())
 bpy.ops.wm.open_mainfile(filepath=str(before/'model.blend'))
 prepare(out,asset_id=cfg['asset_id'],scene_name=cfg['scene_name'],collection_name=cfg['collection_name'],source_path=author/'reference/source.png',grouping_manifest=author/'reference/grouping.json',inventory_path=author/'reference/inventory.json',review_path=author/'reference/grouping-review.json',projection_manifest=author/'projection-layers.json',source_mask_manifest=author/'source-masks.json',width=cfg['width'],height=cfg['height'],context_padding=cfg['context_padding'],framing_padding=cfg.get('framing_padding',1.04))
 bpy.ops.wm.open_mainfile(filepath=str(author/'model.blend'));bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
 print('HALL42 INPUT FROZEN FROM40 GEOMETRY WITH FINAL MASK AUTHORITY; WORKING MODEL FROM41',flush=True)
if __name__=='__main__':main()
