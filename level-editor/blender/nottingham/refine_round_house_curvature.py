"""Moderately round the Nottingham house between its measured perimeter anchors."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import bpy
from mathutils import Vector
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'level-editor/blender/nottingham/freeze_tooling.py').is_file())
sys.path.insert(0,str(ROOT/'level-editor/blender/nottingham'))
from refine_town_shells import replace, SIN, COS
WORK=ROOT/'level-editor/work/nottingham-refinement'
ASSET='nottingham-east-round-house'


def samples(anchors,steps=5,curvature=.7):
    result=[]
    for i in range(len(anchors)):
        a,b,c,d=[anchors[j%len(anchors)]for j in [i-1,i,i+1,i+2]]
        edge=[]
        for j in range(steps):
            t=j/steps;q=copy.deepcopy(b)
            for key in ['x','y']:
                linear=b[key]+(c[key]-b[key])*t
                smooth=.5*(2*b[key]+(-a[key]+c[key])*t+(2*a[key]-5*b[key]+4*c[key]-d[key])*t*t+(-a[key]+3*b[key]-3*c[key]+d[key])*t*t*t)
                q[key]=linear+curvature*(smooth-linear)
            edge.append(q)
        result.append(edge)
    return result


def refine():
    objects={int(o['source_node'].split('-')[-1]):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==ASSET}
    source=WORK/'baseline/nottingham.rhp.json';native=json.loads(source.read_text())['sight_obstacles'];anchors=copy.deepcopy(native[59]['points'])
    edges=samples(anchors);ring=[p for edge in edges for p in edge]
    apex=copy.deepcopy(native[60]['points'][1]);apex.update(x=2219.88,y=1633.10,z_top=255.14)
    mapping={60:[6],61:[7],62:[0],63:[1,2,3],64:[5],65:[4]}
    before={n:o.matrix_world.copy()for n,o in objects.items()};reports=[replace(objects[59],[ring])]
    for n,sectors in mapping.items():
        pieces=[]
        for sector in sectors:
            for j in range(5):
                start=edges[sector][j];end=edges[sector][j+1]if j<4 else edges[(sector+1)%8][0]
                tri=copy.deepcopy([start,end,apex])
                for q in tri:q['z_bottom']=q['z_top']-2.2
                pieces.append(tri)
        reports.append(replace(objects[n],pieces))
    assert all(objects[n].matrix_world==matrix for n,matrix in before.items())
    return {'asset_id':ASSET,'status':'refined','objects':reports,'transform_drift':0,
            'source_native_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'anchor_count':8,'perimeter_samples':40,'curve_blend':.7,
            'changes':['Replaced the eight flat wall chords with40 curved perimeter samples, preserving all eight measured anchors.','Matched the full roof to the rounded perimeter; existing dormers and shared roof apex remain unchanged.'],
            'inference':['Curvature between measured source anchors uses70% periodic cubic interpolation and30% straight interpolation; concealed arcs are inferred.','The source-supported irregular footprint is retained rather than forcing a perfect circle. No source artwork is repainted.']}


def main():
    from freeze_tooling import select_tooling
    from render_slots import acquire
    select_tooling();acquire()
    from refinement_workspace import modified
    out=WORK/'round-1/assets'/ASSET;archive=out/'inspection/pre-roundness'
    if not archive.exists():
        archive.mkdir()
        for name in ['model.blend','candidate.json','geometry-report.json','review.md']:
            shutil.copy2(out/name,archive/name)
        shutil.copytree(out/'modified',archive/'modified')
    bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'))
    report=refine()
    def signature():return {o.name:([tuple(v.co)for v in o.data.vertices],[tuple(f.vertices)for f in o.data.polygons])for o in bpy.data.objects if o.type=='MESH'}
    first=signature();refine();assert signature()==first;report['idempotence']='PASS'
    (out/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
    shutil.copy2(__file__,out/'recipe.py');bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
    print(modified(out),flush=True)
if __name__=='__main__':main()
