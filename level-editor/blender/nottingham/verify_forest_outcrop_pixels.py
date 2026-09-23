"""Compare the saved outcrop mesh projection with its native source silhouette."""
from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image,ImageDraw
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'level-editor/work/nottingham-refinement';P=W/'round-13/assets/nottingham-forest-rock-outcrop';r=json.loads((P/'geometry-report.json').read_text());data=r['actual_mesh_projection'];box=(997,75,1157,257);im=Image.new('1',(box[2]-box[0],box[3]-box[1]));d=ImageDraw.Draw(im)
for face in data['faces']:d.polygon([(data['vertices'][i][0]-box[0],data['vertices'][i][1]-box[1])for i in face],fill=1)
mask=Image.open(W/'mask-review/inventory-v6/000501.png').convert('L');native=Image.new('L',im.size);native.paste(mask,(1007-box[0],85-box[1]));target=np.array(native)>127;actual=np.array(im);outside=actual&~target;missing=target&~actual
fig,axes=plt.subplots(1,3,figsize=(13,6));source=Image.open(W/'source-states/covered.png');axes[0].imshow(source);axes[0].set_xlim(box[0],box[2]);axes[0].set_ylim(box[3],box[1]);axes[0].contour(np.arange(box[0],box[2]),np.arange(box[1],box[3]),actual,levels=[.5],colors=['cyan'],linewidths=.7);number=0
for section in r['source_sections']:
 for x,y in section['outline']:
  number+=1;axes[0].plot(x,y,'.',color='yellow',ms=3)
 axes[0].text(sum(x for x,y in section['outline'])/len(section['outline']),sum(y for x,y in section['outline'])/len(section['outline']),section['name'],fontsize=7,color='yellow',ha='center')
axes[0].set_title('Actual mesh contour / source landmarks')
for ax,name,title in [(axes[1],'input','Frozen prior geometry'),(axes[2],'modified','Six closed source-fitted rock lobes')]:
 image=Image.open(P/name/'textured.png');ax.imshow(image.crop((0,0,image.width//4,image.height//2)));ax.set_title(title);ax.axis('off')
fig.tight_layout();fig.savefig(P/'inspection/source-comparison.png',dpi=150);plt.close(fig)
report={'asset_id':r['asset_id'],'native_mask':501,'mesh_sha256':hashlib.sha256((P/'model.blend').read_bytes()).hexdigest(),'source_sha256':hashlib.sha256((W/'source-states/covered.png').read_bytes()).hexdigest(),'native_mask_sha256':hashlib.sha256((W/'mask-review/inventory-v6/000501.png').read_bytes()).hexdigest(),'measurement_note':'Pixel raster diagnostic of saved recipe world vertices; simplified contour tolerance is 1.8 source pixels. This is a silhouette construction check, not independent evidence of hidden depth.','native_pixels':int(target.sum()),'actual_projection_pixels':int(actual.sum()),'native_pixels_covered':int((target&actual).sum()),'missing_native_pixels':int(missing.sum()),'outside_native_pixels':int(outside.sum()),'limitations':['Source501 includes irregular integrated vegetation; rock geometry follows the main stone boundary rather than every leaf.','Concealed rear volume and inter-lobe depth are inferred.']};(P/'inspection/actual-mesh-source-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
