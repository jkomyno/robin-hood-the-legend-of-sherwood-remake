"""Correct closed mission-prop winding while preserving surfaces and corner UVs."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import bpy,bmesh
sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def surface(obj):
    return sorted((tuple(round(x,6) for x in v.co) for v in obj.data.vertices))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True,type=Path);p.add_argument('--tooling-dir',required=True,type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);from render_slots import acquire
    acquire();tooling=select_tooling(a.tooling_dir);from refinement_workspace import modified
    w=a.workspace.resolve();archive=w/'normal-correction-reference'/sha(w/'model.blend')[:12];archive.mkdir(parents=True,exist_ok=False)
    for name in ['model.blend','candidate.json','review.md','geometry-recipe.json']:
        if (w/name).is_file():shutil.copy2(w/name,archive/name)
    shutil.copytree(w/'modified',archive/'modified')
    bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.window.scene=bpy.data.scenes['nottingham Refinement']
    records=[]
    for obj in bpy.data.collections['nottingham Working'].all_objects:
        if obj.type!='MESH' or obj.get('source_node') not in ['building-551','building-552','building-553','building-554']:continue
        before=surface(obj);normals=[list(f.normal) for f in obj.data.polygons]
        bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free();obj.data.update()
        if before!=surface(obj):raise ValueError('Prop vertex positions changed')
        records.append({'source_node':obj['source_node'],'vertices_preserved':len(before),'normal_before':normals,'normal_after':[list(f.normal) for f in obj.data.polygons]})
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'))
    validation=modified(w)
    record={'status':'PASS','geometry_positions_preserved':True,'records':records,'validation':validation,'tooling':tooling,'archive':str(archive),
            'model_sha256':sha(w/'model.blend'),'modified_views_sha256':sha(w/'modified/views.json'),'recipe_sha256':sha(__file__)}
    (w/'normal-correction.json').write_text(json.dumps(record,indent=2)+'\n');print('PASS outward prop normals and regenerated source projection')

if __name__=='__main__':main()
