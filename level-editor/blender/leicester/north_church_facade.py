"""Flatten the church front and trace both stepped buttresses from native artwork."""
import bpy,bmesh,json,math,sys
from pathlib import Path
from mathutils import Vector
SI,CO=math.sin(math.radians(35)),math.cos(math.radians(35))

def main(w):
 col=bpy.data.collections['Leicester Working'];objects={o['source_node']:o for o in col.all_objects if o.type=='MESH' and o.get('asset_group')=='leicester-church'}
 if any(o.get('church_facade_v2') for o in objects.values()):raise RuntimeError('Facade correction already applied')
 left=Vector((1016.989807,-1595.992065,0));right=Vector((1240.945801,-1725.323486,0));slope=(right.y-left.y)/(right.x-left.x);report={'facade_plane':{'left':list(left),'right':list(right)},'facade_vertices':[],'buttresses':[]}
 for node,ids in [(355,[0,1,2,5]),(356,[0,3,4])]:
  o=objects[f'building-{node}'];verts=[o.matrix_world@v.co for v in o.data.vertices];topcount=len(verts)//2
  for i in ids:
   old=verts[i].copy();new_y=left.y+(old.x-left.x)*slope;delta_y=new_y-old.y;new=Vector((old.x,new_y,old.z-delta_y*SI/CO));o.data.vertices[i].co=o.matrix_world.inverted()@new;o.data.vertices[i+topcount].co=o.matrix_world.inverted()@Vector((old.x,new_y,61.04));report['facade_vertices'].append({'source_node':o['source_node'],'index':i,'before':list(old),'after':list(new),'source_pixel_drift':abs(delta_y*SI+(new.z-old.z)*CO)})
  o['church_facade_v2']=True
 for node,anchor,width,profile in [
  (358,(1043.98291,-1612.230225),18,[(1033,612),(1023,638),(1024,699),(1016,730),(1020,None),(1044,None)]),
  (359,(1227.052368,-1714.792847),19,[(1226,672),(1215,704),(1214,759),(1204,794),(1204,None),(1227,None)])]:
  o=objects[f'building-{node}'];axis=1.643;side=[]
  for x,y in profile:
   wy=anchor[1]+(x-anchor[0])*axis;z=61.04 if y is None else (-wy*SI-y)/CO;side.append(Vector((x,wy,z)))
  cross=Vector((width,-width/axis,0));vs=side+[v+cross for v in side];n=len(side);faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
  mesh=bpy.data.meshes.new(o.name+' / two stepped tile caps');mesh.from_pydata([o.matrix_world.inverted()@v for v in vs],[],faces);mesh.uv_layers.new(name='UVMap')
  for m in o.data.materials:mesh.materials.append(m)
  o.data=mesh;o['church_facade_v2']=True;o['todo']='Native masks247/248 and source silhouettes define two sloped cap steps. Hidden attachment thickness is inferred.'
  report['buttresses'].append({'source_node':o['source_node'],'native_mask':247 if node==358 else 248,'source_side_profile':profile,'width_world':width,'world_vertices':[list(v) for v in vs]})
 for o in objects.values():
  bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-7 for f in bm.faces);bm.to_mesh(o.data);bm.free()
 (w/'facade-correction.json').write_text(json.dumps(report,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'))
if __name__=='__main__':main(Path(sys.argv[sys.argv.index('--')+1]).resolve())
