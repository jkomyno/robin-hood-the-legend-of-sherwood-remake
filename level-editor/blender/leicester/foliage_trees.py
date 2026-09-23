"""Physical foliage cutouts with separate opaque trunks and unknown backs.

Each lobe is a fixed curved surface at an inferred depth, never camera-following.
Native foliage uses exact source RGB/alpha; forest foliage is wholly inferred.
Physical opacity is packed separately from ownership COLOR_0.r.
Paired one-sided reverse surfaces use neutral RGB rather than borrowed artwork.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
import numpy as np
from PIL import Image
from mathutils import Vector

VERSION='leicester-foliage-lobes-v3'
SINE,COSINE=math.sin(math.radians(35)),math.cos(math.radians(35))
RAY=Vector((0,-COSINE,SINE))
CONFIG={
 88:dict(mask=10,ground=1285.,canopy_bottom=1220,seeds=[(2105,1019),(2152,1039),(2227,1070),(2048,1095),(2140,1110),(2265,1140),(2097,1175),(2193,1191)]),
 89:dict(mask=9,ground=1620.,canopy_bottom=1574,seeds=[(2704,1358),(2620,1400),(2768,1411),(2572,1460),(2671,1464),(2726,1488),(2660,1522),(2695,1551)]),
}
DEPTHS=[18.,38.,4.,-12.,24.,6.,-8.,12.]
SLOPES=[(.38,.12),(-.28,.32),(.22,-.30),(-.30,-.12),(.12,.24),(-.2,.3),(.3,-.18),(-.22,-.15)]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometry_hash(obj):
    return hashlib.sha256(json.dumps({'v':[list(v.co) for v in obj.data.vertices],
        'f':[list(f.vertices) for f in obj.data.polygons]},sort_keys=True).encode()).hexdigest()


def source_packet(workspace,node,output):
    config=json.loads((workspace/'workspace.json').read_text());settings=CONFIG[node]
    masks=Path(config['source_mask_manifest']);manifest=json.loads(masks.read_text())
    inventory=(masks.parent/manifest['mask_inventory']).resolve(strict=True)
    record=next(m for m in json.loads(inventory.read_text())['masks'] if m['index']==settings['mask'])
    alpha_path=Path(record['png']);source_path=Path(config['source_path'])
    alpha=np.asarray(Image.open(alpha_path).convert('L'));x,y=record['box_top_left'];height,width=alpha.shape
    rgb=np.asarray(Image.open(source_path).convert('RGB').crop((x,y,x+width,y+height)))
    yy,xx=np.mgrid[:height,:width];sx,sy=xx+x,yy+y
    canopy=(alpha>0)&(sy<=settings['canopy_bottom'])
    seeds=np.asarray(settings['seeds']);distance=(sx[:,:,None]-seeds[:,0])**2+(sy[:,:,None]-seeds[:,1])**2
    labels=np.argmin(distance,axis=2);records=[];assigned=np.zeros_like(alpha,dtype=np.uint8)
    # Rounded overlapping supports avoid exposing straight partition edges.
    # Hidden lobe borders are inferred; source texels retain native positions.
    radii=[]
    for number in range(len(seeds)):
        nearest=canopy&(labels==number)
        radii.append(math.sqrt(float(distance[:,:,number][nearest].max()))*1.25)
    supports=[]
    for number,(cx,cy) in enumerate(seeds):
        theta=np.arctan2(sy-cy,sx-cx)
        scallop=.94+.035*np.sin(theta*11+number)+.025*np.cos(theta*17-number)
        supports.append(np.sqrt(distance[:,:,number]) < radii[number]*scallop)
    if not np.all(np.any(supports,axis=0)[canopy]):
        raise ValueError('Rounded lobe supports do not cover native canopy')
    output.mkdir(parents=True,exist_ok=True)
    for number in range(len(seeds)):
        owned=canopy&supports[number]
        ys,xs=np.nonzero(owned)
        if not len(xs):raise ValueError('Empty measured foliage lobe')
        x0,x1=max(0,int(xs.min())-2),min(width,int(xs.max())+3)
        y0,y1=max(0,int(ys.min())-2),min(height,int(ys.max())+3)
        rgba=np.zeros((y1-y0,x1-x0,4),dtype=np.uint8)
        rgba[:,:,:3]=rgb[y0:y1,x0:x1];rgba[:,:,3]=owned[y0:y1,x0:x1]*255
        front=output/f'lobe-{number:02}-source.png';Image.fromarray(rgba).save(front)
        rgba[:,:,:3]=105;back=output/f'lobe-{number:02}-unknown.png';Image.fromarray(rgba).save(back)
        assigned+=owned.astype(np.uint8)
        records.append(dict(index=number,bbox_source=[x+x0,y+y0,x+x1,y+y1],source=str(front),unknown=str(back),
                            source_sha256=sha(front),unknown_sha256=sha(back),native_pixels=int(owned.sum())))
    if not np.array_equal(assigned.astype(bool),canopy):raise ValueError('Foliage support union differs from native canopy')
    evidence=dict(source_rgb_sha256=sha(source_path),native_alpha_sha256=sha(alpha_path),native_mask=settings['mask'],
                  source_node=f'building-{node:03d}',canopy_pixels=int(canopy.sum()),overlap_pixels=int((assigned>1).sum()),
                  overlap_rule='Identical source-coordinate RGB overlaps; first hit owns projection. Internal rounded borders are inferred.',
                  protected_source_rgb='Direct source crop bytes; native alpha intersected with inferred rounded supports.',lobes=records)
    (output/'source-partition.json').write_text(json.dumps(evidence,indent=2)+'\n')
    return evidence


def inferred_packet(workspace,node,output):
    """Neutral, explicitly inferred forest crown coverage; never native alpha."""
    from props_trees import CROWNS, GROUND
    rows=np.asarray(CROWNS[node],dtype=float)
    left,right=rows[:,1].min(),rows[:,2].max()
    top,bottom=rows[:,0].min(),rows[:,0].max()
    CONFIG[node]=dict(ground=GROUND[node])
    output.mkdir(parents=True,exist_ok=True)
    records=[]
    # Staggered fixed lobes replace the opaque envelope without borrowing
    # neighboring canopy artwork. Every perimeter and gap below is inferred.
    layout=[(.42,.13,.26,.22),(.67,.25,.28,.26),(.25,.32,.28,.25),
            (.47,.46,.31,.29),(.74,.52,.24,.25),(.22,.59,.24,.24),
            (.42,.77,.26,.22),(.63,.76,.23,.22)]
    for number,(u,v,rx,ry) in enumerate(layout):
        cx=left+u*(right-left);cy=top+v*(bottom-top)
        rx*=right-left;ry*=bottom-top
        x0,y0,x1,y1=math.floor(cx-rx),math.floor(cy-ry),math.ceil(cx+rx),math.ceil(cy+ry)
        yy,xx=np.mgrid[y0:y1,x0:x1];dx=(xx-cx)/rx;dy=(yy-cy)/ry
        angle=np.arctan2(dy,dx);radius=np.sqrt(dx*dx+dy*dy)
        edge=.89+.055*np.sin(angle*13+number)+.045*np.cos(angle*21-number)
        coverage=radius<edge
        # Sparse repeatable gaps are design hypotheses, not recovered leaves.
        holes=((np.sin(xx*.63+number)*np.cos(yy*.49-number))>.94)&(radius>.28)
        coverage &= ~holes
        rgba=np.full((y1-y0,x1-x0,4),105,dtype=np.uint8);rgba[:,:,3]=coverage*255
        path=output/f'lobe-{number:02}-inferred.png';Image.fromarray(rgba).save(path)
        records.append(dict(index=number,bbox_source=[x0,y0,x1,y1],source=str(path),unknown=str(path),
                            source_sha256=sha(path),unknown_sha256=sha(path),native_pixels=0,observed=False))
    evidence=dict(source_rgb_sha256='',native_alpha_sha256='',native_mask=None,
                  source_node=f'building-{node:03d}',canopy_pixels=0,duplicate_pixels=0,
                  ownership='No source ownership. All forest foliage coverage, gaps and depth are inferred.',
                  lobes=records)
    (output/'source-partition.json').write_text(json.dumps(evidence,indent=2)+'\n')
    return evidence


def material(name,path,known,evidence):
    mat=bpy.data.materials.new(name);mat.use_nodes=True;mat.use_backface_culling=True
    if hasattr(mat,'surface_render_method'):mat.surface_render_method='DITHERED'
    if hasattr(mat,'alpha_threshold'):mat.alpha_threshold=.5
    for key,value in dict(foliage_physical_opacity=True,opacity_semantics='physical-coverage',
          source_ownership_semantics='separate-mask',source_ownership_channel='vertex-color-r',
          foliage_card_sides='paired-one-sided',foliage_alpha_cutoff=.5,foliage_unlit=True,projection_preserve=True,
          foliage_recipe=VERSION,foliage_source_rgb_sha256=evidence['source_rgb_sha256'],
          foliage_native_alpha_sha256=evidence['native_alpha_sha256'],foliage_observed=known).items():mat[key]=value
    nodes=mat.node_tree.nodes;nodes.clear();links=mat.node_tree.links
    uv=nodes.new('ShaderNodeUVMap');uv.uv_map='Foliage UV'
    tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(path),check_existing=False);tex.image.pack();tex.interpolation='Closest'
    shader=nodes.new('ShaderNodeBsdfPrincipled');shader.inputs['Roughness'].default_value=1
    shader.inputs['Metallic'].default_value=0
    output=nodes.new('ShaderNodeOutputMaterial')
    links.new(uv.outputs['UV'],tex.inputs['Vector']);links.new(tex.outputs['Color'],shader.inputs['Base Color'])
    links.new(tex.outputs['Alpha'],shader.inputs['Alpha'])
    if 'Emission Color' in shader.inputs:
        links.new(tex.outputs['Color'],shader.inputs['Emission Color']);shader.inputs['Emission Strength'].default_value=1
    # Cycles does not use the raster backface-culling flag. Make the same
    # one-sided surface explicit in the authored shader for audit parity.
    geometry=nodes.new('ShaderNodeNewGeometry')
    transparent=nodes.new('ShaderNodeBsdfTransparent');mix=nodes.new('ShaderNodeMixShader')
    links.new(geometry.outputs['Backfacing'],mix.inputs[0])
    links.new(shader.outputs['BSDF'],mix.inputs[1]);links.new(transparent.outputs[0],mix.inputs[2])
    links.new(mix.outputs[0],output.inputs['Surface'])
    return mat


def refine_crown(obj,node,evidence):
    matrix=obj.matrix_world.copy();before=geometry_hash(obj);vertices=[];faces=[];face_mats=[];face_known=[];uvs=[]
    materials=[];ground=CONFIG[node]['ground'];steps=4
    for lobe in evidence['lobes']:
        number=lobe['index'];x0,y0,x1,y1=lobe['bbox_source'];cx,cy=(x0+x1)/2,(y0+y1)/2
        for front in (True,False):
            known=front and lobe.get('observed',True)
            slot=len(materials);materials.append(material(f'{obj.name} lobe{number:02} '+('source' if known else 'unknown'),
                lobe['source' if known else 'unknown'],known,evidence))
            start=len(vertices)
            for j in range(steps+1):
                v=j/steps;y=y0+(y1-y0)*v
                for i in range(steps+1):
                    u=i/steps;x=x0+(x1-x0)*u
                    depth=DEPTHS[number]+(x-cx)*SLOPES[number][0]+(y-cy)*SLOPES[number][1]
                    depth+=12*math.sin(math.pi*u)*math.sin(math.pi*v)
                    depth-=0 if front else .35
                    world=Vector((x,-ground/SINE,(ground-y)/COSINE))+RAY*depth
                    vertices.append(matrix.inverted()@world);uvs.append((u,1-v))
            for j in range(steps):
                for i in range(steps):
                    a=start+j*(steps+1)+i;b=a+1;c=b+steps+1;d=a+steps+1
                    # Both sides must use the same diagonal: reversed nonplanar
                    # quads can tessellate differently and intersect the pair.
                    faces.extend(((a,d,c),(a,c,b)) if front else ((a,b,c),(a,c,d)))
                    face_mats.extend((slot,slot));face_known.extend((known,known))
    mesh=bpy.data.meshes.new(obj.name+' native cutout lobes');mesh.from_pydata(vertices,[],faces);mesh.update()
    for mat in materials:mesh.materials.append(mat)
    uv=mesh.uv_layers.new(name='Foliage UV');ownership=mesh.color_attributes.new(name='Source ownership',type='FLOAT_COLOR',domain='CORNER')
    mesh.color_attributes.active_color=ownership
    for polygon,slot,known in zip(mesh.polygons,face_mats,face_known):
        polygon.material_index=slot
        for loop_index in polygon.loop_indices:
            uv.data[loop_index].uv=uvs[mesh.loops[loop_index].vertex_index]
            ownership.data[loop_index].color=(1. if known else 0.,1.,1.,1.)
    fallback=mesh.attributes.new('reprojection_fallback_material','INT','FACE')
    for polygon in mesh.polygons:fallback.data[polygon.index].value=polygon.material_index
    bm=bmesh.new();bm.from_mesh(mesh)
    degenerate=sum(f.calc_area()<1e-7 for f in bm.faces);boundary=sum(e.is_boundary for e in bm.edges)
    if degenerate:raise ValueError('Degenerate foliage card')
    bm.free();old=obj.data;obj.data=mesh
    if old.users==0:bpy.data.meshes.remove(old)
    obj['leicester_geometry_recipe']=VERSION;obj['foliage_physical_opacity']=True
    if matrix!=obj.matrix_world:raise ValueError('Crown transform changed')
    return dict(source_node=obj['source_node'],projection_component=obj['projection_component'],
                before_geometry_sha256=before,after_geometry_sha256=geometry_hash(obj),world_transform_drift=0,
                lobes=len(evidence['lobes']),paired_card_surfaces=len(evidence['lobes'])*2,
                vertices=len(mesh.vertices),faces=len(mesh.polygons),intentional_card_boundary_edges=boundary,
                degenerate_faces=degenerate,source_partition=evidence)


def run(workspace):
    workspace=Path(workspace).resolve();config=json.loads((workspace/'workspace.json').read_text())
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise ValueError('Open isolated tree worker model')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from refinement_workspace import validate
    validate(workspace)
    objects=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']]
    crowns=[o for o in objects if o.get('projection_component')=='crown']
    if len(crowns)!=1:raise ValueError('Expected one canonical crown component')
    crown=crowns[0];node=int(crown['source_node'][9:])
    if node not in (88,89,90,91,92):raise ValueError('Unsupported tree')
    untouched={o.name:geometry_hash(o) for o in objects if o!=crown}
    evidence=(source_packet if node in (88,89) else inferred_packet)(workspace,node,workspace/'inspection/native-foliage')
    report=refine_crown(crown,node,evidence);first=geometry_hash(crown)
    refine_crown(crown,node,evidence)
    if first!=geometry_hash(crown):raise ValueError('Foliage geometry is not idempotent')
    if untouched!={o.name:geometry_hash(o) for o in objects if o!=crown}:raise ValueError('Wood geometry changed')
    validate(workspace)
    report.update(recipe=VERSION,idempotence='PASS',approval_status='fix-needed; new candidate awaiting full review',
        texture_generation='not-started',projection_status='STALE; needs alpha-aware source review and actual material8views',
        limitations=['Forest090–092 foliage alpha and contours are entirely inferred neutral placeholders, not recovered native foliage.',
                     'Overlapping rounded supports, curved surface depth and fixed orientations are inferred; their source-view union retains exact native alpha and RGB.',
                     'Canopy mask includes fine twig artwork; large measured branches remain separate opaque geometry.',
                     'Back surfaces retain the same inferred cutout silhouette but use neutral RGB and zero ownership.',
                     'Foliage cards intentionally have open boundaries; they are thin render surfaces, not solid collision volumes.'])
    (workspace/'inspection/foliage-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);print(json.dumps(run(args.workspace)))
