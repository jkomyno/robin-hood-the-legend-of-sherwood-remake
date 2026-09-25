"""Complete approved hall atlases without replacing source pixels or UVs.

Generated workers are sampled as donors on the same physical face. Their source
and generated contributions remain explicit in the final per-texel provenance.
"""
import hashlib,io,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(Path(__file__).parent),str(ROOT/'level-editor/refinement/blender'),str(ROOT/'level-editor/blender')]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,indent=2)+'\n')
def sample_donor(rgba,ownership,uv):
    """Sample only fully supported donor taps, reporting their source fraction."""
    h,w=ownership.shape;q=np.asarray(uv)*[w,h]-.5;low=np.floor(q).astype(int);f=q-low
    rgb=np.zeros((len(q),3));source=np.zeros(len(q));valid=np.ones(len(q),bool)
    for dx,dy,weight in [(0,0,(1-f[:,0])*(1-f[:,1])),(1,0,f[:,0]*(1-f[:,1])),(0,1,(1-f[:,0])*f[:,1]),(1,1,f[:,0]*f[:,1])]:
        x=np.clip(low[:,0]+dx,0,w-1);y=np.clip(low[:,1]+dy,0,h-1);flags=ownership[y,x]
        valid &= (weight<1e-8)|np.isin(flags,[1,2]);rgb+=rgba[y,x,:3]*weight[:,None];source+=(flags==1)*weight
    return rgb,valid,source

def triangle_samples(uv,size,padding=2):
    """Atlas triangle samples and nearest barycentric surface point for gutters."""
    a,b,c=np.asarray(uv)*size;lo=np.maximum(0,np.floor(np.minimum(np.minimum(a,b),c))-padding).astype(int);hi=np.minimum(size,np.ceil(np.maximum(np.maximum(a,b),c))+padding).astype(int)
    yy,xx=np.mgrid[lo[1]:hi[1],lo[0]:hi[0]];x=xx.ravel()+.5;y=yy.ravel()+.5
    det=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    if abs(det)<1e-12:return None
    u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/det;v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/det
    bary=np.column_stack([u,v,1-u-v]);score=bary.min(axis=1);clamped=np.maximum(bary,0);clamped/=clamped.sum(axis=1)[:,None]
    return xx.ravel(),yy.ravel(),clamped,score

def image_binding(obj,slot):
    mat=obj.data.materials[slot];images=[n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image];uvs=[n.uv_map for n in mat.node_tree.nodes if n.type=='UVMAP']
    if len(images)!=1 or len(uvs)!=1:raise ValueError('Ambiguous atlas binding '+obj.name)
    return images[0],obj.data.uv_layers[uvs[0]]

def geometry(obj):
    return dict(vertices=[list(v.co) for v in obj.data.vertices],faces=[list(f.vertices) for f in obj.data.polygons],matrix=[list(r) for r in obj.matrix_world],uv={u.name:[list(v.uv) for v in u.data] for u in obj.data.uv_layers},slots=[f.material_index for f in obj.data.polygons])

def donor_inventory(model,reports):
    import bpy
    from PIL import Image
    bpy.ops.wm.open_mainfile(filepath=str(model));bpy.context.view_layer.update()
    provenance={}
    for file in reports:
        for row in read(file)['objects']:
            if 'texel_provenance' in row:provenance.setdefault(row['object'],[]).append(row['texel_provenance'])
    result={}
    for name,entries in provenance.items():
        obj=bpy.data.objects[name];obj.data.calc_loop_triangles();images={};triangles={}
        for slot in {f.material_index for f in obj.data.polygons}:
            image,uv=image_binding(obj,slot);packed=hashlib.sha256(image.packed_file.data).hexdigest();uvhash=hashlib.sha256(json.dumps([list(v.uv) for v in uv.data]).encode()).hexdigest()
            matches=[r for r in entries if r['packed_image_sha256']==packed and r['uv_sha256']==uvhash]
            if len(matches)!=1:raise ValueError('Donor provenance binding missing '+name)
            row=matches[0];assert sha(row['path'])==row['sha256']
            rgba=np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1].copy()/255
            images[slot]=dict(rgba=rgba,ownership=np.load(row['path'])['ownership'])
            for tri in obj.data.loop_triangles:
                if tri.material_index==slot:triangles[tuple(tri.vertices)]=dict(face=tri.polygon_index,slot=slot,uv=np.array([list(uv.data[i].uv) for i in tri.loops]))
        result[name]=dict(vertices=np.array([list(v.co) for v in obj.data.vertices]),matrix=np.array(obj.matrix_world),images=images,triangles=triangles)
    return result

def source_tree(model,collection):
    import bpy
    from mathutils.bvhtree import BVHTree
    bpy.ops.wm.open_mainfile(filepath=str(model));bpy.context.view_layer.update();points=[];faces=[];owners=[]
    for obj in bpy.data.collections[collection].all_objects:
        if obj.type!='MESH' or obj.hide_render:continue
        offset=len(points);points.extend(obj.matrix_world@v.co for v in obj.data.vertices);obj.data.calc_loop_triangles()
        for tri in obj.data.loop_triangles:faces.append(tuple(offset+i for i in tri.vertices));owners.append((obj.name,tri.polygon_index))
    return BVHTree.FromPolygons(points,faces,all_triangles=True),owners

def same_source_hit(point,trees):
    from mathutils import Vector
    import math
    direction=Vector((0,-math.cos(math.radians(35)),math.sin(math.radians(35))));origin=Vector(point)+direction*100000
    hits=[]
    for tree,owners in trees:
        hit,_,index,_=tree.ray_cast(origin,-direction);hits.append((owners[index],hit) if index is not None else None)
    return hits[0] is not None and hits[1] is not None and hits[0][0]==hits[1][0] and (hits[0][1]-hits[1][1]).length<.01


def main(contract_path,out):
    from preserve_hall_contact_states import signature
    from render_slots import acquire
    acquire(slots=2)
    import bpy
    from PIL import Image
    contract=read(contract_path);workspace=Path(contract['source_workspace']);cfg=read(workspace/'workspace.json')
    states={s['state']:s for s in read(workspace/'inspection/state-models/manifest.json')['states']}
    for state,row in states.items():
        assert sha(row['model'])==row['model_sha256']==contract['states'][state]['source_model_sha256']
        assert sha(contract['states'][state]['protection_manifest'])==contract['states'][state]['protection_manifest_sha256']
    for state,row in contract['donors'].items():
        assert sha(row['worker'])==row['worker_sha256']
        assert {path:sha(path) for path in row['reports']}==row['report_sha256']
    donors={state:donor_inventory(Path(d['worker']),d['reports']) for state,d in contract['donors'].items()}
    camera_patch=None;shared_final={}
    if contract.get('shared_camera_repair'):
        patch=contract['shared_camera_repair']
        for key in ('model','provenance','report'):assert sha(patch[key])==patch[key+'_sha256']
        patch_report=read(patch['report']);assert patch_report['status']=='PASS' and patch_report['model_sha256']==patch['model_sha256']
        patch_inventory=donor_inventory(Path(patch['model']),[patch['provenance']])
        shared_final={r['object']:dict(receiver=patch_inventory[r['object']],slot=r['material_slot'],uv_sha256=r['texel_provenance']['uv_sha256'],lineage=np.load(r['texel_provenance']['path'])['donor_source_weight']) for r in read(patch['provenance'])['objects']}
        assert len(patch_report['scope'])==1
        patch_name=next(iter(patch_report['scope']));assert patch_report['scope'][patch_name]==[1]
        patch_row=next(r for r in read(patch['provenance'])['objects'] if r['object']==patch_name)
        camera_patch=dict(name=patch_name,report=patch_report,receiver=patch_inventory[patch_name],uv_sha256=patch_row['texel_provenance']['uv_sha256'],slot=patch_row['material_slot'])
    trees=[source_tree(states[s]['model'],cfg['collection_name']) for s in ('covered','revealed')]
    results=[]
    requested=[sys.argv[sys.argv.index('--state')+1]] if '--state' in sys.argv else ['covered','revealed']
    assert set(requested)<=set(states)
    for state in requested:
        bpy.ops.wm.open_mainfile(filepath=states[state]['model']);bpy.context.view_layer.update();destination=out/state;destination.mkdir(parents=True,exist_ok=False)
        all_geometry={o.name:geometry(o) for o in bpy.data.objects if o.type=='MESH'};report=[]
        protections=read(contract['states'][state]['protection_manifest'])
        target_names={r['object'] for r in protections['objects']}
        outside_before={o.name:signature(o) for o in bpy.data.objects if o.type=='MESH' and o.name not in target_names}
        for entry in protections['objects']:
            obj=bpy.data.objects[entry['object']];slot=entry['slot'];image,uv=image_binding(obj,slot)
            for other in bpy.data.objects:
                if other.type!='MESH' or other==obj:continue
                for active_slot in {f.material_index for f in other.data.polygons}:
                    material=other.data.materials[active_slot] if active_slot<len(other.data.materials) else None
                    if material and material.use_nodes and any(n.type=='TEX_IMAGE' and n.image==image for n in material.node_tree.nodes):
                        raise ValueError('Completion atlas shared with another active receiver: '+other.name)
            assert hashlib.sha256(image.packed_file.data).hexdigest()==entry['packed_image_sha256']
            assert sha(entry['path'])==entry['sha256'];flags=np.load(entry['path'])['ownership'].copy();protected=flags==1
            original=np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1].copy();result=original.copy();h,w=flags.shape
            best=np.full((h,w),-np.inf);lineage=np.full((h,w),-1,np.float32);choice=np.zeros((h,w),np.uint8);fallback=np.zeros((h,w),bool)
            obj.data.calc_loop_triangles()
            for tri in obj.data.loop_triangles:
                if tri.material_index!=slot:continue
                samples=triangle_samples([list(uv.data[i].uv) for i in tri.loops],np.array([w,h]))
                if samples is None:continue
                xx,yy,bary,scores=samples;eligible=(~protected[yy,xx])&(scores>best[yy,xx]);xx,yy,bary,scores=xx[eligible],yy[eligible],bary[eligible],scores[eligible]
                if not len(xx):continue
                local=np.array([list(obj.data.vertices[i].co) for i in tri.vertices]);world=np.array([list(obj.matrix_world@obj.data.vertices[i].co) for i in tri.vertices]);points=bary@world
                use_covered=np.ones(len(xx),bool) if state=='covered' else np.array([same_source_hit(p,trees) for p in points])
                missing_covered=np.zeros(len(xx),bool)
                covered_receiver=donors['covered'].get(obj.name)
                if state=='revealed' and (covered_receiver is None or tuple(tri.vertices) not in covered_receiver['triangles']):
                    missing_covered=use_covered.copy();use_covered[:]=False
                for donor_state,select in [('covered',use_covered),('revealed',~use_covered)]:
                    if not select.any():continue
                    donor=donors[donor_state].get(obj.name)
                    if donor is None:continue
                    if not np.array_equal(donor['vertices'],np.array([list(v.co) for v in obj.data.vertices])) or not np.array_equal(donor['matrix'],np.array(obj.matrix_world)):raise ValueError('Donor geometry differs '+obj.name)
                    triangle=donor['triangles'].get(tuple(tri.vertices))
                    if triangle is None or triangle['face']!=tri.polygon_index:raise ValueError('Donor physical face differs')
                    data=donor['images'][triangle['slot']];rgb,valid,source_fraction=sample_donor(data['rgba'],data['ownership'],bary[select]@triangle['uv'])
                    if state=='revealed' and donor_state=='covered' and obj.name in shared_final:
                        final=shared_final[obj.name]
                        assert hashlib.sha256(json.dumps([list(v.uv) for v in uv.data]).encode()).hexdigest()==final['uv_sha256']
                        atlas=final['receiver']['images'][final['slot']];sx,sy=xx[select],yy[select];exact=atlas['ownership'][sy,sx]==2
                        rgb[exact]=atlas['rgba'][sy[exact],sx[exact],:3];source_fraction[exact]=final['lineage'][sy[exact],sx[exact]];valid[exact]=True
                    indices=np.flatnonzero(select)[valid];ax,ay=xx[indices],yy[indices]
                    result[ay,ax,:3]=np.rint(np.clip(rgb[valid],0,1)*255).astype(np.uint8);flags[ay,ax]=2;lineage[ay,ax]=source_fraction[valid];choice[ay,ax]=1 if donor_state=='covered' else 2;best[ay,ax]=scores[indices];fallback[ay,ax]=missing_covered[indices]
            shared_camera_counts=dict(transferred=0,protected=0,different_state_visibility=0)
            if state=='revealed' and camera_patch and obj.name==camera_patch['name']:
                assert hashlib.sha256(json.dumps([list(v.uv) for v in uv.data]).encode()).hexdigest()==camera_patch['uv_sha256']
                donor=camera_patch['receiver'];assert np.array_equal(donor['vertices'],np.array([list(v.co) for v in obj.data.vertices])) and np.array_equal(donor['matrix'],np.array(obj.matrix_world))
                data=donor['images'][camera_patch['slot']]
                for repair in camera_patch['report']['repairs']:
                    x,y=repair['atlas']
                    if protected[y,x]:shared_camera_counts['protected']+=1;continue
                    if not same_source_hit(repair['world'],trees):shared_camera_counts['different_state_visibility']+=1;continue
                    assert data['ownership'][y,x]==2
                    result[y,x,:3]=np.rint(data['rgba'][y,x,:3]*255).astype(np.uint8);flags[y,x]=2;lineage[y,x]=0;choice[y,x]=1;fallback[y,x]=False;shared_camera_counts['transferred']+=1
            assert np.array_equal(original[protected],result[protected]) and np.array_equal(original[:,:,3],result[:,:,3])
            image.pixels.foreach_set((result.astype(np.float32)/255).ravel());image.update();image.pack()
            path=destination/'provenance'/f'{len(report):03}.npz';path.parent.mkdir(exist_ok=True);np.savez_compressed(path,ownership=flags,donor_source_weight=lineage,donor_state=choice,revealed_fallback_missing_covered_receiver=fallback)
            report.append(dict(object=obj.name,material_slot=slot,shared_camera_repair=shared_camera_counts,protected_source_texels=int(protected.sum()),completion_texels=int((flags==2).sum()),source_alpha_exact=True,revealed_fallback_missing_covered_receiver_texels=int(fallback.sum()),protected_rgba8_sha256=hashlib.sha256(original[protected].tobytes()).hexdigest(),alpha8_sha256=hashlib.sha256(original[:,:,3].tobytes()).hexdigest(),source_protection=dict(path=contract['states'][state]['protection_manifest'],sha256=contract['states'][state]['protection_manifest_sha256']),donor_lineage_counts={'fully_generated':int(((flags==2)&(lineage==0)).sum()),'fully_donor_source':int(((flags==2)&(lineage==1)).sum()),'mixed':int(((flags==2)&(lineage>0)&(lineage<1)).sum())},texel_provenance=dict(path=str(path.resolve()),sha256=sha(path),packed_image_sha256=hashlib.sha256(image.packed_file.data).hexdigest(),uv_sha256=hashlib.sha256(json.dumps([list(v.uv) for v in uv.data]).encode()).hexdigest())))
        assert all_geometry=={o.name:geometry(o) for o in bpy.data.objects if o.type=='MESH'}
        assert outside_before=={name:signature(bpy.data.objects[name]) for name in outside_before}
        bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(destination/'model.blend'))
        bpy.ops.wm.open_mainfile(filepath=str(destination/'model.blend'));bpy.context.view_layer.update()
        assert all_geometry=={o.name:geometry(o) for o in bpy.data.objects if o.type=='MESH'}
        assert outside_before=={name:signature(bpy.data.objects[name]) for name in outside_before}
        for row in report:
            image,uv=image_binding(bpy.data.objects[row['object']],row['material_slot']);proof=row['texel_provenance']
            assert hashlib.sha256(image.packed_file.data).hexdigest()==proof['packed_image_sha256']
            assert hashlib.sha256(json.dumps([list(v.uv) for v in uv.data]).encode()).hexdigest()==proof['uv_sha256']
            flags=np.load(proof['path'])['ownership'];pixels=np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1]
            assert hashlib.sha256(pixels[flags==1].tobytes()).hexdigest()==row['protected_rgba8_sha256']
            assert hashlib.sha256(pixels[:,:,3].tobytes()).hexdigest()==row['alpha8_sha256']
        witnesses={}
        for name,proof_path in [('Castle main hall and revealed interior / Structural volume 504',workspace/'inspection/state-models'/state/'native709-taps.json'),('building-505__castle-hall-northwest-contact',workspace/'inspection/contact-material-provenance.json')]:
            row=next(r for r in report if r['object']==name);flags=np.load(row['texel_provenance']['path'])['ownership'];proof=read(proof_path)
            assert all(flags[t['atlas'][1],t['atlas'][0]]==1 for pixel in proof['pixels'] for t in pixel['taps'] if t['weight']>1e-8)
            witnesses[name]=dict(count=len(proof['pixels']),all_source_taps_exact=True,original_proof=str(proof_path),original_proof_sha256=sha(proof_path))
        shared_consistency=None
        if state=='revealed' and (out/'covered/provenance.json').exists():
            covered_report=read(out/'covered/provenance.json')
            assert sha(out/'covered/model.blend')==covered_report['model_sha256']
            revealed_pixels={row['object']:np.array(Image.open(io.BytesIO(bytes(image_binding(bpy.data.objects[row['object']],row['material_slot'])[0].packed_file.data))).convert('RGBA'))[::-1].copy() for row in report}
            bpy.ops.wm.open_mainfile(filepath=str(out/'covered/model.blend'));bpy.context.view_layer.update()
            consistency=[]
            covered_objects={r['object']:r for r in covered_report['objects']}
            for row in report:
                name=row['object']
                if name not in covered_objects:continue
                other=covered_objects[name]
                assert row['texel_provenance']['uv_sha256']==other['texel_provenance']['uv_sha256']
                current=np.load(row['texel_provenance']['path']);prior=np.load(other['texel_provenance']['path'])
                shared=(current['ownership']==2)&(current['donor_state']==1)&(prior['ownership']==2)
                image,_=image_binding(bpy.data.objects[name],other['material_slot']);covered_pixels=np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1]
                count=int(shared.sum());mismatch=int(np.count_nonzero(np.any(covered_pixels[shared]!=revealed_pixels[name][shared],axis=1)))
                assert mismatch==0,'Shared unknown surface colors differ: '+name
                consistency.append(dict(object=name,shared_completion_texels=count,mismatches=mismatch))
            shared_consistency=dict(status='PASS',covered_model_sha256=covered_report['model_sha256'],objects=consistency)
        write(destination/'workspace.json',cfg)
        write(destination/'provenance.json',dict(objects=report,model_sha256=sha(destination/'model.blend'),contract_sha256=sha(contract_path),status='PASS',shared_surface_consistency=shared_consistency,geometry_uv_exact=True,source_rgba_alpha_exact=True,outside_objects_unchanged=len(outside_before),outside_object_signatures=outside_before,witnesses=witnesses))
        results.append(dict(state=state,model_sha256=sha(destination/'model.blend')))
    name='reconstruction-'+requested[0]+'.json' if len(requested)==1 else 'reconstruction.json'
    write(out/name,dict(states=results,status='awaiting-independent-QA'))
if __name__=='__main__':
    a=sys.argv[sys.argv.index('--')+1:];main(Path(a[0]).resolve(),Path(a[1]).resolve())
