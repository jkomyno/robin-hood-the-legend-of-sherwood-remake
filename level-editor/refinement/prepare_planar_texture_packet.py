"""Prepare one exact approved planar atlas, preserving source and physical holes."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import struct

import numpy as np
from PIL import Image

from prepare_texture_packet import prepare
from review_evidence import sha, bind_decision, load_decisions


def atlas_triangles(path):
    raw=Path(path).read_bytes()
    if raw[:4]!=b'glTF': raise ValueError('Expected audited GLB')
    length,kind=struct.unpack_from('<II',raw,12)
    data=json.loads(raw[20:20+length]); offset=20+length
    size,kind=struct.unpack_from('<II',raw,offset)
    if kind!=0x004E4942: raise ValueError('Expected embedded geometry buffer')
    binary=raw[offset+8:offset+8+size]
    if len(data['meshes'])!=1 or len(data['meshes'][0]['primitives'])!=1:
        raise ValueError('Planar preparation requires one audited mesh and primitive')
    primitive=data['meshes'][0]['primitives'][0]
    material=data['materials'][primitive['material']]
    if material.get('alphaMode','OPAQUE')!='OPAQUE':
        raise ValueError('Physical alpha requires explicit coverage support')
    if primitive.get('mode',4)!=4: raise ValueError('Expected triangles')
    def accessor(index):
        a=data['accessors'][index];v=data['bufferViews'][a['bufferView']]
        if a.get('sparse') or v.get('buffer',0)!=0: raise ValueError('Unsupported accessor')
        dtype={5126:'<f4',5123:'<u2',5125:'<u4'}[a['componentType']]
        columns={'SCALAR':1,'VEC2':2,'VEC3':3}[a['type']]
        stride=v.get('byteStride',np.dtype(dtype).itemsize*columns)
        values=np.ndarray((a['count'],columns),dtype=dtype,buffer=binary,
                          offset=v.get('byteOffset',0)+a.get('byteOffset',0),
                          strides=(stride,np.dtype(dtype).itemsize)).copy()
        if not np.isfinite(values).all(): raise ValueError('Nonfinite audited geometry')
        return values
    positions=accessor(primitive['attributes']['POSITION'])
    singular=np.linalg.svd(positions-positions.mean(0),compute_uv=False)
    if singular[-1]>max(1,float(singular[0]))*1e-6:
        raise ValueError('Receiver is not planar')
    uv=accessor(primitive['attributes']['TEXCOORD_0'])
    indices=accessor(primitive['indices']).ravel().astype(int).reshape(-1,3)
    if (uv< -1e-6).any() or (uv>1+1e-6).any(): raise ValueError('Atlas UVs must stay in unit square')
    return uv[indices]


def coverage(triangles,width,height):
    result=np.zeros((height,width),bool)
    # glTF UV origin is top-left. Test pixel centers, so gaps and holes remain
    # outside even when triangles share an edge or lie between pixel centers.
    x=(np.arange(width)+.5)/width
    for triangle in triangles:
        a,b,c=triangle
        determinant=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        if abs(determinant)<1e-12: raise ValueError('Degenerate atlas triangle')
        for start in range(0,height,128):
            stop=min(height,start+128);y=(np.arange(start,stop)+.5)/height
            dx=x[None,:]-a[0];dy=y[:,None]-a[1]
            u=(dx*(c[1]-a[1])-dy*(c[0]-a[0]))/determinant
            v=((b[0]-a[0])*dy-(b[1]-a[1])*dx)/determinant
            result[start:stop]|=(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)
    return result


def prepare_planar(manifest_path,asset_id,output,source,known_mask,atlas,decisions=None):
    manifest_path=Path(manifest_path).resolve();output=Path(output).resolve()
    source,known_mask,atlas=map(Path,(source,known_mask,atlas))
    eligible=prepare(manifest_path,asset_id,output,decisions,check_only=True)
    data=json.loads(manifest_path.read_text());item=copy.deepcopy(next(i for i in data['items'] if i['id']==asset_id))
    records=load_decisions(Path(decisions) if decisions else manifest_path.parent/'decisions.json',
                           {i['id'] for i in data['items']}|{i['id'] for i in data.get('without_packets',[])})
    bind_decision(item,records)
    def require_bound(path):
        if not any(Path(e['path']).resolve()==path.resolve() and e['sha256']==sha(path)
                   for e in item['revision']['evidence'].values()):
            raise ValueError('Planar evidence is not bound to approved revision: '+str(path))
    ownership_path=Path(item['ownership']);require_bound(ownership_path)
    ownership=json.loads(ownership_path.read_text())
    for path,key in [(source,'source_sha256'),(known_mask,'mask_sha256'),(atlas,'texture_sha256')]:
        if sha(path)!=ownership[key]: raise ValueError('Approved planar evidence changed: '+key)
    source_image=Image.open(source).convert('RGB'); image=Image.open(atlas).convert('RGB')
    known=np.array(Image.open(known_mask).convert('L'))>0
    width,height=image.size
    if source_image.size!=image.size or known.shape!=(height,width): raise ValueError('Planar evidence dimensions differ')
    if width%16 or height%16 or max(width,height)>3840 or max(width,height)/min(width,height)>3 or not 655360<=width*height<=8294400:
        raise ValueError('Exact planar atlas outside generation bounds; do not resize')
    if int(known.sum())!=ownership['accepted_pixels'] or int((~known).sum())!=ownership['unknown_pixels']:
        raise ValueError('Ownership counts differ')
    if np.any(np.array(image)[known]!=np.array(source_image)[known]): raise ValueError('Protected source RGB differs')
    glb=Path(item['stored_material_glb']);require_bound(glb)
    surface=coverage(atlas_triangles(glb),width,height)
    editable=surface&~known
    packet=Path(item['textured']).parent
    gray=None
    for index in range(8):
        solid=np.array(Image.open(packet/'views'/f'view-{index}-solid.png').convert('RGBA'))
        colors=np.unique(solid[solid[:,:,3]>0,:3],axis=0)
        if len(colors)!=1 or not np.all(colors[0]==colors[0,0]):
            raise ValueError('Planar lighting must be uniform pure gray in approved views')
        if gray is not None and gray!=colors[0].tolist(): raise ValueError('Planar lighting differs across approved views')
        gray=colors[0].tolist()
    output.mkdir(parents=True)
    shutil.copyfile(Path(item['workspace'])/'model.blend',output/'approved-model.blend')
    shutil.copyfile(atlas,output/'input.png')
    mask=np.full((height,width,4),255,np.uint8);mask[editable,3]=0
    Image.fromarray(mask).save(output/'mask.png')
    lighting=np.zeros((height,width,4),np.uint8);lighting[surface,:3]=gray;lighting[surface,3]=255
    Image.fromarray(lighting).save(output/'solid.png')
    Image.fromarray((surface*255).astype(np.uint8)).save(output/'surface.png')
    frames=json.loads((packet/'views.json').read_text())
    manifest={'asset_id':asset_id,'projection_kind':'planar-atlas','layout':{'width':width,'height':height},
              'views':[{'index':0,'input':'input.png','mask':'mask.png','crop':{'left':0,'top':0,'width':width,'height':height}}],
              'reviewed_packet':str(packet),'reviewed_manifest_sha256':sha(packet/'views.json'),
              'source_blend':str(output/'approved-model.blend'),'geometry_revision':eligible['revision_sha256'],
              'atlas_source':str(Path(atlas).resolve()),'atlas_sha256':sha(atlas),
              'audited_glb':str(glb),'audited_glb_sha256':sha(glb),'physical_coverage':'Audited opaque triangle UV coverage; holes and outside remain protected',
              'ownership_report':str(ownership_path),'ownership_sha256':sha(ownership_path),
              'known_mask':str(Path(known_mask).resolve()),'known_mask_sha256':sha(known_mask),
              'scene_name':frames['scene_name'],'collection_name':frames['collection_name']}
    (output/'views.json').write_text(json.dumps(manifest,indent=2)+'\n')
    decision=item['user_decision']
    approval={'status':'approved','approved_by':'user','asset_id':asset_id,'geometry_revision':eligible['revision_sha256'],
              'exact_user_text':decision['exact_user_text'],'source_decision':decision,'texture_approval':'pending',
              'input_sha256':sha(output/'input.png'),'solid_sha256':sha(output/'solid.png'),'saved_model_sha256':sha(output/'approved-model.blend'),
              'scope':'Approved planar geometry/source atlas; single-image candidate generation only'}
    (output/'approval.json').write_text(json.dumps(approval,indent=2)+'\n')
    report={'asset_id':asset_id,'status':'prepared' if editable.any() else 'no-generation-needed','editable_pixels':int(editable.sum()),
            'protected_pixels':int((~editable).sum()),'outside_or_hole_pixels':int((~surface).sum()),'uniform_lighting_RGB':gray,
            'files':{str(p.relative_to(output)):sha(p) for p in output.iterdir() if p.is_file()},'approved_revision':eligible['revision_sha256']}
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['manifest','asset_id','output','source','known_mask','atlas']:p.add_argument(name)
    p.add_argument('--decisions');a=p.parse_args()
    print(json.dumps(prepare_planar(a.manifest,a.asset_id,a.output,a.source,a.known_mask,a.atlas,a.decisions),indent=2))
