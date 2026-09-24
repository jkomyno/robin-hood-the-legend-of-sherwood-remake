"""Save explicit hall display-state scenes for lighting and later state export."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from v15_hall_packet import OUT,ASSET,sha,write
import bpy
records=[]
state_dir=Path(json.loads((OUT/'state-packet.json').read_text())['directory'])
for state in json.loads((state_dir/'states.json').read_text())['states']:
 bpy.ops.wm.open_mainfile(filepath=str(OUT/'model.blend'))
 objects=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==ASSET]
 names=set(state['object_names']);assert names<={o.name for o in objects}
 for o in objects:o.hide_render=o.name not in names
 destination=OUT/'inspection/state-models'/state['state']/'model.blend';destination.parent.mkdir(parents=True,exist_ok=True)
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(destination))
 records.append({'state':state['state'],'model':str(destination),'model_sha256':sha(destination),'frame_manifest':str(Path(state['path'])/'views.json'),'frame_manifest_sha256':sha(Path(state['path'])/'views.json'),'object_names':sorted(names)})
write(OUT/'inspection/state-models/manifest.json',{'version':1,'primary_model_sha256':sha(OUT/'model.blend'),'states':records,'scope':'Only authored covered/revealed display visibility; material data and geometry remain unchanged.'})
