"""Verify saved atlas repair changes only explicitly classified inferred texels."""
from pathlib import Path
import hashlib
import json
import sys


def run(previous, output, previous_provenance=None):
    import bpy
    import numpy as np
    previous, output = Path(previous).resolve(), Path(output).resolve()
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    reports = [json.loads((p / 'validation.json').read_text()) for p in (previous, output)]
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
            result[name] = (pixels, mask, geometry, uv)
        return result
    old, new = read(previous, entries[0]), read(output, entries[1])
    records = []
    for name in old:
        before, mask, geometry, uv = old[name]
        after, final_mask, final_geometry, final_uv = new[name]
        changed = final_mask == 3
        if geometry != final_geometry or uv != final_uv:
            raise ValueError('Geometry or UV changed: ' + name)
        if not np.array_equal(final_mask[~changed], mask[~changed]) or np.any(mask[changed] != 0):
            raise ValueError('Repair changed protected provenance: ' + name)
        if not np.array_equal(before[~changed], after[~changed]) or not np.array_equal(before[..., 3], after[..., 3]):
            raise ValueError('Saved untouched RGBA or alpha changed: ' + name)
        count = int(changed.sum())
        if count != sum(r['repaired_texels'] for r in entries[1][name].get('inferred_gap_repairs', [])):
            raise ValueError('Repair count mismatch')
        records.append({'object': name, 'repaired_texels': count, 'protected_source_texels': int((mask == 1).sum()), 'existing_generated_texels': int((mask == 2).sum()), 'unchanged_rgba_exact': True, 'all_alpha_exact': True, 'geometry_and_uv_exact': True})
    report = {'status': 'PASS', 'previous_model_sha256': sha(previous / 'worker.blend'), 'model_sha256': sha(output / 'worker.blend'), 'validation_sha256': sha(output / 'validation.json'), 'objects': records, 'source_and_untouched_rgba_exact': True, 'all_alpha_exact': True}
    if external is not None:report['previous_external_provenance']=external
    (output / 'saved-gap-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('previous');p.add_argument('output');p.add_argument('--previous-provenance')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(args.previous,args.output,args.previous_provenance)
