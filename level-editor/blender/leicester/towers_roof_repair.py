"""Rebuild the unequal-eave west roof sector without changing source ownership."""
import json,sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from towers import native_shell,write_mesh,roof_geometry,split_mesh,combine,diagnostics
workspace=Path(sys.argv[sys.argv.index('--')+1]).resolve()
config=json.loads((workspace/'workspace.json').read_text())
assert config['asset_id']=='leicester-west-moat-tower'
objects=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.get('asset_group')==config['asset_id'] and o.get('source_node')=='building-268']
probe=objects[0].copy();probe.data=objects[0].data.copy()
write_mesh(probe,*native_shell(probe),'native unequal-eave roof anchors')
world,faces=roof_geometry(probe)
bpy.data.objects.remove(probe)
back=split_mesh(world,faces,1,-1847,True);front=split_mesh(world,faces,1,-1847,False)
keep=combine(back,split_mesh(*front,2,456,True));cover=split_mesh(*front,2,456,False)
report=[]
for obj in objects:
 before=diagnostics(obj)
 piece=keep if obj['projection_component']=='tower-retained' else cover
 write_mesh(obj,*piece,obj.name+' unequal-eave shell')
 after=diagnostics(obj)
 assert after['faces'] and not after['nonmanifold_edges'] and not after['degenerate_faces'],after
 report.append(dict(object=obj.name,before=before,after=after))
(workspace/'inspection/unequal-eave-roof-repair.json').write_text(json.dumps(report,indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
