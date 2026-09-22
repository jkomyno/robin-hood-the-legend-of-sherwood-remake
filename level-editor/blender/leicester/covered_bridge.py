"""Measured timber bridge with independent patch003 front covers and receivers.

Two windows in each wall, three visible roof battens, five revealed rail posts.
The rear wall and rear roof slope remain when front wall/roof are removed.
Concealed beam depth and end contacts inside adjacent towers are hypotheses.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector

ASSET='leicester-tower-covered-bridge'
PATCH='patch-003'
NODES={183,212,213,214,215}
TAG='leicester-covered-bridge-v1'
FRONT=Vector((1705.,-1589.,0))
ALONG=Vector((190.,-105.,0))
ACROSS=Vector((34.,61.,0))
FLOOR=268.57
EAVE=325.
RIDGE=377.25


def signature(obj):
    return hashlib.sha256(json.dumps({'v':[list(v.co) for v in obj.data.vertices],
        'f':[list(f.vertices) for f in obj.data.polygons]},sort_keys=True).encode()).hexdigest()


class Mesh:
    def __init__(self):self.vertices=[];self.faces=[]
    def prism(self,polygon,offset):
        start=len(self.vertices);n=len(polygon)
        self.vertices.extend(Vector(p) for p in polygon)
        self.vertices.extend(Vector(p)+Vector(offset) for p in polygon)
        self.faces.extend([tuple(start+i for i in reversed(range(n))),tuple(start+n+i for i in range(n))])
        self.faces.extend((start+i,start+(i+1)%n,start+(i+1)%n+n,start+i+n) for i in range(n))
    def beam(self,a,b,width=3.,depth=None):
        a,b=Vector(a),Vector(b);direction=(b-a).normalized()
        ref=Vector((0,0,1)) if abs(direction.z)<.9 else Vector((1,0,0))
        side=direction.cross(ref).normalized()*width/2
        up=direction.cross(side).normalized()*(depth or width)/2
        self.prism([a-side-up,a+side-up,a+side+up,a-side+up],b-a)


def point(u,v,z):
    return FRONT+u*ALONG+v*ACROSS+Vector((0,0,z))


def wall(mesh,v,windows):
    """One closed gridded wall shell with open window cells and no inner faces."""
    us=sorted({0.,1.,*(edge for window in windows for edge in window)})
    zs=[FLOOR,291.,315.,EAVE]
    occupied={(i,j) for i in range(len(us)-1) for j in range(len(zs)-1)
              if not(j==1 and any(a<=us[i] and us[i+1]<=b for a,b in windows))}
    verts={}
    normal=Vector((-ALONG.y,ALONG.x,0)).normalized()*3.
    def index(i,j,side):
        key=(i,j,side)
        if key not in verts:
            verts[key]=len(mesh.vertices);mesh.vertices.append(point(us[i],v,zs[j])+normal*side)
        return verts[key]
    for i,j in sorted(occupied):
        mesh.faces.extend([(index(i,j,0),index(i+1,j,0),index(i+1,j+1,0),index(i,j+1,0)),
                           (index(i,j+1,1),index(i+1,j+1,1),index(i+1,j,1),index(i,j,1))])
        for neighbor,ends in [((i,j-1),((i,j),(i+1,j))),((i+1,j),((i+1,j),(i+1,j+1))),
                              ((i,j+1),((i+1,j+1),(i,j+1))),((i-1,j),((i,j+1),(i,j)))]:
            if neighbor not in occupied:
                a,b=ends;mesh.faces.append((index(*a,0),index(*b,0),index(*b,1),index(*a,1)))


def geometry(node,component):
    m=Mesh()
    if node==183:
        m.prism([point(.02,.08,FLOOR),point(.92,.08,FLOOR),point(.92,.96,FLOOR),point(.02,.96,FLOOR)],(0,0,-7.))
    elif node==212 and component=='front-cover':
        windows=[(.30,.43),(.51,.64)]
        wall(m,0,windows)
        for u in [.06,.28,.49,.70,.90]:m.beam(point(u,-.035,FLOOR),point(u,-.035,EAVE),3.2)
        for left,right in windows:
            # Visible shutters tilt outwards from the opening's upper edge.
            a=point(left,-.055,315.);b=point(right,-.055,315.)
            m.prism([a,b,b+Vector((-4,-7,-12)),a+Vector((-4,-7,-12))],(0,0,-1.8))
    elif node==212 and component=='front-rail':
        # Five tips counted in the revealed artwork at x1717,1759,1798,1838,1876.
        for x in [1717.,1759.,1798.,1838.,1876.]:
            u=(x-FRONT.x)/ALONG.x;m.beam(point(u,0,FLOOR-3),point(u,0,FLOOR+20),3.6)
        for z in [FLOOR+4,FLOOR+11]:m.beam(point(.065,0,z),point(.90,0,z),3.2,6.)
        m.beam(point(.70,0,FLOOR-3),point(.91,0,FLOOR-41),4.5,6.)
    elif node==213:
        # Mask318 has two apertures, around source x1761..1780 and1801..1819.
        wall(m,1,[(.116,.216),(.326,.421)])
        for u in [0,.10,.24,.31,.45,.72,1]:m.beam(point(u,.96,FLOOR),point(u,.96,EAVE),3.2)
    elif node in (214,215):
        # Extend the ridge's left end into the tower contact: visible cap starts
        # source x1705 rather than the short inherited x1723 envelope.
        lo,hi=-.09,1.01
        if node==214:
            polygon=[point(lo,0,EAVE),point(hi,0,EAVE),point(hi,.52,RIDGE),point(lo,.52,RIDGE)]
        else:
            polygon=[point(lo,.52,RIDGE),point(hi,.52,RIDGE),point(hi,1,EAVE),point(lo,1,EAVE)]
        m.prism(polygon,(0,0,-3.2))
        if node==214:
            for ridge_x in [1733.,1773.,1813.]:
                u=(ridge_x-FRONT.x-.52*ACROSS.x)/ALONG.x
                m.beam(point(u,0,EAVE+1.4),point(u,.52,RIDGE+1.4),3.,2.)
        else:m.beam(point(lo,.52,RIDGE+1),point(hi,.52,RIDGE+1),3.,3.)
    else:raise ValueError('Unsupported bridge component')
    return m


def install(obj,node,component):
    matrix=obj.matrix_world.copy();before=signature(obj);shape=geometry(node,component)
    mesh=bpy.data.meshes.new(obj.name+' measured timber')
    mesh.from_pydata([matrix.inverted()@v for v in shape.vertices],[],shape.faces)
    for material in obj.data.materials:mesh.materials.append(material)
    uv=mesh.uv_layers.new(name='Source fallback')
    si,co=math.sin(math.radians(35)),math.cos(math.radians(35))
    for loop in mesh.loops:
        x,y,z=shape.vertices[loop.vertex_index];uv.data[loop.index].uv=(x/3136,1-(-y*si-z*co)/1984)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    counts=dict(vertices=len(bm.verts),faces=len(bm.faces),nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
                degenerate_faces=sum(f.calc_area()<1e-7 for f in bm.faces))
    if counts['nonmanifold_edges'] or counts['degenerate_faces']:raise ValueError(str(counts))
    bm.to_mesh(mesh);bm.free();mesh.update();old=obj.data;obj.data=mesh
    if old.users==0:bpy.data.meshes.remove(old)
    obj['projection_component']=component;obj['reveal_component_patch_id']=PATCH
    obj['reveal_component_role']='removable-cover' if component in ('front-cover','front-roof') else 'interior-wall' if node==213 else 'interior-floor' if node==183 else 'retained-shell'
    obj['covered_bridge_recipe']=TAG
    if obj.matrix_world!=matrix:raise ValueError('Transform changed')
    return dict(source_node=obj['source_node'],projection_component=component,topology=counts,
                before_geometry_sha256=before,after_geometry_sha256=signature(obj),world_transform_drift=0)


def selector(obj):return {'source_node':obj['source_node'],'projection_component':obj['projection_component'],'patch_id':PATCH}

def receiver(obj):return {'source_node':obj['source_node'],'projection_components':[obj['projection_component']],'patch_id':PATCH}



def prepare_masks(base_manifest, revealed_source, destination):
    """Declare the bridge's interior layer before freezing a new workspace."""
    base_manifest=Path(base_manifest).resolve();destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError(destination)
    data=json.loads(base_manifest.read_text())
    data['mask_inventory']=str((base_manifest.parent/data['mask_inventory']).resolve(strict=True))
    owned={f'building-{n:03}' for n in NODES}
    exterior=data['projections']['exterior']['assignments']
    exterior[:]=[r for r in exterior if r.get('source_node') not in owned]
    for node in sorted(owned):
        exterior.append(dict(source_node=node,mask_indices=[278,279],reviewed=True,
            evidence='Native278/279 full covered bridge silhouette; exact part allocation determined by source-camera first-hit depth.'))
    data['projections']['interior-'+PATCH]={
        'source_sha256':hashlib.sha256(Path(revealed_source).read_bytes()).hexdigest(),
        'state':'Patch003 bridge front cover removed; retained rear wall and roof, walkway and foreground handrail.',
        'assignments':[dict(source_node=node,mask_indices=[278,279],reviewed=True,
             evidence='Initial bridge node envelope; recipe partitions native309 rail and318 retained wall/roof before modified projection.')
                       for node in sorted(owned)]}
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(data,indent=2)+'\n')
    return str(destination)


def update_evidence(workspace,config,parts):
    from refinement_workspace import initialize_working_projection
    path=Path(initialize_working_projection(workspace));manifest=json.loads(path.read_text())
    review=manifest['projection_reviews'][PATCH];owned={f'building-{n:03}' for n in NODES}
    covers=[o for o in parts if o['reveal_component_role']=='removable-cover']
    inside=[o for o in parts if o not in covers]
    for key,values in [('receiver_nodes',{o['source_node'] for o in inside}),('partial_cover_nodes',{'building-212','building-214'})]:
        review[key]=sorted((set(review[key])-owned)|values)
    review['exclude_occluder_components']=[s for s in review['exclude_occluder_components'] if s['source_node'] not in owned]+[selector(o) for o in covers]
    for label,objects in [('exterior',[o for o in parts if o['projection_component']!='front-rail' and o['source_node']!='building-183']),('interior-'+PATCH,inside)]:
        old=review['receiver_components'].get(label,[])
        review['receiver_components'][label]=[s for s in old if s['source_node'] not in owned]+[receiver(o) for o in objects]
    for state,hidden in [('covered',[o for o in inside if o['projection_component'] in ('front-rail','walkway')]),('revealed',covers)]:
        visibility=review['render_visibility'][state]
        visibility['hidden_nodes']=[n for n in visibility['hidden_nodes'] if n not in owned]
        visibility['hidden_components']=[s for s in visibility['hidden_components'] if s['source_node'] not in owned]+[selector(o) for o in hidden]
    review['geometry_ready']=False
    note='Bridge front wall/roof removed; back roof, two-window rear wall, walkway and five-post rail retained. Source-paired review pending.'
    if note not in review['render_visibility']['limitations']:review['render_visibility']['limitations'].append(note)
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    mask_path=Path(config['source_mask_manifest']);masks=json.loads(mask_path.read_text())
    for label in ('exterior','interior-'+PATCH):
        rows=masks['projections'][label]['assignments'];rows[:]=[r for r in rows if r.get('source_node') not in owned]
        for obj in parts:
            component=obj['projection_component'];node=int(obj['source_node'][9:])
            accepted=[278,279] if label=='exterior' else [309] if component=='front-rail' else [318] if node in (213,215) else [278,279]
            rejected=[309,318] if label!='exterior' and node==183 else []
            rows.append(dict(source_node=obj['source_node'],projection_component=component,mask_indices=accepted,
                exclude_mask_indices=rejected,reviewed=True,exclusions_reviewed=True,
                exclusion_reason='Revealed floor excludes native foreground rail and retained back-wall/roof ownership.',
                evidence='Paired covered/revealed crop1680,550..1950,830; native278/279 cover,309 five-post rail,318 rear wall/two holes and retained roof.'))
    mask_path.write_text(json.dumps(masks,indent=2)+'\n')


def run(workspace):
    workspace=Path(workspace).resolve();config=json.loads((workspace/'workspace.json').read_text())
    if config['asset_id']!=ASSET or Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise ValueError('Open owned bridge model')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from refinement_workspace import validate
    validate(workspace)
    collection=bpy.data.collections[config['collection_name']]
    originals={int(o['source_node'][9:]):o for o in collection.all_objects if o.type=='MESH'
               and o.get('asset_group')==ASSET and not o.get('covered_bridge_added')}
    if set(originals)!=NODES:raise ValueError('Bridge canonical inventory mismatch')
    parts=[];records=[]
    for node,component in [(183,'walkway'),(212,'front-cover'),(213,'rear-wall'),(214,'front-roof'),(215,'rear-roof')]:
        obj=originals[node];parts.append(obj);records.append(install(obj,node,component))
    rails=[o for o in collection.all_objects if o.get('asset_group')==ASSET and o.get('covered_bridge_added')]
    if len(rails)>1:raise ValueError('Duplicate bridge rails')
    if rails:rail=rails[0]
    else:
        rail=originals[212].copy();rail.data=originals[212].data.copy();collection.objects.link(rail)
        rail.name=originals[212].name+' / revealed rail';rail['covered_bridge_added']=True
    records.append(install(rail,212,'front-rail'));parts.append(rail)
    hashes=[signature(o) for o in parts]
    for obj in parts:install(obj,int(obj['source_node'][9:]),obj['projection_component'])
    if hashes!=[signature(o) for o in parts]:raise ValueError('Recipe not idempotent')
    update_evidence(workspace,config,parts);validate(workspace)
    report=dict(recipe=TAG,objects=records,idempotence='PASS',window_count_front=2,window_count_rear=2,
        revealed_post_count=5,visible_roof_batten_count=3,projection_status='STALE; regenerate eight fixed views and paired states',
        approval_status='refinement-in-progress',texture_generation='not-started',limitations=[
            'Hidden wall/roof thickness, square beam sections and contacts inside towers are inferred.',
            'Individual plank seams remain source detail; window apertures, shutters, posts and roof battens are geometry.',
            'Repeated framing members intersect at structural contacts; each member is closed/manifold.',
            'Back roof remains through reveal; paired native-mask and source-textured review must confirm the retained strip and front cover boundary.'])
    (workspace/'inspection').mkdir(exist_ok=True);(workspace/'inspection/covered-bridge-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);print(json.dumps(run(args.workspace)))
