"""Complete only unsupported shared samples using a valid revealed face donor."""
import sys,io,json,hashlib,shutil
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(Path(__file__).parent),str(ROOT/'level-editor/refinement/blender'),str(ROOT/'level-editor/blender')]
from reconstruct_hall_generated_states import sha,read,write,donor_inventory,image_binding,geometry,triangle_samples,sample_donor
from preserve_hall_contact_states import signature

def fallback_selection(ownership,primary_valid,secondary_valid):
    """Fallback is restricted to unfilled texels with no supported primary."""
    return (np.asarray(ownership)==0)&~np.asarray(primary_valid,dtype=bool)&np.asarray(secondary_valid,dtype=bool)

def main(source,destination,contract_path):
    import bpy
    from PIL import Image
    from render_slots import acquire
    acquire(slots=2)
    assert not destination.exists();contract=read(contract_path);report=read(source/'provenance.json');assert sha(source/'model.blend')==report['model_sha256']
    for state,row in contract['donors'].items():
        assert sha(row['worker'])==row['worker_sha256'] and {p:sha(p) for p in row['reports']}==row['report_sha256']
    donors={state:donor_inventory(Path(row['worker']),row['reports']) for state,row in contract['donors'].items()}
    generation={}
    for state,row in contract['donors'].items():
        v=read(Path(row['worker']).parent/'validation.json');exp=Path(row['worker']).parents[1];assert sha(v['generated_image'])==v['generated_sha256'];generation[state]=dict(generated_source_sha256=v['generated_sha256'],generated_image=v['generated_image'],generated_camera_manifest=str(exp/'views.json'),generated_camera_manifest_sha256=sha(exp/'views.json'),generated_approved_input_sha256=sha(exp/'input.png'),reconciliation_reference=v.get('reconciliation_reference'),reconciliation_reference_sha256=v.get('reconciliation_reference_sha256'))
    bpy.ops.wm.open_mainfile(filepath=str(source/'model.blend'));bpy.context.view_layer.update();before={o.name:signature(o) for o in bpy.data.objects if o.type=='MESH'};geo={o.name:geometry(o) for o in bpy.data.objects if o.type=='MESH'};destination.mkdir(parents=True);rows=[];changes=[]
    for i,row in enumerate(report['objects']):
        row=dict(row);proof=dict(row['texel_provenance']);assert sha(proof['path'])==proof['sha256'];arrays={k:v.copy() for k,v in np.load(proof['path']).items()};flags=arrays['ownership'];initial=flags.copy();obj=bpy.data.objects[row['object']];image,uv=image_binding(obj,row['material_slot']);original=np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1].copy();pixels=original.copy();h,w=flags.shape;best=np.full((h,w),-np.inf);new=np.zeros((h,w),bool);witnesses=[]
        revealed=donors['revealed'].get(obj.name);covered=donors['covered'].get(obj.name)
        if revealed is not None:
            assert np.array_equal(revealed['vertices'],np.array([list(v.co) for v in obj.data.vertices])) and np.array_equal(revealed['matrix'],np.array(obj.matrix_world));obj.data.calc_loop_triangles()
            if covered is not None:assert np.array_equal(covered['vertices'],revealed['vertices']) and np.array_equal(covered['matrix'],revealed['matrix'])
            for tri in obj.data.loop_triangles:
                if tri.material_index!=row['material_slot']:continue
                samples=triangle_samples([list(uv.data[j].uv) for j in tri.loops],np.array([w,h]))
                if samples is None:continue
                xx,yy,bary,score=samples;eligible=(initial[yy,xx]==0)&(score>best[yy,xx]);xx,yy,bary,score=xx[eligible],yy[eligible],bary[eligible],score[eligible]
                if not len(xx):continue
                triangle=revealed['triangles'].get(tuple(tri.vertices))
                if triangle is None:continue
                assert triangle['face']==tri.polygon_index;data=revealed['images'][triangle['slot']];rgb,valid,lineage=sample_donor(data['rgba'],data['ownership'],bary@triangle['uv']);covered_valid=np.zeros(len(xx),bool)
                if covered is not None and tuple(tri.vertices) in covered['triangles']:
                    ct=covered['triangles'][tuple(tri.vertices)];assert ct['face']==tri.polygon_index;cd=covered['images'][ct['slot']];_,covered_valid,_=sample_donor(cd['rgba'],cd['ownership'],bary@ct['uv'])
                select=fallback_selection(initial[yy,xx],covered_valid,valid);ax,ay=xx[select],yy[select]
                pixels[ay,ax,:3]=np.rint(np.clip(rgb[select],0,1)*255).astype(np.uint8);flags[ay,ax]=2;arrays['donor_source_weight'][ay,ax]=lineage[select];arrays['donor_state'][ay,ax]=2;arrays['revealed_fallback_missing_covered_receiver'][ay,ax]=False;best[ay,ax]=score[select];new[ay,ax]=True
                if select.any():witnesses.append(dict(face=int(tri.polygon_index),triangle_vertices=list(tri.vertices),count=int(select.sum()),fully_supported_revealed_taps=True,covered_taps_unsupported=True))
        assert np.array_equal(pixels[initial!=0],original[initial!=0]) and np.array_equal(pixels[:,:,3],original[:,:,3])
        if new.any():image.pixels.foreach_set((pixels.astype(np.float32)/255).ravel());image.update();image.pack()
        arrays['revealed_fallback_unsupported_covered_sample']=new;path=destination/'provenance'/f'{i:03}.npz';path.parent.mkdir(exist_ok=True);np.savez_compressed(path,**arrays);proof.update(path=str(path.resolve()),sha256=sha(path),packed_image_sha256=hashlib.sha256(image.packed_file.data).hexdigest());row.update(texel_provenance=proof,completion_texels=int((flags==2).sum()),revealed_fallback_unsupported_covered_sample_texels=int(new.sum()),donor_lineage_counts=dict(fully_generated=int(((flags==2)&(arrays['donor_source_weight']==0)).sum()),fully_donor_source=int(((flags==2)&(arrays['donor_source_weight']==1)).sum()),mixed=int(((flags==2)&(arrays['donor_source_weight']>0)&(arrays['donor_source_weight']<1)).sum())))
        lineage=[]
        for state,code in [('covered',1),('revealed',2)]:
            count=int(((flags==2)&(arrays['donor_state']==code)).sum())
            if count:lineage.append(dict(state=state,completion_texels=count,**generation[state]))
        if lineage:
            primary=max(lineage,key=lambda r:r['completion_texels']);mat=obj.data.materials[row['material_slot']]
            for key in ('generated_source_sha256','generated_camera_manifest','generated_approved_input_sha256'):mat[key]=primary[key]
            mat['generated_donor_lineage']=json.dumps(lineage,sort_keys=True);mat['generated_provenance_sha256']=proof['sha256'];row['generated_donor_lineage']=lineage
        rows.append(row)
        if new.any():changes.append(dict(object=obj.name,texels=int(new.sum()),face_witnesses=witnesses,old_allowed_rgba_sha256=hashlib.sha256(original[initial!=0].tobytes()).hexdigest(),old_ownership_path=report['objects'][i]['texel_provenance']['path']))
        print(obj.name,int(new.sum()),flush=True)
    assert geo=={o.name:geometry(o) for o in bpy.data.objects if o.type=='MESH'};changed={r['object'] for r in changes};expected={o.name:signature(o) for o in bpy.data.objects if o.type=='MESH'};assert all(expected[name]==s for name,s in before.items() if name not in changed)
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(destination/'model.blend'));bpy.ops.wm.open_mainfile(filepath=str(destination/'model.blend'));bpy.context.view_layer.update();assert expected=={o.name:signature(o) for o in bpy.data.objects if o.type=='MESH'}
    change_by_name={r['object']:r for r in changes}
    for row in rows:
        image,uv=image_binding(bpy.data.objects[row['object']],row['material_slot']);assert hashlib.sha256(image.packed_file.data).hexdigest()==row['texel_provenance']['packed_image_sha256'];pixels=np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1];flags=np.load(row['texel_provenance']['path'])['ownership'];assert hashlib.sha256(pixels[flags==1].tobytes()).hexdigest()==row['protected_rgba8_sha256'];assert hashlib.sha256(pixels[:,:,3].tobytes()).hexdigest()==row['alpha8_sha256']
        if row['object'] in change_by_name:
            c=change_by_name[row['object']];old=np.load(c['old_ownership_path'])['ownership'];assert hashlib.sha256(pixels[old!=0].tobytes()).hexdigest()==c['old_allowed_rgba_sha256']
    report.update(objects=rows,model_sha256=sha(destination/'model.blend'),unsupported_covered_fallback=dict(status='PASS',source_model_sha256=sha(source/'model.blend'),contract_sha256=sha(contract_path),old_completed_and_source_rgba_exact=True,alpha_geometry_uv_exact=True,changes=changes,total=sum(r['texels'] for r in changes)));write(destination/'provenance.json',report);shutil.copy2(source/'workspace.json',destination/'workspace.json');print(json.dumps(dict(status='PASS',model_sha256=report['model_sha256'],fallback_texels=report['unsupported_covered_fallback']['total'])))
if __name__=='__main__':
    a=sys.argv[sys.argv.index('--')+1:];main(*(Path(p).resolve() for p in a))
