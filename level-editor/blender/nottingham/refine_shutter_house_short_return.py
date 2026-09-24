"""Source-aligned front return with conservative hidden side beneath the existing roof."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 from render_slots import acquire
 from freeze_tooling import select_tooling
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,bmesh
 from mathutils import Vector
 from correct_prison_ramp_projection import clone_workspace
 from correct_source_projection import geometry
 from refinement_workspace import modified
 old=WORK/'round-1/assets/nottingham-southeast-shutter-house';w=WORK/'round-33/assets/nottingham-southeast-shutter-house'
 if w.exists():raise RuntimeError('Immutable candidate already exists')
 clone_workspace(old,w);bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));before=geometry();config=json.loads((w/'workspace.json').read_text())
 objects={o.get('source_node'):o for o in bpy.data.collections[config['collection_name']].all_objects if o.get('asset_group')==config['asset_id']}
 obj=objects['building-036'];v=[obj.matrix_world@p.co for p in obj.data.vertices]
 # The outer timber return is about twenty-two source pixels wide. Retain the
 # facade's existing inner edge; localize the return to a short depth instead
 # of stretching its source strip across the entire hidden building side.
 for i in [6,7]:v[i].x=1833.033447265625
 v.extend([Vector((1833.033447265625,-3379.912841796875,0.0004621826810762286)),Vector((1833.033447265625,-3379.912841796875,0))])
 def roof_height(roof,index,x,y):
  face=roof.data.polygons[index];a,b,c=[roof.matrix_world@roof.data.vertices[k].co for k in list(face.vertices)[:3]];n=(b-a).cross(c-a);return a.z-(n.x*(x-a.x)+n.y*(y-a.y))/n.z
 for i in [5,7,9]:v[i].z=roof_height(objects['building-040'],8,v[i].x,v[i].y)-.25
 for i in [2,3]:v[i].z=roof_height(objects['building-041'],4,v[i].x,v[i].y)-.25
 faces=[(0,1,2,3),(3,5,4,0),(5,9,8,4),(9,7,6,8),(7,2,1,6),(2,7,9),(2,9,5),(2,5,3),(0,4,8,6,1)]
 mesh=bpy.data.meshes.new('Shutter house / short front return and fitted roof contact');mesh.from_pydata([obj.matrix_world.inverted()@p for p in v],[],faces);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces);bm.to_mesh(mesh);bm.free()
 mat=bpy.data.materials.new('Shutter house return / unknown');mat.diffuse_color=(.32,.32,.32,1);mesh.materials.append(mat);mesh.uv_layers.new(name='UVMap');obj.data=mesh
 masks=json.loads((WORK/'coordinator-audit/shutter-stripe/corrected-masks.json').read_text());(w/'source-masks.json').write_text(json.dumps(masks,indent=2)+'\n')
 bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));modified(w);after=geometry();changed=[n for n in before if before[n]!=after[n]];assert changed==[obj.name],changed
 report=dict(status='awaiting-independent-review',model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),approved_model_sha256=sha(old/'model.blend'),changed_meshes=changed,geometry_inference='Hidden rear side x1833.03; sixty-world-unit short front return preserves the original narrow source domain. Top wall vertices meet the unchanged original roof planes. These depth choices are inferred and require review.',source_evidence='coordinator-audit/shutter-stripe',recipe=str(Path(__file__).resolve()),recipe_sha256=sha(__file__),approval='pending')
 (w/'short-return-correction.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
if __name__=='__main__':main()
