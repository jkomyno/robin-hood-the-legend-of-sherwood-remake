"""Stage, freeze and regenerate the measured southern gate review workspace."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).resolve().parent))
from render_slots import acquire
from freeze_tooling import select_tooling

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['stage','prepare','modify']);parser.add_argument('--tooling',type=Path,required=True);parser.add_argument('--source',type=Path);parser.add_argument('--catalog',type=Path);parser.add_argument('--inventory',type=Path);parser.add_argument('--review',type=Path);parser.add_argument('--workspace',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);acquire(slots=2);tooling=select_tooling(args.tooling)
    import bpy
    from refinement_workspace import prepare,modified,validate
    from refine_south_gate_arch import refine,AUDIT
    workspace=args.workspace.resolve();AUDIT.mkdir(parents=True,exist_ok=True)
    if args.operation=='stage':
        if not args.source or not args.source.exists():raise ValueError('Reviewed grouped source required')
        geometry={};sources=[]
        for asset,nodes in [('nottingham-south-gate-arch',[213,214]),('nottingham-south-curtain-wall',[205])]:
            path=WORK/'round-1/assets'/asset/'model.blend';bpy.ops.wm.open_mainfile(filepath=str(path));sources.append(dict(path=str(path),sha256=sha(path)))
            for obj in bpy.data.collections['nottingham Working'].all_objects:
                if obj.type=='MESH'and obj.get('source_node')in[f'building-{n:03}'for n in nodes]:
                    geometry[obj['source_node']]=dict(vertices=[list(v.co)for v in obj.data.vertices],faces=[list(p.vertices)for p in obj.data.polygons],matrix=[list(row)for row in obj.matrix_world])
        assert set(geometry)=={'building-205','building-213','building-214'}
        bpy.ops.wm.open_mainfile(filepath=str(args.source));bpy.context.view_layer.update()
        for obj in bpy.data.collections['nottingham Working'].all_objects:
            node=obj.get('source_node')
            if obj.type!='MESH'or node not in geometry:continue
            if obj.get('asset_group')!='nottingham-south-gate-arch':raise ValueError('Catalog transfer205 not installed')
            data=geometry[node]
            if max(abs(a-b)for row,target in zip(obj.matrix_world,data['matrix'])for a,b in zip(row,target))>1e-5:raise ValueError('Inherited transform mismatch')
            mesh=bpy.data.meshes.new(obj.name+' / prior reviewed shape');mesh.from_pydata(data['vertices'],[],data['faces']);mesh.update();mesh.uv_layers.new(name='UVMap')
            for mat in obj.data.materials:mesh.materials.append(mat)
            obj.data=mesh
        target=AUDIT/'staged-v8-before.blend'
        if target.exists():raise FileExistsError(target)
        bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(target))
        (AUDIT/'staged-source.json').write_text(json.dumps(dict(grouped_source=str(args.source),grouped_sha256=sha(args.source),imports=sources,staged_sha256=sha(target),note='Geometry-only staging preserves the current measured arch aperture and prior rear crown; source is freshly projected before freezing input.'),indent=2)+'\n')
        return
    if args.operation=='prepare':
        if workspace.exists():raise FileExistsError(workspace)
        bpy.ops.wm.open_mainfile(filepath=str(args.source))
        prepare(workspace,asset_id='nottingham-south-gate-arch',scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=WORK/'source-states/covered.png',grouping_manifest=args.catalog,inventory_path=args.inventory,review_path=args.review,source_mask_manifest=WORK/'mask-review/source-masks-v11-baseline.json',width=384,height=384,elevation_degrees=35,context_padding=32)
        (workspace/'tooling.json').write_text(json.dumps(tooling,indent=2)+'\n');validate(workspace);return
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'));bpy.context.view_layer.update()
    def shapes():
        return {o.name:sha_mesh(o)for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'}
    before=shapes();report=refine();once=shapes();refine();assert shapes()==once
    report['idempotent']=True;report['changed_objects']=[n for n in before if before[n]!=once[n]];report['tooling']=tooling
    # Native129 is a composite gate envelope, never standalone ownership.
    # The measured crown and exact first-hit scene depth restrict the receiver.
    # Adjacent tower silhouettes overlap painted foreground parapet pixels, so
    # subtracting them wholesale would clip valid cap artwork.
    mask_path=workspace/'source-masks.json';mask=json.loads(mask_path.read_text());rows=mask['projections']['exterior']['assignments'];old=next(a for a in rows if a['source_node']=='building-205')
    rows[rows.index(old)]=dict(reviewed=True,source_node='building-205',mask_indices=[129],constraint_kind='reviewed-native-silhouette',review_evidence=str((AUDIT/'205-numbered-source.png').resolve()),review_note='Rear gate crown only, within composite native gate129; numbered artwork corners bind the measured run and exact source-camera first-hit receiver is mandatory. Native tower masks130/131 overlap painted foreground cap pixels and are not subtracted indiscriminately.')
    mask_path.write_text(json.dumps(mask,indent=2)+'\n')
    report['recipe_sha256']=sha(ROOT/'level-editor/blender/nottingham/refine_south_gate_arch.py');(workspace/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    result=modified(workspace);(workspace/'regeneration.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SOUTH GATE ARCH MODIFIED',json.dumps(result))

def sha_mesh(obj):
    return hashlib.sha256(json.dumps(dict(vertices=[list(v.co)for v in obj.data.vertices],faces=[list(p.vertices)for p in obj.data.polygons],matrix=[list(row)for row in obj.matrix_world]),sort_keys=True).encode()).hexdigest()
if __name__=='__main__':main()
