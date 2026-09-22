"""Close village shell undersides and reconcile measured shared roof seams."""
import argparse
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector
import bmesh
PAIRS=[('building-024','building-029'),('building-016','building-017'),('building-003','building-007'),('building-009','building-014'),('building-064','building-065'),('building-093','building-096'),('building-079','building-080')]

def ladder(obj):
    # Eight rungs are visible between y=633 and y=697 in the native crop.
    lows=[Vector((2422.819,-1230.717,0)),Vector((2435.569,-1221.603,0))]
    highs=[Vector((2416.394,-1206.113,76.946)),Vector((2428,-1197.823,76.946))]
    vertices=[];faces=[]
    def beam(a,b,width):
        axis=(b-a).normalized();side=axis.cross(Vector((0,0,1)))
        if side.length<0.001:side=axis.cross(Vector((0,1,0)))
        side.normalize();other=axis.cross(side).normalized();base=len(vertices)
        vertices.extend(p+side*x*width/2+other*y*width/2 for p in [a,b] for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)])
        faces.extend(tuple(base+i for i in f) for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    for low,high in zip(lows,highs):beam(low,high,1.8)
    for i in range(8):
        t=0.1+i*0.8/7;beam(lows[0].lerp(highs[0],t),lows[1].lerp(highs[1],t),1.5)
    mesh=bpy.data.meshes.new('Leicester Cottage Ladder');mesh.from_pydata([obj.matrix_world.inverted()@v for v in vertices],[],faces)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='UVMap')
    mat=bpy.data.materials.get('Leicester Ladder Unknown') or bpy.data.materials.new('Leicester Ladder Unknown');mat.diffuse_color=(0.5,0.5,0.5,1);mesh.materials.append(mat);obj.data=mesh
    return {'source_node':'building-021','rails':2,'rungs':8,'visible_rung_pixel_y':[633,642,651,660,669,678,687,697],'inference':'Square rail width1.8 and rung width1.5 scene units; source positions define rung phase and spacing.','geometry_representation':'Ten closed timber beam components in the canonical ladder mesh; source slab removed.'}

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
    targets=[o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==c['asset_id']]
    if not targets:raise ValueError('Missing owned meshes')
    reports=[repair(o) for o in targets];seams=[]
    bynode={o['source_node']:o for o in targets}
    for left,right in PAIRS:
        if left not in bynode or right not in bynode:continue
        a,b=bynode[left],bynode[right]
        va=[a.matrix_world@v.co for v in a.data.vertices];vb=[b.matrix_world@v.co for v in b.data.vertices]
        tolerance=7.0 if (left,right)==('building-016','building-017') else 0.8
        matches=[(i,j) for i,x in enumerate(va) for j,y in enumerate(vb) if (x-y).length<tolerance]
        if len({i for i,j in matches})!=len(matches) or len({j for i,j in matches})!=len(matches):raise ValueError('Ambiguous seam vertex correspondence')
        maximum=0
        for i,j in matches:
            midpoint=(va[i]+vb[j])*0.5;maximum=max(maximum,(midpoint-va[i]).length)
            a.data.vertices[i].co=a.matrix_world.inverted()@midpoint;b.data.vertices[j].co=b.matrix_world.inverted()@midpoint
        a.data.update();b.data.update();seams.append({'source_nodes':[left,right],'matched_vertices':len(matches),'maximum_world_vertex_movement':maximum,'correspondence_tolerance':tolerance,'note':'The rear016/017 ridge junction is occluded by chimney and adjacent roof; midpoint is inferred hidden connectivity.' if tolerance>1 else 'Subpixel shared junction.'})
    join_report=close_mill_north_joins(bynode) if c['asset_id']=='leicester-mill-north-cottage' else None
    ladder_report=ladder(bynode['building-021']) if c['asset_id']=='leicester-mill-north-cottage' else None
    report={'hidden_join_repairs':join_report,'ladder':ladder_report,'asset_id':c['asset_id'],'recipe':'village-cottage-v1','shell_repairs':reports,'shared_roof_seams':seams,'world_transform_drift':0,'inference':'Only planar underside closure; shared junctions reconciled at their average using reported per-pair tolerances. No source silhouette redesign.','limitations':['Doors/windows/timber detail remains source projection unless represented by an existing distinct component.','Hidden roof/back depth remains the inherited geometric hypothesis; component interiors may overlap.'],'projection_status':'STALE'}
    (w/'inspection').mkdir(exist_ok=True);(w/'inspection'/'cottage-recipe.json').write_text(json.dumps(report,indent=2)+'\n');validate(w);bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));print(json.dumps({'asset_id':c['asset_id'],'seams':seams}))
    if args.reproject:
        from refinement_workspace import modified
        print(json.dumps(modified(w)))
if __name__=='__main__':main()
