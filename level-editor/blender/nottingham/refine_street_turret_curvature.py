"""Round the street turret between preserved masonry and roof anchors."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import bpy
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'level-editor/blender/nottingham/freeze_tooling.py').is_file())
sys.path.insert(0,str(ROOT/'level-editor/blender/nottingham'))
from refine_town_shells import replace
from refine_round_house_curvature import samples
WORK=ROOT/'level-editor/work/nottingham-refinement'
ASSET='nottingham-upper-street-turret'

def refine():
    objects={int(o['source_node'].split('-')[-1]):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==ASSET}
    source=WORK/'baseline/nottingham.rhp.json';native=json.loads(source.read_text())['sight_obstacles'];p={n:copy.deepcopy(native[n]['points'])for n in objects}
    wall=[q for edge in samples(p[150],steps=6)for q in edge]
    ring=[p[151][0],p[151][1],p[152][1],p[153][1],p[150][2],p[150][3],p[154][2]]
    edges=samples(ring,steps=5);apex=copy.deepcopy(p[151][2]);apex.update(x=1347.10,y=761.38,z_top=145.46)
    matrices={n:o.matrix_world.copy()for n,o in objects.items()};reports=[replace(objects[150],[wall])]
    for n,sectors in {151:[0],152:[1],153:[2,3,4,5],154:[6]}.items():
        pieces=[]
        for sector in sectors:
            for j in range(5):
                start=edges[sector][j];end=edges[sector][j+1]if j<4 else edges[(sector+1)%7][0]
                tri=copy.deepcopy([start,end,apex])
                for q in tri:q['z_bottom']=q['z_top']-2.2
                pieces.append(tri)
        reports.append(replace(objects[n],pieces))
    assert all(objects[n].matrix_world==m for n,m in matrices.items())
    return {'asset_id':ASSET,'status':'refined','objects':reports,'transform_drift':0,
            'source_native_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'masonry_anchor_count':6,'masonry_samples':36,'roof_anchor_count':7,'roof_samples':35,'curve_blend':.7,
            'changes':['Rounded the six-sided masonry into36 curved perimeter samples while preserving all measured corners.','Rounded the full pointed roof into35 perimeter samples, preserving its seven source anchors, western overhang and shared apex.'],
            'inference':['Between-anchor curvature uses70% periodic cubic and30% linear interpolation; concealed rear arcs are inferred.','The measured irregular footprint and asymmetric eave overhang remain; geometry is not forced into an ideal circular cone.'],
            'dependencies':{name:hashlib.sha256((ROOT/'level-editor/blender/nottingham'/name).read_bytes()).hexdigest()for name in ['refine_town_shells.py','refine_round_house_curvature.py']}}

def main():
    from freeze_tooling import select_tooling
    from render_slots import acquire
    select_tooling();acquire()
    from refinement_workspace import modified
    out=WORK/'round-1/assets'/ASSET;archive=out/'inspection/pre-roundness'
    if not archive.exists():
        archive.mkdir()
        for name in ['model.blend','candidate.json','geometry-report.json','review.md']:shutil.copy2(out/name,archive/name)
        shutil.copytree(out/'modified',archive/'modified')
    bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'));report=refine()
    def sig():return {o.name:([tuple(v.co)for v in o.data.vertices],[tuple(f.vertices)for f in o.data.polygons])for o in bpy.data.objects if o.type=='MESH'}
    first=sig();refine();assert sig()==first;report['idempotence']='PASS'
    (out/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,out/'recipe.py');bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));print(modified(out),flush=True)
if __name__=='__main__':main()
