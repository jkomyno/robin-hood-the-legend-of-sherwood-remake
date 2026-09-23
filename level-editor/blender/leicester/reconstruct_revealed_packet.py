"""Reproduce frozen tower state pixels before linking legacy ownership evidence."""
import hashlib
import json
from pathlib import Path
import sys
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'refinement/blender'))
from refinement_review import render_review


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reconstruct(manifest_path, asset_id, output):
    manifest_path, output = Path(manifest_path), Path(output)
    manifest = json.loads(manifest_path.read_text())
    item = next(i for i in manifest['items'] if i['id'] == asset_id)
    revision = item['revision']
    for evidence in revision['evidence'].values():
        if sha(evidence['path']) != evidence['sha256']:
            raise ValueError('Approved evidence changed: '+evidence['path'])
    workspace = Path(item['workspace'])
    model = workspace/'model.blend'
    if sha(model) != revision['model_sha256']:
        raise ValueError('Approved geometry changed')
    primary_path = Path(item['textured']).parent/'views.json'
    if not any(Path(e['path']).resolve() == primary_path.resolve() for e in revision['evidence'].values()):
        raise ValueError('Primary frame lacks direct approval binding')
    primary = json.loads(primary_path.read_text())
    state_dir = Path(item['revealed_textured']).parent
    state_path = state_dir/'views.json'
    state = json.loads(state_path.read_text())
    for key in ('asset_id','scene_name','collection_name','tile_size','elevation_degrees','lighting','projection_layers','source_mask_evidence'):
        if state.get(key) != primary.get(key):
            raise ValueError('State differs from approved primary contract: '+key)
    clean = lambda v:{k:x for k,x in v.items() if k not in ('counts','ownership_sha256')}
    if [clean(v) for v in state['views']] != [clean(v) for v in primary['views']]:
        raise ValueError('State camera or crop changed')
    matching=[]
    for entry in item['stored_material_states']:
        if 'revealed' not in entry['id']:
            continue
        audit=json.loads(Path(entry['audit']).read_text())
        if sorted(audit['render_object_names']) == sorted(state['render_object_names']):
            if not any(Path(e['path']).resolve() == Path(entry['audit']).resolve() for e in revision['evidence'].values()):
                raise ValueError('State audit lacks approval binding')
            matching.append(entry)
    if len(matching) != 1:
        raise ValueError('Expected one directly bound revealed visibility audit')
    bpy.ops.wm.open_mainfile(filepath=str(model))
    render_review(output/'reconstructed',scene_name=state['scene_name'],collection_name=state['collection_name'],
                  asset_id=asset_id,source_path=state['source_image'],frame_manifest=state,
                  projection_layers=state['projection_layers'],source_mask_manifest=state.get('source_mask_manifest'),
                  render_object_names=state['render_object_names'])
    files={}
    for name in ['solid.png','textured.png']+[f'views/view-{i}-known.png' for i in range(8)]:
        old,new=state_dir/name,output/'reconstructed'/name
        if sha(old) != sha(new):
            raise ValueError('Reconstructed state differs from reviewed pixels: '+name)
        files[name]=sha(new)
    report={'status':'PASS','asset_id':asset_id,'geometry_revision':revision['sha256'],
            'model_sha256':sha(model),'reviewed_state_manifest':str(state_path.resolve()),
            'reviewed_state_manifest_sha256':sha(state_path),'primary_manifest':str(primary_path.resolve()),'primary_manifest_sha256':sha(primary_path),
            'visibility_audit':str(Path(matching[0]['audit']).resolve()),'visibility_audit_sha256':sha(matching[0]['audit']),'state_id':matching[0]['id'],
            'source_rgb_preserved':True,'solid_pixels_preserved':True,'ownership_buffers_reproduced':True,
            'artifact_sha256':files,'reconstructed_directory':str((output/'reconstructed').resolve()),
            'helper_sha256':sha(__file__),'renderer_sha256':sha(Path(__file__).resolve().parents[2]/'refinement/blender/refinement_review.py'),'method':'Frozen approved geometry and approved camera/layer contracts reproduce exact reviewed source, solid and ownership pixels; visibility matches a directly bound state audit.'}
    (output/'reconstruction.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    return report


if __name__=='__main__':
    reconstruct(*sys.argv[sys.argv.index('--')+1:])
