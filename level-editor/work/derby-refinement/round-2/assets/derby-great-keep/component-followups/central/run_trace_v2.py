import sys,json,math,hashlib
from pathlib import Path
W=Path(__file__).resolve().parent
ROOT=W.parents[7]
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages',str(ROOT/'level-editor/blender')]
import bpy,bmesh
from refinement_workspace import _geometry,_reproject
from refinement_review import render_review
from review_sunlight import DEFAULT_LIGHTING
from derby_round4_keep_central_trace import refine
nodes={f'building-{n:03}' for n in [*range(152,163),170,181]}
scene=bpy.data.scenes['Derby Refinement'];bpy.context.window.scene=scene
outside={o.name:_geometry(o) for o in scene.objects if o.get('source_node') not in nodes}
out=W/'trace-v2';out.mkdir(exist_ok=True)
report=refine()
assert outside=={o.name:_geometry(o) for o in scene.objects if o.get('source_node') not in nodes}
objects=[o for o in scene.objects if o.type=='MESH' and o.get('source_node') in nodes and not o.hide_render]
topology=[]
for o in objects:
 bm=bmesh.new();bm.from_mesh(o.data)
 topology.append({'name':o.name,'boundary':sum(e.is_boundary for e in bm.edges),'nonmanifold':sum(not e.is_manifold for e in bm.edges),'volume':bm.calc_volume(signed=True)})
 bm.free()
assert all(not r['boundary'] and not r['nonmanifold'] and r['volume']>0 for r in topology),topology
report['topology']=topology;report['outside_objects_unchanged']=len(outside)
projected=[]
for o in objects:
 if o.get('source_node') not in ['building-153','building-158']:continue
 vs=[o.matrix_world@v.co for v in o.data.vertices]
 projected.append({'node':o['source_node'],'vertices':[list(v) for v in vs], 'projected':[[v.x,-v.y*math.sin(math.radians(35))-v.z*math.cos(math.radians(35))] for v in vs], 'faces':[list(f.vertices) for f in o.data.polygons]})
(out/'projected-geometry.json').write_text(json.dumps(projected,indent=2))
(out/'validation.json').write_text(json.dumps(report,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
config=json.loads((W.parents[1]/'workspace.json').read_text());config['part_ids']=sorted(nodes);config['source_mask_manifest']=str(W/'source-masks.json')
_reproject(config,out/'projection')
baseline=W/'modified/views.json';data=json.loads(baseline.read_text())
layers=data['projection_layers']
for i,layer in enumerate(layers):layer['projection_label']='exterior' if i==0 else f'interior-patch-{i-1:03}'
groups={o:o.get('asset_group') for o in objects}
try:
 for o in objects:o['asset_group']='derby-keep-central-gallery'
 render_review(out/'modified',scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id='derby-keep-central-gallery',source_path=data['source_image'],projection_layers=layers,frame_manifest=baseline,width=512,height=640,source_mask_manifest=str(W/'source-masks.json'),lighting=DEFAULT_LIGHTING)
finally:
 for o,g in groups.items():o['asset_group']=g
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
