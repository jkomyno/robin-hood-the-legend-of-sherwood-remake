"""Local stream-bed hypothesis below the village bridge, preserving source rays.

No riverbed elevation is directly observed. The candidate uses the lowest
visible bridge pier (-106 world units) and 14 units of clearance. Its local bank
boundary is constrained by the source stream; no other terrain is displaced.
"""
import hashlib
import json
import math

import bpy
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt
from mathutils.bvhtree import BVHTree

SINE = math.sin(math.radians(35))
COSINE = math.cos(math.radians(35))
OUTER = [(1400,3050),(1565,3050),(1565,3230),(1495,3370),(1400,3370)]
INNER = [(1406,3160),(1555,3160),(1564,3190),(1564,3220),(1495,3260),(1406,3260)]
DEPTH = -120.0
TAG = 'nottingham_bridge_stream_bed_v1'


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def _geometry(obj):
    return {'vertices':[list(v.co) for v in obj.data.vertices],
            'faces':[list(p.vertices) for p in obj.data.polygons]}


def _inside(point, polygon):
    x,y = point
    result=False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if (a[1]>y)!=(b[1]>y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            result=not result
    return result


def validate_bridge_clearance(ground, bridge):
    """Report core clearance separately from deliberately retained bank contacts."""
    vertices=[ground.matrix_world@v.co for v in ground.data.vertices]
    tree=BVHTree.FromPolygons(vertices,[tuple(p.vertices) for p in ground.data.polygons])
    view=Vector((0,-COSINE,SINE))
    bridge.data.calc_loop_triangles()
    samples=[]
    for triangle in bridge.data.loop_triangles:
        corners=[bridge.matrix_world@bridge.data.vertices[i].co for i in triangle.vertices]
        samples.extend(corners)
        samples.append(sum(corners,Vector((0,0,0)))/3)
    counts={region:{'samples':0,'camera_occluded':0,'ground_above_surface':0} for region in ['core','bank_transition','outside_local_stream']}
    core_failures=[]
    bank_contacts=[]
    for point in samples:
        pixel=(point.x,-point.y*SINE-point.z*COSINE)
        region='core' if _inside(pixel,INNER) else ('bank_transition' if _inside(pixel,OUTER) else 'outside_local_stream')
        counts[region]['samples']+=1
        location,normal,index,distance=tree.ray_cast(point+view*10000,-view,10000-.01)
        if location is not None:
            counts[region]['camera_occluded']+=1
            if region=='core':core_failures.append({'pixel':pixel,'world':list(point),'ground_hit':list(location)})
            elif region=='bank_transition':bank_contacts.append({'pixel':list(pixel),'world':list(point),'ground_hit':list(location)})
        location,normal,index,distance=tree.ray_cast(Vector((point.x,point.y,1000)),Vector((0,0,-1)),2000)
        if location is not None and location.z>point.z+.01:
            counts[region]['ground_above_surface']+=1
    if core_failures:
        raise ValueError(f'Core bridge source samples remain occluded: {core_failures}')
    return {'status':'PASS-core-clearance','regions':counts,'bank_contacts':bank_contacts,
            'limitations':['Bank-transition and outside abutment contacts are reported, not treated as clear.',
                           'Sampling proves the checked source points only; combined map image review is still required.']}


def refine():
    candidates=[obj for obj in bpy.data.collections['nottingham Working'].all_objects
                if obj.type=='MESH' and obj.get('source_node')=='ground' and not obj.hide_render]
    if len(candidates)!=1:
        raise ValueError('Expected exactly one working ground receiver')
    ground=candidates[0]
    if ground.get(TAG):
        return json.loads(ground[TAG])
    if len(ground.data.vertices)!=4 or len(ground.data.polygons)!=2:
        raise ValueError('Terrain recipe requires the frozen four-corner ground proxy')
    before=_geometry(ground)
    world=[ground.matrix_world@v.co for v in ground.data.vertices]
    source=[Vector((p.x,-p.y*SINE-p.z*COSINE)) for p in world]
    width=max(p.x for p in source)
    height=max(p.y for p in source)
    max_z=max(p.z for p in world)
    coords=source+[Vector(p) for p in OUTER]+[Vector(p) for p in INNER]
    loops=[list(range(4)),list(range(4,4+len(OUTER))),list(range(4+len(OUTER),len(coords)))]
    edges=[(ring[i],ring[(i+1)%len(ring)]) for ring in loops for i in range(len(ring))]
    tri_coords,_,faces,original_ids,_,_=delaunay_2d_cdt(coords,edges,[],0,1e-6)
    depths=[p.z for p in world]+[p[1]/height*max_z for p in OUTER]+[DEPTH]*len(INNER)
    inverse=ground.matrix_world.inverted()
    vertices=[]
    projected_error=0
    for point,ids in zip(tri_coords,original_ids):
        if len(ids)!=1:
            raise ValueError('Terrain triangulation introduced an unsupported point')
        original=ids[0]
        z=depths[original]
        p=world[original].copy() if original<4 else Vector((point.x,(-point.y-z*COSINE)/SINE,z))
        projected_error=max(projected_error,abs(p.x-point.x),abs(-p.y*SINE-p.z*COSINE-point.y))
        vertices.append(inverse@p)
    # Source-image Y is downward; reverse the triangulator's winding in world XY.
    faces=[tuple(reversed(face)) for face in faces]
    mesh=bpy.data.meshes.new('Ground / bridge stream depression')
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    uv=mesh.uv_layers.new(name=ground.data.uv_layers.active.name)
    for loop in mesh.loops:
        point=tri_coords[loop.vertex_index]
        uv.data[loop.index].uv=(point.x/width,1-point.y/height)
    for material in ground.data.materials:
        mesh.materials.append(material)
    points=[ground.matrix_world@v.co for v in mesh.vertices]
    folded=[]
    for polygon in mesh.polygons:
        a,b,c=[points[i] for i in polygon.vertices]
        if (b-a).cross(c-a).z<=0:
            folded.append(polygon.index)
    if folded:
        raise ValueError(f'Ray-preserving terrain would fold in XY: faces {folded}')
    for index,p in enumerate(world):
        found=next(i for i,ids in enumerate(original_ids) if ids==[index])
        if (points[found]-p).length>1e-3:
            raise ValueError('Original map boundary vertex moved')
    outside_faces=0
    for polygon in mesh.polygons:
        center=sum((tri_coords[i] for i in polygon.vertices),Vector((0,0)))/len(polygon.vertices)
        if not _inside(center,OUTER):
            outside_faces+=1
            for i in polygon.vertices:
                expected=tri_coords[i].y/height*max_z
                if abs(points[i].z-expected)>1e-3:
                    raise ValueError('Terrain outside source-supported boundary moved')
    ground.data=mesh
    report={'status':'candidate-inferred-stream-bed','source_node':'ground',
            'source_boundary':OUTER,'source_core':INNER,'world_bed_height':DEPTH,
            'lowest_visible_pier_height':-106,'clearance_below_lowest_visible_pier':14,
            'before_geometry_sha256':_hash(before),'after_geometry_sha256':_hash(_geometry(ground)),
            'vertices':len(vertices),'faces':len(faces),'outside_faces_unchanged_plane':outside_faces,
            'source_projection_max_error_pixels':projected_error,'folded_triangles':folded,
            'original_boundary_preserved':True,'material_preserved':True,
            'approval':'pending','limitations':[
                'Bed depth and concealed bank profile are inferred from bridge clearance, not measured bathymetry.',
                'Only the local stream beneath the bridge is represented; the rest of the map remains a flat proxy.',
                'Far abutments remain embedded in the banks outside the stream footprint.',
                'Source-ground texture ownership must remain separate from geometry clearance validation.']}
    ground[TAG]=json.dumps(report,sort_keys=True)
    return report


if __name__=='__main__':
    import argparse
    import sys
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output.mkdir(parents=True,exist_ok=False)
    bpy.context.window.scene=bpy.data.scenes['nottingham Refinement']
    result=refine()
    repeated=refine()
    if json.dumps(result,sort_keys=True)!=json.dumps(repeated,sort_keys=True):
        raise ValueError('Terrain recipe is not idempotent')
    result['idempotence']='PASS'
    bpy.ops.wm.save_as_mainfile(filepath=str((args.output/'model.blend').resolve()))
    (args.output/'geometry-recipe.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
