"""Render individual keep patch states plus the combined covered/revealed keep."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from asset_reference_views import render_states,state_objects
from refinement_workspace import _review_layers,_validated_projection,_validated_masks
from refinement_review import render_review


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace',type=Path)
    parser.add_argument('--output',default='inspection/states-final')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);workspace=args.workspace.resolve()
    output=workspace/args.output
    individual=render_states(workspace,output)
    config=json.loads((workspace/'workspace.json').read_text());manifest=_validated_projection(config)
    masks=_validated_masks(config);base=Path(config['projection_manifest']).parent
    objects=list(bpy.data.collections[config['collection_name']].all_objects)
    frame=json.loads((workspace/'input/views.json').read_text());definitions=_review_layers(config)
    patches=sorted({record['patch_id'] for record in individual['states']})
    records=[]
    for state,key in [('covered','exterior'),('revealed','interior')]:
        selected=None
        for patch in patches:
            current=set(state_objects(objects,config['asset_id'],patch,manifest['projection_reviews'][patch]['render_visibility'],state))
            selected=current if selected is None else selected&current
        source=(base/manifest['sources'][key]).resolve(strict=True)
        framing=copy.deepcopy(frame);framing['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
        result=render_review(output/'combined'/state,scene_name=config['scene_name'],collection_name=config['collection_name'],
            asset_id=config['asset_id'],source_path=source,frame_manifest=framing,
            projection_layers=definitions,source_mask_manifest=config.get('source_mask_manifest'),
            render_object_names=sorted(o.name for o in selected),allow_projection_revision=True,
            allow_mask_revision=bool(masks))
        records.append({'state':state,'path':str(output/'combined'/state),'objects':result['object_names']})
    (output/'combined-states.json').write_text(json.dumps({'patches':patches,'states':records},indent=2)+'\n')
    print(json.dumps({'output':str(output),'states':len(individual['states'])+len(records)},indent=2))

if __name__=='__main__':main()
