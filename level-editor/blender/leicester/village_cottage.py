"""Close village shell undersides and reconcile measured shared roof seams."""
import argparse
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector
import bmesh
import math
import hashlib
import numpy as np
PAIRS=[('building-001','building-002'),('building-024','building-029'),('building-016','building-017'),('building-003','building-007'),('building-009','building-014'),('building-064','building-065'),('building-093','building-096'),('building-079','building-080')]

def access_pole(obj,workspace):
    config=json.loads((workspace/'workspace.json').read_text())
    assignment=Path(config['source_mask_manifest']);contract=json.loads(assignment.read_text());inventory_path=(assignment.parent/contract['mask_inventory']).resolve()
    native=next(m for m in json.loads(inventory_path.read_text())['masks'] if m['index']==154)
    path=(inventory_path.parent/native['png']).resolve(strict=True);image=bpy.data.images.load(str(path),check_existing=False);width,height=image.size
    pixels=np.empty(width*height*4,dtype=np.float32);image.pixels.foreach_get(pixels);bpy.data.images.remove(image);bitmap=pixels.reshape(height,width,4)[::-1,:,0]>0.5
    occupied={(int(x),int(y)) for y,x in np.argwhere(bitmap)};edges={}
    for x,y in occupied:
        for neighbor,edge in [((x,y-1),((x,y),(x+1,y))),((x+1,y),((x+1,y),(x+1,y+1))),((x,y+1),((x+1,y+1),(x,y+1))),((x-1,y),((x,y+1),(x,y)))]:
            if neighbor not in occupied:
                if edge[0] in edges:raise ValueError('Ambiguous native pole contour')
                edges[edge[0]]=edge[1]
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35));top_y=-1206.113;top_z=76.946;bottom_y=-1230.717;top_pixel=-top_y*sine-top_z*cosine;bottom_pixel=-bottom_y*sine
    dy=(bottom_y-top_y)/(bottom_pixel-top_pixel);dz=(-1-dy*sine)/cosine;normal=Vector((0,-dz,dy)).normalized()
    grid=sorted({p for x,y in occupied for p in [(x,y),(x+1,y),(x+1,y+1),(x,y+1)]});front=[]
    for px,py in grid:
        x=px+native['box_top_left'][0];pixel_y=py+native['box_top_left'][1];y=top_y+(pixel_y-top_pixel)*dy;z=(-pixel_y-y*sine)/cosine;front.append(Vector((x,y,z)))
    n=len(front);vertices=front+[p+normal*2.0 for p in front];indices={p:i for i,p in enumerate(grid)}
    front_faces=[tuple(indices[p] for p in [(x,y),(x+1,y),(x+1,y+1),(x,y+1)]) for x,y in sorted(occupied)]
    faces=front_faces+[tuple(n+i for i in reversed(face)) for face in front_faces]+[(indices[a],indices[b],n+indices[b],n+indices[a]) for a,b in edges.items()]
    mesh=bpy.data.meshes.new('Leicester Pegged Access Pole');mesh.from_pydata([obj.matrix_world.inverted()@v for v in vertices],[],faces)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='UVMap')
    mat=bpy.data.materials.get('Leicester Access Pole Unknown') or bpy.data.materials.new('Leicester Access Pole Unknown');mat.diffuse_color=(0.5,0.5,0.5,1);mesh.materials.append(mat);obj.data=mesh
    return {'source_node':'building-021','native_mask':154,'native_mask_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'silhouette_pixels':len(occupied),'grid_vertices_per_side':n,'boundary_edges':len(edges),'visible_crosspegs':9,'peg_pixel_y':[618,631,638,649,659,668,679,687,695],'inference':'A two-unit-deep extrusion along the existing tilted receiver plane; unseen roundness/depth cannot be established.','geometry_representation':'Exact native silhouette preserving the one upright, crosspegs and diagonal branch/brace; no invented second rail.'}

def close_mill_north_joins(bynode):
    reports=[]
    for node in ['building-016','building-018','building-022']:
        obj=bynode[node];bm=bmesh.new();bm.from_mesh(obj.data)
        def nearest(p):
            p=Vector(p);v=min(bm.verts,key=lambda v:(obj.matrix_world@v.co-p).length)
            if (obj.matrix_world@v.co-p).length>0.6:raise ValueError(f'Missing measured join anchor {node}/{p}')
            return v
        if node=='building-016':
            start=nearest((2315.24,-1277.98,76.91));end=nearest((2437.17,-1191.14,76.91))
            long=bm.edges.get((start,end))
            if long and long.is_boundary:
                for point in [(2416.32,-1206.01,76.91),(2427.93,-1197.73,76.91)]:
                    target=nearest(point);edge=bm.edges.get((start,end));a=obj.matrix_world@start.co;b=obj.matrix_world@end.co;t=((obj.matrix_world@target.co-a).dot(b-a))/(b-a).length_squared
                    _,created=bmesh.utils.edge_split(edge,start,t);created.co=target.co.copy();start=created
                bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.2)
        else:
            anchors=([[(2242.41,-1173.83,83.01),(2242.47,-1173.77,0),(2228.16,-1183.63,0),(2228.16,-1183.63,50.05),(2242.41,-1173.83,55.48)]] if node=='building-018' else [[(2228.2,-1183.9,50.05),(2242.41,-1173.83,55.48),(2305.09,-1130.75,79.35)],[(2228.2,-1183.9,0),(2228.2,-1183.9,50.05),(2242.41,-1173.83,55.48),(2242.41,-1173.83,0)]])
            for points in anchors:
                vertices=[nearest(p) for p in points]
                if bm.faces.get(vertices) is None:bm.faces.new(vertices)
        edges=[e for e in bm.edges if e.is_boundary]
        # The recorded join faces reduce the remaining opening to a ground
        # underside (018/022) or the four-edge eave lip (016).
        if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        remaining=sum(not e.is_manifold for e in bm.edges)
        if remaining:raise ValueError(f'Join repair left {remaining} nonmanifold edges on {node}')
        reports.append({'source_node':node,'nonmanifold_edges':remaining,'inference':'Hidden component joining faces and underside; original visible wall/roof anchors retained.'})
        bm.to_mesh(obj.data);bm.free();obj.data.update()
    return reports

def weld_measured_splits(obj):
    if obj.get('source_node') not in {'building-003','building-007','building-065','building-096'}:return None
    bm=bmesh.new();bm.from_mesh(obj.data);before=len(bm.verts)
    # The native diagnostic measures 0.77–0.85 world-unit duplicated corners
    # along existing straight roof/wall seams, just beyond the default weld.
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.9)
    bm.to_mesh(obj.data);bm.free();obj.data.update()
    return {'source_node':obj['source_node'],'merged_vertices':before-len(obj.data.vertices),'weld_distance':0.9,'evidence':'shell-diagnostic.json boundary_world_edges: existing duplicated roof/wall corners.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);p.add_argument('--reproject',action='store_true');args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);w=args.workspace.resolve();c=json.loads((w/'workspace.json').read_text())
    helpers=next(p/'level-editor/blender' for p in Path(__file__).resolve().parents if (p/'level-editor/blender/refinement_workspace.py').exists());sys.path.insert(0,str(helpers))
    from refinement_workspace import validate
    support=Path(__file__).resolve().parent/'recipe_support'
    if support.exists():
        sys.path.insert(0,str(support));from village_shells import repair
    else:
        from leicester.village_shells import repair
    validate(w)
    targets=[o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==c['asset_id'] and not o.get('projection_component')]
    if not targets:raise ValueError('Missing owned meshes')
    measured_welds=[r for o in targets if (r:=weld_measured_splits(o)) is not None];reports=[repair(o) for o in targets];seams=[]
    bynode={o['source_node']:o for o in targets}
    for left,right in PAIRS:
        if left not in bynode or right not in bynode:continue
        a,b=bynode[left],bynode[right]
        va=[a.matrix_world@v.co for v in a.data.vertices];vb=[b.matrix_world@v.co for v in b.data.vertices]
        tolerance=7.0 if (left,right)==('building-016','building-017') else (1.1 if (left,right) in [('building-001','building-002'),('building-003','building-007')] else 0.8)
        matches=[(i,j) for i,x in enumerate(va) for j,y in enumerate(vb) if (x-y).length<tolerance]
        if len({i for i,j in matches})!=len(matches) or len({j for i,j in matches})!=len(matches):raise ValueError('Ambiguous seam vertex correspondence')
        maximum=0
        for i,j in matches:
            midpoint=(va[i]+vb[j])*0.5;maximum=max(maximum,(midpoint-va[i]).length)
            a.data.vertices[i].co=a.matrix_world.inverted()@midpoint;b.data.vertices[j].co=b.matrix_world.inverted()@midpoint
        a.data.update();b.data.update();seams.append({'source_nodes':[left,right],'matched_vertices':len(matches),'maximum_world_vertex_movement':maximum,'correspondence_tolerance':tolerance,'note':'The rear016/017 ridge junction is occluded by chimney and adjacent roof; midpoint is inferred hidden connectivity.' if (left,right)==('building-016','building-017') else 'Subpixel shared junction.'})
    join_report=close_mill_north_joins(bynode) if c['asset_id']=='leicester-mill-north-cottage' else None
    pole_report=access_pole(bynode['building-021'],w) if c['asset_id']=='leicester-mill-north-cottage' else None
    wheel_report=None
    if c['asset_id']=='leicester-northeast-longhouse':
        if support.exists():from village_details import longhouse_wheel
        else:from leicester.village_details import longhouse_wheel
        wheel_report=longhouse_wheel(w,c)
    report={'spare_wheel':wheel_report,'measured_seam_welds':measured_welds,'hidden_join_repairs':join_report,'access_pole':pole_report,'asset_id':c['asset_id'],'recipe':'village-cottage-v1','shell_repairs':reports,'shared_roof_seams':seams,'world_transform_drift':0,'inference':'Only planar underside closure; shared junctions reconciled at their average using reported per-pair tolerances. No source silhouette redesign.','limitations':['Doors/windows/timber detail remains source projection unless represented by an existing distinct component.','Hidden roof/back depth remains the inherited geometric hypothesis; component interiors may overlap.'],'projection_status':'STALE'}
    (w/'inspection').mkdir(exist_ok=True);(w/'inspection'/'cottage-recipe.json').write_text(json.dumps(report,indent=2)+'\n');validate(w);bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));print(json.dumps({'asset_id':c['asset_id'],'seams':seams}))
    if args.reproject:
        from refinement_workspace import modified
        print(json.dumps(modified(w)))
if __name__=='__main__':main()
