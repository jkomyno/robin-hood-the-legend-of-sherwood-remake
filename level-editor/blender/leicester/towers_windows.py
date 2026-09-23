"""Physical northwest front timber openings from reviewed source contours."""
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from towers import diagnostics,SPECS


def refine(workspace):
    config = json.loads((workspace/'workspace.json').read_text())
    if config['asset_id'] not in SPECS:
        raise ValueError(config['asset_id'])
    filename='nw-front-windows.json' if config['asset_id']=='leicester-northwest-tower' else config['asset_id']+'-windows.json'
    evidence = Path(__file__).resolve().parents[2]/'work/leicester-refinement/round-1/north-inspection'/filename
    record = json.loads(evidence.read_text())
    objects = [o for o in bpy.data.collections[config['collection_name']].all_objects
               if o.get('asset_group') == config['asset_id'] and o.get('source_node') in record['source_nodes']
               and o.get('projection_component') in ['tower-cover','tower-retained']]
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    ray = Vector((0, -cosine, sine))
    previous=workspace/'inspection/front-windows.json'
    reports = json.loads(previous.read_text()).get('changes',[]) if previous.exists() else []
    applied={(r['object'],tuple(r['seed'])) for r in reports}
    changed=0
    for hole in record['holes']:
        plane_y=SPECS[config['asset_id']]['center_y']
        ring = [Vector((x, plane_y, (-plane_y*sine-y)/cosine)) for x,y in hole['outline']]
        n = len(ring)
        verts = [v+ray*d for d in [-400,400] for v in ring]
        faces = [tuple(reversed(range(n))), tuple(range(n,2*n))]
        faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        mesh = bpy.data.meshes.new('Reviewed timber opening contour')
        mesh.from_pydata(verts, [], faces)
        bm = bmesh.new(); bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bmesh.ops.triangulate(bm, faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
        cutter = bpy.data.objects.new('Reviewed timber opening cutter', mesh)
        bpy.context.scene.collection.objects.link(cutter)
        for obj in objects:
            if obj.get('projection_component') != hole['projection_component']:continue
            if hole.get('source_nodes') and obj.get('source_node') not in hole['source_nodes']:continue
            if (obj.name,tuple(hole['seed'])) in applied:continue
            before = diagnostics(obj)
            modifier = obj.modifiers.new('Reviewed timber window opening', 'BOOLEAN')
            modifier.operation='DIFFERENCE'; modifier.solver='EXACT'; modifier.object=cutter
            bpy.context.view_layer.objects.active=obj
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            after=diagnostics(obj)
            if after['nonmanifold_edges'] or after['degenerate_faces']:
                raise RuntimeError('Window subtraction topology failure: '+str(after))
            if before!=after:
                reports.append(dict(object=obj.name,seed=hole['seed'],before=before,after=after));changed+=1
        bpy.data.objects.remove(cutter,do_unlink=True);bpy.data.meshes.remove(mesh)
    if not changed:raise RuntimeError('No new window geometry changed')
    (workspace/'inspection/front-windows.json').write_text(json.dumps(dict(record,changes=reports),indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))


if __name__=='__main__':refine(Path(sys.argv[sys.argv.index('--')+1]).resolve())
