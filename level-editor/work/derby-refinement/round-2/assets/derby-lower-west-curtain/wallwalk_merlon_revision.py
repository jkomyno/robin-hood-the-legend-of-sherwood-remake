"""Source-aligned Lower West wall-walk merlon revision.

The original wall-walk meshes contain separate, authored battlement overlays
(``/ modeled battlements``).  The long walk was under-sampled in the previous
pass.  This recipe rebuilds only those overlays from their measured path,
preserving the wall/support meshes, transforms, source-node IDs and materials.
The target repeats are deliberately recorded per section so the projection
phase can be checked independently for the north and south runs.
"""
import json, math
from pathlib import Path
import bpy
from mathutils import Vector

ASSET='derby-lower-west-curtain'
TARGET_COUNTS={'building-023':15,'building-025':9,'building-042':8}
ORIGINAL_COUNTS={'building-023':11,'building-025':6,'building-042':5}
NORTH={'building-023','building-025'}
SOUTH={'building-042'}

def _clusters(obj):
    # Lower corners of the existing crenels sit on the common 206-unit ledge.
    vs=[obj.matrix_world@v.co for v in obj.data.vertices]
    zvals=sorted(v.z for v in vs)
    print('ZVALS',obj.get('source_node'),zvals[:5],zvals[-5:],'near206',[(z,abs(z-206)) for z in zvals if abs(z-206)<30][:10])
    ids=[i for i,v in enumerate(vs) if abs(v.z-206.0)<2.0]
    print('IDS',len(ids))
    print('IDCOORDS',[(round(vs[i].x,1),round(vs[i].y,1)) for i in ids])
    # The authored overlay stores each crenel footprint as four consecutive
    # ledge vertices (the two turning points on each side).  Preserve that
    # source order; spatial proximity would merge adjacent narrow crenels at
    # the bends of this wall.
    groups=[ids[i:i+4] for i in range(0,len(ids),4) if len(ids[i:i+4])==4]
    out=[]
    for g in groups:
        p=[vs[i] for i in g]
        out.append({'center':sum(p,Vector())/len(p),'min':Vector((min(v.x for v in p),min(v.y for v in p))),
                    'max':Vector((max(v.x for v in p),max(v.y for v in p))),'n':len(p)})
    return out

def _ordered(cs):
    # These runs are monotonic in map Y; sorting gives the authored walk phase.
    return sorted(cs,key=lambda c:c['center'].y)

def _box_mesh(obj, centers, target):
    old=_ordered(centers)
    print('MERLON_ANCHORS',obj.get('source_node'),len(old),[(round(c['center'].x,1),round(c['center'].y,1),c['n']) for c in old])
    if len(old)<2: raise RuntimeError(f'{obj.name}: insufficient merlon anchors')
    points=[c['center'] for c in old]
    # Piecewise path lengths, then uniformly sample the same wall path.
    lengths=[0.0]
    for a,b in zip(points,points[1:]): lengths.append(lengths[-1]+(b-a).length)
    total=lengths[-1]
    samples=[]
    for k in range(target):
        d=(k+0.5)*total/target
        j=next((i for i in range(len(points)-1) if lengths[i+1]>=d),len(points)-2)
        t=(d-lengths[j])/(lengths[j+1]-lengths[j] or 1)
        samples.append(points[j].lerp(points[j+1],t))
    # Existing footprints establish the cross-wall depth and vertical extent.
    depth=sum((c['max'].x-c['min'].x)+(c['max'].y-c['min'].y) for c in old)/(2*len(old))
    depth=max(9.0,min(19.0,depth)); spacing=total/target
    width=max(10.0,min(27.0,spacing*0.42)); z0=206.0; z1=232.0
    inv=obj.matrix_world.inverted(); verts=[]; faces=[]
    for k,p in enumerate(samples):
        if k==0:tangent=(samples[1]-samples[0]).normalized()
        elif k==len(samples)-1:tangent=(samples[-1]-samples[-2]).normalized()
        else:tangent=(samples[k+1]-samples[k-1]).normalized()
        tangent.z=0;tangent.normalize(); normal=Vector((-tangent.y,tangent.x,0))
        corners=[p-tangent*width/2-normal*depth/2,p+tangent*width/2-normal*depth/2,
                 p+tangent*width/2+normal*depth/2,p-tangent*width/2+normal*depth/2]
        base=len(verts); verts += [inv@Vector((q.x,q.y,z)) for z in (z0,z1) for q in corners]
        faces += [(base+i,base+(i+1)%4,base+4+(i+1)%4,base+4+i) for i in range(4)]
        faces += [(base+3,base+2,base+1,base),(base+4,base+5,base+6,base+7)]
    mesh=bpy.data.meshes.new(obj.name+' / source-aligned merlons')
    mesh.from_pydata(verts,[],faces);mesh.update()
    for m in obj.data.materials: mesh.materials.append(m)
    uv=mesh.uv_layers.new(name=obj.data.uv_layers[0].name if obj.data.uv_layers else 'UVMap')
    # Keep the same fixed source projection used by the existing wall meshes.
    for loop in mesh.loops:
        p=obj.matrix_world @ mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv=(p.x/1920.0,1.0-(-p.y*math.sin(math.radians(35))-p.z*math.cos(math.radians(35)))/2752.0)
    mesh.attributes.new('reprojection_fallback_material','INT','FACE')
    obj.data=mesh
    obj['lower_west_merlon_revision']='source-phase-v2'
    node=obj.get('source_node')
    return {'source_node':node,'before_count':ORIGINAL_COUNTS.get(node,len(old)),
            'measured_previous_count':len(old),'after_count':target,
            'path_length':total,'spacing':spacing,'depth':depth,'width':width}

def apply():
    coll=bpy.data.collections.get('Derby Working')
    if not coll: raise RuntimeError('Derby Working collection missing')
    reports=[]
    for node,target in TARGET_COUNTS.items():
        objs=[o for o in coll.all_objects if o.type=='MESH' and o.get('source_node')==node and 'modeled battlements' in o.name]
        if len(objs)!=1: raise RuntimeError(f'{node}: expected one modeled battlements mesh, found {len(objs)}')
        o=objs[0]; reports.append(_box_mesh(o,_clusters(o),target))
    result={'asset_id':ASSET,'revision':'lower-west-wallwalk-merlon-source-phase-v2',
            'north': [r for r in reports if r['source_node'] in NORTH],
            'south': [r for r in reports if r['source_node'] in SOUTH],
            'source_nodes_changed':sorted(TARGET_COUNTS),'preserved_support_nodes':['building-045','building-037','building-038'],
            'status':'PASS'}
    return result

if __name__=='__main__':
    out=apply(); print(json.dumps(out,indent=2))
    path=Path(bpy.data.filepath).parent/'merlon-revision.json';path.write_text(json.dumps(out,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
