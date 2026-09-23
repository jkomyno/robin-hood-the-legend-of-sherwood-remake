"""Check frozen source RGB membership and camera invariance for a north asset packet."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from PIL import Image
w=Path(sys.argv[1]);a=json.loads((w/'input/views.json').read_text());b=json.loads((w/'modified/views.json').read_text());src=Path(b['source_image']);rgb=np.asarray(Image.open(src).convert('RGB'),dtype=np.uint32);colors=np.unique((rgb[:,:,0]<<16)|(rgb[:,:,1]<<8)|rgb[:,:,2]);rows=[]
for i in range(8):
 im=np.asarray(Image.open(w/f'modified/views/view-{i}-textured.png').convert('RGB'),dtype=np.uint32);known=np.asarray(Image.open(w/f'modified/views/view-{i}-known.png').convert('L'))>0;values=((im[:,:,0]<<16)|(im[:,:,1]<<8)|im[:,:,2])[known];missing=int((~np.isin(values,colors)).sum());assert missing==0;rows.append({'view':i,'known_pixels':int(known.sum()),'unmatched_rgb':missing})
keys=['index','azimuth_degrees','camera_location','camera_matrix_world','camera_rotation_euler','ortho_scale'];same=all(x[k]==y[k] for x,y in zip(a['views'],b['views']) for k in keys);assert same
report={'method':'Known pixel RGB membership in frozen source artwork; checks byte color provenance, not independent positional correspondence. Renderer ray ownership and native masks establish positional constraints.','views':rows,'fixed_camera_views_equal':same,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'camera_keys_compared':keys};(w/'inspection/source-rgb-and-framing.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS: eight fixed cameras and exact source RGB membership')
