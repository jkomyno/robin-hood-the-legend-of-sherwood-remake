"""Close three retained east tower collision shells without changing anchors."""
import json,sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from towers import native_shell,write_mesh,split_mesh,diagnostics

workspace=Path(sys.argv[sys.argv.index('--')+1]).resolve()
config=json.loads((workspace/'workspace.json').read_text())
if config['asset_id']!='leicester-east-moat-tower':raise ValueError(config['asset_id'])
reports=[]
for obj in bpy.data.collections[config['collection_name']].all_objects:
 if obj.get('asset_group')!=config['asset_id'] or obj.get('source_node') not in ['building-165','building-166','building-182']:continue
 before=diagnostics(obj);verts,faces=native_shell(obj)
 if obj.get('projection_component') in ['tower-cover','tower-retained']:
  verts,faces=split_mesh(verts,faces,1,-1694,obj['projection_component']=='tower-retained')
 write_mesh(obj,verts,faces,obj.name+' closed native contour')
 after=diagnostics(obj)
 if after['nonmanifold_edges'] or after['degenerate_faces']:raise RuntimeError(str(after))
 reports.append(dict(object=obj.name,before=before,after=after))
(workspace/'inspection/wall-repairs.json').write_text(json.dumps(reports,indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
