"""Reconstruct the village well opening and four roof supports.

The inherited eight-corner masonry footprint and roof slab remain the measured
anchors. Inner wall thickness and the concealed cavity floor are inferred.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector

TAG='leicester-village-well-v1'
OUTER=[(2756.07,-1446.78),(2765.19,-1427.75),(2791.08,-1420.54),(2807.72,-1428.93),(2813.45,-1453.42),(2808.39,-1466.92),(2779.13,-1475.41),(2767.36,-1470.05)]
POSTS=[(2744,-1440,72),(2760,-1483,76.9),(2810,-1415,72),(2827,-1459,76.9)]

def mesh_object(name,vertices,faces,template,collection):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata([template.matrix_world.inverted()@Vector(v) for v in vertices],[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj);obj.parent=template.parent
    obj.matrix_parent_inverse=template.matrix_parent_inverse.copy();obj.matrix_world=template.matrix_world.copy()
    for key in template.keys():obj[key]=template[key]
    obj['leicester_geometry_recipe']=TAG
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    mesh.uv_layers.new(name='UVMap')
    material=bpy.data.materials.get('Leicester Well Unknown') or bpy.data.materials.new('Leicester Well Unknown')
    material.diffuse_color=(0.5,0.5,0.5,1)
    mesh.materials.append(material)
    return obj

def main():
    p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);w=a.workspace.resolve()
    c=json.loads((w/'workspace.json').read_text());assert c['asset_id']=='leicester-village-well'
    assert Path(bpy.data.filepath).resolve()==w/'model.blend'
    sys.path.insert(0,str(next(p/'level-editor/blender' for p in Path(__file__).resolve().parents if (p/'level-editor/blender/refinement_workspace.py').exists())));from refinement_workspace import validate
    validate(w)
    collection=bpy.data.collections[c['collection_name']]
    targets=[o for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')==c['asset_id']]
    shaft=next(o for o in targets if o.get('source_node')=='building-068')
    roof=next(o for o in targets if o.get('source_node')=='building-069' and o.get('leicester_geometry_recipe')!=TAG)
    bm=bmesh.new();bm.from_mesh(roof.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.75)
    edges=[e for e in bm.edges if e.is_boundary]
    if edges:
        if len(edges)!=4:raise ValueError('Expected exactly one four-edge roof underside opening')
        bmesh.ops.holes_fill(bm,edges=edges,sides=4)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(roof.data);bm.free()
    roof['leicester_roof_closure']=TAG
    for obj in list(targets):
        if obj!=shaft and obj.get('leicester_geometry_recipe')==TAG:bpy.data.objects.remove(obj,do_unlink=True)
    cx=sum(x for x,y in OUTER)/8;cy=sum(y for x,y in OUTER)/8
    inner=[(cx+(x-cx)*0.79,cy+(y-cy)*0.79) for x,y in OUTER]
    vertices=[(x,y,z) for points,z in [(OUTER,0),(OUTER,55),(inner,55),(inner,15)] for x,y in points]
    faces=[]
    for i in range(8):
        j=(i+1)%8;faces.extend([(i,j,8+j,8+i),(8+i,8+j,16+j,16+i),(16+i,16+j,24+j,24+i)])
    faces.extend([tuple(reversed(range(8))),tuple(range(24,32))])
    replacement=mesh_object(shaft.name+'-replacement',vertices,faces,shaft,collection)
    old=shaft.data;shaft.data=replacement.data;replacement.data=old;bpy.data.objects.remove(replacement,do_unlink=True)
    shaft['leicester_geometry_recipe']=TAG
    for i,(x,y,height) in enumerate(POSTS):
        vertices=[(x+dx,y+dy,z) for z in [0,height] for dx,dy in [(-2,-2),(2,-2),(2,2),(-2,2)]]
        mesh_object(f'Leicester Well | support {i+1}',vertices,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],roof,collection)
    report={'recipe':TAG,'asset_id':c['asset_id'],'source_nodes':['building-068','building-069'],'repeated_elements':{'roof_supports':4,'shaft_outer_corners':8},'source_supported':'Existing outer masonry footprint, rim elevation and roof corners. Four timber supports visible around the shaft.','inference':'Approximate square timber width 4 scene units; 21% radial cavity inset and cavity floor z=15 inferred from dark opening. Concealed rear supports and internal faces require gray unknown surface handling.','limitations':['Roof slab remains inherited shallow single pitch; plank irregularity is texture detail.','No rope or lifting spindle reconstructed; the artwork is partly occluded.','Closed roof underside is an inferred hidden surface.'],'projection_status':'STALE','approval_status':'refinement in progress'}
    (w/'inspection').mkdir(exist_ok=True);(w/'inspection'/'well-recipe.json').write_text(json.dumps(report,indent=2)+'\n');validate(w)
    bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));print(json.dumps(report))
if __name__=='__main__':main()
