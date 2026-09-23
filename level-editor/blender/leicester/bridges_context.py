"""Freeze a bridge context containing only source-verified tower doorway cuts."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'refinement/blender'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from refinement_workspace import _geometry
import towers
import towers_doorway
ROOT=Path('level-editor/work/leicester-refinement').resolve()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def prepare_context():
 source=ROOT/'round-1/grouped-v2/leicester.blend';output=ROOT/'round-1/bridge-context';target=output/'doorway.blend'
 if target.exists():
  record=json.loads((output/'provenance.json').read_text())
  if sha(target)!=record['output_sha256']:raise ValueError('Frozen bridge context changed')
  if any(sha(path)!=digest for path,digest in record['dependencies'].items()):raise ValueError('Doorway dependency changed; create a new reviewed context revision')
  return target
 evidence=ROOT/'round-1/north-inspection/east-tower-doorway.json'
 diagnostic=ROOT/'bridge-evidence/tower-doorway-diagnostic'
 owners=json.loads((diagnostic/'ray-owners.json').read_text())
 if sum(owners.values())!=1904 or any('component 387' not in name for name in owners):raise ValueError('Doorway pixel-ownership diagnostic must pass first')
 output.mkdir(exist_ok=False);(output/'inspection').mkdir()
 bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.window.scene=bpy.data.scenes['Leicester Refinement'];bpy.context.view_layer.update()
 collection=bpy.data.collections['Leicester Working'];targets=[o for o in collection.all_objects if o.type=='MESH' and o.get('source_node') in ['building-162','building-163']]
 if len(targets)!=2:raise ValueError('Expected exactly two doorway wall components')
 protected={o.name:_geometry(o) for o in bpy.context.scene.objects if o not in targets}
 original_matrices={o.name:[list(row) for row in o.matrix_world] for o in targets}
 for obj in targets:
  vertices,faces=towers.horizontal_shell(obj);towers.write_mesh(obj,vertices,faces,obj.name+' verified doorway shell')
  towers_doorway.cut_east_doorway(obj,output)
 bpy.context.view_layer.update()
 if protected!={o.name:_geometry(o) for o in bpy.context.scene.objects if o not in targets}:raise ValueError('Context recipe changed another object')
 if original_matrices!={o.name:[list(row) for row in o.matrix_world] for o in targets}:raise ValueError('Doorway transform drift')
 bpy.ops.wm.save_as_mainfile(filepath=str(target))
 originals=[evidence,Path(towers.__file__),Path(towers_doorway.__file__),diagnostic/'ray-owners.json',diagnostic/'ray-samples.json',Path(__file__)]
 snapshots=output/'provenance-sources';snapshots.mkdir()
 for path in originals:shutil.copy2(path,snapshots/path.name)
 deps=[source,*snapshots.iterdir()]
 record={'source':str(source),'output':str(target),'output_sha256':sha(target),'dependencies':{str(p):sha(p) for p in deps},
  'original_dependency_paths':{str(p):sha(p) for p in originals},
  'recipe_sha256':sha(__file__),'modified_source_nodes':['building-162','building-163'],'protected_object_count':len(protected),'outside_geometry_unchanged':True,
  'doorway_source_rays':{'accepted':1904,'total':1904},'status':'Immutable projection context; full tower refinement and owner geometry approval remain separate'}
 (output/'provenance.json').write_text(json.dumps(record,indent=2)+'\n');target.chmod(0o444)
 return target
def prepare_canopy_context():
 source=prepare_context();output=ROOT/'round-1/bridge-context-canopy-v2';target=output/'canopy.blend'
 if target.exists():
  record=json.loads((output/'provenance.json').read_text())
  if sha(target)!=record['output_sha256']:raise ValueError('Frozen canopy context changed')
  if any(sha(path)!=digest for path,digest in record['dependencies'].items()):raise ValueError('Frozen canopy dependency changed')
  return target
 import towers_canopy
 diagnostic=ROOT/'bridge-evidence/east-hardware-canopy-ray-audit.json'
 evidence=ROOT/'round-1/north-inspection/node221-source-overlay.png'
 if not diagnostic.is_file() or not evidence.is_file():raise ValueError('Canopy source and ray evidence required')
 output.mkdir(exist_ok=False);(output/'inspection').mkdir()
 bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.window.scene=bpy.data.scenes['Leicester Refinement']
 collection=bpy.data.collections['Leicester Working'];obj=next(o for o in collection.all_objects if o.get('source_node')=='building-221')
 protected={o.name:_geometry(o) for o in bpy.context.scene.objects if o!=obj};matrix=[list(row) for row in obj.matrix_world]
 report=towers_canopy.refine(obj);bpy.context.view_layer.update()
 if protected!={o.name:_geometry(o) for o in bpy.context.scene.objects if o!=obj}:raise ValueError('Canopy context changed another object')
 if matrix!=[list(row) for row in obj.matrix_world]:raise ValueError('Canopy transform drift')
 (output/'inspection/canopy221.json').write_text(json.dumps(report,indent=2)+'\n')
 bpy.ops.wm.save_as_mainfile(filepath=str(target))
 originals=[Path(towers_canopy.__file__),Path(__file__),diagnostic,evidence];snapshots=output/'provenance-sources';snapshots.mkdir()
 for path in originals:shutil.copy2(path,snapshots/path.name)
 deps=[source,*snapshots.iterdir()]
 record={'source':str(source),'output':str(target),'output_sha256':sha(target),'dependencies':{str(p):sha(p) for p in deps},
         'original_dependency_paths':{str(p):sha(p) for p in originals},'modified_source_nodes':['building-221'],
         'inherited_context_nodes':['building-162','building-163'],'outside_geometry_unchanged':True,'protected_object_count':len(protected),
         'status':'Immutable source-supported projection context; three-unit underside thickness remains an explicit hypothesis.'}
 (output/'provenance.json').write_text(json.dumps(record,indent=2)+'\n');target.chmod(0o444)
 return target

if __name__=='__main__':print(prepare_canopy_context() if '--canopy' in sys.argv else prepare_context())
