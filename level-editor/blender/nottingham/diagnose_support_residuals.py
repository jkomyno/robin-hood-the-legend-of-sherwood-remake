"""Read-only UV triangle audit of unfilled physical atlas texels after support filtering."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import bpy
import numpy as np
from texture_experiment_paths import selected_experiment
cross=lambda a,b:a[...,0]*b[...,1]-a[...,1]*b[...,0]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for asset in sys.argv[sys.argv.index('--')+1:]:
 folder=selected_experiment(asset)/'bake-background-support-001'
 validation=json.loads((folder/'validation.json').read_text())
 bpy.ops.wm.open_mainfile(filepath=str(folder/'worker.blend'))
 records=[]
 for layer in validation['layers']:
  for entry in layer['objects']:
   obj=bpy.data.objects[entry['object']];proof=entry['texel_provenance']
   if sha(proof['path'])!=proof['sha256']:raise ValueError('Provenance drift')
   ownership=np.load(proof['path'])['ownership'];height,width=ownership.shape
   positions=np.array([tuple(obj.matrix_world@v.co) for v in obj.data.vertices])
   minimum=float(positions[:,2].min());mesh=obj.data;mesh.calc_loop_triangles()
   materials={poly.material_index for poly in mesh.polygons}
   if len(materials)!=1:raise ValueError('Ambiguous receiver material')
   material=obj.data.materials[next(iter(materials))]
   images=[n for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
   if len(images)!=1:raise ValueError('Ambiguous receiver image')
   node=images[0]
   if hashlib.sha256(node.image.packed_file.data).hexdigest()!=proof['packed_image_sha256']:raise ValueError('Packed image drift')
   links=node.inputs['Vector'].links
   if len(links)!=1 or links[0].from_node.type!='UVMAP':raise ValueError('Unsupported material UV binding')
   uv=mesh.uv_layers[links[0].from_node.uv_map].data;faces={}
   for tri in mesh.loop_triangles:
    coords=np.array([tuple(uv[i].uv) for i in tri.loops])*[width,height]
    lo=np.maximum(np.floor(coords.min(axis=0)).astype(int),0);hi=np.minimum(np.ceil(coords.max(axis=0)).astype(int),[width,height])
    if np.any(hi<=lo):continue
    yy,xx=np.mgrid[lo[1]:hi[1],lo[0]:hi[0]];points=np.stack([xx+.5,yy+.5],axis=-1)
    a,b,c=coords;den=cross(b-a,c-a)
    if abs(den)<1e-10:continue
    u=cross(points-a,c-a)/den;v=cross(b-a,points-a)/den
    inside=(u>=1e-7)&(v>=1e-7)&(u+v<=1-1e-7)
    ys,xs=yy[inside],xx[inside]
    world=(1-u[inside]-v[inside])[:,None]*positions[tri.vertices[0]]+u[inside,None]*positions[tri.vertices[1]]+v[inside,None]*positions[tri.vertices[2]]
    unknown=ownership[ys,xs]==0
    f=faces.setdefault(tri.polygon_index,dict(face=tri.polygon_index,interior_texels=0,class0_texels=0,class0_bottom4_texels=0,zmin=None,zmax=None))
    f['interior_texels']+=int(inside.sum());f['class0_texels']+=int(unknown.sum())
    f['class0_bottom4_texels']+=int((unknown&(world[:,2]<=minimum+4)).sum())
    if unknown.any():
     zs=world[unknown,2];f['zmin']=min(f['zmin'] if f['zmin'] is not None else float('inf'),float(zs.min()));f['zmax']=max(f['zmax'] if f['zmax'] is not None else -float('inf'),float(zs.max()))
   records.append(dict(object=obj.name,minimum_world_z=minimum,provenance_sha256=proof['sha256'],faces=[f for f in faces.values() if f['class0_texels']]))
 report=dict(status='DIAGNOSTIC-ONLY',model_sha256=sha(folder/'worker.blend'),validation_sha256=sha(folder/'validation.json'),method='Strictly interior UV triangle pixel centers; excludes atlas padding and triangle edges. Class zero means unfilled physical surface, not proof of camera visibility.',objects=records)
 (folder/'residual-physical-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
 print(asset,sum(f['class0_texels'] for o in records for f in o['faces']),flush=True)
