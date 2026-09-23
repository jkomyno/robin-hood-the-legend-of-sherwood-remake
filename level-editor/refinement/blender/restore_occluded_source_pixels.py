"""Restore explicitly audited source pixels in one existing packed atlas.

Configuration binds the source node, source-pixel support, contaminated source,
clean source, and output directory. Geometry, UVs and all other atlases stay
unchanged. This is an original-artwork correction, not texture synthesis.
"""
import sys
import json
import math
import hashlib
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from refinement_workspace import _geometry

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def restore(config_path):
    config=json.loads(Path(config_path).read_text());out=Path(config['output'])
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    scene=bpy.data.scenes[config['scene_name']];bpy.context.window.scene=scene
    from render_source_atlas_crop import render as render_crop
    render_crop(config['collection_name'],config['crop'],out/'before.png')
    targets=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and not o.hide_render and o.get('source_node')==config['source_node']]
    if len(targets)!=1:raise ValueError('Expected exactly one audited receiver')
    obj=targets[0];geometry={o.name:_geometry(o) for o in scene.objects}
    uv_before={uv.name:[list(p.uv) for p in uv.data] for uv in obj.data.uv_layers}
    slots={f.material_index for f in obj.data.polygons}
    if len(slots)!=1:raise ValueError('Expected one active atlas')
    material=obj.data.materials[next(iter(slots))]
    textures=[n for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    if len(textures)!=1:raise ValueError('Expected one source-owned packed atlas')
    texture=textures[0];image=texture.image
    if material.users!=1 or image.users!=1:raise ValueError('Shared atlas requires explicit isolation first')
    nodes=[n for n in material.node_tree.nodes if n.type=='UVMAP']
    if len(nodes)!=1:raise ValueError('Expected one atlas UV map')
    uv=obj.data.uv_layers[nodes[0].uv_map]
    old=np.array(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4)
    changed=old.copy();edit=np.zeros(old.shape[:2],dtype=bool)
    def load(path):
        im=bpy.data.images.load(str(Path(path).resolve()),check_existing=False)
        pixels=np.array(im.pixels[:],dtype=np.float32).reshape(im.size[1],im.size[0],4)[::-1].copy();bpy.data.images.remove(im);return pixels
    before=load(config['contaminated_source']);clean=load(config['clean_source'])
    if before.shape!=clean.shape:raise ValueError('Source dimensions differ')
    support={tuple(p) for p in json.loads(Path(config['support']).read_text())['pixels']}
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    toward=Vector((0,-cosine,sine));h,w=old.shape[:2];skipped=0;matches=set()
    for face in obj.data.polygons:
        if (obj.matrix_world.to_3x3().inverted().transposed()@face.normal).normalized().dot(toward)<=.05:continue
        loops=list(face.loop_indices);coords=np.array([uv.data[i].uv[:] for i in loops]);world=np.array([obj.matrix_world@obj.data.vertices[obj.data.loops[i].vertex_index].co for i in loops])
        system=np.column_stack((coords,np.ones(len(coords))))
        affine=np.linalg.lstsq(system,world,rcond=None)[0]
        if np.abs(system@affine-world).max()>1e-3:raise ValueError('Non-affine UV face requires triangle-specific correction')
        low=np.maximum(0,np.floor(coords.min(axis=0)*[w,h]).astype(int)-2)
        high=np.minimum([w,h],np.ceil(coords.max(axis=0)*[w,h]).astype(int)+2)
        for y in range(low[1],high[1]):
            for x in range(low[0],high[0]):
                p=np.array([(x+.5)/w,(y+.5)/h,1])@affine
                sx,sy=int(math.floor(p[0])),int(math.floor(-p[1]*sine-p[2]*cosine))
                if (sx,sy) not in support:continue
                # Guard against overwriting generated detail or unrelated padding.
                if np.max(np.abs(old[y,x,:3]-before[sy,sx,:3]))>1/255+.00001:
                    skipped+=1;continue
                changed[y,x,:3]=clean[sy,sx,:3];edit[y,x]=True;matches.add((sx,sy))
    if not edit.any():raise ValueError('No source-owned atlas samples matched the audited support')
    if not np.array_equal(old[~edit],changed[~edit]):raise RuntimeError('Unrelated atlas texels changed')
    np.save(out/'atlas-before.npy',old);np.save(out/'atlas-after.npy',changed);np.save(out/'atlas-edited.npy',edit)
    image.pixels.foreach_set(changed.ravel());image.update();image.pack()
    evidence={key:{'path':str(Path(config[key]).resolve()),'sha256':sha(config[key])} for key in ('contaminated_source','clean_source','support')}
    material['source_pixel_correction']=json.dumps({'receiver':config['source_node'],'evidence':evidence,'reason':config['reason']},sort_keys=True)
    obj['source_projection_correction']=material['source_pixel_correction']
    if geometry!={o.name:_geometry(o) for o in scene.objects}:raise RuntimeError('Geometry changed')
    if uv_before!={u.name:[list(p.uv) for p in u.data] for u in obj.data.uv_layers}:raise RuntimeError('UV changed')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'worker.blend'))
    report={'source_node':config['source_node'],'object':obj.name,'geometry_unchanged':True,'uv_unchanged':True,'other_atlas_pixels_changed':0,'source_pixel_support':len(support),'matched_source_pixels':len(matches),'atlas_texels_selected':int(edit.sum()),'atlas_texels_rgb_changed':int(np.any(old[:,:,:3]!=changed[:,:,:3],axis=2).sum()),'nonmatching_texels_preserved':skipped,'evidence':evidence,'worker_sha256':sha(out/'worker.blend'),'future_projection':'Use the clean covered-source layer for this permanent landing, or reapply this exact correction. The bridge sprite belongs exclusively to the separate mission asset.'}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    render_crop(config['collection_name'],config['crop'],out/'after.png')
    print(json.dumps(report),flush=True)

if __name__=='__main__':restore(sys.argv[sys.argv.index('--')+1])
