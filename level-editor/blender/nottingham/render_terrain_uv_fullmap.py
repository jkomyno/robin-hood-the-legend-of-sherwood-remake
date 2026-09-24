"""Supplement frozen terrain closeups with complete saved-material map views."""
from pathlib import Path
import sys,json,hashlib
from array import array
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from render_multiview_asset import render
from refinement_review import _tile
W=ROOT/'level-editor/work/nottingham-refinement/texture-generation/nottingham-terrain-ground-uv-atlas-v1/bake-uv-v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
model=W/'worker.blend';before=sha(model);bpy.ops.wm.open_mainfile(filepath=str(model))
evidence=json.loads((W/'uv-evidence.json').read_text());points=[Vector(p) for t in evidence['triangles'] for p in t['world']]
frames=json.loads((W/'qa-views.json').read_text());frames['tile_size']=[512,512];frames['layout'].update(width=2048,height=1024)
center=Vector(tuple((min(p[k] for p in points)+max(p[k] for p in points))/2 for k in range(3)))
for v in frames['views']:
 matrix=Matrix(v['camera_matrix_world']);right=matrix.to_3x3().col[0];up=matrix.to_3x3().col[1];back=matrix.to_3x3().col[2]
 xs=[(p-center).dot(right) for p in points];ys=[(p-center).dot(up) for p in points]
 target=center+right*((min(xs)+max(xs))/2)+up*((min(ys)+max(ys))/2)
 matrix.translation=target+back*10000;v.update(camera_matrix_world=[list(row) for row in matrix],camera_location=list(matrix.translation),ortho_scale=max(max(xs)-min(xs),max(ys)-min(ys))*1.08,crop=dict(left=v['index']%4*512,top=v['index']//4*512,width=512,height=512))
frames['framing']='Supplemental complete saved terrain mesh; frozen source closeups retained separately'
manifest=W/'fullmap-views.json';manifest.write_text(json.dumps(frames,indent=2)+'\n');render(manifest,W/'actual-fullmap',width=512)
buffers=[]
for i in range(8):
 image=bpy.data.images.load(str(W/'actual-fullmap'/f'view-{i}-textured.png'),check_existing=False);pixels=array('f',[0])*len(image.pixels);image.pixels.foreach_get(pixels);buffers.append(pixels);bpy.data.images.remove(image)
_tile(buffers,512,512,W/'actual-fullmap/textured.png');assert before==sha(model)
(W/'fullmap-review-evidence.json').write_text(json.dumps(dict(model_sha256=before,fullmap_frames_sha256=sha(manifest),actual_sheet_sha256=sha(W/'actual-fullmap/textured.png'),inspected_views='pending',model_unchanged=True),indent=2)+'\n')
