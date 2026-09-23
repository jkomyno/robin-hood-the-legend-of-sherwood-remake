"""Record polygon-interior unfilled texels during an unchanged shared texture bake."""
import inspect,json,sys
from pathlib import Path
import numpy as np
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve()
sys.path.insert(0,str(HERE.parents[2]/'refinement/blender'))
import project_reviewed_texture as projector
from bake_reviewed_asset import stage
original_bake=projector.bake
records=[]
def diagnostic_bake(*args,**kwargs):
 sampler=kwargs['hidden_sampler']
 def instrumented(obj,normal,positions,accepted,colors):
  # The sampler is called once per source atlas face by the shared baker.
  frame=inspect.currentframe().f_back
  assert frame.f_code.co_name=='bake'
  inside=frame.f_locals['best']>=0
  before=colors.copy()
  sampler(obj,normal,positions,accepted,colors)
  remaining=~accepted & np.all(colors[:,:3]==before[:,:3],axis=1)
  interior=remaining & inside
  if interior.any():
   fid=frame.f_locals['fid'];face=obj.data.polygons[fid]
   points=[list(obj.matrix_world@obj.data.vertices[i].co) for i in face.vertices]
   closure=inspect.getclosurevars(sampler).nonlocals
   candidates=closure['cameras'];tree=closure['tree'];mask=closure['mask'];height=closure['height']
   sample_indices=np.flatnonzero(interior);sample_indices=sample_indices[np.linspace(0,len(sample_indices)-1,min(32,len(sample_indices))).astype(int)]
   reasons={'no_camera_facing':0,'occluded_in_all_facing_views':0,'visible_but_mask_protected':0,'visible_editable':0}
   for index in sample_indices:
    point=Vector(positions[index]);facing=False;visible=False;editable=False
    for view,inverse,direction in candidates:
     if normal.dot(direction)<=.12:continue
     facing=True
     hit,_,_,_=tree.ray_cast(point+direction*100000,-direction)
     if hit is None or (hit-point).length>.02:continue
     visible=True;local=inverse@point;crop=view['crop'];scale=view['ortho_scale']
     x=int(np.floor(crop['left']+(.5+local.x/(scale*crop['width']/crop['height']))*crop['width']))
     y=int(np.floor(height-crop['top']-(.5-local.y/scale)*crop['height']))
     if crop['left']<=x<crop['left']+crop['width'] and height-crop['top']-crop['height']<=y<height-crop['top'] and mask[y,x,3]<.5:editable=True
    reasons['visible_editable' if editable else 'visible_but_mask_protected' if visible else 'occluded_in_all_facing_views' if facing else 'no_camera_facing']+=1
   records.append(dict(sampled_unfilled_camera_reasons=reasons,object=obj.name,source_node=obj.get('source_node'),face=fid,normal=list(normal),world_vertices=points,unfilled_polygon_texels=int(interior.sum()),polygon_texels=int(inside.sum()),unfilled_padding_texels=int((remaining&~inside).sum()),direction='downward' if normal.z<-.5 else 'side-or-upward'))
 kwargs['hidden_sampler']=instrumented
 return original_bake(*args,**kwargs)
projector.bake=diagnostic_bake
experiment=Path(sys.argv[sys.argv.index('--')+1]).resolve()
output=experiment/(sys.argv[sys.argv.index('--')+2] if len(sys.argv)>sys.argv.index('--')+2 else 'bake-preserved-wave2-v2')
report=stage(experiment/'views.json',experiment/'generation-short-no-mask-with-lighting/generated-preserved.png',output,texels_per_unit=2,reconciliation_reference=experiment/'generation-short-no-mask-with-lighting/generated-raw.png')
result=dict(asset_id=report['asset_id'],method='Unchanged shared sampler; polygon-interior samples selected from source baker barycentric inside mask. Unchanged neutral RGB classifies unfilled samples; generated wood/straw colors are chromatic.',faces=records,unfilled_polygon_texels=sum(r['unfilled_polygon_texels'] for r in records),downward_unfilled_polygon_texels=sum(r['unfilled_polygon_texels'] for r in records if r['direction']=='downward'),geometry_verified=report['geometry_verified'])
(output/'surface-coverage.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='faces'}))
