"""Complete five measured roof envelopes, preserving canonical source ownership."""
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
from refine_town_shells import replace
WORK=ROOT/'level-editor/work/nottingham-refinement'

def slab(poly,thickness=2.2):
    poly=copy.deepcopy(poly)
    for q in poly:q['z_bottom']=q['z_top']-thickness
    return poly

def plane(poly,x,y):
    a,b,c=[Vector((q['x'],q['y'],q['z_top'])) for q in poly[:3]]
    n=(b-a).cross(c-a)
    return a.z-(n.x*(x-a.x)+n.y*(y-a.y))/n.z

def clip(poly,a,b,sign):
    def side(p):return sign*((b['x']-a['x'])*(p['y']-a['y'])-(b['y']-a['y'])*(p['x']-a['x']))
    out=[]
    for q,r in zip(poly,poly[1:]+poly[:1]):
        v,w=side(q),side(r)
        if v>=0:out.append(copy.deepcopy(q))
        if (v<0)!=(w<0):
            t=v/(v-w);s=copy.deepcopy(q)
            for k in ['x','y']:s[k]=q[k]+t*(r[k]-q[k])
            out.append(s)
    return out

def supports(footprint,roof1,roof2,a,b):
    out=[]
    for sign in [1,-1]:
        poly=clip(footprint,a,b,sign)
        if len(poly)<3:raise ValueError('Ridge does not cross footprint')
        cx=sum(q['x']for q in poly)/len(poly);cy=sum(q['y']for q in poly)/len(poly)
        # Roof planes descend away from the ridge; the lower is the physical envelope.
        roof=min([roof1,roof2],key=lambda r:plane(r,cx,cy))
        for q in poly:q.update(z_bottom=0,z_top=plane(roof,q['x'],q['y'])-2.2)
        out.append(poly)
    return out

def refine(aid):
    objs={int(o['source_node'].split('-')[-1]):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==aid}
    path=WORK/'baseline/nottingham.rhp.json';native=json.loads(path.read_text())['sight_obstacles'];p={n:copy.deepcopy(native[n]['points'])for n in objs};edits={};notes=[]
    if aid=='nottingham-east-round-house':
        apex=copy.deepcopy(p[60][1]);apex.update(x=2219.88,y=1633.10,z_top=255.14)
        ring=copy.deepcopy(p[59]);mapping={60:[6],61:[7],62:[0],63:[1,2,3],64:[5],65:[4]}
        for n,edges in mapping.items():edits[n]=[slab([ring[i],ring[(i+1)%8],apex])for i in edges]
        edits[59]=[p[59]]
        for n in [66,67,68,69]:
            for q in p[n]:q['z_bottom']=166.667
            edits[n]=[p[n]]
        changes=['Completed eight closed roof sectors around one shared apex, including two previously missing rear sectors; retained four source-measured dormer components with supports confined above the masonry eave, and closed the original eight-sided wall envelope.']
        notes=['Rear roof facets follow the eight-sided masonry footprint. Shared apex reconciles native subpixel discrepancies; source-hidden facets remain neutral.']
    elif aid=='nottingham-upper-street-turret':
        apex=copy.deepcopy(p[151][2]);apex.update(x=1347.10,y=761.38,z_top=145.46)
        ring=[p[151][0],p[151][1],p[152][1],p[153][1],p[150][2],p[150][3],p[154][2]]
        for n,edges in {151:[0],152:[1],153:[2,3,4,5],154:[6]}.items():edits[n]=[slab([ring[i],ring[(i+1)%7],apex])for i in edges]
        changes=['Completed the pointed roof around its full perimeter, retaining the measured western overhang and adding concealed rear slopes.']
        notes=['Shared apex averages native peak heights spanning 1.69 vertical source units. Concealed rear sectors are inferred from masonry footprint; western eave remains at its measured overhang.']
    elif aid=='nottingham-east-boarded-house':
        p[77][2]=copy.deepcopy(p[76][1]);p[77][3]=copy.deepcopy(p[76][0])
        edits={76:[slab(p[76])],77:[slab(p[77])],73:supports(p[73],p[76],p[77],p[76][0],p[76][1]),78:[slab(p[78])]}
        support=copy.deepcopy(p[78])
        for q in support:q.update(z_bottom=0,z_top=q['z_top']-2.2)
        edits[79]=[support]
        changes=['Closed both main roof slabs along one measured ridge and fitted two supporting wall volumes within the original masonry footprint.','Added closed support beneath the separate source-edge roof, replacing its floating lower receiver.']
        notes=['Detached parts078/079 are a separate source-edge structure retained in their canonical group; their concealed support depth is inferred. Main wall footprint is unchanged.']
    elif aid=='nottingham-castle-east-attached-house':
        front=p[142];back=[copy.deepcopy(front[0]),copy.deepcopy(front[3]),copy.deepcopy(p[141][3]),copy.deepcopy(p[141][0])]
        for q in back[2:]:q['z_top']=127.63801
        edits={142:[slab(front),slab(back)],141:supports(p[141],front,back,front[0],front[3])}
        changes=['Added a closed rear roof slope between the measured ridge and original back wall footprint; fitted the supporting wall envelope to both roof undersides.']
        notes=['The rear roof pitch is inferred inside the existing wall footprint; the source-visible front slope and chimney remain measured.']
    elif aid=='nottingham-north-stone-house':
        # A lower receiver uses the same source pixel positions as the roof but
        # sits one storey below it; shifting y and z equally preserves y-z.
        for q in p[116]:q['y']+=117;q['z_top']+=117;q['z_bottom']+=117
        ridge=copy.deepcopy(p[113][3]);rear=copy.deepcopy(p[113][2])
        p[112][2]=copy.deepcopy(ridge);p[114][2]=copy.deepcopy(ridge);p[115][2]=copy.deepcopy(ridge);p[116][1]=copy.deepcopy(ridge)
        p[117][1]=copy.deepcopy(ridge);p[117][2]=copy.deepcopy(rear)
        p[116][0]=copy.deepcopy(p[115][0]);p[116][2]=copy.deepcopy(p[117][0])
        gable=copy.deepcopy(p[114][0]);gable.update(x=1698.02,y=688.254,z_top=156.5)
        p[114][0]=copy.deepcopy(gable);p[115][1]=copy.deepcopy(gable)
        wall=copy.deepcopy(p[111]);wall[-1]['z_top']=p[115][0]['z_top']-2.2
        wall.append(copy.deepcopy(gable));wall[-1].update(z_bottom=0,z_top=gable['z_top']-2.2)
        edits={n:[slab(p[n])]for n in [112,113,114,115,116,117]}
        edits[117].append(slab([p[113][1],rear,p[117][3]]))
        edits[118]=[p[118]]
        edits[111]=[wall]
        changes=['Moved the detached roof triangle up117 source-height units and back117 source-depth units, preserving its source-camera position before subpixel ridge reconciliation.','Closed roof slopes with finite thickness, shared ridge anchors and a concealed rear end cap; filled the front decorative gable wall to its measured raised eave, closing the opening above the original flat wall cap.']
        notes=['The117-unit source-ray depth correction is inferred from adjacent roof datum117.334. The translated116 front eave is reconciled upward8.65 source-height units to the visible115 eave so both slopes share a continuous edge; this secondary receiver correction is inferred from adjacent source-visible roof geometry. Concealed end cap is inferred.']
    else:raise ValueError(aid)
    matrices={n:o.matrix_world.copy()for n,o in objs.items()}
    reports=[replace(objs[n],pieces)for n,pieces in edits.items()]
    assert all(objs[n].matrix_world==m for n,m in matrices.items())
    return {'asset_id':aid,'status':'refined','objects':reports,'changes':changes,'inference':notes+['All unsupported source pixels remain neutral; canonical source ownership and world transforms are preserved.'],'transform_drift':0,'mesh_helper_sha256':hashlib.sha256((ROOT/'level-editor/blender/nottingham/refine_town_shells.py').read_bytes()).hexdigest(),'source_native_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def main():
    from freeze_tooling import select_tooling
    from render_slots import acquire
    select_tooling();acquire()
    from refinement_workspace import modified
    for aid in sys.argv[sys.argv.index('--')+1:]:
        out=WORK/'round-1/assets'/aid
        archived=out/'inspection/pre-completion-model.blend'
        if not archived.exists():shutil.copy2(out/'model.blend',archived)
        bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'))
        report=refine(aid)
        def signature():return {o.name:([tuple(v.co)for v in o.data.vertices],[tuple(f.vertices)for f in o.data.polygons])for o in bpy.data.objects if o.type=='MESH'}
        once=signature();refine(aid);assert signature()==once;report['idempotence']='PASS'
        (out/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
        shutil.copy2(__file__,out/'recipe.py');bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
        result=modified(out);print(aid,result['status'],flush=True)
if __name__=='__main__':main()
