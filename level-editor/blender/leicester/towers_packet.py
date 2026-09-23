import sys,json,bpy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from refinement_workspace import modified
from asset_reference_views import render_states
p=Path(sys.argv[sys.argv.index('--')+1]).resolve()
for obj in bpy.data.objects:
 if obj.get('projection_component')=='tower-cover':obj['reveal_component_role']='removable-cover'
version=1
while (p/f'inspection/states-v{version}').exists():version+=1
print(json.dumps(modified(p),indent=2));print(json.dumps(render_states(p,p/f'inspection/states-v{version}'),indent=2))
