"""Rebuild the two source-reviewed upper-west groups after chimney reassignment."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
from prepare_assets import preflight_source
from refine_town_shells import refine as house_refine, replace, SIN, COS

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'level-editor').is_dir())
WORK = ROOT/'level-editor/work/nottingham-refinement'
ASSETS = ['nottingham-upper-west-house', 'nottingham-upper-west-lean-to']


def refine_lean_to():
    objects = {o.get('source_node'):o for o in bpy.data.collections['nottingham Working'].all_objects
               if o.type=='MESH' and o.get('asset_group')==ASSETS[1]}
    if set(objects) != {'building-165','building-166'}:
        raise ValueError('Lean-to must include its source-supported chimney 166')
    obj=objects['building-165']; tag='nottingham_lean_to_eave_v1'
    if tag in obj:return json.loads(obj[tag])
    native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][165]['points']
    cx=sum(p['x'] for p in native)/4;cy=sum(p['y'] for p in native)/4
    # Preserve the source roof perimeter exactly. Its shallow inset underside
    # gives the visible eave a finite thickness without changing the silhouette.
    points=[]
    for ring in range(4):
        for p in native:
            x,y=p['x'],p['y'];z=p['z_bottom'] if ring==0 else p['z_top']-(2.2 if ring<3 else 0)
            if ring in (0,1):
                dx,dy=cx-x,cy-y;length=(dx*dx+dy*dy)**.5
                x+=dx/length*1.2;y+=dy/length*1.2
            points.append(Vector((x,-y/SIN,z/COS)))
    faces=[(3,2,1,0),(12,13,14,15)]
    for ring in range(3):
        for i in range(4):
            a=ring*4+i;b=ring*4+(i+1)%4;faces.append((a,b,b+4,a+4))
    inverse=obj.matrix_world.inverted();mesh=bpy.data.meshes.new(obj.name+' / closed eave profile')
    mesh.from_pydata([inverse@p for p in points],[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
    if any(defects.values()):raise ValueError(defects)
    bm.to_mesh(mesh);bm.free();uv=mesh.uv_layers.new(name='Source projection')
    for loop in mesh.loops:
        p=points[loop.vertex_index];uv.data[loop.index].uv=(p.x/2304,1-(-p.y*SIN-p.z*COS)/3520)
    for mat in obj.data.materials:mesh.materials.append(mat)
    obj.data=mesh
    chimney_points=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][166]['points']
    chimney_report=replace(objects['building-166'],[chimney_points])
    report={'asset_id':ASSETS[1],'status':'refined','changes':['Retained source165 roof perimeter and slope; closed the full body with a thin eave profile.','Associated the visible chimney166 with its own roof165; both remain independently selectable parts.'],
            'inference':['The concealed wall inset is 1.2 native planar units; the finite roof edge is 2.2 native vertical units.','Rear and underside continuation are inferred; no unsupported interior is asserted.'],
            'objects':[{'source_node':'building-165','vertices':len(mesh.vertices),'faces':len(mesh.polygons),**defects},chimney_report],
            'grouping_evidence':'grouping/166-grouping-audit.json','approval':'pending','texture_generation':'not started'}
    obj[tag]=json.dumps(report,sort_keys=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tooling-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    from render_slots import acquire
    acquire();tooling=select_tooling(args.tooling_dir)
    from refinement_workspace import prepare,modified
    import refinement_review
    fit=refinement_review.fit_camera
    def padded(*a,**kw):kw['padding']=1.25;return fit(*a,**kw)
    refinement_review.fit_camera=padded
    catalog=WORK/'grouping/catalog-v6.json';inventory=WORK/'inventory/inventory-v2.json';review=WORK/'grouping/grouping-review-v6.json'
    for asset in ASSETS:
        output=args.output.resolve()/asset
        if output.exists():raise FileExistsError(output)
        bpy.ops.wm.open_mainfile(filepath=str(WORK/'grouped/nottingham-grouped-v6.blend'))
        preflight_source('nottingham Refinement','nottingham Working',json.loads(catalog.read_text()))
        prepared=prepare(output,asset_id=asset,scene_name='nottingham Refinement',collection_name='nottingham Working',
                         source_path=WORK/'source-states/covered.png',grouping_manifest=catalog,inventory_path=inventory,review_path=review,
                         source_mask_manifest=WORK/'mask-review/source-masks-v11-baseline.json',width=256,height=256,context_padding=36)
        report=house_refine(asset) if asset==ASSETS[0] else refine_lean_to()
        if asset==ASSETS[0]:report['inference']=[x.replace('The detached canonical pillar 166 is preserved in place pending grouping review.','Chimney166 now belongs to the separately selectable rear lean-to.') for x in report['inference']]
        def geometry():
            return {o.name:([list(v.co) for v in o.data.vertices],[list(p.vertices) for p in o.data.polygons],[list(r) for r in o.matrix_world]) for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'}
        first=geometry()
        house_refine(asset) if asset==ASSETS[0] else refine_lean_to()
        if first!=geometry():raise ValueError('Geometry recipe is not idempotent')
        report['idempotence']='PASS'
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(output/'model.blend'))
        (output/'geometry-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
        validation=modified(output)
        (output/'regrouping-validation.json').write_text(json.dumps({'status':'PASS','tooling':tooling,'validation':validation,'prepared':prepared,'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
        print('COMPLETE '+asset,flush=True)


if __name__=='__main__':main()
