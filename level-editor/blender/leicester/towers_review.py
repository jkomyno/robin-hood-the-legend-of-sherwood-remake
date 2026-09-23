"""Render a tower packet, paired display states, and their stored materials."""
import json
import hashlib
import sys
from pathlib import Path

HERE=Path(__file__).resolve()
sys.path.insert(0,str(HERE.parents[1]))
sys.path.insert(0,str(HERE.parents[2]/'refinement/blender'))
from refinement_workspace import modified,_review_layers
from refinement_review import render_review
from asset_reference_views import render_states
from audit_stored_materials import run as audit


def run(workspace):
    version=1
    while (workspace/f'inspection/states-v{version}').exists():version+=1
    modified(workspace)
    states=render_states(workspace,workspace/f'inspection/states-v{version}')
    if len(states['states'])>2:
        config=json.loads((workspace/'workspace.json').read_text())
        layer_path=Path(config['projection_manifest']);layers=json.loads(layer_path.read_text())
        native_states=list(states['states'])
        for state in ['covered','revealed']:
            matching=[s for s in native_states if s['state']==state]
            names=sorted(set.intersection(*(set(s['object_names']) for s in matching)))
            source=(layer_path.parent/layers['sources']['exterior' if state=='covered' else 'interior']).resolve()
            frame=json.loads((workspace/'input/views.json').read_text());frame['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
            target=workspace/f'inspection/states-v{version}/combined/{state}'
            render_review(target,scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id=config['asset_id'],source_path=source,frame_manifest=frame,
                          projection_layers=_review_layers(config),source_mask_manifest=config.get('source_mask_manifest'),render_object_names=names,
                          allow_projection_revision=True,allow_mask_revision=True)
            states['states'].append(dict(patch_id='combined',state=state,path=str(target),object_names=names,evidence='Intersection of explicit native patch display selections; both independent tower transitions applied together.'))
        (workspace/f'inspection/states-v{version}/states.json').write_text(json.dumps(states,indent=2)+'\n')
    reports=[]
    for state in states['states']:
        target=workspace/f'inspection/stored-material-{state["patch_id"]}-{state["state"]}-v{version}'
        report=audit(workspace,target,render=True,export=True,
                     render_object_names=state['object_names'],frame_manifest=workspace/'input/views.json')
        reports.append(dict(path=str(target),status=report['status'],problems=report['problems']))
    print(json.dumps(dict(workspace=str(workspace),state_version=version,material_audits=reports),indent=2))


if __name__=='__main__':run(Path(sys.argv[sys.argv.index('--')+1]).resolve())
