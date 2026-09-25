"""Verify source texels and saved geometry after a new generated inference pass."""
from pathlib import Path
import hashlib,json,sys

def run(previous,output):
    import bpy,numpy as np
    previous,output=Path(previous).resolve(),Path(output).resolve()
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    def snapshot(folder):
        validation=json.loads((folder/'validation.json').read_text())
        if validation.get('geometry_verified') is not True or type(validation.get('outside_objects_unchanged')) is not int:raise ValueError('Missing saved geometry/outside proof')
        bpy.ops.wm.open_mainfile(filepath=str(folder/'worker.blend'));objects={}
        for layer in validation['layers']:
            for entry in layer['objects']:
                name=entry['object'];obj=bpy.data.objects[name];proof=entry['texel_provenance'];indices={p.material_index for p in obj.data.polygons}
                if len(indices)!=1:raise ValueError('Ambiguous receiver material')
                mat=obj.data.materials[next(iter(indices))];nodes=[n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
                if len(nodes)!=1:raise ValueError('Ambiguous atlas image')
                node=nodes[0];image=node.image
                if hashlib.sha256(image.packed_file.data).hexdigest()!=proof['packed_image_sha256'] or sha(Path(proof['path']))!=proof['sha256']:raise ValueError('Packed source/provenance drift')
                bound=node.inputs['Vector'].links[0].from_node.uv_map;coords=[list(v.uv) for v in obj.data.uv_layers[bound].data]
                if hashlib.sha256(json.dumps(coords).encode()).hexdigest()!=proof['uv_sha256']:raise ValueError('Material UV provenance drift')
                pixels=np.asarray(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4);mask=np.load(proof['path'])['ownership']
                geometry=([tuple(v.co) for v in obj.data.vertices],[tuple(p.vertices) for p in obj.data.polygons],[tuple(row) for row in obj.matrix_world],{u.name:[tuple(v.uv) for v in u.data] for u in obj.data.uv_layers})
                objects[name]=(pixels,mask,geometry)
        return validation,objects
    before,old=snapshot(previous);after,new=snapshot(output)
    if old.keys()!=new.keys() or before.get('source_mask_evidence')!=after.get('source_mask_evidence'):raise ValueError('Source ownership contract changed')
    results=[]
    for name,(pixels,mask,geometry) in old.items():
        final,flags,final_geometry=new[name]
        if pixels.shape!=final.shape or geometry!=final_geometry:raise ValueError('Geometry, all UV or atlas layout changed')
        known=mask==1
        if not np.array_equal(known,flags==1) or not np.array_equal(pixels[known],final[known]) or not np.array_equal(pixels[...,3],final[...,3]):raise ValueError('Protected source RGBA/ownership or alpha changed')
        results.append(dict(object=name,source_texels=int(known.sum()),source_rgba_exact=True,source_mask_exact=True,all_alpha_exact=True,geometry_and_all_uv_exact=True))
    report=dict(status='PASS',previous_model_sha256=sha(previous/'worker.blend'),model_sha256=sha(output/'worker.blend'),validation_sha256=sha(output/'validation.json'),objects=results,outside_objects_unchanged=after['outside_objects_unchanged'],scope='Source protection only: generated RGB is intentionally allowed to change; composition evidence and all8 material review must validate generated changes separately.')
    (output/'saved-source-audit.json').write_text(json.dumps(report,indent=2)+'\n');print('SAVED SOURCE PASS',output)

if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
