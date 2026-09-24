"""Closed neutral crown volume with separately guarded regional fringe opacity.

The regional silhouette bounds physical coverage, never individual-tree RGB
ownership. Continuous depth is inferred; neighboring crowns and off-map shape
remain ambiguous. No camera-facing cards or transverse fins are retained.
"""
import argparse
from collections import deque
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
import numpy as np
from PIL import Image, ImageFilter
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import forest_fringe as fringe
import foliage_trees as foliage
from props_trees import GROUND

VERSION='leicester-continuous-forest-volume-v8'


def crown_volume(obj,node,packet,output,depth_fraction=.46,step=2):
    """Replace one crown with a closed smooth shell; preserve source-ray footprint."""
    box=packet['source_box'];left,top,right,bottom=box;w,h=right-left,bottom-top
    coverage=np.asarray(Image.open(output/'derived-neutral-coverage.png').convert('L'))>0
    # Geometry follows a coarse envelope, while the original finer coverage
    # remains an independent physical alpha texture. Close leaf-sized holes
    # in the envelope without assigning their pixels any source ownership.
    image=Image.fromarray(coverage.astype(np.uint8)*255)
    envelope=image.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    nx,ny=math.ceil(w/step),math.ceil(h/step)
    cells=np.asarray(envelope.resize((nx,ny),Image.Resampling.BOX))>64
    cells=np.asarray(Image.fromarray(cells.astype(np.uint8)*255).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3)))>0
    # Keep the connected main crown; detached source speckles are not solid
    # disconnected spheres. Fine alpha still contributes the leaf boundary.
    visited=np.zeros_like(cells);components=[]
    for yy,xx in zip(*np.nonzero(cells)):
        if visited[yy,xx]:continue
        q=deque([(yy,xx)]);visited[yy,xx]=True;component=[]
        while q:
            y,x=q.popleft();component.append((y,x))
            for a,b in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                if 0<=a<ny and 0<=b<nx and cells[a,b] and not visited[a,b]:visited[a,b]=True;q.append((a,b))
        components.append(component)
    main=max(components,key=len);cells[:]=False
    for y,x in main:cells[y,x]=True
    # Fill diagonal-only pinches in the support envelope. This preserves a
    # two-manifold rim while the alpha texture retains exact fringe gaps.
    for _ in range(4):
        changes=[]
        for y in range(ny-1):
            for x in range(nx-1):
                a,b,c,d=cells[y,x],cells[y,x+1],cells[y+1,x],cells[y+1,x+1]
                if a and d and not b and not c:changes.append((y,x+1))
                if b and c and not a and not d:changes.append((y,x))
        for y,x in changes:cells[y,x]=True
        if not changes:break
    sy=np.minimum(ny-1,np.floor((np.arange(h)+.5)*ny/h).astype(int))
    sx=np.minimum(nx-1,np.floor((np.arange(w)+.5)*nx/w).astype(int))
    support=cells[sy[:,None],sx[None,:]]
    Image.fromarray(support.astype(np.uint8)*255).save(output/'geometry-envelope.png')
    Image.fromarray((coverage&~support).astype(np.uint8)*255).save(output/'omitted-fringe-speckles.png')
    coverage_stats={'alpha_pixels':int(coverage.sum()),'supported_alpha_pixels':int((coverage&support).sum()),'omitted_fringe_speckle_pixels':int((coverage&~support).sum())}
    used=set();rim=set()
    for y,x in zip(*np.nonzero(cells)):
        used.update(((y,x),(y,x+1),(y+1,x),(y+1,x+1)))
    for y,x in used:
        if any(not(0<=a<ny and 0<=b<nx and cells[a,b]) for a,b in ((y-1,x-1),(y-1,x),(y,x-1),(y,x))):rim.add((y,x))
    rimxy=np.array([(x*w/nx,y*h/ny) for y,x in rim]);dist={}
    for y,x in used:
        dist[y,x]=float(np.sqrt(((rimxy-[x*w/nx,y*h/ny])**2).sum(axis=1).min()))
    maxdist=max(dist.values());radius=w*depth_fraction
    if maxdist<=0:raise ValueError('Empty crown interior')
    vertices=[];uv=[];indices={};matrix=obj.matrix_world.copy();inverse=matrix.inverted()
    for side in (1,-1):
        for y,x in sorted(used):
            px,py=left+x*w/nx,top+y*h/ny
            # A broad continuous depth field tapers to a negligible rim thickness at the complete
            # rim. No rectangular rim, detached rear sheet, or transverse card.
            t=dist[y,x]/maxdist
            depth=side*(.025+radius*math.sin(math.pi*t/2))
            world=Vector((px,-GROUND[node]/foliage.SINE,(GROUND[node]-py)/foliage.COSINE))+foliage.RAY*depth
            indices[side,y,x]=len(vertices);vertices.append(inverse@world);uv.append((x/nx,1-y/ny))
    faces=[];slots=[]
    for y,x in zip(*np.nonzero(cells)):
        for side in (1,-1):
            a,b,c,d=[indices[side,j,i] for j,i in ((y,x),(y,x+1),(y+1,x+1),(y+1,x))]
            for face in ((a,d,c),(a,c,b)) if side==1 else ((a,b,c),(a,c,d)):
                if len(set(face))==3:
                    vs=[Vector(vertices[i]) for i in face]
                    if (vs[1]-vs[0]).cross(vs[2]-vs[0]).length>1e-7:faces.append(face);slots.append(0 if side==1 else 1)
    # Stitch only the true perimeter. A 0.05-unit rim avoids singular
    # pinches where both endpoints of an interior edge touch the boundary.
    edges={}
    for y,x in zip(*np.nonzero(cells)):
        ring=[(y,x),(y,x+1),(y+1,x+1),(y+1,x)]
        for a,b in zip(ring,ring[1:]+ring[:1]):
            key=tuple(sorted((a,b)));edges[key]=edges.get(key,0)+1
    for (a,b),count in edges.items():
        if count!=1:continue
        i,j,k,l=indices[1,*a],indices[1,*b],indices[-1,*b],indices[-1,*a]
        faces.extend(((i,j,k),(i,k,l)));slots.extend((1,1))
    rgba=np.full((h,w,4),105,dtype=np.uint8);rgba[:,:,3]=coverage*255
    back=output/'volume-neutral.png';Image.fromarray(rgba).save(back)
    # Keep measured wood visible on the nearest shell. The closed back remains
    # neutral rather than removing a trunk-shaped hole through the full volume.
    front=rgba.copy()
    ws_manifest=json.loads(Path(packet['_source_mask_manifest']).read_text())
    inventory_path=(Path(packet['_source_mask_manifest']).parent/ws_manifest['mask_inventory']).resolve()
    masks={r['index']:r for r in json.loads(inventory_path.read_text())['masks']}
    wood=np.zeros_like(coverage)
    own_wood=set()
    for projection in ws_manifest['projections'].values():
        for assignment in projection.get('assignments',[]):
            if assignment.get('source_node')==f'building-{node:03d}' and assignment.get('projection_component')=='wood':
                own_wood.update(assignment['mask_indices'])
    if not own_wood:raise ValueError('Missing native individual wood authority')
    for index in own_wood:wood|=fringe.paste_mask(masks[index],box)
    front[:,:,3]&=(~wood).astype(np.uint8)*255
    frontpath=output/'volume-front.png';Image.fromarray(front).save(frontpath)
    mesh=bpy.data.meshes.new(obj.name+' continuous crown');mesh.from_pydata(vertices,[],faces);mesh.update()
    for name,path in [('front',frontpath),('back',back)]:
        mat=foliage.material(obj.name+' coherent '+name,path,False,packet,two_sided=True)
        mat['foliage_recipe']=VERSION;mesh.materials.append(mat)
    layer=mesh.uv_layers.new(name='Foliage UV');ownership=mesh.color_attributes.new(name='Source ownership',type='FLOAT_COLOR',domain='CORNER');mesh.color_attributes.active_color=ownership
    fallback=mesh.attributes.new('reprojection_fallback_material','INT','FACE')
    for face,slot in zip(mesh.polygons,slots):
        face.material_index=slot;face.use_smooth=True;fallback.data[face.index].value=slot
        for loop in face.loop_indices:layer.data[loop].uv=uv[mesh.loops[loop].vertex_index];ownership.data[loop].color=(0.,1.,1.,1.)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    degenerate=sum(f.calc_area()<1e-7 for f in bm.faces);nonmanifold=sum(not e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True)
    bm.to_mesh(mesh);bm.free()
    if degenerate or nonmanifold:raise ValueError(f'Invalid continuous crown: degenerate={degenerate}, nonmanifold={nonmanifold}')
    old=obj.data;obj.data=mesh
    if not old.users:bpy.data.meshes.remove(old)
    obj['leicester_geometry_recipe']=VERSION;obj['foliage_physical_opacity']=True
    return dict(vertices=len(mesh.vertices),faces=len(mesh.polygons),depth_radius=radius,depth_fraction=depth_fraction,source_box=box,nonmanifold_edges=nonmanifold,degenerate_faces=degenerate,signed_volume=volume,source_ownership_pixels=0,coverage=coverage_stats,grid_step=step,envelope_close_pixels=5,depth_profile='sin(pi*t/2), finite rim slope',rim_thickness=.05,front_wood_mask_indices=sorted(own_wood),front_wood_cutout_pixels=int((coverage&wood).sum()),continuous_shell=True,transverse_cards=0,side_depth_inferred=True)


def run(workspace,depth_fraction=.46):
    workspace=Path(workspace).resolve();config=json.loads((workspace/'workspace.json').read_text())
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise ValueError('Load isolated worker')
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'refinement/blender'))
    from refinement_workspace import validate
    validate(workspace)
    objects=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']]
    crown=next(o for o in objects if o.get('projection_component')=='crown');node=int(crown['source_node'][9:]);unchanged={o.name:foliage.geometry_hash(o) for o in objects if o!=crown}
    output=workspace/'inspection/continuous-volume';packet=fringe.evidence(workspace,node,output);packet['_source_mask_manifest']=config['source_mask_manifest'];source_hash=foliage.sha(config['source_mask_manifest'])
    report=crown_volume(crown,node,packet,output,depth_fraction);fingerprint=foliage.geometry_hash(crown);crown_volume(crown,node,packet,output,depth_fraction)
    if fingerprint!=foliage.geometry_hash(crown):raise ValueError('Non-idempotent volume')
    if unchanged!={o.name:foliage.geometry_hash(o) for o in objects if o!=crown}:raise ValueError('Wood changed')
    if source_hash!=foliage.sha(config['source_mask_manifest']):raise ValueError('Ownership changed')
    validate(workspace);report.update(recipe=VERSION,asset_id=config['asset_id'],idempotence='PASS',wood_geometry_unchanged=True,source_ownership_unchanged=True,limitations=['Regional alpha constrains forest coverage but cannot identify a complete individual tree.','Lateral tree allocation, rounded off-map completion and continuous shell depth are inferred.','Neutral crown carries zero source ownership; physical alpha is independently packed.', 'A two-pixel support envelope omits isolated fringe speckles; their exact source-aligned binary mask and counts are retained beside untouched alpha evidence.'])
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('workspace');p.add_argument('--depth-fraction',type=float,default=.46);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);print(json.dumps(run(a.workspace,a.depth_fraction)))
