"""Replace a nonplanar wall cap with two planar front-gable wall pieces."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import bpy
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'level-editor/blender/nottingham/freeze_tooling.py').is_file())
sys.path.insert(0,str(ROOT/'level-editor/blender/nottingham'))
from refine_town_roof_completions import refine as complete_roof
from refine_town_shells import replace
WORK=ROOT/'level-editor/work/nottingham-refinement'
ASSET='nottingham-north-stone-house'

def refine():
    report=complete_roof(ASSET)
    native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles']
    wall=copy.deepcopy(native[111]['points'])
    left=copy.deepcopy(wall[0]);right=copy.deepcopy(wall[-1]);right['z_top']=native[115]['points'][0]['z_top']-2.2
    middle=copy.deepcopy(left);middle.update(x=1698.02,z_top=154.3)
    t=(middle['x']-left['x'])/(right['x']-left['x']);middle['y']=left['y']+t*(right['y']-left['y'])
    pieces=[wall]
    for a,b in [(left,middle),(middle,right)]:
        aa,bb=copy.deepcopy(a),copy.deepcopy(b);aa['y']-=2;bb['y']-=2
        poly=copy.deepcopy([a,b,bb,aa])
        for q in poly:q['z_bottom']=119.0
        pieces.append(poly)
    obj=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==ASSET and o.get('source_node')=='building-111')
    corrected=replace(obj,pieces)
    report['objects']=[o for o in report['objects']if o['source_node']!='building-111']+[corrected]
    report['changes'].append('Removed the nonplanar masonry top cap that protruded through the front-right roof valley; replaced it with two thin planar gable wall pieces supported by the original flat wall cap.')
    report['inference'].append('The front gable has a two-source-depth-unit concealed thickness and penetrates the original wall slightly for a closed contact; its visible outline follows the existing roof eaves.')
    report['diagnosis']='Flat part-ID render identifies stray triangular protrusion as building-111 wall cap, not building-116 roof receiver.'
    report['dependencies']={name:hashlib.sha256((ROOT/'level-editor/blender/nottingham'/name).read_bytes()).hexdigest()for name in ['refine_town_roof_completions.py','refine_town_shells.py']}
    return report

def main():
    from freeze_tooling import select_tooling
    from render_slots import acquire
    select_tooling();acquire()
    from refinement_workspace import modified
    out=WORK/'round-1/assets'/ASSET;archive=out/'inspection/pre-gable-correction'
    if not archive.exists():
        archive.mkdir()
        for name in ['model.blend','candidate.json','geometry-report.json','review.md']:shutil.copy2(out/name,archive/name)
        shutil.copytree(out/'modified',archive/'modified')
    bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'));report=refine()
    def sig():return {o.name:([tuple(v.co)for v in o.data.vertices],[tuple(f.vertices)for f in o.data.polygons])for o in bpy.data.objects if o.type=='MESH'}
    first=sig();refine();assert sig()==first;report['idempotence']='PASS'
    (out/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,out/'recipe.py');bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));print(modified(out),flush=True)
if __name__=='__main__':main()
