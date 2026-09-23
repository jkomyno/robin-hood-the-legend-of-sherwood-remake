"""Trace the north dormer rear roof pitch and flared eave from source pixels."""
import json,math,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
ASSET='nottingham-north-dormer-house'
TAG='nottingham_dormer_rear_roof_v2'
S=math.sin(math.radians(35));C=math.cos(math.radians(35))
# Original full-map pixels, traced on the far roof silhouette. The final
# broad eave turns shallower than the upper tile courses.
TRACE=[(1744.23,317.57),(1759,337),(1775,353),(1790,365),(1804.51,370)]
def refine():
 obj=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==ASSET and o.get('source_node')=='building-124')
 if obj.get(TAG):return json.loads(obj[TAG])
 old=[obj.matrix_world@v.co for v in obj.data.vertices]
 # The original prism's far and near ridge anchors retain their exact world
 # position, keeping its contact with the unchanged western roof half.
 a=old[7];b=old[6];delta=b-a
 far=[]
 for x,y in TRACE:
  t=(x-a.x)/(old[4].x-a.x);wy=a.y+(old[4].y-a.y)*t
  far.append(Vector((x,wy,(-wy*S-y)/C)))
 near=[p+delta for p in far]
 vertices=far+near+[Vector((p.x,p.y,0)) for p in far+near]
 count=len(far);faces=[]
 for i in range(count-1):
  faces.extend([(i,i+1,count+i+1,count+i),(2*count+i,3*count+i,3*count+i+1,2*count+i+1),
                (i,2*count+i,2*count+i+1,i+1),(count+i,count+i+1,3*count+i+1,3*count+i)])
 faces += [(0,count,3*count,2*count),(count-1,2*count-1,4*count-1,3*count-1)]
 mesh=bpy.data.meshes.new('North dormer rear roof / traced pitch and flare');inv=obj.matrix_world.inverted();mesh.from_pydata([inv@v for v in vertices],[],faces);mesh.update()
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
 assert not any(defects.values()),defects
 bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='UVMap')
 for mat in obj.data.materials:mesh.materials.append(mat)
 obj.data=mesh;obj['projection_min_cosine']=.05
 report=dict(status='refined',asset_id=ASSET,source_node='building-124',trace=TRACE,changes=['Replaced the shallow rear roof plane with five measured silhouette anchors and four steep-to-flared tile-course bands.','Lowered the far eave approximately 21 source pixels onto the painted silhouette; continued that profile under the unchanged front roof.'],inference=['Roof cross-section continues along the existing ridge direction. Concealed wall/back and ground closure retain conservative solid-envelope construction.'],objects=[dict(source_node='building-124',vertices=len(mesh.vertices),faces=len(mesh.polygons),**defects)],source_fit='Far roof silhouette traced with approximately 2 native-pixel manual uncertainty; exact target residual is a construction check only.')
 obj[TAG]=json.dumps(report);return report

def main():
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9')
 from refinement_workspace import prepare,modified
 w=WORK/'round-19/assets'/ASSET;old=WORK/'round-1/assets'/ASSET
 operation=sys.argv[sys.argv.index('--')+1]
 if operation=='prepare':
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
  prepare(w,asset_id=ASSET,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=384,height=448,context_padding=28,framing_padding=1.15)
  (w/'tooling.json').write_text(json.dumps(tooling,indent=2)+'\n')
 else:
  bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();report=refine();refine();(w/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));modified(w)
if __name__=='__main__':main()
