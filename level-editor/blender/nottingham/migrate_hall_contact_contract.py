"""Bind preserved hall appearances to their complete-state review contract."""
import hashlib
import json
import sys
from pathlib import Path
import bpy

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def write(p,d): Path(p).write_text(json.dumps(d,indent=2)+'\n')

def normalize_sources(p):
    config=read(p/'workspace.json');authority=read(config['projection_manifest'])
    directory=Path(config['projection_manifest']).parent
    sources={key:str((directory/authority['sources'][key]).resolve()) for key in ('exterior','interior')}
    binding=read(p/'inspection/state-models/manifest.json')
    files=[p/'modified/views.json',p/'projection-state-layers.json']
    files += [Path(s['frame_manifest']) for s in binding['states']]
    files += [p/'inspection/state-models'/s/'modified/views.json' for s in ('covered','revealed')]
    old=sha(p/'modified/views.json')
    for file in files:
        data=read(file)
        rows=[r for values in data.values() for r in values] if file.name=='projection-state-layers.json' else data['projection_layers']
        for row in rows:
            source=sources['exterior' if row['projection_label']=='exterior' else 'interior']
            assert sha(row['source_path'])==sha(source)
            row['source_path']=source
        if 'source_image' in data:
            source=next(v for v in sources.values() if sha(v)==data['source_sha256'])
            assert sha(data['source_image'])==sha(source);data['source_image']=source
        write(file,data)
    for state in binding['states']:state['frame_manifest_sha256']=sha(state['frame_manifest'])
    write(p/'inspection/state-models/manifest.json',binding)
    new=sha(p/'modified/views.json')
    for name in ('known-rgb-validation.json','geometry-report.json','inspection/hall-state-independent-review.json'):
        report=read(p/name);assert report['modified_views_sha256']==old;report['modified_views_sha256']=new
        if name=='inspection/hall-state-independent-review.json':report['known_source_rgb']['modified_views_sha256']=new
        write(p/name,report)
    proof=read(p/'inspection/complete-state-contract-migration.json')
    assert all(sha(p/f)==h for f,h in proof['protected_models_and_pngs'].items())
    proof['new_frame_sha256']=new;proof['only_frame_semantic_change']='Removed redundant covered selector; replaced source paths with exact byte-identical candidate-local frozen artwork.'
    write(p/'inspection/complete-state-contract-migration.json',proof)
    for filename,key in [('inspection/stored-materials/audit.json','frame_manifest_sha256'),('source-coverage-audit.json','modified_views_sha256')]:
        path=p/filename
        if path.exists():
            report=read(path);assert report[key] in (proof['old_frame_sha256'],old,new)
            report[key]=new;write(path,report)
    origin=Path(__file__).resolve().parents[3]/'level-editor/work/nottingham-refinement/round-42/assets/nottingham-castle-main-hall/inspection/state-models/manifest.json'
    supplement=read(p/'contact-state-supplement.json')
    supplement['original_state_manifest']=dict(path=str(origin),sha256=sha(origin))
    write(p/'contact-state-supplement.json',supplement)
    print('FINAL_MIGRATED_FRAME',new)

def main(p):
    config=read(p/'workspace.json'); binding=read(p/'inspection/state-models/manifest.json')
    manifest=read(config['projection_manifest'])
    visibility=manifest['projection_reviews']['patch-008']['render_visibility']
    protected={str(f.relative_to(p)):sha(f) for f in p.rglob('*') if f.is_file() and f.suffix in ('.png','.blend')}
    records={};layers={};proofs={}
    for state in binding['states']:
        label=state['state'];model=Path(state['model'])
        assert sha(model)==state['model_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(model))
        for o in bpy.data.objects:
            if o.type!='MESH' or o.get('asset_group')!=config['asset_id']:continue
            # Superseded canonical meshes are absent from both reviewed appearances.
            if o.name not in set().union(*(set(s['object_names']) for s in binding['states'])):continue
            row=records.setdefault(o.name,dict(object=o.name,source_node=o.get('source_node'),projection_component=o.get('projection_component')))
            row[label+'_face_materials']={str(f.index):dict(slot=f.material_index,material=o.data.materials[f.material_index].name) for f in o.data.polygons}
        packet=read(state['frame_manifest'])
        layers[label]=[{k:v for k,v in row.items() if k!='source_sha256'} for row in packet['projection_layers']]
        state['hidden_context_nodes']=sorted(set(visibility[label].get('hidden_nodes',[]))-set(config['part_ids']))
        proof=Path(state['preservation_report']);assert read(proof)['status']=='PASS'
        proofs[label]=dict(path=str(proof),sha256=sha(proof),model_sha256=state['model_sha256'])
    materials=dict(version=1,model_sha256=sha(p/'model.blend'),records=sorted(records.values(),key=lambda r:r['object']))
    write(p/'material-states.json',materials);write(p/'projection-state-layers.json',layers)
    binding['material_states_sha256']=sha(p/'material-states.json');write(p/'inspection/state-models/manifest.json',binding)
    cap=p/'inspection/contact-material-provenance.json';assert read(cap)['all_source_pixels']==407
    write(p/'contact-state-supplement.json',dict(version=1,model_sha256=sha(p/'model.blend'),source_node='building-505',component='castle-hall-northwest-contact',patch_id='patch-008',cap_proof=dict(path=str(cap),sha256=sha(cap)),states=proofs))
    frame=p/'modified/views.json';before=frame.read_bytes();packet=read(frame)
    expected=[dict(r,source_sha256=sha(r['source_path'])) for r in layers['covered']]
    actual=packet['projection_layers'];assert len(actual)==1
    selector=actual[0].pop('receiver_components',None)
    assert selector==[dict(source_node='building-505',projection_components=['castle-hall-retained-roof','castle-hall-removable-cover','castle-hall-northwest-contact'],patch_id='patch-008')]
    assert actual==expected
    history=p/'history/before-complete-state-contract';history.mkdir(exist_ok=False)
    (history/'views.json').write_bytes(before);old=hashlib.sha256(before).hexdigest();write(frame,packet);new=sha(frame)
    for name in ('known-rgb-validation.json','geometry-report.json','inspection/hall-state-independent-review.json'):
        report=read(p/name);assert report['modified_views_sha256']==old
        report['modified_views_sha256']=new
        if name=='inspection/hall-state-independent-review.json':report['known_source_rgb']['modified_views_sha256']=new
        write(p/name,report)
    assert all(sha(p/f)==h for f,h in protected.items())
    write(p/'inspection/complete-state-contract-migration.json',dict(status='PASS',model_sha256=sha(p/'model.blend'),old_frame_sha256=old,new_frame_sha256=new,only_frame_semantic_change='Removed redundant complete covered receiver selector.',protected_models_and_pngs=protected))
    normalize_sources(p)
if __name__=='__main__':
    p=Path(sys.argv[sys.argv.index('--')+1]).resolve()
    normalize_sources(p) if '--normalize-sources' in sys.argv else main(p)
