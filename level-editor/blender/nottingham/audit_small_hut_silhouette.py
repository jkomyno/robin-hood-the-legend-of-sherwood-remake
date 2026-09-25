"""Measure source silhouette excess independently of candidate ownership masks."""
import json,math,hashlib,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter,ImageDraw
from small_hut_source_domain import domain
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main(w):
 w=Path(w);rows=json.loads((w/'inspection/faces.json').read_text());s,c=math.sin(math.radians(35)),math.cos(math.radians(35));tow=np.array([0,-c,s]);box=(340,2745,470,2910);yy,xx=np.mgrid[box[1]:box[3],box[0]:box[2]];pts=np.stack([xx+.5,yy+.5],-1);d,proof=domain();native=np.array(d.crop(box))>0;near=np.array(Image.fromarray(native.astype('uint8')*255).filter(ImageFilter.MaxFilter(5)))>0
 depth=np.full(xx.shape,-np.inf);owner=np.zeros(xx.shape,int);coverage=np.zeros(xx.shape,bool)
 for o in rows:
  vs=np.array(o['vertices']);node=int(o['node'].split('-')[1]);p=np.column_stack([vs[:,0],-vs[:,1]*s-vs[:,2]*c])
  for ids in o['triangles']:
   a,b,d=p[ids];basis=np.array([b-a,d-a])
   if abs(np.linalg.det(basis))<1e-9:continue
   u,v=((pts-a)@np.linalg.inv(basis)).transpose(2,0,1);inside=(u>=0)&(v>=0)&(u+v<=1);coverage|=inside;z=np.stack([1-u-v,u,v],-1)@(vs[ids]@tow);take=inside&(z>depth);depth[take]=z[take];owner[take]=node
 miss=native&~coverage;excess=coverage&~native;far=coverage&~near;src=np.array(Image.open(w/'reference/source.png').convert('RGB').crop(box));src[far]=[255,0,0];src[miss]=[255,0,255];Image.fromarray(src).resize((780,990),Image.Resampling.NEAREST).save(w/'inspection/source-silhouette-excess.png')
 report=dict(status='AWAITING-VISUAL-CLASSIFICATION',model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),faces_sha256=sha(w/'inspection/faces.json'),source_sha256=sha(w/'reference/source.png'),domain=proof,native_pixels=int(native.sum()),missing=int(miss.sum()),projected_excess=int(excess.sum()),excess_beyond_two_pixels=int(far.sum()),roof_excess_beyond_two_pixels=int(np.sum(far&np.isin(owner,[282,283]))),excess_pixels=[dict(pixel=[int(x),int(y)],node=int(owner[y-box[1],x-box[0]]))for y,x in zip(yy[far],xx[far])],method='Exact saved triangle projection at source pixel centers. Red marks projected geometry beyond a two-pixel native210+211 outline dilation; magenta is missing native artwork. No candidate mask acceptance used.')
 (w/'inspection/source-silhouette-excess.json').write_text(json.dumps(report,indent=2)+'\n');print({k:report[k]for k in ['native_pixels','missing','projected_excess','excess_beyond_two_pixels','roof_excess_beyond_two_pixels']})
if __name__=='__main__':main(sys.argv[1])
