"""Measured Nottingham town-fortification geometry recipes.

Run inside an isolated asset workspace, never on the frozen source scene:
blender --background <asset>/model.blend --python <this-script> -- --asset
nottingham-north-curtain-wall --report <asset>/inspection/geometry-recipe.json
Regenerate source projection and all fixed review cameras after this recipe.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / 'level-editor/work/nottingham-refinement/fortifications-audit'
# Native source-pixel measurements: notches between separately counted merlons.
NORTH_NOTCHES = [(1592,1607),(1632,1647),(1672,1687),(1712,1727),
                 (1752,1767),(1792,1810),(1915,1929),(1953,1967),
                 (1990,2005),(2028,2042),(2066,2080)]


def north_wall_geometry(points):
    """One connected ribbon with explicit vertical sides at each crenel step."""
    vertices, faces, index = [], [], {}
    def vertex(p):
        key = tuple(round(float(v), 6) for v in p)
        if key not in index:
            index[key] = len(vertices)
            vertices.append(key)
        return index[key]
    def face(coords):
        ids = [vertex(c) for c in coords]
        ids = [v for i,v in enumerate(ids) if v != ids[i-1]]
        if len(set(ids)) >= 3:
            faces.append(ids)
    def lerp(a,b,t,z):
        return (a['x']+(b['x']-a['x'])*t,a['y']+(b['y']-a['y'])*t,z)
    pairs = [(6,7),(5,8),(4,9),(3,10),(2,11),(1,12),(0,13)]
    def prism(a,b,c,d,lo,hi,z0,z1):
        al,bl=lerp(a,c,lo,z0),lerp(b,d,lo,z0)
        ar,br=lerp(a,c,hi,z0),lerp(b,d,hi,z0)
        atl,btl=lerp(a,c,lo,z1),lerp(b,d,lo,z1)
        atr,btr=lerp(a,c,hi,z1),lerp(b,d,hi,z1)
        face([al,ar,atr,atl]);face([br,bl,btl,btr])
        face([atl,atr,btr,btl]);face([bl,br,ar,al])
        face([bl,al,atl,btl]);face([ar,br,btr,atr])
    for segment, ((ai,bi),(ci,di)) in enumerate(zip(pairs,pairs[1:])):
        a,b,c,d = points[ai],points[bi],points[ci],points[di]
        cuts = [0.0,1.0]
        # Straight visible runs only; central turret remains an audited limitation.
        notches = NORTH_NOTCHES if segment in (0,5) else []
        for lo,hi in notches:
            for x in (lo,hi):
                t=(x-a['x'])/(c['x']-a['x'])
                if 0 < t < 1: cuts.append(t)
        cuts=sorted(set(cuts))
        for lo,hi in zip(cuts,cuts[1:]):
            x=a['x']+(c['x']-a['x'])*(lo+hi)/2
            low=a['z_top']-13
            prism(a,b,c,d,lo,hi,0,low)
            if not any(l < x < r for l,r in notches):
                prism(a,b,c,d,lo,hi,low,a['z_top'])
    # Neighboring cells share exact vertices; cancel their internal faces.
    shells={}
    for face_ids in faces:
        key=tuple(sorted(face_ids))
        if key in shells: del shells[key]
        else: shells[key]=face_ids
    faces=list(shells.values())
    return vertices,faces


def stair_geometry(points, count=14):
    """Closed stair with fourteen source-counted risers and horizontal treads."""
    # Native polygon walks top-right, bottom-right, bottom-left, top-left.
    a,c,d,b=points
    height=a['z_top']
    profile=[(0,0),(0,height)]
    for i in range(count):
        t=(i+1)/count
        profile.append((t,height*(1-i/count)))
        profile.append((t,height*(1-(i+1)/count)))
    vertices=[]
    for start,end in ((a,c),(b,d)):
        vertices.extend((start['x']+(end['x']-start['x'])*t,
                         start['y']+(end['y']-start['y'])*t,z)
                        for t,z in profile)
    n=len(profile)
    faces=[list(reversed(range(n))),list(range(n,2*n))]
    faces.extend([i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n))
    return vertices,faces


def gate_arch_geometry(points, anchors):
    """Extrude the source-measured pointed opening edge through native wall depth."""
    xlo=min(p['x'] for p in points);xhi=max(p['x'] for p in points)
    ymin=min(p['y'] for p in points);ymax=max(p['y'] for p in points)
    top=points[0]['z_top']
    anchors=[(xlo,anchors[0][1])]+[(x,y) for x,y in anchors if xlo<x<xhi]+[(xhi,anchors[-1][1])]
    profile=[(xlo,top),(xhi,top)]+[(x,ymax-y) for x,y in reversed(anchors)]
    verts=[(x,y,z) for y in (ymin,ymax) for x,z in profile]
    n=len(profile);faces=[list(reversed(range(n))),list(range(n,2*n))]
    faces.extend([i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n))
    return verts,faces


def main():
    import bpy
    import bmesh
    from mathutils import Vector
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser=argparse.ArgumentParser();parser.add_argument('--asset',required=True)
    parser.add_argument('--report',type=Path,required=True);opts=parser.parse_args(args)
    if opts.asset not in ('nottingham-north-curtain-wall','nottingham-north-wall-stair','nottingham-south-gate-arch'):
        raise ValueError('No measured recipe yet for '+opts.asset)
    blend=Path(bpy.data.filepath).resolve()
    if 'baseline' in blend.parts or blend.name == 'baseline.blend':
        raise ValueError('Recipe refuses to change a frozen baseline')
    collection=bpy.data.collections.get('nottingham Working')
    node={'nottingham-north-curtain-wall':'building-178','nottingham-north-wall-stair':'building-170','nottingham-south-gate-arch':'building-213'}[opts.asset]
    candidates=[o for o in bpy.context.scene.objects if o.type=='MESH' and
                o.get('source_node',o.get('source_obstacle'))==node and
                (collection is None or o.name in collection.all_objects)]
    if len(candidates)!=1: raise ValueError('Expected exactly one working '+node)
    obj=candidates[0];before=[list(r) for r in obj.matrix_world]
    evidence=json.loads((AUDIT/'measurements.json').read_text())
    is_wall=node=='building-178'
    if is_wall:
        verts,faces=north_wall_geometry(evidence['north_wall']['native_points'])
    elif node=='building-170':
        verts,faces=stair_geometry(evidence['stairs']['170']['native_points'])
    else:
        verts,faces=gate_arch_geometry(evidence['south_arch']['native_points'],evidence['south_arch']['inner_arch_anchors_source'])
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35))
    inverse=obj.matrix_world.inverted()
    local=[inverse@Vector((x,-y/sine,z/cosine)) for x,y,z in verts]
    old=obj.data;mesh=bpy.data.meshes.new(obj.name+' Measured Crenellation')
    mesh.from_pydata(local,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    nonmanifold=sum(not e.is_manifold for e in bm.edges)
    if nonmanifold: raise ValueError(f'Generated wall has {nonmanifold} nonmanifold edges')
    bm.to_mesh(mesh);bm.free()
    neutral=bpy.data.materials.get('Nottingham Unknown Neutral') or bpy.data.materials.new('Nottingham Unknown Neutral')
    neutral.diffuse_color=(0.45,0.45,0.45,1);mesh.materials.append(neutral)
    obj.data=mesh
    if old.users==0:bpy.data.meshes.remove(old)
    obj['refinement_recipe']='nottingham/refine_fortifications.py'
    obj['source_projection_current']=False
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report={'asset_id':opts.asset,'recipe':str(Path(__file__).resolve()),
            'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'changed_objects':[obj.name],'source_nodes':[node],
            'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'nonmanifold_edges':nonmanifold,
            'world_transform_drift':0 if before==[list(r) for r in obj.matrix_world] else None,
            'repeated_elements':({'west_visible_merlons':6,'east_visible_merlons':5,'notches':11} if is_wall else {'risers':14} if node=='building-170' else {'opening_anchors':11}),
            'projection_current':False,'status':'refinement-in-progress',
            'limitations':(['Central projecting turret crenels still need count/phase refinement.',
             'Occluded continuation under northeast tower retains a solid parapet.',
             'Hidden depth follows the native obstacle; not visible artwork evidence.',
             'Regenerate full modified packet before review.'] if is_wall else ['Fourteen risers counted on the native source crop; fixed-camera projection requires visual verification.','Hidden stair sides/underside are inferred from obstacle footprint.','Regenerate full modified packet before review.'] if node=='building-170' else ['Only front component213 underside is shaped; thickness receiver214 requires inspection for aperture occlusion.','Parapet merlon geometry remains pending.','Arch underside depth is inferred from native wall thickness.','Regenerate full modified packet before review.'])}
    opts.report.parent.mkdir(parents=True,exist_ok=True);opts.report.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
