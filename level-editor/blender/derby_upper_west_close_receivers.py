"""Close identified missing receiver faces without moving source-fitted vertices."""
import sys
import json
from pathlib import Path
sys.path[:0] = ['/usr/lib/python3.14', '/usr/lib/python3.14/lib-dynload',
    '/usr/lib/python3.14/site-packages', str(Path(__file__).parent)]
import bpy
import bmesh
from refinement_workspace import _geometry, _reproject, _freeze_masks
from refinement_review import render_review

ASSET = 'derby-upper-west-curtain'
FACES = {
 'building-116': [(1,0,25,28),(3,5,7,8),(31,22,24),(9,30,12),(9,12,11,10),
   (0,2,5,7,6,10,11,13,16,15,17,21,20,22,24,26,25)],
 'building-127': [(4,2,7,5),(1,2,4,3)],
 'building-128': [(2,6,5,3),(1,3,5,4),(7,2,0)],
}


def main():
    candidate, output = map(Path, sys.argv[sys.argv.index('--')+1:])
    output = output.resolve()
    output.mkdir(exist_ok=False)
    working = bpy.data.collections['Derby Working']
    before = {o.name: _geometry(o) for o in working.all_objects}
    results = []
    for obj in working.all_objects:
        node = obj.get('source_node')
        if obj.type != 'MESH' or obj.hide_render or obj.get('asset_group') != ASSET or node not in FACES:
            continue
        coords = [tuple(v.co) for v in obj.data.vertices]
        assert len(coords) == {'building-116':33, 'building-127':8, 'building-128':9}[node]
        obj.data = obj.data.copy()
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        old_faces = len(bm.faces)
        if node == 'building-128':
            # A redundant point sags 0.037 units below the planar landing and
            # leaves a hairline triangular opening. Replace those two top
            # triangles with their shared planar triangle, retaining corners.
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.faces[7], bm.faces[8]], context='FACES_ONLY')
            bm.verts.remove(bm.verts[8])
            bm.verts.ensure_lookup_table()
        for indices in FACES[node]:
            bm.faces.new([bm.verts[i] for i in indices])
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        assert all(e.is_manifold for e in bm.edges), node
        assert all(f.calc_area() > 1e-8 for f in bm.faces), node
        volume = bm.calc_volume(signed=True)
        assert volume > 0, (node, volume)
        bm.to_mesh(obj.data)
        bm.free()
        expected_coords = coords[:8] if node == 'building-128' else coords
        assert expected_coords == [tuple(v.co) for v in obj.data.vertices]
        obj.data.update()
        results.append(dict(source_node=node, added_faces=len(obj.data.polygons)-old_faces,
            retained_vertex_positions_identical=True,
            redundant_top_vertex_removed=(node == 'building-128'),
            boundary_edges=0, nonmanifold_edges=0,
            signed_volume=volume, added_face_vertex_indices=FACES[node]))
    bpy.context.view_layer.update()
    after = {o.name: _geometry(o) for o in working.all_objects}
    changed = [n for n in before if before[n] != after[n]]
    assert len(changed) == 3 and all(bpy.data.objects[n].get('source_node') in FACES for n in changed)
    config = json.loads((candidate/'workspace.json').read_text())
    # Freeze the existing reviewed assignment authority in this new output.
    # The full input evidence is compared before any projection happens.
    from occlusion_constraints import evidence_record
    frame = json.loads((candidate/'modified/views.json').read_text())
    assert frame['source_mask_evidence'] == evidence_record(config['source_mask_manifest'])
    _freeze_masks(output, config)
    projection = _reproject(config, output/'projection')
    assert after == {o.name: _geometry(o) for o in working.all_objects}
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'model.blend'))
    frame['lighting']['toward_sun'] = [-0.4916794601,-0.4538579920,0.7431448255]
    render_review(output/'modified', scene_name=config['scene_name'],
        collection_name=config['collection_name'], asset_id=ASSET,
        source_path=frame['source_image'], frame_manifest=frame,
        projection_layers=frame['projection_layers'], lighting=frame['lighting'],
        source_mask_manifest=config['source_mask_manifest'])
    proof = dict(changed_objects=changed, outside_geometry_unchanged=True,
        unchanged_object_count=len(before)-3, before_hashes=before, after_hashes=after,
        meshes=results, source_masks_unchanged=True, projection=projection)
    (output/'validation.json').write_text(json.dumps(proof,indent=2))
    print(json.dumps(results),flush=True)


if __name__ == '__main__':
    main()
