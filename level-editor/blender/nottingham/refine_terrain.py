"""Local stream-bed hypothesis below the village bridge, preserving source rays.

No riverbed elevation is directly observed. The candidate uses the lowest
visible bridge pier (-106 world units) and 14 units of clearance. Two inferred local bank transitions surround the complete physical arch
footprints, including their reverse faces. No terrain outside them is displaced.
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
OUTER = [(1300,2960),(1680,2960),(1680,3500),(1300,3500)]
INNER = [(1335,3150),(1640,3150),(1640,3310),(1335,3310)]
WEST_OUTER = [(490,2790),(720,2790),(720,3310),(490,3310)]
WEST_INNER = [(535,2980),(680,2980),(680,3120),(535,3120)]
BASINS = [(OUTER, INNER), (WEST_OUTER, WEST_INNER)]
DEPTH = -120.0
TAG = 'nottingham_bridge_stream_bed_v2'


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
    """Dense full-depth surface and opening-corridor clearance, both faces."""
    tree=BVHTree.FromPolygons([ground.matrix_world@v.co for v in ground.data.vertices],
                             [tuple(p.vertices) for p in ground.data.polygons])
    bridge.data.calc_loop_triangles()
    failures=[];samples=0;minimum=1e9
    for tri in bridge.data.loop_triangles:
        a,b,c=[bridge.matrix_world@bridge.data.vertices[i].co for i in tri.vertices]
        for i in range(13):
            for j in range(13-i):
                p=a+(b-a)*(i/12)+(c-a)*(j/12)
                hit=tree.ray_cast(Vector((p.x,p.y,1000)),Vector((0,0,-1)),3000)[0]
                if hit is None:raise ValueError('Ground missing under bridge')
                gap=p.z-hit.z;minimum=min(minimum,gap);samples+=1
                if gap<-.01:failures.append({'point':list(p),'ground':list(hit),'gap':gap})
    if failures:raise ValueError(f'Physical bridge surface buried: {failures[:8]} ({len(failures)} samples)')
    # Include the empty opening corridors, not just masonry vertices. The
    # sampled quadrilaterals span front-to-reverse depth and approach margins.
    west='Western' in bridge.name
    if west:
        ax,ay,bx,by=425.27533,-3046.347/SINE,682.6511,-2934.8538/SINE
        openings=[(605,641)];depth=Vector((-31,85,0))
    else:
        ax,ay,bx,by=1347.75,-5432.77,1586.61,-5573.47
        openings=[(1418,1480),(1500,1555)];depth=Vector((39,86,0))
    corridor=[]
    for lo,hi in openings:
        highest=-1e9
        for i in range(41):
            x=lo+(hi-lo)*i/40;y=ay+(by-ay)*(x-ax)/(bx-ax)
            for j in range(41):
                p=Vector((x,y,0))+depth*(-.1+1.2*j/40)
                hit=tree.ray_cast(Vector((p.x,p.y,1000)),Vector((0,0,-1)),3000)[0]
                if hit is None:raise ValueError('Missing corridor ground')
                highest=max(highest,hit.z)
        corridor.append({'front_x_range':[lo,hi],'depth_fraction':[-.1,1.1],
                         'samples':1681,'highest_bed':highest})
        if highest>DEPTH+.01:raise ValueError(f'Raised ground blocks complete arch corridor: {corridor[-1]}')
    return {'status':'PASS-full-depth-clearance','surface_samples':samples,
            'minimum_surface_clearance':minimum,'corridors':corridor,
            'method':'Dense barycentric surface samples and 41 by 41 vertical rays through each opening, including ten percent front and rear approach margins.'}


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
    coords=list(source)
    loops=[list(range(4))]
    depths=[p.z for p in world]
    for outer,inner in BASINS:
        for ring,bed in ((outer,False),(inner,True)):
            start=len(coords)
            coords.extend(Vector(p) for p in ring)
            loops.append(list(range(start,len(coords))))
            depths.extend(DEPTH if bed else p[1]/height*max_z for p in ring)
    edges=[(ring[i],ring[(i+1)%len(ring)]) for ring in loops for i in range(len(ring))]
    tri_coords,_,faces,original_ids,_,_=delaunay_2d_cdt(coords,edges,[],0,1e-6)
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
        if not any(_inside(center,outer) for outer,inner in BASINS):
            outside_faces+=1
            for i in polygon.vertices:
                expected=tri_coords[i].y/height*max_z
                if abs(points[i].z-expected)>1e-3:
                    raise ValueError('Terrain outside source-supported boundary moved')
    ground.data=mesh
    report={'status':'candidate-inferred-stream-bed','source_node':'ground',
            'source_boundary':OUTER,'source_core':INNER,'basins':[{'outer':o,'core':i} for o,i in BASINS],'world_bed_height':DEPTH,
            'lowest_visible_pier_height':-106,'clearance_below_lowest_visible_pier':14,
            'before_geometry_sha256':_hash(before),'after_geometry_sha256':_hash(_geometry(ground)),
            'vertices':len(vertices),'faces':len(faces),'outside_faces_unchanged_plane':outside_faces,
            'source_projection_max_error_pixels':projected_error,'folded_triangles':folded,
            'original_boundary_preserved':True,'material_preserved':True,
            'approval':'pending','limitations':[
                'Bed depth and concealed bank profile are inferred from bridge clearance, not measured bathymetry.',
                'Two local bridge basins represent clearance beneath complete arch depth; remaining terrain stays a flat proxy.',
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
