"""Independently check saved atlas RGB against source pixels and native ownership."""
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
EDITOR = HERE.parents[1]
sys.path[:0] = [str(HERE), str(EDITOR/'refinement/blender'), str(EDITOR/'blender/lincoln')]
from stage_grouping_review import fingerprint, sha
from occlusion_constraints import SourceMaskConstraints
import global_reproject as gr

gr.COLLECTION = 'Sherwood Working'
gr.OWNERSHIP_LABEL = 'exterior'
root, mask_root = (Path(p).resolve() for p in sys.argv[sys.argv.index('--')+1:])
r = json.loads((root/'reprojection.json').read_text())
assert sha(root/'source-only.blend') == r['worker_sha256']
source_path = EDITOR.parent/'datadirs/fullgame_gog_hackable/Data/Levels/Day/sherwood.map.png'
assert sha(source_path) == r['source_day_sha256']
source = np.asarray(Image.open(source_path).convert('RGB'))
height, width = source.shape[:2]
constraints = SourceMaskConstraints(mask_root/'source-masks.json', 'exterior', sha(source_path), (width,height))
for filename, expected in r['source_mask_evidence'].items():
    assert sha(filename) == expected, filename
bpy.ops.wm.open_mainfile(filepath=str(root/'source-only.blend'))
objects = sorted((o for o in bpy.data.collections[gr.COLLECTION].objects if o.type=='MESH'),key=lambda o:o.name)
assert fingerprint(objects) == r['geometry_uv_material_fingerprint']
assert set(r['ownership']) == {o.name for o in objects}
known_count = 0
for obj in objects:
    masks = constraints.for_object(obj)
    assert masks is not None, obj.name
    path = r['ownership'][obj.name]
    assert sha(path) == r['ownership_sha256'][obj.name]
    with np.load(path) as data:
        flags, xy = data['ownership'], data['source_xy']
    material = obj.data.materials[obj.data.polygons[0].material_index]
    image = next(n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
    rgba = gr.read_image(image)
    known = flags==1
    assert flags.shape == rgba.shape[:2]
    assert set(np.unique(flags)) <= {0,1}
    assert np.all(rgba[~known,:3] == 128), obj.name
    if known.any():
        x,y = xy[...,0][known].astype(int),xy[...,1][known].astype(int)
        assert np.all((x>=0)&(x<width)&(y>=0)&(y<height)), obj.name
        assert constraints.allowed(masks,x,height-1-y).all(), obj.name
        assert np.array_equal(rgba[known,:3], source[y,x]), obj.name
    known_count += int(known.sum())
assert known_count == r['accepted_texels']
report = dict(status='PASS_PARTIAL_AUDIT', worker_sha256=r['worker_sha256'], checked_meshes=len(objects),
    accepted_texels=known_count, accepted_rgb_mismatches=0, outside_mask_accepted_texels=0,
    unconstrained_receivers=0, unknown_rgb_is_neutral=True, geometry_uv_transforms_unchanged=True,
    synthesis_ready=False, unresolved_source_nodes=r['unresolved_source_nodes'])
(root/'saved-worker-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
