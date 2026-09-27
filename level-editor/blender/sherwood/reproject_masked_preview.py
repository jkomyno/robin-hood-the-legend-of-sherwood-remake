"""Fresh masked Day projection into the approved worker's existing UV atlases.

Partial assignments create an audit-only worker, never a synthesis authority.
Every atlas starts neutral; prior Day/AI RGB is discarded. Unresolved source
nodes and separate canopy layers remain explicitly unknown in this preview.
"""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
EDITOR = HERE.parents[1]
sys.path[:0] = [str(HERE), str(EDITOR/'refinement'), str(EDITOR/'refinement/blender'),
                str(EDITOR/'blender/lincoln')]
from render_slots import acquire
from stage_grouping_review import fingerprint, sha
from occlusion_constraints import SourceMaskConstraints, evidence_record
from compile_source_masks import verify_coverage
import global_reproject as gr

gr.SCENE, gr.COLLECTION = 'Sherwood Editor Migration', 'Sherwood Working'
gr.OWNERSHIP_LABEL = 'exterior'


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def main(grouping, masks, output):
    grouping, masks, output = (Path(p).resolve() for p in (grouping, masks, output))
    coverage = json.loads((masks/'coverage.json').read_text())
    worker = Path(coverage.get('worker', grouping/'grouped-source-only.blend'))
    if sha(worker) != coverage.get('worker_sha256', coverage['grouped_worker_sha256']):
        raise ValueError('Approved grouped worker changed')
    for path, expected in coverage['evidence'].items():
        if sha(path) != expected:
            raise ValueError('Mask evidence changed: '+path)
    output.mkdir(parents=True, exist_ok=False)
    (output/'ownership').mkdir()
    acquire()
    bpy.ops.wm.open_mainfile(filepath=str(worker))
    bpy.context.window.scene = bpy.data.scenes[gr.SCENE]
    objects = sorted((o for o in bpy.data.collections[gr.COLLECTION].objects if o.type == 'MESH'), key=lambda o:o.name)
    before = fingerprint(objects)
    source_path = EDITOR.parent/'datadirs/fullgame_gog_hackable/Data/Levels/Day/sherwood.map.png'
    source = np.asarray(Image.open(source_path).convert('RGB'))
    height, width = source.shape[:2]
    constraints = SourceMaskConstraints(masks/'source-masks.json', 'exterior', sha(source_path), (width, height))
    verify_coverage(constraints, [dict(name=o.name, **{k:o.get(k) for k in ('source_node','asset_group','projection_component')}) for o in objects])
    rules = json.loads((masks/'source-masks.json').read_text())['projections']['exterior']['assignments']
    resolved = {r['source_node'] for r in rules if r['ownership_status'] == 'reviewed'}
    leaves = [o for o in objects if any(m and m.get('foliage_physical_opacity') for m in o.data.materials)]
    original_visibility = {o.name:o.hide_render for o in leaves}
    for obj in leaves:
        obj.hide_render = True
    scene = gr.Scene()
    print(f'Rasterizing original Day visibility for {len(scene.objects)} meshes', flush=True)
    ids, planes = gr.rasterize(scene, width, height)
    print('Day visibility complete', flush=True)
    records = {r['object'].name:r for r in scene.meshes}
    ownership, rows, image_users = {}, [], {}
    for obj in objects:
        for slot in {p.material_index for p in obj.data.polygons}:
            binding = scene.slot_binding(obj, slot)
            if binding is None:
                raise ValueError('Unbound atlas: '+obj.name)
            image_users.setdefault(binding['image'].name, []).append(obj.name)
    shared = {n:v for n,v in image_users.items() if len(v)>1}
    if shared:
        raise ValueError('Projection requires distinct per-mesh atlases: '+str(shared))
    accepted_total = 0
    for number, obj in enumerate(objects):
        slots = {p.material_index for p in obj.data.polygons}
        if len(slots) != 1:
            raise ValueError('One provenance atlas required per mesh: '+obj.name)
        slot = next(iter(slots))
        binding = scene.slot_binding(obj, slot)
        atlas = gr.read_image(binding['image'])
        physical = atlas[...,3].copy()
        atlas[...,:3] = 128
        flags = np.zeros(atlas.shape[:2], dtype=np.uint8)
        accepted = rejected_mask = rejected_visibility = 0
        sample_map = np.full((*atlas.shape[:2],2), -1, dtype=np.int16)
        if obj.get('source_node') in resolved and obj not in leaves:
            record = records[obj.name]
            uv = gr.slot_uvs(obj, binding['uv'])
            for face, ty, tx, positions, normals, interior in gr.islands(record, uv, binding['image'].size, lambda _:True):
                sx, sy, _ = gr.screen(positions)
                px, py = np.floor(sx).astype(int), np.floor(sy).astype(int)
                seen = gr.visible(positions, ids, planes, width, height)
                allowed = constraints.allowed(constraints.for_object(obj), px, height-1-py)
                take = seen & allowed & (np.abs(normals@gr.TOWARD) >= .05)
                rejected_mask += int((seen & ~allowed & interior).sum())
                rejected_visibility += int((allowed & ~seen & interior).sum())
                cx, cy = np.clip(px,0,width-1), np.clip(py,0,height-1)
                atlas[ty[take],tx[take],:3] = source[cy[take],cx[take]]
                flags[ty[take],tx[take]] = 1
                sample_map[ty[take],tx[take]] = np.stack((cx[take],cy[take]),axis=1)
        known = flags == 1
        if known.any():
            expected = source[sample_map[...,1][known],sample_map[...,0][known]]
            if not np.array_equal(atlas[known,:3], expected):
                raise ValueError('Accepted source RGB mismatch: '+obj.name)
        if not np.array_equal(atlas[...,3], physical):
            raise ValueError('Physical alpha changed: '+obj.name)
        gr.write_image(binding['image'], atlas)
        colors = obj.data.color_attributes.get('source_ownership')
        if colors:
            # Conservative display ownership; exact authority remains per texel.
            values = np.ones((len(colors.data),4), dtype=np.float32)
            values[:,0] = 0
            colors.data.foreach_set('color', values.ravel())
        filename = output/'ownership'/f'{number:04}.npz'
        np.savez_compressed(filename, ownership=flags, source_xy=sample_map)
        ownership[obj.name] = str(filename)
        accepted = int(known.sum())
        accepted_total += accepted
        rows.append(dict(object=obj.name, source_node=obj.get('source_node'), asset_group=obj.get('asset_group'),
                         accepted_texels=accepted, mask_rejected_samples=rejected_mask,
                         visibility_rejected_samples=rejected_visibility,
                         status='PROJECTED' if obj.get('source_node') in resolved else 'UNRESOLVED_UNKNOWN'))
        if number%50 == 0:
            print(f'Projected {number+1}/{len(objects)} meshes; {accepted_total} accepted texels', flush=True)
    for obj in leaves:
        obj.hide_render = original_visibility[obj.name]
    if fingerprint(objects) != before:
        raise ValueError('Mask projection changed geometry, transforms, UVs or material bindings')
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'source-only.blend'), compress=True)
    result = dict(status='PARTIAL_MASKED_DAY_AUDIT', synthesis_ready=False,
        worker_sha256=sha(output/'source-only.blend'), source_day_sha256=sha(source_path),
        geometry_uv_material_fingerprint=before, geometry_uv_transforms_unchanged=True,
        physical_alpha_unchanged=True, previous_rgb_reused=False, accepted_source_rgb_mismatches=0,
        accepted_texels=accepted_total, unresolved_source_nodes=coverage['unresolved_source_nodes'],
        unconstrained_receivers=0, source_mask_evidence=evidence_record(masks/'source-masks.json'),
        ownership=ownership, ownership_sha256={name:sha(path) for name,path in ownership.items()}, objects=rows)
    write(output/'reprojection.json',result)
    print('PARTIAL MASKED DAY AUDIT COMPLETE', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--grouping', required=True)
    parser.add_argument('--masks', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    main(args.grouping,args.masks,args.output)
