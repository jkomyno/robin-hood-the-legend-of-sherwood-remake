import json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import matplotlib.pyplot as plt
W=Path('level-editor/work/nottingham-refinement');P=W/'round-10/assets/nottingham-northeast-round-tower';E=W/'fortifications-audit/north-user-revision';fit=json.loads((E/'tower-roof-fit.json').read_text());data=json.loads((P/'inspection/actual-roof-projection.json').read_text())
im=Image.new('1',(180,200));d=ImageDraw.Draw(im)
for ob in data.values():
 for f in ob['faces']:d.polygon([(ob['vertices'][i][0]-2060,ob['vertices'][i][1]-185)for i in f],fill=1)
a=np.asarray(im);ys=np.asarray(fit['source_y']);rows=a[ys-185];left=rows.argmax(axis=1)+2060;right=rows.shape[1]-1-rows[:,::-1].argmax(axis=1)+2060;error=(abs(left-np.array(fit['source_left']))+abs(right-np.array(fit['source_right'])))/2
fig,axs=plt.subplots(1,3,figsize=(12,8));source=Image.open(W/'source-states/covered.png');axs[0].imshow(source);axs[0].set_xlim(2064,2230);axs[0].set_ylim(365,184);axs[0].plot(fit['source_left'],ys,':',color='white',lw=.8,label='Native roof mask');axs[0].plot(fit['source_right'],ys,':',color='white',lw=.8);axs[0].plot(left,ys,color='cyan',lw=.8,label='Actual revised mesh');axs[0].plot(right,ys,color='cyan',lw=.8)
for i,(name,xy) in enumerate([('pole',(2147,194)),('small ball',(2147,224)),('large ball',(2147,239)),('cap',(2147,259))]):axs[0].annotate(f'{i+1}: {name}',xy,xytext=(2170,xy[1]),fontsize=8,color='yellow',arrowprops={'arrowstyle':'-','color':'yellow'})
axs[0].legend(loc='lower center',fontsize=7);axs[0].set_title(f'Actual mesh mean roof error {error.mean():.3f} px')
for ax,f,title in [(axs[1],P/'input/textured.png','Frozen prior geometry'),(axs[2],P/'modified/textured.png','Revised roof and finial')]:
 image=Image.open(f);ax.imshow(image.crop((0,0,image.width//4,image.height//2)));ax.set_title(title);ax.axis('off')
fig.tight_layout();fig.savefig(P/'inspection/user-revision-comparison.png',dpi=150);plt.close(fig)
r={'version':1,'model_sha256':hashlib.sha256((P/'model.blend').read_bytes()).hexdigest(),'native_mask':116,'source_y_range':[263,338],'actual_mesh_mean_outline_error_pixels':float(error.mean()),'maximum_side_error_pixels':int(max(abs(left-np.array(fit['source_left'])).max(),abs(right-np.array(fit['source_right'])).max())),'source_left':fit['source_left'],'source_right':fit['source_right'],'actual_left':left.tolist(),'actual_right':right.tolist(),'finial_landmarks':[[2147,194],[2147,224],[2147,239],[2147,259]],'limitations':['Axisymmetry and hidden roof contour inferred from visible native outline.','Metal finial depth inferred; its strong reverse-view cast shadow is confirmed by separate no-shadow diagnostic.']};(P/'inspection/actual-mesh-pixel-validation.json').write_text(json.dumps(r,indent=2)+'\n');print(r['actual_mesh_mean_outline_error_pixels'],r['maximum_side_error_pixels'])
