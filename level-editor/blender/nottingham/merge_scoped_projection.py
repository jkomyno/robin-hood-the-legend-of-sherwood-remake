"""Merge only newly generated samples on named faces into a proved saved atlas.

Existing source, generated pixels, alpha, UV layout and scene geometry are
immutable. The donor is a separately baked, narrowly scoped projection, never
an image inferred from apparent coverage or alpha alone.
"""
import sys,json,hashlib
from pathlib import Path
import bpy
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).parent));sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from repair_ramp_isolated_edge import physical_face,pixels,rgba8
from refinement_workspace import _geometry
from bake_reviewed_asset import _materials
from scoped_projection_merge import newly_generated_mask
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def atlas(obj, proof):
    assert sha(proof['path'])==proof['sha256']
    matches=[]
    for mat in obj.data.materials:
        if mat and mat.use_nodes:
            for n in mat.node_tree.nodes:
                if n.type=='TEX_IMAGE' and n.image and n.image.packed_file and hashlib.sha256(n.image.packed_file.data).hexdigest()==proof['packed_image_sha256']:
                    matches.append(n)
    assert matches
    node=matches[0];uv=obj.data.uv_layers[node.inputs['Vector'].links[0].from_node.uv_map]
    assert hashlib.sha256(json.dumps([list(x.uv)for x in uv.data]).encode()).hexdigest()==proof['uv_sha256']
    own=np.load(proof['path'])['ownership'].copy()
    assert own.shape==(node.image.size[1],node.image.size[0])
    return node.image,uv,own


def run(config):
    cfg=json.loads(config.read_text());old=Path(cfg['target_bake']);donor=Path(cfg['donor_bake']);out=Path(cfg['output']);covpath=Path(cfg['coverage']);cov=json.loads(covpath.read_text())
    assert not out.exists()
    assert sha(old/'worker.blend')==cfg['target_model_sha256']==cov['model_sha256']
    assert sha(donor/'worker.blend')==cfg['donor_model_sha256']
    assert sha(covpath)==cfg['coverage_sha256']
    dv=json.loads((donor/'validation.json').read_text());donorproofs={e['object']:e['texel_provenance']for l in dv['layers']for e in l['objects']}
    bpy.ops.wm.open_mainfile(filepath=str(donor/'worker.blend'))
    payload={}
    for name,faces in cfg['faces'].items():
        obj=bpy.data.objects[name];proof=donorproofs[name];image,uv,own=atlas(obj,proof)
        physical=np.zeros(own.shape,bool)
        for fid in faces:
            (x,y),mask,_=physical_face(obj,obj.data.polygons[fid],uv,own.shape)
            physical[y:y+mask.shape[0],x:x+mask.shape[1]]|=mask
        payload[name]=dict(rgba=pixels(image),ownership=own,physical=physical,geometry=_geometry(obj),uv_sha256=proof['uv_sha256'],proof=proof)
    bpy.ops.wm.open_mainfile(filepath=str(old/'worker.blend'))
    geometry={o.name:_geometry(o)for o in bpy.data.objects};layout={o.name:_materials(o)for o in bpy.data.objects if o.type=='MESH'}
    imagehash={i.name:hashlib.sha256(i.packed_file.data).hexdigest()for i in bpy.data.images if i.packed_file and i.users}
    proofs={e['object']:dict(e['provenance'])for e in cov['atlas_evidence']}
    for evidence in cov['atlas_evidence']:
        assert sha(evidence['report'])==evidence['report_sha256']
        atlas(bpy.data.objects[evidence['object']],evidence['provenance'])
    buffers={};oldbytes={};owns={};images={};allowed={};records=[]
    for name,data in payload.items():
        obj=bpy.data.objects[name];assert _geometry(obj)==data['geometry'],name
        image,uv,own=atlas(obj,proofs[name]);assert proofs[name]['uv_sha256']==data['uv_sha256']
        values=pixels(image);assert values.shape==data['rgba'].shape
        allow=newly_generated_mask(data['physical'],own,data['ownership'])
        assert allow.any(),name
        oldbytes[name]=rgba8(values);buffers[name]=values.copy();buffers[name][allow,:3]=data['rgba'][allow,:3];owns[name]=own.copy();owns[name][allow]=2;allowed[name]=allow;images[name]=image.name
        y,x=np.where(allow);xy=np.c_[x,y].astype('<i4');records.append(dict(object=name,faces=cfg['faces'][name],filled_texels=int(allow.sum()),target_xy_sha256=hashlib.sha256(xy.tobytes()).hexdigest(),old_provenance=proofs[name].copy(),donor_provenance=data['proof']))
    out.mkdir(parents=True);(out/'merge-script.py').write_bytes(Path(__file__).read_bytes())
    for name,values in buffers.items():
        image=bpy.data.images[images[name]];image.pixels.foreach_set(values.ravel());image.update();image.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'worker.blend'));bpy.ops.wm.open_mainfile(filepath=str(out/'worker.blend'))
    assert geometry=={o.name:_geometry(o)for o in bpy.data.objects}
    assert layout=={o.name:_materials(o)for o in bpy.data.objects if o.type=='MESH'}
    for name,digest in imagehash.items():
        if name not in images.values():assert hashlib.sha256(bpy.data.images[name].packed_file.data).hexdigest()==digest,name
    for name,before in oldbytes.items():
        image=bpy.data.images[images[name]];after=rgba8(pixels(image));allow=allowed[name]
        assert np.array_equal(before[~allow],after[~allow]);assert np.array_equal(before[:,:,3],after[:,:,3])
        assert np.array_equal(after[allow,:3],rgba8(payload[name]['rgba'])[allow,:3])
        dest=out/('provenance-'+hashlib.sha256(name.encode()).hexdigest()[:16]+'.npz');np.savez_compressed(dest,ownership=owns[name]);proofs[name].update(path=str(dest),sha256=sha(dest),packed_image_sha256=hashlib.sha256(image.packed_file.data).hexdigest(),rgba8_sha256=hashlib.sha256(after.tobytes()).hexdigest());proofs[name].pop('rgba_float32_sha256',None)
        np.savez_compressed(out/('patch-'+hashlib.sha256(name.encode()).hexdigest()[:16]+'.npz'),mask=allow)
    report=dict(objects=[dict(object=name,texel_provenance=proof)for name,proof in proofs.items()]);(out/'layer-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    validation=json.loads((old/'validation.json').read_text());count=sum(r['filled_texels']for r in records);validation['layers_before_sparse_merge']=validation['layers'];validation['layers']=[report];validation['counts']['unfilled_texels_including_padding']-=count;validation['counts']['generated_texels_including_padding']+=count;validation['model_sha256']=sha(out/'worker.blend');validation['scoped_projection_merge']=dict(config=str(config),config_sha256=sha(config),new_generated_texels=count,old_model_sha256=cfg['target_model_sha256'],donor_model_sha256=cfg['donor_model_sha256']);(out/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    audit=dict(status='PASS',model_sha256=sha(out/'worker.blend'),source_existing_generated_alpha_all_outside_rgba_exact=True,geometry_uv_material_layout_exact=True,only_named_face_physical_class0_to_generated_class2=True,filled_texels=count,objects=records,evidence_sha256={str(config):sha(config),str(old/'worker.blend'):sha(old/'worker.blend'),str(old/'validation.json'):sha(old/'validation.json'),str(donor/'worker.blend'):sha(donor/'worker.blend'),str(donor/'validation.json'):sha(donor/'validation.json'),str(covpath):sha(covpath)},script_sha256=sha(__file__));(out/'saved-scoped-projection-audit.json').write_text(json.dumps(audit,indent=2)+'\n');print('SAVED MERGE PASS',count,sha(out/'worker.blend'),flush=True)


if __name__=='__main__':
    run(Path(sys.argv[sys.argv.index('--')+1]).resolve())
