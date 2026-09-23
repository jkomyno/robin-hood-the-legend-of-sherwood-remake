"""Reopen original and baked workers to verify persistent foliage preservation."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from foliage_texture_bake import physical_records, _geometry, _materials, sha


def state(path,asset):
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False)
    scene=bpy.context.scene
    objects=[o for o in scene.objects if o.type=='MESH' and o.get('asset_group')==asset and not o.hide_render]
    records=physical_records(objects)
    physical={(o.name,m.name):(bool(m.get('foliage_observed')),data) for o,_,m,_,data in records}
    uv={o.name:{l.name:[tuple(d.uv) for d in l.data] for l in o.data.uv_layers} for o in objects
        if any(m and m.get('foliage_physical_opacity') for m in o.data.materials)}
    return dict(geometry={o.name:_geometry(o) for o in scene.objects},uv=uv,physical=physical,
                outside={o.name:_materials(o) for o in scene.objects if o.type=='MESH' and o not in objects})


def run(experiment,bake):
    experiment=Path(experiment).resolve();bake=Path(bake).resolve()
    approval=json.loads((experiment/'approval.json').read_text());asset=approval['asset_id']
    assert sha(experiment/'approved-model.blend')==approval['saved_model_sha256']
    original=state(experiment/'approved-model.blend',asset);candidate=state(bake/'worker.blend',asset)
    for key in ('geometry','uv','outside'):assert original[key]==candidate[key],key
    assert original['physical'].keys()==candidate['physical'].keys()
    rows=[]
    for key,(known,before) in original['physical'].items():
        known_after,after=candidate['physical'][key]
        assert known==known_after and np.array_equal(before[:,:,3],after[:,:,3]),key
        if known:assert np.array_equal(before,after),key
        rows.append({'object':key[0],'material':key[1],'known':known,'alpha_identical':True,
                     'alpha_sha256':hashlib.sha256(before[:,:,3].tobytes()).hexdigest(),
                     'known_rgba_identical':True if known else None})
    report={'status':'PASS','approved_model_sha256':sha(experiment/'approved-model.blend'),
            'baked_model_sha256':sha(bake/'worker.blend'),'geometry_unchanged':True,'foliage_uv_unchanged':True,
            'outside_materials_unchanged':True,'physical_alpha_unchanged':True,'known_rgba_unchanged':True,'materials':rows}
    (bake/'reopened-preservation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('REOPENED FOLIAGE PRESERVATION PASS',asset,len(rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('experiment');parser.add_argument('bake')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);run(args.experiment,args.bake)
