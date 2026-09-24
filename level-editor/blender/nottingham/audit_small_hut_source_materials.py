"""Compare native hut artwork with actual saved UV atlases at source pixel centers."""
import sys,json,math,hashlib
from pathlib import Path
import bpy,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'level-editor/work/nottingham-refinement';A='nottingham-village-small-hut'
S=math.sin(math.radians(35));C=math.cos(math.radians(35));tow=np.array([0,-C,S]);box=(340,2745,470,2910)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sample(path):
 bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.view_layer.update()
 yy,xx=np.mgrid[box[1]:box[3],box[0]:box[2]];pts=np.stack([xx+.5,yy+.5],-1);depth=np.full(xx.shape,-np.inf);rgb=np.zeros((*xx.shape,3));owners=np.zeros(xx.shape,int);facing=np.zeros(xx.shape);cache={}
 for obj in bpy.data.collections['nottingham Working'].all_objects:
  if obj.type!='MESH' or obj.hide_render or obj.get('asset_group')!=A:continue
  mesh=obj.data;mesh.calc_loop_triangles();vs=np.array([list(obj.matrix_world@v.co)for v in mesh.vertices]);proj=np.column_stack([vs[:,0],-vs[:,1]*S-vs[:,2]*C]);nd=int(obj['source_node'].split('-')[1])
  for tr in mesh.loop_triangles:
   ids=list(tr.vertices);a,b,c=proj[ids];basis=np.array([b-a,c-a]);det=np.linalg.det(basis)
   if abs(det)<1e-8:continue
   uv=(pts-a)@np.linalg.inv(basis);u,v=uv[:,:,0],uv[:,:,1];weight=np.stack([1-u-v,u,v],-1);z=weight@(vs[ids]@tow);take=(u>=0)&(v>=0)&(u+v<=1)&(z>depth)
   if not np.any(take):continue
   mat=mesh.materials[tr.material_index];tex=next(n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image);im=tex.image
   if im.name not in cache:
    pix=np.empty(im.size[0]*im.size[1]*4,dtype=np.float32);im.pixels.foreach_get(pix);cache[im.name]=pix.reshape(im.size[1],im.size[0],4)
   atlas=cache[im.name];uvnode=tex.inputs['Vector'].links[0].from_node;layer=mesh.uv_layers[uvnode.uv_map];tuv=np.array([list(layer.data[i].uv)for i in tr.loops]);q=weight[take]@tuv;ix=np.clip((q[:,0]*im.size[0]).astype(int),0,im.size[0]-1);iy=np.clip((q[:,1]*im.size[1]).astype(int),0,im.size[1]-1)
   rgb[take]=atlas[iy,ix,:3];depth[take]=z[take];owners[take]=nd
   normal=np.cross(vs[ids[1]]-vs[ids[0]],vs[ids[2]]-vs[ids[0]]);normal/=np.linalg.norm(normal);facing[take]=normal@tow
 return (np.clip(rgb*255+.5,0,255).astype('uint8'),owners,facing)
def main():
 out=Path(sys.argv[sys.argv.index('--')+1]).resolve();old=W/'round-23/assets'/A
 before,bo,bf=sample(old/'model.blend');after,ao,af=sample(out/'model.blend')
 mask=Image.new('L',(2304,3520));mask.paste(Image.open(W/'mask-review/inventory-v6/000210.png').convert('L'),(352,2755));domain=np.array(mask.crop(box))>0
 original=np.array(Image.open(old/'reference/source.png').convert('RGB').crop(box));panels=[]
 for rgb in [original,before,after]:
  rgb=rgb.copy();rgb[~domain]=original[~domain]//3;panels.append(Image.fromarray(rgb).resize((520,660),Image.Resampling.NEAREST))
 composite=Image.new('RGB',(1560,686));d=ImageDraw.Draw(composite)
 for i,(im,label) in enumerate(zip(panels,['Original artwork / native210','Approved saved materials','Proposed saved materials'])):composite.paste(im,(i*520,26));d.text((i*520+5,5),label,fill='white')
 folder=out/'inspection';folder.mkdir(exist_ok=True);composite.save(folder/'source-material-comparison.png')
 missing_image=original.copy();missing_image[domain&(ao==0)]=[255,0,255];Image.fromarray(missing_image).resize((780,990),Image.Resampling.NEAREST).save(folder/'missing-source-receivers.png')
 np.savez_compressed(folder/'source-domain-hits.npz',domain=domain,old_owner=bo,new_owner=ao)
 newmiss=domain&(bo>0)&(ao==0);both=domain&(bo>0)&(ao>0);changed=both&(bo!=ao)
 rows={}
 for nd in [281,282,283,284]:rows[str(nd)]={'before_pixels':int(np.sum(domain&(bo==nd))),'after_pixels':int(np.sum(domain&(ao==nd))),'after_source_facing_pixels':int(np.sum(domain&(ao==nd)&(af>.05)))}
 report={'status':'AWAITING-VISUAL-COVERAGE-REVIEW','model_sha256':sha(out/'model.blend'),'previous_model_sha256':sha(old/'model.blend'),'modified_views_sha256':sha(out/'modified/views.json'),'source_sha256':sha(old/'reference/source.png'),'native_domain_sha256':sha(W/'mask-review/inventory-v6/000210.png'),'native_pixels':int(domain.sum()),'unchanged_native_domain':True,'new_geometry_misses':int(newmiss.sum()),'original_geometry_misses':int(np.sum(domain&(bo==0))),'proposed_geometry_misses':int(np.sum(domain&(ao==0))),'changed_receiver_pixels':int(changed.sum()),'receivers':rows,'limitations':['Source camera samples exact saved UV atlas images at native pixel-center intersections. Atlas discretization means sampled RGB can differ from the continuous source projection diagnostic.','Domain is full original native210 independent of candidate acceptance. Context occluders are omitted from this isolated material comparison; the standard projection retains them.','Geometry revision requires renewed user approval.']}
 (folder/'source-material-comparison.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
