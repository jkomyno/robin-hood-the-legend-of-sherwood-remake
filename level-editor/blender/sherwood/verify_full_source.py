"""Reopen source atlases and independently check RGB, ownership, alpha and UV samples."""
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent;EDITOR=HERE.parents[1]
sys.path[:0]=[str(HERE),str(EDITOR/'refinement/blender'),str(EDITOR/'blender/lincoln')]
from stage_grouping_review import fingerprint
from source_authority import sha
from occlusion_constraints import SourceMaskConstraints
import global_reproject as gr

gr.SCENE='Sherwood Editor Migration';gr.COLLECTION='Sherwood Working';gr.OWNERSHIP_LABEL='exterior'
root,masks=map(lambda p:Path(p).resolve(),sys.argv[sys.argv.index('--')+1:])
r=json.loads((root/'reprojection.json').read_text());coverage=json.loads((masks/'coverage.json').read_text())
assert coverage['unresolved_source_nodes']==0 and coverage['unconstrained_receivers']==0
assert sha(root/'source-only.blend')==r['worker_sha256']
assert sha(r['day_report'])==r['day_report_sha256']
assert sha(r['canopy_manifest'])==r['canopy_manifest_sha256']
assert r['source_mask_evidence'][str(masks/'source-masks.json')]==sha(masks/'source-masks.json')
assert len(r['canopy_sources'])==6
for path,digest in r['source_mask_evidence'].items():assert sha(path)==digest,path
source_path=EDITOR.parent/'datadirs/fullgame_gog_hackable/Data/Levels/Day/sherwood.map.png'
sources={'Day':np.asarray(Image.open(source_path).convert('RGBA'))}
constraints=SourceMaskConstraints(masks/'source-masks.json','exterior',sha(source_path),Image.open(source_path).size)
for profile,layer in r['canopy_sources'].items():
    for field in ('source','mask','sprite'):assert sha(layer[field])==layer[field+'_sha256']
    sources[profile]=np.asarray(Image.open(layer['source']).convert('RGBA'))
    assert np.array_equal(np.asarray(Image.open(layer['mask']).convert('L'))>0,sources[profile][...,3]>=128)
bpy.ops.wm.open_mainfile(filepath=str(root/'source-only.blend'));scene=gr.Scene();objects=scene.objects
assert fingerprint(objects)==r['geometry_uv_material_fingerprint']
assert set(r['ownership'])=={o.name for o in objects}
rows={x['object']:x for x in r['objects']};count=0;uv_checks=0;stats=[]
for number,record in enumerate(scene.meshes):
    obj=record['object'];name=obj.name;row=rows[name];source=sources[row['source_layer']];h,w=source.shape[:2]
    binding=scene.slot_binding(obj,obj.data.polygons[0].material_index);rgba=gr.read_image(binding['image'])
    assert hashlib.sha256(rgba[...,3].tobytes()).hexdigest()==r['physical_alpha_sha256'][name],name
    path=r['ownership'][name];assert sha(path)==r['ownership_sha256'][name]
    with np.load(path) as data:flags,xy=data['ownership'],data['source_xy']
    assert flags.shape==rgba.shape[:2] and set(np.unique(flags))<={0,1}
    known=flags==1;assert np.all(rgba[~known,:3]==128),name
    yy,xx=np.where(known);px,py=xy[...,0][known].astype(int),xy[...,1][known].astype(int)
    assert np.all((px>=0)&(px<w)&(py>=0)&(py<h)),name
    assert np.array_equal(rgba[known,:3],source[py,px,:3]),name
    if row['source_layer']=='Day':
        assert not binding['material'].get('foliage_physical_opacity'),name
        rule=constraints.for_object(obj);assert rule is not None,name
        assert constraints.allowed(rule,px,h-1-py).all(),name
    else:
        layer=r['canopy_sources'][row['source_layer']]
        assert name in layer['receivers'] and binding['material'].get('foliage_physical_opacity'),name
        assert (rgba[...,3][known]>=128).all() and (source[py,px,3]>=128).all(),name
    # Independently invert UV triangles at a deterministic spread of atlas pixels.
    # Gutter pixels outside polygons are omitted from this interior-only check.
    if len(xx):
        chosen=np.linspace(0,len(xx)-1,min(32,len(xx)),dtype=int)
        test=np.stack(((xx[chosen]+.5)/rgba.shape[1],(yy[chosen]+.5)/rgba.shape[0]),axis=1)
        uv=gr.slot_uvs(obj,binding['uv'])[record['loops']]
        a,b,c=uv[:,0],uv[:,1],uv[:,2];v0,v1=b-a,c-a
        den=v0[:,0]*v1[:,1]-v1[:,0]*v0[:,1];valid=np.abs(den)>1e-14
        for i,p in enumerate(test):
            delta=p-a
            wb=np.divide(delta[:,0]*v1[:,1]-v1[:,0]*delta[:,1],den,out=np.full(len(den),-2.),where=valid)
            wc=np.divide(v0[:,0]*delta[:,1]-delta[:,0]*v0[:,1],den,out=np.full(len(den),-2.),where=valid)
            hits=np.flatnonzero(valid&(wb>=0)&(wc>=0)&(wb+wc<=1))
            if not len(hits):continue
            t=hits[0];world=(1-wb[t]-wc[t])*record['corners'][t,0]+wb[t]*record['corners'][t,1]+wc[t]*record['corners'][t,2]
            actual=np.array([world[0],-world[1]*math.sin(math.radians(35))-world[2]*math.cos(math.radians(35))])
            stored=xy[yy[chosen[i]],xx[chosen[i]]]
            assert np.all((actual-stored>=-.002)&(actual-stored<=1.002)),(name,actual.tolist(),stored.tolist())
            uv_checks+=1
    n=int(known.sum());assert n==row['accepted_texels'];count+=n
    stats.append(dict(object=name,source_layer=row['source_layer'],accepted_texels=n))
    if number%100==0:print('Verified',number+1,'/',len(objects),'meshes',flush=True)
assert count==r['accepted_texels'];assert uv_checks>1000
result=dict(status='PASS_REPROJECTION_CHECKS',worker_sha256=r['worker_sha256'],checked_meshes=len(objects),canopy_layers=6,
    accepted_texels=count,independent_uv_samples=uv_checks,accepted_rgb_mismatches=0,outside_mask_accepted_texels=0,
    unconstrained_receivers=0,unresolved_source_nodes=0,geometry_uv_transforms_unchanged=True,physical_alpha_unchanged=True,
    source_visible_meshes_without_accepted_samples=[x['object'] for x in stats if x['accepted_texels']==0],
    note='Zero-sample meshes retain unknown textures; source mask visibility does not imply complete model/art registration.',synthesis_ready=False)
(root/'saved-worker-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='source_visible_meshes_without_accepted_samples'},indent=2))
