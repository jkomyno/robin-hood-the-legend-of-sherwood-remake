"""Partition current curtain meshes into selectable sections with face provenance."""
from pathlib import Path
import json,math,sys,hashlib
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'level-editor/work/nottingham-refinement'
SIN=math.sin(math.radians(35))

def clipped(poly,normal,offset,sign):
 out=[]
 for p,q in zip(poly,poly[1:]+poly[:1]):
  dp=sign*(sum(a*b for a,b in zip(normal,p))-offset);dq=sign*(sum(a*b for a,b in zip(normal,q))-offset)
  if dp>=-1e-7:out.append(tuple(p))
  if (dp>1e-7 and dq < -1e-7) or(dp < -1e-7 and dq>1e-7):out.append(tuple(a+(b-a)*(dp/(dp-dq)) for a,b in zip(p,q)))
 return out

def area(poly):
 total=0.0
 for i in range(1,len(poly)-1):
  a=[x-y for x,y in zip(poly[i],poly[0])];b=[x-y for x,y in zip(poly[i+1],poly[0])];cross=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];total+=math.sqrt(sum(v*v for v in cross))/2
 return total

def build():
 import bpy,bmesh
 from mathutils import Vector
 sys.path.insert(0,str(Path(__file__).resolve().parent))
 from render_slots import acquire
 acquire()
 baseline='--baseline' in sys.argv
 plans=[json.loads((R/name).read_text())for name in('south-wall-partition-proposal.json','southwest-wall-partition-proposal.json')]
 records=[]
 for asset,nodes in [('nottingham-south-curtain-wall',[200,202]),('nottingham-south-gate-east-tower',[201]),('nottingham-southwest-curtain-wall',[219,220])]:
  path=R/'round-1/assets'/asset/('baseline.blend' if baseline else 'model.blend');bpy.ops.wm.open_mainfile(filepath=str(path))
  for node in nodes:
   found=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==asset and o.get('source_node')==f'building-{node}' and not o.hide_render]
   if len(found)!=1:raise ValueError((asset,node,len(found)))
   obj=found[0]
   original_vertices=[v.co.copy() for v in obj.data.vertices];original_faces=[list(f.vertices) for f in obj.data.polygons]
   pre=bmesh.new();pre.from_mesh(obj.data);original_defects={'nonmanifold_edges':sum(not e.is_manifold for e in pre.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in pre.faces)};pre.free()
   repaired=False
   if not baseline and node in [201,202,220]:
    points=json.loads((R/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][node]['points'];n=len(points);inv=obj.matrix_world.inverted();cos=math.cos(math.radians(35))
    coords=[inv@Vector((p['x'],-p['y']/SIN,p[level]/cos))for level in ['z_bottom','z_top']for p in points]
    faces=[list(reversed(range(n))),list(range(n,2*n))]+[[i,(i+1)%n,(i+1)%n+n,i+n]for i in range(n)]
    mesh=bpy.data.meshes.new(f'Reconstructed closed walk {node}');mesh.from_pydata(coords,[],faces);mesh.update();obj.data=mesh;repaired=True
   obj.data.calc_loop_triangles();world=[obj.matrix_world@v.co for v in obj.data.vertices]
   parents=list(range(len(world)))
   def root(v):
    while parents[v]!=v:v=parents[v]
    return v
   for edge in obj.data.edges:
    a,b=edge.vertices;parents[root(a)]=root(b)
   triangles=[{'polygon':t.polygon_index,'triangle':i,'island':root(t.vertices[0]),'points':[tuple(world[v])for v in t.vertices]}for i,t in enumerate(obj.data.loop_triangles)]
   if node in[219,220]:
    plan=plans[1];cut=plan['native_xy_cut'];n=Vector((cut['normal'][0],-SIN*cut['normal'][1],0));off=cut['offset']
    configs=[{'id':f'wall-{node}-{side}','asset':f'nottingham-southwest-curtain-wall-{side}','cuts':[(n,off,sgn)]}for side,sgn in [('north',1),('south',-1)]]
   else:
    entry=next(p for p in plans[0]['canonical_partitions']if p['canonical_obstacle']==node)
    configs=[{'id':p['component_id'],'asset':p['asset_id'],'cuts':[(Vector((1,0,0)),p['native_x_min'],1),(Vector((1,0,0)),p['native_x_max'],-1)]}for p in entry['components']]
   records.append({'node':node,'source':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'matrix':obj.matrix_world.copy(),'triangles':triangles,'configs':configs,'source_name':obj.name,'original_vertices':original_vertices,'original_faces':original_faces,'baseline_defects':original_defects,'envelope_reconstructed':repaired})
 bpy.ops.wm.read_factory_settings(use_empty=True);collection=bpy.data.collections.new('Curtain wall partitions');bpy.context.scene.collection.children.link(collection)
 report={'version':1,'sources':[],'components':[],'canonical_policy':'Component meshes retain native source_node. Canonical source object must be retained once and hidden by V8 grouping.'}
 for rec in records:
  canonical_mesh=bpy.data.meshes.new(f"Canonical {rec['node']}");canonical_mesh.from_pydata(rec['original_vertices'],[],rec['original_faces']);canonical_mesh.update()
  canonical=bpy.data.objects.new(rec['source_name'],canonical_mesh);collection.objects.link(canonical);canonical.matrix_world=rec['matrix'];canonical['source_node']=f"building-{rec['node']}";canonical['asset_group']={200:'nottingham-south-curtain-wall-1',202:'nottingham-south-curtain-wall-3',201:'nottingham-south-gate-east-tower',219:'nottingham-southwest-curtain-wall-north',220:'nottingham-southwest-curtain-wall-north'}[rec['node']];canonical.hide_render=True;canonical.hide_viewport=True
  sums=[0.0]*len(rec['triangles']);source={'node':rec['node'],'path':rec['source'],'sha256':rec['sha256'],'baseline_defects':rec['baseline_defects'],'envelope_reconstructed':rec['envelope_reconstructed'],'triangles':[]}
  for config in rec['configs']:
   vertices=[];faces=[];provenance=[];lookup={}
   def vert(p,island):
    key=(island,)+tuple(round(v,4)for v in p)
    if key not in lookup:lookup[key]=len(vertices);vertices.append(rec['matrix'].inverted()@Vector(p))
    return lookup[key]
   for tri in rec['triangles']:
    poly=tri['points']
    for normal,offset,sign in config['cuts']:poly=clipped(poly,normal,offset,sign)
    ar=area(poly)
    if ar<1e-8:continue
    face=[vert(p,tri['island'])for p in poly];face=list(dict.fromkeys(face))
    if len(face)<3:continue
    faces.append(face);provenance.append({'original_polygon':tri['polygon'],'original_triangle':tri['triangle'],'clipped_area':ar});sums[tri['triangle']]+=ar
   mesh=bpy.data.meshes.new(config['id']);mesh.from_pydata(vertices,[],faces);mesh.update();bm=bmesh.new();bm.from_mesh(mesh)
   layer=bm.faces.layers.int.new('source_triangle_plus_one')
   for face,origin in zip(bm.faces,provenance):face[layer]=origin['original_triangle']+1
   boundary=[e for e in bm.edges if e.is_boundary];caps=bmesh.ops.holes_fill(bm,edges=boundary,sides=0)['faces'] if boundary and not baseline else []
   for face in caps:face[layer]=-1
   bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces))
   bmesh.ops.dissolve_degenerate(bm,dist=1e-4,edges=list(bm.edges))
   defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces)}
   if any(defects.values()) and not baseline:raise ValueError((config['id'],defects,[(tuple(e.verts[0].co),tuple(e.verts[1].co),len(e.link_faces)) for e in bm.edges if not e.is_manifold],[(f.calc_area(),[tuple(v.co) for v in f.verts],f[layer]) for f in bm.faces if f.calc_area()<1e-8]))
   caparea=sum(f.calc_area()for f in bm.faces if f[layer]==-1);bm.to_mesh(mesh);bm.free()
   obj=bpy.data.objects.new(config['id'],mesh);collection.objects.link(obj);obj.matrix_world=rec['matrix'];obj['source_node']=f"building-{rec['node']}";obj['projection_component']=config['id'];obj['asset_group']=config['asset'];obj['wall_partition_version']=1
   uv=mesh.uv_layers.new(name='Source projection');cos=math.cos(math.radians(35))
   for loop in mesh.loops:
    p=obj.matrix_world@mesh.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(p.x/2304,1-(-p.y*SIN-p.z*cos)/3520)
   report['components'].append({'id':config['id'],'asset_id':config['asset'],'source_node':obj['source_node'],'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'new_seam_cap_area_local':caparea,'validation':defects,'clipped_faces':provenance,'numerical_seam_cleanup_tolerance_world':0.0001,'geometry_sha256':hashlib.sha256(json.dumps({'vertices':[list(v.co) for v in mesh.vertices],'faces':[list(p.vertices) for p in mesh.polygons],'matrix':[list(row) for row in obj.matrix_world]},sort_keys=True).encode()).hexdigest()})
  for tri,total in zip(rec['triangles'],sums):
   original=area(tri['points']);residual=original-total
   if abs(residual)>max(1e-5,original*2e-6):raise ValueError(('area conservation',rec['node'],tri['triangle'],original,total))
   source['triangles'].append({'original_polygon':tri['polygon'],'original_triangle':tri['triangle'],'source_area':original,'sum_clipped_area':total,'residual':residual})
  report['sources'].append(source)
 out=R/'wall-partitions-v8';out.mkdir(exist_ok=True)
 previous_path=out/('baseline-partition-proof.json' if baseline else 'partition-proof.json')
 if previous_path.exists():
  previous=json.loads(previous_path.read_text());a={c['id']:c.get('geometry_sha256') for c in previous['components']};b={c['id']:c['geometry_sha256'] for c in report['components']};report['idempotence']={'same_geometry_as_previous_export':a==b}
 bpy.ops.wm.save_as_mainfile(filepath=str(out/('baseline-components.blend' if baseline else 'components.blend')));(out/('baseline-partition-proof.json' if baseline else 'partition-proof.json')).write_text(json.dumps(report,indent=2)+'\n');print('WALL_PARTITIONS_PASS',len(report['components']))

if __name__=='__main__':build()
