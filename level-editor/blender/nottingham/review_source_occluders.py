"""Prepare fresh source-visibility revisions without changing any map geometry."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def geometry(collection):
    return {o.name:{'node':o.get('source_node'),'group':o.get('asset_group'),'vertices':[list(v.co)for v in o.data.vertices],'faces':[list(f.vertices)for f in o.data.polygons],'matrix':[list(r)for r in o.matrix_world]}for o in collection.all_objects if o.type=='MESH'}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['tooling-dir','old-workspace','output','masks']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);from render_slots import acquire
    acquire();tooling=select_tooling(a.tooling_dir);from refinement_workspace import prepare,modified
    old=a.old_workspace.resolve();config=json.loads((old/'workspace.json').read_text());oldsha=sha(old/'model.blend')
    bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));before=geometry(bpy.data.collections[config['collection_name']])
    prepared=prepare(a.output,asset_id=config['asset_id'],scene_name=config['scene_name'],collection_name=config['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=a.masks,width=config['width'],height=config['height'],context_padding=config['context_padding'],framing_padding=config.get('framing_padding',1.04))
    validation=modified(a.output)
    if before!=geometry(bpy.data.collections[config['collection_name']]):raise ValueError('Geometry changed during source-visibility revision')
    if sha(old/'model.blend')!=oldsha:raise ValueError('Previous worker changed')
    first=json.loads((old/'input/views.json').read_text());fresh=json.loads((a.output/'input/views.json').read_text());same=all(x['camera_matrix_world']==y['camera_matrix_world'] and x['ortho_scale']==y['ortho_scale']for x,y in zip(first['views'],fresh['views']))
    report={'status':'PASS','geometry_preserved':True,'mesh_count':len(before),'geometry_sha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),'previous_workspace':str(old),'previous_model_sha256':oldsha,'model_sha256':sha(a.output/'model.blend'),'modified_views_sha256':sha(a.output/'modified/views.json'),'prior_input_cameras_identical':same,'tooling':tooling,'recipe_sha256':sha(__file__),'prepared':prepared,'validation':validation}
    (a.output/'source-visibility-correction.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',config['asset_id'],report['model_sha256'],flush=True)
if __name__=='__main__':main()
