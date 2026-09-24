"""Independently re-open a transferred worker and prove exact stored RGBA."""
from pathlib import Path
import hashlib
import json
import sys


def run(output):
    import bpy
    import numpy as np
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    sys.path.append(str(Path(__file__).resolve().parents[2]/'blender/nottingham'))
    from render_slots import acquire
    from transfer_shared_inferred import merge_inferred
    acquire()
    output=Path(output).resolve()
    validation=json.loads((output/'validation.json').read_text())
    transfer=validation['shared_inferred_transfer']
    canonical,target=map(Path,(transfer['canonical'],transfer['target']))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    for path,digest in transfer['inputs_sha256'].items():
        if sha(Path(path))!=digest:raise ValueError('Input drift: '+path)
    names={entry['object'] for entry in transfer['changed']}
    def read(model):
        bpy.ops.wm.open_mainfile(filepath=str(model))
        result={}
        for name in names:
            obj=bpy.data.objects[name]
            slots={p.material_index for p in obj.data.polygons}
            if len(slots)!=1:raise ValueError('Ambiguous transferred material')
            material=obj.data.materials[next(iter(slots))]
            images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
            if len(images)!=1:raise ValueError('Ambiguous transferred image')
            image=images[0]
            result[name]=np.asarray(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4)
        return result
    def masks(experiment):
        report_path=experiment/'bake-v1/validation.json'
        report=json.loads(report_path.read_text())
        entries=[e for l in report['layers'] for e in l['objects']]
        if not all(e.get('texel_provenance',{}).get('packed_image_sha256') for e in entries):
            report_path=experiment/'provenance-replay-v2/report.json'
            report=json.loads(report_path.read_text());entries=[e for l in report['layers'] for e in l['objects']]
        return {e['object']:np.load(e['texel_provenance']['path'])['ownership'] for e in entries if e['object'] in names}
    donor=read(canonical/'bake-v1/worker.blend');prior=read(target/'bake-v1/worker.blend')
    donor_masks,target_masks=masks(canonical),masks(target)
    saved=read(output/'worker.blend');records=[]
    for name in sorted(names):
        expected,count=merge_inferred(donor[name],prior[name],donor_masks[name],target_masks[name])
        if not np.array_equal(saved[name],expected):
            diff=np.abs(saved[name]-expected)
            raise ValueError(f'Saved RGBA mismatch {name}: {np.count_nonzero(diff)} channels; max {diff.max()}')
        records.append({'object':name,'exact_stored_rgba':True,'transferred_texels':count,'protected_source_texels':int((target_masks[name]==1).sum())})
    report={'status':'PASS','model_sha256':sha(output/'worker.blend'),'validation_sha256':sha(output/'validation.json'),'objects':records,'source_and_untouched_rgba_exact':True,'all_alpha_exact':True}
    (output/'saved-roundtrip-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':run(sys.argv[sys.argv.index('--')+1])
