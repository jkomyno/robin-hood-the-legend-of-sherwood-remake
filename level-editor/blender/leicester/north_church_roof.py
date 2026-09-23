"""Join planar church roof slopes to the corrected flat front facade."""
import bpy,bmesh,json,sys
from pathlib import Path
from mathutils import Vector

def main(w):
 r=json.loads((w/'facade-correction.json').read_text())
 front=Vector(next(v['after'] for v in r['facade_vertices'] if v['source_node']=='building-355' and v['index']==5));oldfront=Vector(next(v['before'] for v in r['facade_vertices'] if v['source_node']=='building-355' and v['index']==5))
 objects={o['source_node']:o for o in bpy.data.collections['Leicester Working'].all_objects if o.type=='MESH' and o.get('asset_group')=='leicester-church'}
 applied=bool(r.get('planar_roof_refinement'))
 original={k:[o.matrix_world@v.co for v in o.data.vertices] for k,o in objects.items()}
 back=Vector(r['planar_roof_refinement']['back_ridge']) if applied else original['building-355'][4]+(front-oldfront);back.z=front.z;axis=back-front;axis.z=0;axis.normalize()
 for node,frontidx,backidx in [(355,2,3),(356,3,2)]:
  o=objects[f'building-{node}'];frontidx,backidx=(1,2) if applied else (frontidx,backidx);eave=original[o['source_node']][frontidx];far=original[o['source_node']][backidx];far=eave+axis*(far-eave).dot(axis)
  top=[front,eave,far,back];verts=top+[Vector((v.x,v.y,61.04)) for v in top];faces=[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
  mesh=bpy.data.meshes.new(o.name+' / planar roof and facade');mesh.from_pydata([o.matrix_world.inverted()@v for v in verts],[],faces);mesh.uv_layers.new(name='UVMap')
  for m in o.data.materials:mesh.materials.append(m)
  bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges);bm.to_mesh(mesh);bm.free();o.data=mesh
 hip=objects['building-364'];roof=objects['building-355'];far=roof.matrix_world@roof.data.vertices[2].co
 for i,p in [(1,back),(2,far)]:
  hip.data.vertices[i].co=hip.matrix_world.inverted()@p;hip.data.vertices[i+5].co=hip.matrix_world.inverted()@Vector((p.x,p.y,61.04))
 r['planar_roof_refinement']={'front_ridge':list(front),'back_ridge':list(back),'notes':'Translate ridge along source rays to retain native ridge silhouette while meeting a single front facade plane. Roof slopes rebuilt as planar quads, retaining eave anchors; redundant source-sampling kinks removed.'};(w/'facade-correction.json').write_text(json.dumps(r,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'))
if __name__=='__main__':main(Path(sys.argv[sys.argv.index('--')+1]).resolve())
