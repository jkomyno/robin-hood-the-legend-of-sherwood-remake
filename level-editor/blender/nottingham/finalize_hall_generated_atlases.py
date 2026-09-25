"""Finalize preserved hall atlases with exact scoped camera repairs and donor tags."""
import sys,json,hashlib,io,math,shutil
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(Path(__file__).parent),str(ROOT/'level-editor/refinement/blender'),str(ROOT/'level-editor/blender')]
from reconstruct_hall_generated_states import sha,read,write,image_binding,geometry
from preserve_hall_contact_states import signature

def taps(uv,size):
    q=np.asarray(uv)*size-.5;lo=np.floor(q).astype(int);f=q-lo
    return [(int(lo[0]+dx),int(lo[1]+dy),float(weight)) for dx,dy,weight in [(0,0,(1-f[0])*(1-f[1])),(1,0,f[0]*(1-f[1])),(0,1,(1-f[0])*f[1]),(1,1,f[0]*f[1])] if weight>1e-8]

def main(source,destination,experiment,repair=False):
    import bpy
    from PIL import Image
    from mathutils import Vector,Matrix
    from mathutils.bvhtree import BVHTree
    from generated_visibility import bounded_faces,far_plane,bounded_origin,visible_sample
    from texture_camera import orthographic_extents
    from project_reviewed_texture import _read,_reconcile
    assert not destination.exists()
    provenance=read(source/'provenance.json');assert sha(source/'model.blend')==provenance['model_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(source/'model.blend'));bpy.context.view_layer.update()
    before={o.name:signature(o) for o in bpy.data.objects if o.type=='MESH'};geo={o.name:geometry(o) for o in bpy.data.objects if o.type=='MESH'}
    destination.mkdir(parents=True);rows=[];repairs=[];changed_object=None
    manifest=read(experiment/'views.json'); generated_meta={}
    for state in ('covered','revealed'):
        folder=experiment.parent/state
        donor=folder/('bake-donor-v1' if state=='covered' else 'bake-donor-v2')
        if (donor/'validation.json').exists():
            v=read(donor/'validation.json');assert sha(v['generated_image'])==v['generated_sha256']
            generated_meta[state]=dict(reconciliation_reference=v.get('reconciliation_reference'),reconciliation_reference_sha256=v.get('reconciliation_reference_sha256'),generated_source_sha256=v['generated_sha256'],generated_image=v['generated_image'],generated_camera_manifest=str(folder/'views.json'),generated_camera_manifest_sha256=sha(folder/'views.json'),generated_approved_input_sha256=sha(folder/'input.png'))
    repair_targets={};tree=None
    if repair:
        hits=read(source/'coverage/center-ray-classification.json')['views'][2]['unfilled_center_hits']
        name='Castle main hall and revealed interior / Structural volume 529';assert len(hits)==15
        assert all(h['object']==name and h['face']==1 and h['material_slot']==4 for h in hits)
        row=next(r for r in provenance['objects'] if r['object']==name);arr=np.load(row['texel_provenance']['path']);flags=arr['ownership'];H,W=flags.shape
        wanted={(x,y) for hit in hits for x,y,w in taps(hit['uv'],[W,H]) if flags[y,x]==0}
        obj=bpy.data.objects[name];image,uv=image_binding(obj,4);obj.data.calc_loop_triangles()
        for tri in obj.data.loop_triangles:
            if tri.polygon_index!=1:continue
            coords=np.array([list(uv.data[i].uv) for i in tri.loops]);basis=np.vstack([coords.T,np.ones(3)])
            for x,y in wanted:
                bary=np.linalg.solve(basis,np.array([(x+.5)/W,(y+.5)/H,1]))
                if bary.min()>=-1e-6:
                    world=bary@np.array([list(obj.matrix_world@obj.data.vertices[i].co) for i in tri.vertices]);repair_targets[(x,y)]=world
        assert set(repair_targets)==wanted,'Repair needs real same-face atlas texels, not inferred gutters'
        points=[];triangles=[];owners=[]
        for o in bpy.data.collections[manifest['collection_name']].all_objects:
            if o.type!='MESH' or o.hide_render:continue
            start=len(points);points.extend(o.matrix_world@v.co for v in o.data.vertices);o.data.calc_loop_triangles()
            for t in o.data.loop_triangles:triangles.append(tuple(start+i for i in t.vertices));owners.append((o.name,t.polygon_index))
        tree=BVHTree.FromPolygons(points,triangles,all_triangles=True)
        scoped=dict(manifest,texture_generated_bounded_visibility={name:[1]});assert bounded_faces(scoped,{name:len(obj.data.polygons)})=={(name,1)}
        mask=_read(experiment/'mask.png');generated=_read(generated_meta['covered']['generated_image']);reference=generated_meta['covered']['reconciliation_reference'];assert sha(reference)==generated_meta['covered']['reconciliation_reference_sha256'];generated=_reconcile(generated,manifest,_read(reference));height,width=mask.shape[:2];view=next(v for v in manifest['views'] if v['index']==2);matrix=Matrix(view['camera_matrix_world']);direction=matrix.to_3x3()@Vector((0,0,1));inverse=matrix.inverted();plane=far_plane(points,direction);normal=(obj.matrix_world.to_3x3().inverted().transposed()@obj.data.polygons[1].normal).normalized();assert normal.dot(direction)>.12
        for (x,y),world in repair_targets.items():
            p=Vector(world);local=inverse@p;horizontal,vertical=orthographic_extents(view);crop=view['crop'];px=crop['left']+(.5+local.x/horizontal)*crop['width'];py=height-crop['top']-(.5-local.y/vertical)*crop['height'];ix,iy=math.floor(px),math.floor(py)
            assert crop['left']<=ix<crop['left']+crop['width'] and height-crop['top']-crop['height']<=iy<height-crop['top']
            assert mask[iy,ix,3]<.5
            hit,_,index,_=tree.ray_cast(Vector(bounded_origin(p,direction,plane)),-direction);assert visible_sample(hit,p,owners[index] if index is not None else None,(name,1))
            old,_,oi,_=tree.ray_cast(p+direction*100000,-direction)
            fx,fy=px-.5,py-.5;x0,y0=math.floor(fx),math.floor(fy);ax,ay=fx-x0,fy-y0;x0=max(crop['left'],min(crop['left']+crop['width']-1,x0));y0=max(height-crop['top']-crop['height'],min(height-crop['top']-1,y0));x1=min(crop['left']+crop['width']-1,x0+1);y1=min(height-crop['top']-1,y0+1)
            color=(generated[y0,x0,:3]*(1-ax)+generated[y0,x1,:3]*ax)*(1-ay)+(generated[y1,x0,:3]*(1-ax)+generated[y1,x1,:3]*ax)*ay
            repairs.append(dict(atlas=[x,y],world=list(world),view=2,image_coordinate=[px,py],mask_alpha=float(mask[iy,ix,3]),facing=normal.dot(direction),bounded_hit=owners[index],bounded_error=(hit-p).length,legacy_error=(old-p).length if old else None,rgb8=np.rint(np.clip(color,0,1)*255).astype(int).tolist()))
        changed_object=name
    for i,row in enumerate(provenance['objects']):
        row=dict(row);proof=dict(row['texel_provenance']);assert sha(proof['path'])==proof['sha256'];arrays={k:v.copy() for k,v in np.load(proof['path']).items()};flags=arrays['ownership'];obj=bpy.data.objects[row['object']];image,uv=image_binding(obj,row['material_slot']);original=np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1].copy();pixels=original.copy()
        if row['object']==changed_object:
            for record in repairs:
                x,y=record['atlas'];assert flags[y,x]==0;pixels[y,x,:3]=record['rgb8'];flags[y,x]=2;arrays['donor_source_weight'][y,x]=0;arrays['donor_state'][y,x]=1
            allowed=np.zeros(flags.shape,bool)
            for x,y in repair_targets:allowed[y,x]=True
            assert np.array_equal(pixels[~allowed],original[~allowed]) and np.array_equal(pixels[:,:,3],original[:,:,3])
            image.pixels.foreach_set((pixels.astype(np.float32)/255).ravel());image.update();image.pack()
            row['completion_texels']=int((flags==2).sum());row['donor_lineage_counts']['fully_generated']+=len(repairs)
        path=destination/'provenance'/f'{i:03}.npz';path.parent.mkdir(exist_ok=True);np.savez_compressed(path,**arrays)
        proof.update(path=str(path.resolve()),sha256=sha(path),packed_image_sha256=hashlib.sha256(image.packed_file.data).hexdigest());row['texel_provenance']=proof
        lineage=[]
        for state,code in [('covered',1),('revealed',2)]:
            count=int(((flags==2)&(arrays['donor_state']==code)).sum())
            if count:assert state in generated_meta;lineage.append(dict(state=state,completion_texels=count,**generated_meta[state]))
        if lineage:
            primary=max(lineage,key=lambda r:r['completion_texels']);mat=obj.data.materials[row['material_slot']]
            for key in ('generated_source_sha256','generated_camera_manifest','generated_approved_input_sha256'):mat[key]=primary[key]
            mat['generated_donor_lineage']=json.dumps(lineage,sort_keys=True);mat['generated_provenance_sha256']=proof['sha256'];mat['generated_source_protection_manifest_sha256']=row['source_protection']['sha256'];row['generated_donor_lineage']=lineage
        rows.append(row)
    assert geo=={o.name:geometry(o) for o in bpy.data.objects if o.type=='MESH'}
    expected={o.name:signature(o) for o in bpy.data.objects if o.type=='MESH'}
    assert all(expected[name]==value for name,value in before.items() if name!=changed_object)
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(destination/'model.blend'));bpy.ops.wm.open_mainfile(filepath=str(destination/'model.blend'));bpy.context.view_layer.update()
    assert expected=={o.name:signature(o) for o in bpy.data.objects if o.type=='MESH'}
    for row in rows:
        image,uv=image_binding(bpy.data.objects[row['object']],row['material_slot']);assert hashlib.sha256(image.packed_file.data).hexdigest()==row['texel_provenance']['packed_image_sha256'];pixels=np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1];flags=np.load(row['texel_provenance']['path'])['ownership'];assert hashlib.sha256(pixels[flags==1].tobytes()).hexdigest()==row['protected_rgba8_sha256'];assert hashlib.sha256(pixels[:,:,3].tobytes()).hexdigest()==row['alpha8_sha256']
    if repair:
        flags=np.load(next(r for r in rows if r['object']==changed_object)['texel_provenance']['path'])['ownership'];assert all(flags[y,x] in (1,2) for hit in hits for x,y,w in taps(hit['uv'],[W,H]))
    provenance.update(objects=rows,model_sha256=sha(destination/'model.blend'),finalization=dict(source_model_sha256=sha(source/'model.blend'),source_provenance_sha256=sha(source/'provenance.json'),unchanged_other_mesh_material_image_uv_signatures={name:value for name,value in before.items() if name!=changed_object},geometry_uv_exact=True,source_alpha_exact=True,repair_texels=len(repairs),repaired_center_witnesses=15 if repair else 0))
    write(destination/'provenance.json',provenance);write(destination/'camera-repair.json',dict(status='PASS',model_sha256=provenance['model_sha256'],scope={changed_object:[1]} if repair else {},original_generated_image=generated_meta.get('covered'),manifest_sha256=sha(experiment/'views.json'),mask_sha256=sha(experiment/'mask.png'),repairs=repairs));shutil.copy2(source/'workspace.json',destination/'workspace.json');print(json.dumps(dict(status='PASS',model_sha256=provenance['model_sha256'],repair_texels=len(repairs))))
if __name__=='__main__':
    a=sys.argv[sys.argv.index('--')+1:];main(Path(a[0]).resolve(),Path(a[1]).resolve(),Path(a[2]).resolve(),'--repair-529' in a)
