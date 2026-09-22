"""Regenerate prison candidates from immutable V11 packets and endpoint evidence."""
import argparse, copy, hashlib, json, shutil, sys
from pathlib import Path
import bpy
ROOT=Path.cwd()
BASE=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(ROOT/'level-editor/blender/nottingham'))
from freeze_tooling import select_tooling
select_tooling()
from render_slots import acquire
acquire()
import refine_prison
import refinement_workspace as rw
from asset_reference_views import render_states, state_objects
from render_animation_states import render_endpoints

def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def execute(workspace):
    workspace=workspace.resolve(); config=json.loads((workspace/'workspace.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
    upper=config['asset_id']=='nottingham-upper-prison'; patch='patch-002' if upper else 'patch-007'
    prefix='upper-prison-door' if upper else 'southwest-prison-door'
    doors=['building-453','building-455'] if upper else ['building-476','building-477']
    bpy.context.window.scene=bpy.data.scenes[config['scene_name']]
    (refine_prison.refine_upper if upper else refine_prison.refine)(workspace)
    path=Path(config['projection_manifest']); manifest=json.loads(path.read_text())
    review=json.loads((BASE/'prison-audit'/f"{config['asset_id']}-layers-final.json").read_text())['projection_reviews'][patch]
    manifest['projection_reviews'][patch]=review;write(path,manifest)
    maskpath=Path(config['source_mask_manifest']); masks=json.loads(maskpath.read_text())
    overrides=json.loads((BASE/'mask-review/component-state-overrides-v11.json').read_text())
    for label,entries in overrides['projections'].items():
        owned=[e for e in entries if e.get('source_node') in config['part_ids']]
        if not owned:continue
        replaced={e['source_node'] for e in owned}
        masks['projections'][label]['assignments']=[e for e in masks['projections'][label]['assignments'] if e.get('source_node') not in replaced]+owned
    if not upper:
        extra=json.loads((BASE/'mask-review/prison-466-overrides-v11.json').read_text())
        authority=masks['projections'][extra['projection']]
        if authority['source_sha256']!=extra['source_sha256']:raise ValueError('466 mask source drift')
        authority['assignments']=[e for e in authority['assignments'] if e.get('source_node')!='building-466']+extra['assignments']
    write(maskpath,masks)
    endpoint_dir=workspace/'door-reference';endpoint_dir.mkdir(exist_ok=True)
    sources={}; source_records={}
    for endpoint in ['initial','applied']:
        label=prefix+'-'+endpoint
        source=BASE/'state-review/owned-masks'/f'{label}-source.png'
        target=endpoint_dir/source.name
        expected=masks['projections'][label]['source_sha256']
        if sha(source)!=expected:raise ValueError('Endpoint source does not match frozen authority')
        if target.exists() and sha(target)!=expected:raise ValueError('Frozen endpoint evidence changed')
        if not target.exists():shutil.copy2(source,target)
        sources[label]=str(target);source_records[label]={'source':str(target),'sha256':expected}
    write(endpoint_dir/'manifest.json',source_records)
    # Endpoint labels use the same explicitly reviewed room cover components.
    # Preserve the pinned selector validation by resolving their owning room.
    import reveal_components
    original_filter=reveal_components.filter_occluders
    def endpoint_filter(objects, selectors=None, *, projection_label, available_objects=None):
        owner_label='interior-'+patch if projection_label in sources else projection_label
        return original_filter(objects,selectors,projection_label=owner_label,available_objects=available_objects)
    reveal_components.filter_occluders=endpoint_filter
    original_layers=rw._review_layers
    def layers(cfg):
        definitions=copy.deepcopy(original_layers(cfg))
        interior=next(d for d in definitions if d['projection_label']=='interior-'+patch)
        for definition in definitions:
            definition['receiver_nodes']=[n for n in definition['receiver_nodes'] if n not in doors]
            definition['occluder_nodes']=[n for n in definition['occluder_nodes'] if n not in doors]
        for label,node in zip(sources,doors):
            definitions.append({'source_path':sources[label],'receiver_nodes':[node],
                'occluder_nodes':sorted(set(interior['occluder_nodes'])|{node}),
                'exclude_occluder_components':interior.get('exclude_occluder_components',[]),
                'projection_label':label})
        return definitions
    def reproject(cfg,report_dir):
        from reproject_map import restore_projection,reproject_map
        from source_projection_bake import bake
        rw._validated_masks(cfg,rw._objects(cfg));rw._validated_projection(cfg)
        report_dir=Path(report_dir);report_dir.mkdir(parents=True,exist_ok=True)
        restore_projection(cfg['map_name']);reports=[]
        for definition in layers(cfg):
            receivers=sorted(set(definition['receiver_nodes'])&set(cfg['part_ids']))
            if not receivers:continue
            label=definition['projection_label']
            kwargs={k:definition[k] for k in ['occluder_nodes','projection_label','exclude_occluder_components','receiver_components'] if k in definition}
            reproject_map(cfg['map_name'],definition['source_path'],report_dir/(label+'.json'),receiver_nodes=receivers,elevation_deg=cfg['elevation_degrees'],**kwargs)
            reports.append(bake(cfg['map_name'],definition['source_path'],report_dir/(label+'-ownership.json'),receiver_nodes=receivers,elevation_deg=cfg['elevation_degrees'],preserve_authored=False,source_mask_manifest=cfg['source_mask_manifest'],projection_region=definition.get('projection_region'),**kwargs))
        report={'version':1,'asset_id':cfg['asset_id'],'ownership_bakes':reports,'door_sources':source_records,'recipe_sha256':sha(__file__)}
        write(report_dir/'layers-report.json',report);return report
    rw._review_layers=layers;rw._reproject=reproject
    result=rw.modified(workspace)
    inspection=workspace/'inspection';inspection.mkdir(exist_ok=True)
    state_target=inspection/'final-states'
    for name in ['final-states','final-doors']:
        previous=inspection/name
        if previous.exists():
            import uuid
            previous.rename(inspection/(name+'-history-'+uuid.uuid4().hex[:8]))
    render_states(workspace,state_target)
    objects=list(bpy.data.collections[config['collection_name']].all_objects)
    revealed=state_objects(objects,config['asset_id'],patch,review['render_visibility'],'revealed')
    definitions={};selections={}
    for label,node in zip(sources,doors):
        definitions[label]=[d for d in layers(config) if not d['projection_label'].startswith(prefix) or d['projection_label']==label]
        selections[label]=[o.name for o in revealed if o.get('source_node') not in doors]+[o.name for o in objects if o.type=='MESH' and o.get('source_node')==node]
    render_endpoints(workspace,inspection/'final-doors',definitions,selections,sources)
    write(workspace/'final-packet-run.json',dict(result,recipe_sha256=sha(__file__),status='awaiting-visual-inspection',door_sources=source_records))
    print('FINAL PRISON PACKET '+config['asset_id'],flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('workspace',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);execute(args.workspace)
