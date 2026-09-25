"""Copy inferred atlas colors between strictly identical approved state surfaces.

Run in Blender: -- canonical-experiment target-experiment fresh-output.
All original state source texels and all input files remain untouched.
"""
from pathlib import Path
import hashlib
import json
import sys


def transferred_ownership(donor, target, *, allow_bounded_donors=False):
    import numpy as np
    if donor.shape!=target.shape or not np.isin(donor,[0,1,2,3]).all() or not np.isin(target,[0,1,2,3]).all():
        raise ValueError('Invalid transfer ownership buffers')
    selected=((donor==2)|(allow_bounded_donors & (donor==3)))&(target!=1)
    result=target.copy();result[selected]=donor[selected]
    return result,selected


def merge_inferred(canonical, target, donor_ownership, target_ownership, *, allow_bounded_donors=False):
    import numpy as np
    if canonical.shape != target.shape or canonical.shape[-1] != 4:
        raise ValueError('Atlas dimensions differ')
    if not np.isfinite(canonical).all() or not np.isfinite(target).all():
        raise ValueError('Nonfinite atlas pixels')
    for ownership in (donor_ownership,target_ownership):
        if ownership.shape != target.shape[:2] or not np.isin(ownership,[0,1,2,3]).all():
            raise ValueError('Invalid explicit texel provenance')
    _,selected=transferred_ownership(donor_ownership,target_ownership,allow_bounded_donors=allow_bounded_donors)
    result = target.copy()
    result[selected, :3] = canonical[selected, :3]
    assert np.array_equal(result[..., 3], target[..., 3])
    assert np.array_equal(result[~selected], target[~selected])
    return result, int(selected.sum())


def run(canonical, target, output, *, allow_bounded_donors=False):
    import bpy
    import numpy as np
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.append(str(Path(__file__).resolve().parents[2] / 'blender/nottingham'))
    from render_slots import acquire, release
    acquire()
    from refinement_workspace import _geometry
    from workspace_components import appearance_state
    from render_multiview_asset import render
    from refinement_review import _tile
    from array import array
    canonical, target, output = map(lambda p: Path(p).resolve(), (canonical, target, output))
    if output.exists():
        raise ValueError('Output must be new')
    manifests = [json.loads((p/'views.json').read_text()) for p in (canonical, target)]
    approvals = [json.loads((p/'approval.json').read_text()) for p in (canonical, target)]
    if manifests[0]['asset_id'] != manifests[1]['asset_id'] or approvals[0]['geometry_revision'] != approvals[1]['geometry_revision']:
        raise ValueError('States must share approved parent geometry identity')
    paths = [p/name for p in (canonical,target) for name in ('approved-model.blend','views.json','approval.json','bake-v1/worker.blend','bake-v1/validation.json')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    hashes = {str(p):sha(p) for p in paths}
    for experiment,approval,manifest in zip((canonical,target),approvals,manifests):
        if approval.get('status')!='approved' or approval.get('saved_model_sha256')!=sha(experiment/'approved-model.blend'):
            raise ValueError('Prepared model differs from approved geometry binding')
        validation=json.loads((experiment/'bake-v1/validation.json').read_text())
        if not validation.get('geometry_verified') or validation['asset_id']!=manifest['asset_id']:
            raise ValueError('Input bake lacks geometry validation')
    if allow_bounded_donors:
        from inferred_gap_repair import validate_policy
        donor_validation=json.loads((canonical/'bake-v1/validation.json').read_text())
        policy=donor_validation.get('inferred_gap_repair')
        if policy is None or policy!=manifests[0].get('texture_inferred_gap_repair'):
            raise ValueError('Bounded donor policy is missing or differs from frozen manifest')
        validate_policy(policy,manifests[0]['render_object_names'])
        audit_path=canonical/'bake-v1/saved-gap-audit.json'
        audit=json.loads(audit_path.read_text())
        if (audit.get('status')!='PASS' or audit.get('model_sha256')!=sha(canonical/'bake-v1/worker.blend') or
            audit.get('validation_sha256')!=sha(canonical/'bake-v1/validation.json') or
            audit.get('source_and_untouched_rgba_exact') is not True or audit.get('all_alpha_exact') is not True or
            not audit.get('objects') or not all(row.get('geometry_and_uv_exact') is True for row in audit['objects'])):
            raise ValueError('Bounded donor lacks exact saved source/alpha/geometry proof')
        hashes[str(audit_path)]=sha(audit_path)
    appearance_cache={};pixel_cache={}
    def load(path, manifest):
        appearance_cache.clear();pixel_cache.clear()
        bpy.ops.wm.open_mainfile(filepath=str(path))
        bpy.context.window.scene = bpy.data.scenes[manifest['scene_name']]
        bpy.context.view_layer.update()
        names = set(manifest['render_object_names'])
        return {o.name:o for o in bpy.context.scene.objects if o.name in names and o.type=='MESH' and o.get('asset_group')==manifest['asset_id']}
    def signature(obj, *, full_pixels=True):
        appearance = appearance_state(obj,appearance_cache)
        def image_hash(image):
            if not full_pixels and image.packed_file and not image.is_dirty:
                return 'packed:'+hashlib.sha256(image.packed_file.data).hexdigest()
            key=image.as_pointer()
            if key not in pixel_cache:
                pixel_cache[key]=hashlib.sha256(np.asarray(image.pixels[:],dtype=np.float32).tobytes()).hexdigest()
            return pixel_cache[key]
        # Include actual pixels, not merely packed-file bytes or image paths.
        appearance['image_pixels'] = [image_hash(n.image)
            for m in obj.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
        return (_geometry(obj), hashlib.sha256(json.dumps(appearance,sort_keys=True).encode()).hexdigest())
    def provenance(experiment, manifest):
        performed_replay=False
        validation=json.loads((experiment/'bake-v1/validation.json').read_text())
        entries=[entry for layer in validation['layers'] for entry in layer['objects']]
        if not all(entry.get('texel_provenance',{}).get('packed_image_sha256') for entry in entries):
            replay=experiment/'provenance-replay-v2'
            import fcntl
            with (experiment/'provenance-replay-v2.lock').open('a+') as replay_lock:
                try:
                    fcntl.flock(replay_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise ValueError('Canonical provenance replay is already running; retry after it finishes') from error
                if not (replay/'report.json').exists():
                    if replay.exists():
                        raise ValueError('Incomplete provenance replay exists; inspect before retrying')
                    from project_reviewed_texture import apply
                    load(experiment/'approved-model.blend',manifest)
                    apply(experiment/'views.json', validation['generated_image'], replay,
                          texels_per_unit=2,reconciliation_reference=validation.get('reconciliation_reference'))
                    performed_replay=True
            replay_report=json.loads((replay/'report.json').read_text())
            if replay_report['generated_sha256']!=validation['generated_sha256'] or replay_report['input_sha256']!=validation['input_sha256']:
                raise ValueError('Provenance replay input mismatch')
            entries=[entry for layer in replay_report['layers'] for entry in layer['objects']]
            hashes[str(replay/'report.json')]=sha(replay/'report.json')
        result={}
        for entry in entries:
            proof=entry['texel_provenance'];path=Path(proof['path'])
            if sha(path)!=proof['sha256']:raise ValueError('Provenance file changed')
            hashes[str(path)]=sha(path)
            result[entry['object']]=(proof,np.load(path)['ownership'])
        return result,performed_replay
    provenance_maps=[]
    for experiment,manifest in zip((canonical,target),manifests):
        print('Transfer: verifying provenance for '+str(experiment),flush=True)
        provenance_map,performed_replay=provenance(experiment,manifest)
        provenance_maps.append(provenance_map)
        if not performed_replay:
            continue
        # No Blender operation remains in flight here. Let queued assets run
        # between expensive state replays, then recheck all immutable inputs.
        release()
        import time
        time.sleep(1.1)
        acquire()
        if hashes!={p:sha(Path(p)) for p in hashes}:
            raise ValueError('Transfer input changed while yielding the render lease')
    if allow_bounded_donors:
        bounded_count=sum(int((mask==3).sum()) for _,mask in provenance_maps[0].values())
        if (not bounded_count or bounded_count!=donor_validation['counts'].get('extrapolated_texels_including_padding') or
            bounded_count!=sum(row.get('repaired_texels',0) for row in audit['objects'])):
            raise ValueError('Bounded donor provenance count differs from exact repair proof')
    original=[]
    for p,m in zip((canonical,target),manifests):
        original.append({name:signature(o) for name,o in load(p/'approved-model.blend',m).items()})
    common={name for name in original[0].keys() & original[1].keys() if original[0][name]==original[1][name]}
    def atlas(obj):
        slots={f.material_index for f in obj.data.polygons}
        if len(slots)!=1:return None
        material=obj.data.materials[next(iter(slots))]
        if not material or not material.get('generated_source_sha256') or material.get('source_ownership_alpha')!='one=observed,zero=inferred;material remains opaque':return None
        images=[n for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
        uvs=[n.uv_map for n in material.node_tree.nodes if n.type=='UVMAP']
        if len(images)!=1 or len(uvs)!=1:return None
        image=images[0].image
        layout=[list(obj.data.uv_layers[uvs[0]].data[i].uv) for f in obj.data.polygons for i in f.loop_indices]
        pixels=np.asarray(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4)
        return material,images[0],layout,pixels
    def verified_mask(name, data, mapping, obj):
        proof,mask=mapping[name]
        pixels=data[3]
        if hashlib.sha256(data[1].image.packed_file.data).hexdigest()!=proof['packed_image_sha256']:
            raise ValueError('Replay atlas differs from saved baked pixels: '+name)
        uv_name=next(n.uv_map for n in data[0].node_tree.nodes if n.type=='UVMAP')
        uv=[list(entry.uv) for entry in obj.data.uv_layers[uv_name].data]
        if hashlib.sha256(json.dumps(uv).encode()).hexdigest()!=proof['uv_sha256']:
            raise ValueError('Replay atlas differs from saved baked UV layout: '+name)
        return mask
    donors={}
    for name,obj in load(canonical/'bake-v1/worker.blend',manifests[0]).items():
        data=atlas(obj) if name in common else None
        if data and _geometry(obj)==original[0][name][0]:donors[name]=(_geometry(obj),data[2],data[3],verified_mask(name,data,provenance_maps[0],obj))
    targets=load(target/'bake-v1/worker.blend',manifests[1])
    geometry={o.name:_geometry(o) for o in bpy.context.scene.objects}
    print('Transfer: binding complete scene appearance before edits',flush=True)
    before={o.name:signature(o,full_pixels=False) for o in bpy.context.scene.objects if o.type=='MESH'}
    changed=[];skipped=[];expected_saved={};updated_masks={}
    for name,obj in targets.items():
        data=atlas(obj) if name in donors else None
        if not data or donors[name][0]!=_geometry(obj) or original[1][name][0]!=_geometry(obj) or donors[name][1]!=data[2]:
            skipped.append(name);continue
        target_mask=verified_mask(name,data,provenance_maps[1],obj)
        merged,count=merge_inferred(donors[name][2],data[3],donors[name][3],target_mask,allow_bounded_donors=allow_bounded_donors)
        if not count:continue
        material,node,_,pixels=data
        # Detach material and image even if another state/context shares them.
        slot=obj.data.polygons[0].material_index
        replacement=material.copy();obj.data.materials[slot]=replacement
        node=next(n for n in replacement.node_tree.nodes if n.type=='TEX_IMAGE')
        image=node.image.copy();node.image=image
        image.pixels.foreach_set(merged.ravel());image.update();image.pack()
        expected_saved[name]=merged
        donor_mask=donors[name][3]
        updated_masks[name],_=transferred_ownership(donor_mask,target_mask,allow_bounded_donors=allow_bounded_donors)
        changed.append({'object':name,'inferred_texels':count,'protected_texels':int((target_mask==1).sum()),'before_rgba_sha256':hashlib.sha256(pixels.tobytes()).hexdigest(),'after_rgba_sha256':hashlib.sha256(merged.tobytes()).hexdigest()})
    if not changed:raise ValueError('No eligible shared inferred atlas texels')
    changed_names={r['object'] for r in changed}
    if geometry!={o.name:_geometry(o) for o in bpy.context.scene.objects}:raise ValueError('Geometry changed')
    appearance_cache.clear();pixel_cache.clear()
    print('Transfer: checking unchanged scene appearance after edits',flush=True)
    if any(before[o.name]!=signature(o,full_pixels=False) for o in bpy.context.scene.objects if o.type=='MESH' and o.name not in changed_names):raise ValueError('Outside appearance changed')
    if hashes!={p:sha(Path(p)) for p in hashes}:raise ValueError('Inputs changed')
    output.mkdir(parents=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'worker.blend'))
    saved=load(output/'worker.blend',manifests[1])
    for name,expected in expected_saved.items():
        actual=atlas(saved[name])
        if actual is None or not np.array_equal(actual[3],expected):
            raise ValueError('Saved packed image roundtrip changed transferred or protected texels: '+name)
    report=json.loads((target/'bake-v1/validation.json').read_text())
    report['shared_inferred_transfer']={'allow_bounded_donors':allow_bounded_donors,'inputs_sha256':hashes,'canonical':str(canonical),'target':str(target),'changed':changed,'skipped':skipped,'geometry_preserved':True,'outside_appearance_preserved':True,'target_observed_rgba_preserved':True,'all_target_alpha_preserved':True,'saved_roundtrip_rgba_exact':True}
    proof_dir=output/'provenance-transfer';proof_dir.mkdir()
    for layer in report['layers']:
        for entry in layer['objects']:
            name=entry['object']
            original_proof,original_mask=provenance_maps[1][name]
            if name not in updated_masks:
                entry['texel_provenance']=original_proof
                continue
            actual=atlas(saved[name]);mask=updated_masks[name]
            proof_path=proof_dir/(hashlib.sha256(name.encode()).hexdigest()[:20]+'.npz')
            np.savez_compressed(proof_path,ownership=mask)
            entry['texel_provenance']={**original_proof,'path':str(proof_path),'sha256':sha(proof_path),
                'packed_image_sha256':hashlib.sha256(actual[1].image.packed_file.data).hexdigest(),
                'rgba8_sha256':hashlib.sha256(np.rint(np.clip(actual[3],0,1)*255).astype(np.uint8).tobytes()).hexdigest(),
                'semantics':{'0':'unfilled-or-padding','1':'protected-source','2':'generated','3':'bounded-same-face-extrapolation'}}
    final_masks=[updated_masks.get(name,mask) for name,(_,mask) in provenance_maps[1].items()]
    report['counts'].update(protected_texels_including_padding=sum(int((m==1).sum()) for m in final_masks),
        generated_texels_including_padding=sum(int((m==2).sum()) for m in final_masks),
        extrapolated_texels_including_padding=sum(int((m==3).sum()) for m in final_masks),
        unfilled_texels_including_padding=sum(int((m==0).sum()) for m in final_masks))
    report['model_sha256']=sha(output/'worker.blend')
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    width,height=manifests[1]['tile_size']
    render(target/'views.json',output/'actual',width=width)
    buffers=[]
    for i in range(8):
        image=bpy.data.images.load(str(output/'actual'/f'view-{i}-textured.png'),check_existing=False)
        pixels=array('f',[0])*len(image.pixels);image.pixels.foreach_get(pixels);buffers.append(pixels);bpy.data.images.remove(image)
    _tile(buffers,width,height,output/'actual/textured.png')
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('canonical');parser.add_argument('target');parser.add_argument('output')
    parser.add_argument('--allow-bounded-donors',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    run(args.canonical,args.target,args.output,allow_bounded_donors=args.allow_bounded_donors)
