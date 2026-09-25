"""Verify scoped generated visibility corrections separately from inferred gap fills."""
from pathlib import Path
import hashlib
import json
import sys


def verify_samples(before, mask, after, final_mask, scoped):
    import numpy as np
    if before.shape!=after.shape or mask.shape!=before.shape[:2] or final_mask.shape!=mask.shape or scoped.shape!=mask.shape or scoped.dtype!=bool:
        raise ValueError('Saved visibility sample layout changed')
    original=mask==1
    if not np.array_equal(original,final_mask==1) or not np.array_equal(before[original],after[original]):
        raise ValueError('Original source ownership/RGBA changed')
    inferred=(final_mask==3)&(mask==0)
    allowed=inferred | (scoped & ~original & (mask!=3))
    if not np.array_equal(before[~allowed],after[~allowed]) or not np.array_equal(mask[~allowed],final_mask[~allowed]):
        raise ValueError('Outside scoped face/inferred destination changed')
    if not np.array_equal(before[...,3],after[...,3]):raise ValueError('Physical alpha changed')
    newly_projected=(mask==0)&(final_mask==2)
    if np.any(newly_projected & ~scoped):raise ValueError('New generated texel outside exact visibility scope')
    changed=np.any(before!=after,axis=-1)
    return dict(new_projected_class2_texels=int(newly_projected.sum()),new_inferred_class3_texels=int(inferred.sum()),changed_existing_generated_texels=int(((mask==2)&changed).sum()),protected_source_texels=int(original.sum()),source_rgba_exact=True,source_mask_exact=True,all_alpha_exact=True,outside_scoped_face_and_inferred_rgba_exact=True)


def run(previous, output, manifest, previous_provenance=None):
    import bpy
    import numpy as np
    previous, output = Path(previous).resolve(), Path(output).resolve()
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    reports = [json.loads((p / 'validation.json').read_text()) for p in (previous, output)]
    manifest=Path(manifest).resolve();contract=json.loads(manifest.read_text());scope=contract.get('texture_generated_bounded_visibility',{})
    if not scope:raise ValueError('Explicit bounded visibility face scope required')
    if reports[1].get('generated_bounded_visibility')!=scope or reports[1].get('evidence_sha256',{}).get(str(manifest))!=sha(manifest):raise ValueError('Visibility manifest is not bound to this saved bake')
    if reports[1].get('geometry_verified') is not True:raise ValueError('Missing saved geometry verification')
    for bands in contract.get('texture_inferred_gap_repair',{}).get('face_coordinate_bands',{}).values():
        for rule in bands.values():
            if rule['reference_model_sha256']!=sha(previous/'worker.blend'):raise ValueError('Coordinate band reference model drift')

    if reports[0].get('source_mask_evidence')!=reports[1].get('source_mask_evidence'):raise ValueError('Original source mask evidence changed')
    entries = [{e['object']: e for layer in r['layers'] for e in layer['objects']} for r in reports]
    external = None
    if previous_provenance is not None:
        path=Path(previous_provenance).resolve()
        external=json.loads(path.read_text())
        alternate={e['object']:e for layer in external['layers'] for e in layer['objects']}
        if alternate.keys()!=entries[0].keys():raise ValueError('External provenance receiver set changed')
        entries[0]={name:{**entry,'texel_provenance':alternate[name]['texel_provenance']} for name,entry in entries[0].items()}
        external={'path':str(path),'sha256':sha(path)}
    if entries[0].keys() != entries[1].keys():
        raise ValueError('Receiver set changed')
    def read(folder, records):
        bpy.ops.wm.open_mainfile(filepath=str(folder / 'worker.blend'))
        result = {}
        for name, entry in records.items():
            obj = bpy.data.objects[name]
            materials = {p.material_index for p in obj.data.polygons}
            if len(materials) != 1:
                raise ValueError('Ambiguous atlas material')
            material = obj.data.materials[next(iter(materials))]
            images = [n.image for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
            if len(images) != 1:
                raise ValueError('Ambiguous atlas image')
            image = images[0]
            proof = entry['texel_provenance']
            if hashlib.sha256(image.packed_file.data).hexdigest() != proof['packed_image_sha256']:
                raise ValueError('Saved atlas differs from provenance')
            provenance = Path(proof['path'])
            if sha(provenance) != proof['sha256']:
                raise ValueError('Provenance drift')
            pixels = np.asarray(image.pixels[:], dtype=np.float32).reshape(image.size[1], image.size[0], 4)
            mask = np.load(provenance)['ownership']
            uv_nodes=[n.uv_map for n in material.node_tree.nodes if n.type=='UVMAP']
            if len(uv_nodes)!=1:raise ValueError('Ambiguous material UV binding')
            bound_uv=[list(v.uv) for v in obj.data.uv_layers[uv_nodes[0]].data]
            if hashlib.sha256(json.dumps(bound_uv).encode()).hexdigest()!=proof['uv_sha256']:raise ValueError('Provenance UV binding changed')
            if mask.shape!=pixels.shape[:2] or not np.isin(mask,[0,1,2,3]).all():raise ValueError('Invalid provenance classes/layout')
            geometry = ([tuple(v.co) for v in obj.data.vertices], [tuple(p.vertices) for p in obj.data.polygons], [tuple(row) for row in obj.matrix_world])
            uv = {layer.name:[tuple(v.uv) for v in layer.data] for layer in obj.data.uv_layers}
            scoped=np.zeros(mask.shape,dtype=bool)
            bound=obj.data.uv_layers[uv_nodes[0]].data
            for face_index in scope.get(name,[]):
                if type(face_index) is not int or not 0<=face_index<len(obj.data.polygons):raise ValueError('Invalid visibility face scope')
                face=obj.data.polygons[face_index];coords=np.array([tuple(bound[i].uv) for i in face.loop_indices])*[image.size[0],image.size[1]]
                snapped=np.where(np.abs(coords-np.rint(coords))<1e-3,np.rint(coords),coords)
                lo=np.maximum(np.floor(snapped.min(0)).astype(int)-2,0);hi=np.minimum(np.ceil(snapped.max(0)).astype(int)+2,[image.size[0],image.size[1]])
                scoped[lo[1]:hi[1],lo[0]:hi[0]]=True
            result[name] = (pixels, mask, geometry, uv, scoped)
        return result
    old, new = read(previous, entries[0]), read(output, entries[1])
    records = []
    if not set(scope)<=set(old):raise ValueError('Visibility scope names a foreign receiver')
    for name in old:
        before, mask, geometry, uv, scoped = old[name]
        after, final_mask, final_geometry, final_uv, final_scoped = new[name]
        if geometry != final_geometry or uv != final_uv or not np.array_equal(scoped,final_scoped):
            raise ValueError('Geometry, UV or scoped island changed: '+name)
        evidence=verify_samples(before,mask,after,final_mask,scoped)
        if int((final_mask==3).sum())!=sum(v['repaired_texels'] for v in entries[1][name].get('inferred_gap_repairs',[])):raise ValueError('Inferred provenance count mismatch')
        records.append(dict(object=name,**evidence,geometry_and_all_uv_exact=True))
    report=dict(status='PASS',previous_model_sha256=sha(previous/'worker.blend'),model_sha256=sha(output/'worker.blend'),validation_sha256=sha(output/'validation.json'),manifest_sha256=sha(manifest),generated_bounded_visibility=scope,objects=records,source_mask_evidence_exact=True,outside_objects_unchanged=reports[1].get('outside_objects_unchanged'),sample_evidence=reports[1].get('bounded_visibility_sample_evidence'),sample_evidence_note='Whole generated image, approved mask, cameras and selected samples bound by validation evidence; class2 reprojection is distinct from class3 extrapolation.')
    if type(report['outside_objects_unchanged']) is not int or report['outside_objects_unchanged'] < 0:raise ValueError('Missing outside object preservation count')
    if external is not None:report['previous_external_provenance']=external
    (output / 'saved-visibility-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('previous');p.add_argument('output');p.add_argument('manifest');p.add_argument('--previous-provenance')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(args.previous,args.output,args.manifest,args.previous_provenance)
