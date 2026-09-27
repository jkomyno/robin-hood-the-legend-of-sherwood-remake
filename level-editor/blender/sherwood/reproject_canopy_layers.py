"""Reproject the six original canopy layers into unchanged, physically cutout leaves.

Run only after the complete masked Day pass. This creates a review candidate;
independent saved-file and visual checks must still grant synthesis authority.
"""
import argparse
import gc
import json
import shutil
from pathlib import Path
import sys
import bpy
import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent;EDITOR=HERE.parents[1]
sys.path[:0]=[str(HERE),str(EDITOR/'refinement'),str(EDITOR/'refinement/blender'),str(EDITOR/'blender/lincoln')]
from render_slots import acquire
from stage_grouping_review import fingerprint
from source_authority import sha
import global_reproject as gr
import texture_packets as tp

gr.SCENE='Sherwood Editor Migration';gr.COLLECTION='Sherwood Working';gr.OWNERSHIP_LABEL='exterior'

def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')

class ArtCamera:
    def __init__(self,size):self.tile=max(size)
    def project(self,points):return gr.screen(points)

def main(day,layers,output):
    day,layers,output=map(lambda p:Path(p).resolve(),(day,layers,output))
    report=json.loads((day/'reprojection.json').read_text())
    if report['unresolved_source_nodes'] or sha(day/'source-only.blend')!=report['worker_sha256']:
        raise ValueError('Incomplete or changed Day pass')
    for path,expected in report['source_mask_evidence'].items():
        if sha(path)!=expected:raise ValueError('Day source evidence changed')
    manifest=json.loads((layers/'manifest.json').read_text())
    for path,expected in manifest['evidence'].items():
        if sha(path)!=expected:raise ValueError('Canopy inventory changed')
    output.mkdir(parents=True,exist_ok=False);(output/'ownership').mkdir()
    acquire();bpy.ops.wm.open_mainfile(filepath=str(day/'source-only.blend'))
    bpy.context.window.scene=bpy.data.scenes[gr.SCENE]
    objects=sorted((o for o in bpy.data.collections[gr.COLLECTION].objects if o.type=='MESH'),key=lambda o:o.name)
    before=fingerprint(objects);scene=gr.Scene();records={r['object'].name:r for r in scene.meshes}
    leaf_names={o.name for o in objects if any(m and m.get('foliage_physical_opacity') for m in o.data.materials)}
    specified=[n for layer in manifest['layers'] for n in layer['receivers']]
    if len(specified)!=len(set(specified)) or set(specified)!=leaf_names:
        raise ValueError('Canopy receiver coverage is incomplete or duplicated')
    ownership={};tp.MASKS.clear();rows={r['object']:dict(r,source_layer='Day') for r in report['objects']}
    for n,path in report['ownership'].items():
        if sha(path)!=report['ownership_sha256'][n]:raise ValueError('Day provenance changed')
        target=output/'ownership'/Path(path).name;shutil.copy2(path,target);ownership[n]=str(target)
        tp.MASKS[n]=np.load(target)['ownership']
    sources={};physical_hashes={}
    for o in objects:
        b=scene.slot_binding(o,o.data.polygons[0].material_index)
        physical_hashes[o.name]=__import__('hashlib').sha256(gr.read_image(b['image'])[...,3].tobytes()).hexdigest()
    old_ss=gr.SS;gr.SS=1
    for layer in manifest['layers']:
        profile=layer['profile'];source_path=Path(layer['source']);source=np.asarray(Image.open(source_path).convert('RGBA'))
        source_mask=np.asarray(Image.open(layer['mask']).convert('L'))>0
        if sha(source_path)!=layer['source_sha256'] or sha(layer['mask'])!=layer['mask_sha256'] or sha(layer['sprite'])!=layer['sprite_sha256']:
            raise ValueError('Canopy source pixels changed')
        if not np.array_equal(source_mask,source[...,3]>=128):raise ValueError('Canopy ownership is not the original sprite alpha')
        names=layer['receivers'];assets=sorted({bpy.data.objects[n]['asset_group'] for n in names})
        target=tp.Target(dict(id=profile,assets=assets,patches=[],receivers=names),scene,gr)
        height,width=source.shape[:2];camera=ArtCamera((width,height))
        print('Rasterizing original layer '+profile,flush=True)
        _,ids,_=tp.raster(camera,target.corners,1)
        x,y,z=gr.screen(target.corners);matrix=np.stack([x,y,np.ones_like(x)],axis=2)
        area=(x[:,1]-x[:,0])*(y[:,2]-y[:,0])-(x[:,2]-x[:,0])*(y[:,1]-y[:,0])
        good=np.abs(area)>1e-9;planes=np.full((len(x),3),np.nan)
        planes[good]=np.linalg.solve(matrix[good],z[good][...,None])[...,0]
        accepted=0
        for number,name in enumerate(names):
            obj=bpy.data.objects[name];record=records[name];slot=obj.data.polygons[0].material_index
            binding=scene.slot_binding(obj,slot);atlas=gr.read_image(binding['image']);alpha=atlas[...,3].copy();atlas[...,:3]=128
            flags=np.zeros(atlas.shape[:2],dtype=np.uint8);xy=np.full((*flags.shape,2),-1,dtype=np.int16)
            interiors=np.zeros(flags.shape,dtype=bool)
            uv=gr.slot_uvs(obj,binding['uv'])
            for face,ty,tx,positions,normals,interior in gr.islands(record,uv,binding['image'].size,lambda _:True):
                sx,sy,_=gr.screen(positions);px,py=np.floor(sx).astype(int),np.floor(sy).astype(int)
                cx,cy=px.clip(0,width-1),py.clip(0,height-1)
                in_image=(px>=0)&(px<width)&(py>=0)&(py<height)
                take=in_image & source_mask[cy,cx] & (alpha[ty,tx]>=128)
                take &= gr.visible(positions,ids,planes,width,height) & (np.abs(normals@gr.TOWARD)>=.05)
                take &= ~interiors[ty,tx] | interior
                interiors[ty[interior],tx[interior]]=True
                atlas[ty[interior],tx[interior],:3]=128
                flags[ty[interior],tx[interior]]=0;xy[ty[interior],tx[interior]]=-1
                atlas[ty[take],tx[take],:3]=source[cy[take],cx[take],:3]
                flags[ty[take],tx[take]]=1;xy[ty[take],tx[take]]=np.stack((cx[take],cy[take]),axis=1)
            assert np.array_equal(alpha,atlas[...,3]);gr.write_image(binding['image'],atlas)
            np.savez_compressed(ownership[name],ownership=flags,source_xy=xy)
            tp.MASKS[name]=flags
            count=int((flags==1).sum());accepted+=count
            rows[name].update(source_layer=profile,accepted_texels=count,status='PROJECTED_ORIGINAL_CANOPY',source_sha256=layer['source_sha256'])
            print(f'{profile}: {number+1}/{len(names)} receivers, {accepted} accepted texels',flush=True)
        sources[profile]=layer
        del target,ids,planes,matrix,x,y,z;tp.TARGETS.clear();gc.collect()
    gr.SS=old_ss
    if fingerprint(objects)!=before:raise ValueError('Canopy pass changed geometry or UVs')
    for o in objects:
        b=scene.slot_binding(o,o.data.polygons[0].material_index)
        if __import__('hashlib').sha256(gr.read_image(b['image'])[...,3].tobytes()).hexdigest()!=physical_hashes[o.name]:
            raise ValueError('Physical opacity changed: '+o.name)
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'source-only.blend'),compress=True)
    result=dict(report,status='FULL_SOURCE_REPROJECTION_REVIEW_REQUIRED',synthesis_ready=False,
        worker_sha256=sha(output/'source-only.blend'),geometry_sha256=before,geometry_uv_material_fingerprint=before,
        day_worker_sha256=report['worker_sha256'],day_report=str(day/'reprojection.json'),day_report_sha256=sha(day/'reprojection.json'),
        canopy_manifest=str(layers/'manifest.json'),canopy_manifest_sha256=sha(layers/'manifest.json'),
        canopy_sources=sources,physical_alpha_sha256=physical_hashes,ownership=ownership,
        ownership_sha256={n:sha(p) for n,p in ownership.items()},objects=list(rows.values()),
        accepted_texels=sum(r['accepted_texels'] for r in rows.values()),unresolved_source_nodes=0,unconstrained_receivers=0)
    write(output/'reprojection.json',result);print('FULL ORIGINAL-ART REPROJECTION SAVED',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--day',required=True);p.add_argument('--layers',required=True);p.add_argument('--output',required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);main(a.day,a.layers,a.output)
