"""Refresh the retained Upper West candidate at the user-selected review sun.

Run in Blender with the candidate model loaded. This does not alter geometry,
materials, source masks, or the camera elevation. Output must not already exist.
"""
import json
import sys
from pathlib import Path

sys.path[:0] = ['/usr/lib/python3.14', '/usr/lib/python3.14/lib-dynload',
                '/usr/lib/python3.14/site-packages', str(Path(__file__).parent)]
import bpy
import bmesh
from refinement_review import render_review


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    candidate, output = map(Path, args)
    frame = json.loads((candidate / 'modified/views.json').read_text())
    frame['lighting']['toward_sun'] = [-0.4916794601, -0.4538579920, 0.7431448255]
    parent = candidate.parent.parent
    report = render_review(output, scene_name='Derby Refinement',
        collection_name='Derby Working', asset_id=frame['asset_id'],
        source_path=frame['source_image'], frame_manifest=frame,
        projection_layers=frame['projection_layers'], lighting=frame['lighting'],
        source_mask_manifest=parent / 'source-masks.json')
    meshes = []
    for obj in bpy.data.collections['Derby Working'].all_objects:
        if obj.type != 'MESH' or obj.hide_render or obj.get('asset_group') != frame['asset_id']:
            continue
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        meshes.append(dict(name=obj.name, source_node=obj.get('source_node'),
            vertices=len(bm.verts), faces=len(bm.faces),
            boundary_edges=sum(e.is_boundary for e in bm.edges),
            nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
            zero_area_faces=sum(f.calc_area() < 1e-8 for f in bm.faces)))
        bm.free()
    (output / 'geometry-audit.json').write_text(json.dumps(dict(
        model=bpy.data.filepath, geometry_changed=False, meshes=meshes), indent=2))
    print(json.dumps(dict(output=str(output), lighting=report['lighting'], meshes=meshes)), flush=True)


if __name__ == '__main__':
    main()
