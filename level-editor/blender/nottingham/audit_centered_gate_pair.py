"""Compose exact saved pair meshes and audit their disputed source domain."""
import sys,json,hashlib,math,collections,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from mathutils import Vector,Matrix
 from mathutils.bvhtree import BVHTree
 from mathutils.geometry import barycentric_transform
 from PIL import Image,ImageDraw
 from audit_stored_materials import run
 gate=WORK/'round-39/assets/nottingham-castle-gate-arch';tower=WORK/'round-43/assets/nottingham-castle-gate-east-tower';out=gate/'inspection/paired-v43';out.mkdir(exist_ok=True);asset='nottingham-castle-gateway-pair'
 bpy.ops.wm.open_mainfile(filepath=str(tower/'model.blend'));bpy.context.view_layer.update();recs={o.name:dict(vertices=[list(o.matrix_world@v.co)for v in o.data.vertices],visible=not o.hide_render)for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==tower.name}
 bpy.ops.wm.open_mainfile(filepath=str(gate/'model.blend'));bpy.context.view_layer.update();coll=bpy.data.collections['nottingham Working']
 for o in list(coll.all_objects):
  if o.get('asset_group')==gate.name:o['paired_original_asset']=gate.name;o['asset_group']=asset
  elif o.get('asset_group')==tower.name:o.hide_render=True
 with bpy.data.libraries.load(str(tower/'model.blend'),link=False)as(a,b):b.objects=list(recs)
 for name,o in zip(recs,b.objects):
  coll.objects.link(o);o.parent=None;o.matrix_world=Matrix.Identity(4)
  for v,p in zip(o.data.vertices,recs[name]['vertices']):v.co=p
  o['paired_original_asset']=tower.name;o['asset_group']=asset;o.hide_render=not recs[name]['visible'];o.hide_set(o.hide_render)
 bpy.context.view_layer.update();config=json.loads((gate/'workspace.json').read_text());config['asset_id']=asset;(out/'workspace.json').write_text(json.dumps(config,indent=2)+'\n')
 frames=copy.deepcopy(json.loads((gate/'modified/views.json').read_text()));frames['asset_id']=asset
 for r in frames['views']:r['ortho_scale']*=1.5
 (out/'views.json').write_text(json.dumps(frames,indent=2)+'\n');bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
 if '--atlas-only' not in sys.argv:run(out,out/'stored-materials',render=True,export=False,frame_manifest=out/'views.json')
 bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'));bpy.context.view_layer.update()
 objects=[o for o in coll.all_objects] if False else [o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==asset and not o.hide_render]
 verts=[];tris=[];records=[]
 for o in objects:
  o.data.calc_loop_triangles()
  for tri in o.data.loop_triangles:
   ps=[o.matrix_world@o.data.vertices[v].co for v in tri.vertices];tris.append(tuple(range(len(verts),len(verts)+3)));verts+=ps;records.append((o,tri,ps))
 tree=BVHTree.FromPolygons(verts,tris,all_triangles=True);s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));source=Image.open(gate/'reference/source.png').convert('RGB');counts=collections.Counter();rows=[];cache={};poly=[(966,1414),(980,1427),(981,1488),(966,1477)];domain=Image.new('L',source.size);ImageDraw.Draw(domain).polygon(poly,fill=255)
 mi=json.loads((tower/'source-masks.json').read_text());ip=Path(mi['mask_inventory']);inv=json.loads(ip.read_text());r=next(r for r in inv['masks']if r['index']==375);mask=Image.new('L',source.size);mask.paste(Image.open(ip.parent/r['png']).convert('L'),r['box_top_left'])
 crop=(950,1400,990,1500);im=source.crop(crop).resize((400,1000),Image.Resampling.NEAREST);draw=ImageDraw.Draw(im)
 for y in range(1414,1489):
  for x in range(966,982):
   if not domain.getpixel((x,y)):continue
   origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,n,i,d=tree.ray_cast(origin,-toward);row=dict(pixel=[x,y],native375=bool(mask.getpixel((x,y))))
   if i is None:key='no-receiver'
   else:
    o,tri,points=records[i];row.update(first_node=o.get('source_node'),first_asset=o.get('paired_original_asset'),material_index=tri.material_index);mat=o.data.materials[tri.material_index];tex=[node.image for node in mat.node_tree.nodes if node.type=='TEX_IMAGE' and node.image]if mat and mat.use_nodes else [];samples=[]
    for image in tex:
     if image.name not in cache:cache[image.name]=list(image.pixels)
     uvnodes=[q for q in mat.node_tree.nodes if q.type=='UVMAP'];layer=o.data.uv_layers[uvnodes[0].uv_map]if uvnodes else o.data.uv_layers.active;uv=[Vector((*layer.data[l].uv,0))for l in tri.loops];p=barycentric_transform(hit,*points,*uv);ix=min(image.size[0]-1,max(0,int(p.x*image.size[0])));iy=min(image.size[1]-1,max(0,int(p.y*image.size[1])));k=(iy*image.size[0]+ix)*4;rgba=cache[image.name][k:k+4];samples.append(dict(image=image.name,rgba=rgba,color_space=image.colorspace_settings.name))
    row['samples']=samples;known=any(max(q['rgba'][:3])-min(q['rgba'][:3])>1/255 for q in samples);key=('source-colored:'if known else 'neutral:')+str(o.get('source_node'))
   if not row['native375']:key='native-mask-fringe:'+key
   row['classification']=key;rows.append(row);counts[key]+=1
   if not key.startswith('source-colored:'):draw.rectangle(((x-crop[0])*10,(y-crop[1])*10,(x-crop[0])*10+5,(y-crop[1])*10+5),fill='red')
 im.save(out/'brown-source-atlas.png');report=dict(gate_model_sha256=sha(gate/'model.blend'),tower_model_sha256=sha(tower/'model.blend'),composite_model_sha256=sha(out/'model.blend'),actual_material_sheet_sha256=sha(out/'stored-materials/materials.png')if(out/'stored-materials/materials.png').exists()else None,domain_polygon=poly,counts=dict(counts),rows=rows);(out/'source-atlas.json').write_text(json.dumps(report,indent=2)+'\n')
 def boundary_distance(point,a,b):
  d=[b[i]-a[i]for i in range(2)];t=max(0,min(1,sum((point[i]-a[i])*d[i]for i in range(2))/sum(x*x for x in d)));return math.dist(point,[a[i]+t*d[i]for i in range(2)])
 fringe=[]
 for row in rows:
  if row['classification'].startswith('source-colored:'):continue
  distance=min(boundary_distance([q+.5 for q in row['pixel']],poly[i],poly[(i+1)%4])for i in range(4));fringe.append(dict(pixel=row['pixel'],classification=row['classification'],trace_boundary_distance=distance,reason='native mask excludes sample'if not row['native375']else 'sloping bottom contact or traced outer boundary'))
 assert max(r['trace_boundary_distance']for r in fringe if r['classification']=='neutral:building-333')<1
 assert max(r['trace_boundary_distance']for r in fringe if r['classification']=='neutral:building-337')<2
 (out/'source-atlas-classification.json').write_text(json.dumps(dict(status='PASS',atlas_sha256=sha(out/'source-atlas.json'),colored_core_samples=counts['source-colored:building-337'],uncolored_samples=fringe,interpretation='All native-positive uncolored samples remain within measured trace/contact uncertainty: arch less than one pixel; tower less than two pixels.'),indent=2)+'\n');print(dict(counts),flush=True)
if __name__=='__main__':main()
