"""Compare exact inherited and proposed forge mesh topology without saving."""
import sys,json,hashlib
from pathlib import Path
import bpy,bmesh
ROOT=Path(__file__).resolve().parents[3];A='nottingham-village-small-hut';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inspect(path):
 bpy.ops.wm.open_mainfile(filepath=str(path));rows={}
 for o in bpy.context.scene.objects:
  if o.type!='MESH' or o.hide_render or o.get('asset_group')!=A:continue
  mesh=bmesh.new();mesh.from_mesh(o.data)
  rows[o.name]=dict(vertices=len(mesh.verts),edges=len(mesh.edges),faces=len(mesh.faces),nonmanifold_edges=sum(not e.is_manifold for e in mesh.edges),boundary_edges=sum(e.is_boundary for e in mesh.edges),zero_area_faces=sum(f.calc_area()<1e-8 for f in mesh.faces),topology_sha256=hashlib.sha256(json.dumps([list(f.vertices)for f in o.data.polygons]).encode()).hexdigest());mesh.free()
 return rows
def main(w):
 w=Path(w);old=ROOT/'level-editor/work/nottingham-refinement/round-23/assets'/A/'model.blend';before=inspect(old);after=inspect(w/'model.blend');body=next(n for n in after if 'Structural volume 281' in n)
 assert before[body]['topology_sha256']==after[body]['topology_sha256'] and before[body]['nonmanifold_edges']==after[body]['nonmanifold_edges']
 for name,row in after.items():
  assert not row['zero_area_faces']
  if name!=body:assert row['nonmanifold_edges']==0,(name,row)
 r=dict(status='PASS',model_sha256=sha(w/'model.blend'),previous_model_sha256=sha(old),before=before,after=after,limitations=['The inherited forge masonry body is an open surface assembly; its exact topology is preserved while its low source outline moves. New roof, hood and supports are closed and nondegenerate.'])
 (w/'inspection/topology-comparison.json').write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
if __name__=='__main__':main(sys.argv[sys.argv.index('--')+1])
