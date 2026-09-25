"""Compare prepared hall geometry with final and frozen approved geometry."""
import bpy,json,hashlib,pathlib,sys
p=pathlib.Path(sys.argv[sys.argv.index('--')+1]).resolve()
records={}
for file in ['baseline.blend','model.blend','../../../../round-42/assets/nottingham-castle-main-hall/model.blend']:
 bpy.ops.wm.open_mainfile(filepath=str(p/file))
 rows={}
 for o in bpy.data.objects:
  if o.type!='MESH' or o.get('asset_group')!='nottingham-castle-main-hall':continue
  d={'vertices':[list(v.co) for v in o.data.vertices],'faces':[list(f.vertices) for f in o.data.polygons],'matrix':[list(r) for r in o.matrix_world],'source_node':o.get('source_node'),'component':o.get('projection_component')}
  rows[o.name]=hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
 records[file]=rows
old,new=records['baseline.blend'],records['model.blend'];out={'baseline_sha256':hashlib.sha256((p/'baseline.blend').read_bytes()).hexdigest(),'model_sha256':hashlib.sha256((p/'model.blend').read_bytes()).hexdigest(),'added':sorted(set(new)-set(old)),'removed':sorted(set(old)-set(new)),'changed':sorted(n for n in old.keys()&new.keys() if old[n]!=new[n]),'signatures':records}
original=records['../../../../round-42/assets/nottingham-castle-main-hall/model.blend'];out['original42_sha256']=hashlib.sha256((p/'../../../../round-42/assets/nottingham-castle-main-hall/model.blend').read_bytes()).hexdigest();out['original42_added']=sorted(set(new)-set(original));out['original42_changed']=sorted(n for n in original.keys()&new.keys() if original[n]!=new[n]);
(p/'inspection/baseline-geometry-comparison.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='signatures'}))
