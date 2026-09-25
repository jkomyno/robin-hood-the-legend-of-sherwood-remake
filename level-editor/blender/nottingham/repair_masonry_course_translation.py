"""Prototype a measured rigid masonry-course copy on unchanged generated atlases.

Each patch binds its face, physical height interval and rigid translation.
Coplanar sibling triangles additionally bind explicit target/donor coordinates
and the subpixel world-space sampling error.
Only original class-2 donors may replace original class-0 targets. Unsupported
samples remain unfilled. Separately measured small components may use bounded
same-face donors, with exact component coordinates and explicit distance caps.
The saved/reloaded worker is checked against every unchanged value.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT / 'level-editor/refinement/blender'))
from repair_ramp_isolated_edge import physical_face, pixels, rgba8
from refinement_workspace import _geometry
from bake_reviewed_asset import _materials
from course_patch_guards import coordinates, coplanar_measurements, ownership_classes
from isolated_edge_texels import donor


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(config_path):
    spec = json.loads(config_path.read_text())
    old, out = Path(spec['bake']), Path(spec['output'])
    assert sha(old / 'worker.blend') == spec['model_sha256']
    if out.exists():
        raise FileExistsError(out)
    validation = json.loads((old / 'validation.json').read_text())
    reports = {p.name: json.loads(p.read_text()) for p in old.glob('layer-*.json')}
    proofs = {e['object']: e for r in reports.values() for e in r['objects'] if e.get('texel_provenance')}
    bpy.ops.wm.open_mainfile(filepath=str(old / 'worker.blend'))
    geometry = {o.name: _geometry(o) for o in bpy.data.objects}
    materials = {o.name: _materials(o) for o in bpy.data.objects if o.type == 'MESH'}
    packed = {i.name: hashlib.sha256(i.packed_file.data).hexdigest() for i in bpy.data.images if i.packed_file and i.users > 0}
    buffers, flags, images, edits = {}, {}, {}, []
    for patch in spec.get('patches', []):
        name, fid = patch['object'], patch['face']
        obj = bpy.data.objects[name]
        face = obj.data.polygons[fid]
        image_node = next(n for n in obj.data.materials[face.material_index].node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
        uv = obj.data.uv_layers[image_node.inputs['Vector'].links[0].from_node.uv_map]
        proof = proofs[name]['texel_provenance']
        assert sha(proof['path']) == proof['sha256']
        assert hashlib.sha256(image_node.image.packed_file.data).hexdigest() == proof['packed_image_sha256']
        assert hashlib.sha256(json.dumps([list(e.uv) for e in uv.data]).encode()).hexdigest() == proof['uv_sha256']
        if name not in buffers:
            buffers[name] = pixels(image_node.image)
            flags[name] = np.load(proof['path'])['ownership'].copy()
            images[name] = image_node.image
        own = flags[name]
        (left, bottom), physical, pos = physical_face(obj, face, uv, own.shape)
        h, w = physical.shape
        local = own[bottom:bottom+h, left:left+w]
        target = physical & (local == 0) & (pos[:, :, 2] >= patch['z_min']) & (pos[:, :, 2] <= patch['z_max'])
        ty, tx = np.where(target)
        target_xy = np.c_[tx+left, ty+bottom].astype('<i4')
        assert len(tx) == patch['target_texels']
        assert hashlib.sha256(target_xy.tobytes()).hexdigest() == patch['target_xy_sha256']
        dx, dy = patch['shift_xy']
        sy, sx = ty+dy, tx+dx
        valid = (sy >= 0) & (sy < h) & (sx >= 0) & (sx < w)
        valid[valid] &= physical[sy[valid], sx[valid]] & (local[sy[valid], sx[valid]] == 2)
        ty, tx, sy, sx = ty[valid], tx[valid], sy[valid], sx[valid]
        assert len(tx) == patch['expected_repaired_texels']
        delta = pos[sy, sx] - pos[ty, tx]
        assert np.max(np.linalg.norm(delta[:, :2], axis=1)) <= patch['max_horizontal_world']
        assert delta[:, 2].min() >= patch['min_rise_world']
        assert delta[:, 2].max() <= patch['max_rise_world']
        edits.append(dict(object=name, face=fid, shift_xy=[dx, dy], target_xy=np.c_[tx+left, ty+bottom].tolist(), donor_xy=np.c_[sx+left, sy+bottom].tolist(), untouched_unsupported_texels=patch['target_texels']-len(tx), world_shift_mean=delta.mean(0).tolist(), original_provenance=proof.copy()))
    for patch in spec.get('coplanar_sibling_patches', []):
        name = patch['object']; obj = bpy.data.objects[name]
        face, sibling = (obj.data.polygons[patch[k]] for k in ['face', 'donor_face'])
        assert face.material_index == sibling.material_index
        nodes = obj.data.materials[face.material_index].node_tree.nodes
        node = next(n for n in nodes if n.type == 'TEX_IMAGE' and n.image)
        uv = obj.data.uv_layers[node.inputs['Vector'].links[0].from_node.uv_map]
        proof = proofs[name]['texel_provenance']
        assert sha(proof['path']) == proof['sha256']
        assert hashlib.sha256(node.image.packed_file.data).hexdigest() == proof['packed_image_sha256']
        assert hashlib.sha256(json.dumps([list(e.uv) for e in uv.data]).encode()).hexdigest() == proof['uv_sha256']
        if name not in buffers:
            buffers[name] = pixels(node.image)
            flags[name] = np.load(proof['path'])['ownership'].copy()
            images[name] = node.image
        vertices = [np.array([obj.matrix_world @ obj.data.vertices[i].co for i in f.vertices], dtype=np.float64) for f in [face, sibling]]
        normal_error, plane_error = coplanar_measurements(vertices)
        assert normal_error <= patch['max_normal_delta']
        assert plane_error <= patch['max_plane_offset_world']
        shape = flags[name].shape
        domains = [physical_face(obj, f, uv, shape) for f in [face, sibling]]
        coords = coordinates(patch['target_xy'], patch['donor_xy'], shape)
        for key, values in zip(['target_xy', 'donor_xy'], coords):
            assert hashlib.sha256(values.tobytes()).hexdigest() == patch[key+'_sha256']
        positions=[]
        for (origin, physical, pos), xy in zip(domains, coords):
            local=xy-np.array(origin); x,y=local.T
            assert (local >= 0).all() and (local < [physical.shape[1], physical.shape[0]]).all()
            assert physical[y,x].all()
            positions.append(pos[y,x])
        tx,ty=coords[0].T; sx,sy=coords[1].T
        assert (flags[name][ty,tx]==0).all() and (flags[name][sy,sx]==2).all()
        desired=np.array(patch['world_translation'])
        errors=np.linalg.norm(positions[1]-positions[0]-desired,axis=1)
        assert errors.max() <= patch['max_sampling_error_world']
        assert (positions[0][:,2] >= patch['z_min']).all() and (positions[0][:,2] <= patch['z_max']).all()
        edits.append(dict(object=name,face=face.index,donor_face=sibling.index,target_xy=coords[0].tolist(),donor_xy=coords[1].tolist(),world_translation=desired.tolist(),sampling_error_max_world=float(errors.max()),unique_donor_texels=len(np.unique(coords[1],axis=0)),plane_offset_world=plane_error,normal_delta=normal_error,original_provenance=proofs[name]['texel_provenance'].copy()))
    if spec.get('measured_component_patches'):
        assert sha(spec['component_report']) == spec['component_report_sha256']
    for patch in spec.get('measured_component_patches', []):
        name, fid = patch['object'], patch['face']
        obj = bpy.data.objects[name]; face = obj.data.polygons[fid]
        node = next(n for n in obj.data.materials[face.material_index].node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
        uv = obj.data.uv_layers[node.inputs['Vector'].links[0].from_node.uv_map]
        proof = proofs[name]['texel_provenance']
        assert sha(proof['path']) == proof['sha256']
        assert hashlib.sha256(node.image.packed_file.data).hexdigest() == proof['packed_image_sha256']
        assert hashlib.sha256(json.dumps([list(e.uv) for e in uv.data]).encode()).hexdigest() == proof['uv_sha256']
        if name not in buffers:
            buffers[name] = pixels(node.image)
            flags[name] = np.load(proof['path'])['ownership'].copy()
            images[name] = node.image
        own = flags[name]
        target, _ = coordinates(patch['target_xy'], patch['target_xy'], own.shape)
        assert hashlib.sha256(target.tobytes()).hexdigest() == patch['target_xy_sha256']
        (left, bottom), physical, pos = physical_face(obj, face, uv, own.shape)
        local_xy = target - [left, bottom]
        assert (local_xy >= 0).all() and (local_xy < [physical.shape[1], physical.shape[0]]).all()
        h, w = physical.shape; local = own[bottom:bottom+h, left:left+w]
        expected = [(int(y), int(x)) for x, y in local_xy]
        assert len(target) <= patch['max_count']
        assert len(target) / int(physical.sum()) <= patch['max_fraction']
        obj.data.calc_loop_triangles()
        area = 0.0
        for tri in obj.data.loop_triangles:
            if tri.polygon_index == fid:
                verts = np.array([obj.matrix_world @ obj.data.vertices[i].co for i in tri.vertices])
                area += float(np.linalg.norm(np.cross(verts[1]-verts[0], verts[2]-verts[0])) / 2)
        assert area * len(target) / int(physical.sum()) <= patch['max_area_world2']
        selected, distances = [], []
        for x, y in local_xy:
            (sy, sx), texels, world = donor(local, physical, pos, (int(y), int(x)), max_texels=patch['max_texels'], max_world=patch['max_world'], expected_component=expected)
            selected.append([int(sx+left), int(sy+bottom)])
            distances.append(dict(texels=texels, world=world))
        edits.append(dict(object=name, face=fid, method='bounded-measured-same-face-component', target_xy=target.tolist(), donor_xy=selected, distances=distances, component_area_world2=area*len(target)/int(physical.sum()), original_provenance=proof.copy()))
    original = {name: rgba8(values) for name, values in buffers.items()}
    original_flags = {name: value.copy() for name, value in flags.items()}
    allowed = {name: np.zeros(value.shape, bool) for name, value in flags.items()}
    for edit in edits:
        name=edit['object']; tx,ty=np.array(edit['target_xy']).T; sx,sy=np.array(edit['donor_xy']).T
        ownership_classes(original_flags[name], edit['target_xy'], edit['donor_xy'])
        assert not allowed[name][ty,tx].any()
        buffers[name][ty,tx,:3]=buffers[name][sy,sx,:3]
        flags[name][ty,tx]=3
        allowed[name][ty,tx]=True
    out.mkdir(parents=True)
    (out/'repair-script.py').write_bytes(Path(__file__).read_bytes())
    for name,image in images.items():
        image.pixels.foreach_set(buffers[name].ravel()); image.update(); image.pack()
    image_names = {name: image.name for name, image in images.items()}
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'worker.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(out/'worker.blend'))
    assert geometry == {o.name: _geometry(o) for o in bpy.data.objects}
    assert materials == {o.name: _materials(o) for o in bpy.data.objects if o.type=='MESH'}
    changed = set(image_names.values())
    for name,digest in packed.items():
        if name not in changed:
            assert hashlib.sha256(bpy.data.images[name].packed_file.data).hexdigest()==digest
    for name,before in original.items():
        image=bpy.data.images[image_names[name]]
        after=rgba8(pixels(image))
        assert np.array_equal(before[~allowed[name]],after[~allowed[name]])
        assert np.array_equal(before[:,:,3],after[:,:,3])
        for edit in edits:
            if edit['object']!=name: continue
            tx,ty=np.array(edit['target_xy']).T; sx,sy=np.array(edit['donor_xy']).T
            assert np.array_equal(after[ty,tx,:3],before[sy,sx,:3])
        proof=proofs[name]['texel_provenance']; dest=out/'provenance-course'/Path(proof['path']).name
        dest.parent.mkdir(exist_ok=True); np.savez_compressed(dest,ownership=flags[name])
        proof.update(path=str(dest.resolve()),sha256=sha(dest),packed_image_sha256=hashlib.sha256(image.packed_file.data).hexdigest(),rgba8_sha256=hashlib.sha256(after.tobytes()).hexdigest())
        if any(edit['object'] == name and edit.get('donor_face', edit['face']) != edit['face'] for edit in edits):
            proof['semantics'] = {**proof.get('semantics', {}), '3': 'bounded-same-face-or-proved-coplanar-continuation'}
    for filename,report in reports.items():
        (out/filename).write_text(json.dumps(report,indent=2)+'\n')
    count=sum(int(a.sum()) for a in allowed.values())
    validation['layers']=list(reports.values())
    validation['counts_before_course_copy']=dict(validation['counts'])
    validation['counts']['unfilled_texels_including_padding']-=count
    validation['counts']['extrapolated_texels_including_padding']=validation['counts'].get('extrapolated_texels_including_padding',0)+count
    validation['course_translation']={'config_path':str(config_path.resolve()),'sha256':sha(config_path),'repaired_texels':count}
    if spec.get('measured_component_patches'):
        validation['measured_component_repairs'] = {'component_report': spec['component_report'], 'component_report_sha256': spec['component_report_sha256'], 'components': len(spec['measured_component_patches']), 'method': 'bounded-measured-same-face-component'}
    (out/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    report=dict(status='PASS',model_sha256=sha(out/'worker.blend'),previous_model_sha256=spec['model_sha256'],geometry_uv_material_layout_exact=True,alpha_exact=True,source_and_existing_generated_exact=True,outside_patch_rgba_exact=True,original_class2_donors_only=True,repaired_texels=count,edits=edits,config_sha256=sha(config_path),script_sha256=sha(__file__))
    (out/'saved-course-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    run(args.config)
