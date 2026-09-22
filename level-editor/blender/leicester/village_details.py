"""Source-silhouette joinery details with explicitly inferred hidden thickness."""
import json
import math
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector


def silhouette_prism(workspace, index, pixel_to_world, thickness):
    c=json.loads((workspace/'workspace.json').read_text());manifest=Path(c['source_mask_manifest']);contract=json.loads(manifest.read_text());inventory=(manifest.parent/contract['mask_inventory']).resolve();m=next(m for m in json.loads(inventory.read_text())['masks'] if m['index']==index)
    image=bpy.data.images.load(str((inventory.parent/m['png']).resolve()),check_existing=False);width,height=image.size;pixels=np.empty(width*height*4,dtype=np.float32);image.pixels.foreach_get(pixels);bpy.data.images.remove(image);bitmap=pixels.reshape(height,width,4)[::-1,:,0]>0.5
    occupied={(int(x),int(y)) for y,x in np.argwhere(bitmap)};boundary=[]
    for x,y in occupied:
        for neighbor,edge in [((x,y-1),((x,y),(x+1,y))),((x+1,y),((x+1,y),(x+1,y+1))),((x,y+1),((x+1,y+1),(x,y+1))),((x-1,y),((x,y+1),(x,y)))]:
            if neighbor not in occupied:boundary.append((edge,(x,y)))
    corners={p for x,y in occupied for p in [(x,y),(x+1,y),(x+1,y+1),(x,y+1)]};indices={};grid=[];split_corners=0
    # Raster diagonals touch at one corner only. Keep their incident faces in
    # separate vertex fans so no vertical edge acquires four side faces.
    for px,py in sorted(corners):
        pending={(x,y) for x,y in [(px-1,py-1),(px,py-1),(px-1,py),(px,py)] if (x,y) in occupied};fans=0
        while pending:
            seed=min(pending);pending.remove(seed);fan={seed};queue=[seed]
            while queue:
                x,y=queue.pop();neighbors={(x-1,y),(x+1,y),(x,y-1),(x,y+1)}&pending;pending-=neighbors;fan|=neighbors;queue.extend(neighbors)
            index=len(grid);grid.append((px,py));fans+=1
            for cell in fan:indices[((px,py),cell)]=index
        split_corners+=fans-1
    front=[Vector(pixel_to_world(x+m['box_top_left'][0],y+m['box_top_left'][1])) for x,y in grid];n=len(front)
    normal=(Vector(pixel_to_world(1,0))-Vector(pixel_to_world(0,0))).cross(Vector(pixel_to_world(0,1))-Vector(pixel_to_world(0,0))).normalized();vertices=front+[v+normal*thickness for v in front]
    quads=[tuple(indices[(p,(x,y))] for p in [(x,y),(x+1,y),(x+1,y+1),(x,y+1)]) for x,y in sorted(occupied)];faces=quads+[tuple(n+i for i in reversed(f)) for f in quads]+[(indices[(a,cell)],indices[(b,cell)],n+indices[(b,cell)],n+indices[(a,cell)]) for (a,b),cell in boundary]
    mesh=bpy.data.meshes.new(f'Leicester Native{index} Detail');mesh.from_pydata(vertices,[],faces);mesh.uv_layers.new(name='UVMap');bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);bm.to_mesh(mesh);bm.free()
    if bad:raise ValueError(f'Native{index} prism has {bad} nonmanifold edges')
    material=bpy.data.materials.get('Leicester Detail Unknown') or bpy.data.materials.new('Leicester Detail Unknown');material.diffuse_color=(.5,.5,.5,1);mesh.materials.append(material)
    return mesh,{'native_mask':index,'source_pixels':len(occupied),'thickness':thickness,'nonmanifold_edges':bad,'diagonal_pixel_fans_split':split_corners}


def longhouse_wheel(workspace,config):
    sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35));dy_dx=-0.2125;dy_dpy=-8/34
    def plane(px,py):
        y=-716/sine+(px-2771.5)*dy_dx+(py-716)*dy_dpy
        return px,y,(-py-y*sine)/cosine
    mesh,report=silhouette_prism(workspace,132,plane,2.5)
    name='Leicester Longhouse Spare Wheel';obj=bpy.data.objects.get(name)
    if obj is None:
        obj=bpy.data.objects.new(name,mesh);bpy.data.collections[config['collection_name']].objects.link(obj)
    else:obj.data=mesh
    obj['source_node']='building-003';obj['asset_group']=config['asset_id'];obj['projection_component']='spare-wheel';obj['part_name']='Eight-spoke spare wheel'
    manifest=Path(config['source_mask_manifest']);contract=json.loads(manifest.read_text());rows=contract['projections']['exterior']['assignments'];rows[:]=[r for r in rows if not(r.get('source_node')=='building-003' and r.get('projection_component')=='spare-wheel')];rows.append({'source_node':'building-003','projection_component':'spare-wheel','mask_indices':[132],'reviewed':True,'evidence':'Native132 silhouette and wheel132-mask.png: single rim, hub, eight radial spokes. Location2771.5,699 source pixels; hidden lean8world units and thickness2.5 inferred.'});manifest.write_text(json.dumps(contract,indent=2)+'\n')
    report.update(spokes=8,inference='Plane follows the front wall orientation and leans eight world units toward it; hidden thickness2.5. Exact native rim, hub and spoke apertures retained.')
    return report
