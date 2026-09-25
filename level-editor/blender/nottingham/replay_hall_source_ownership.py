"""Replay original source-only hall atlases into immutable ownership evidence."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(Path(__file__).parent),str(ROOT/'level-editor/refinement/blender'),str(ROOT/'level-editor/blender')]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def snapshot(obj):
    rows={}
    for index in {f.material_index for f in obj.data.polygons}:
        m=obj.data.materials[index]
        images=[n.image for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
        uv=[n.uv_map for n in m.node_tree.nodes if n.type=='UVMAP']
        if len(images)!=1 or len(uv)!=1:raise ValueError('Expected one source atlas binding: '+obj.name)
        rows[index]=dict(image_sha256=hashlib.sha256(images[0].packed_file.data).hexdigest(),
            uv_sha256=hashlib.sha256(json.dumps([list(v.uv) for v in obj.data.uv_layers[uv[0]].data]).encode()).hexdigest(),
            faces=[f.index for f in obj.data.polygons if f.material_index==index])
    return list(rows.values())

def main(workspace,state,out):
    import bpy
    import numpy as np
    from PIL import Image
    import io,math
    from reconstruct_hall_generated_states import triangle_samples,image_binding
    import source_projection_bake
    bake=source_projection_bake.bake
    if '--historical-face-normals' in sys.argv:
        # Reproduce the frozen source-only shader convention; never alter models.
        text=Path(source_projection_bake.__file__).read_text()
        old='triangle_normals[triangle.index] = (normal if triangle_normal.dot(normal) > 1-1e-5\n                                                    else triangle_normal)'
        assert text.count(old)==1
        code=text.replace(old,'triangle_normals[triangle.index] = normal')
        namespace=dict(__file__=source_projection_bake.__file__)
        exec(compile(code,source_projection_bake.__file__,'exec'),namespace)
        bake=namespace['bake']
    from render_slots import acquire
    acquire(slots=2)
    original=ROOT/'level-editor/work/nottingham-refinement/round-42/assets/nottingham-castle-main-hall'
    cfg=json.loads((original/'workspace.json').read_text());d=json.loads((original/'projection-state-layers.json').read_text())[state][0]
    model=original/'inspection/state-models'/state/'model.blend'
    binding=next(s for s in json.loads((original/'inspection/state-models/manifest.json').read_text())['states'] if s['state']==state)
    bpy.ops.wm.open_mainfile(filepath=str(model));bpy.context.view_layer.update()
    names=binding['object_names']
    if '--nodes' in sys.argv:
        nodes=sys.argv[sys.argv.index('--nodes')+1].split(',');names=[n for n in names if bpy.data.objects[n].get('source_node') in nodes]
    originals={}
    for n in names:
        o=bpy.data.objects[n];m=o.data.materials[o.data.polygons[0].material_index];image=next(x.image for x in m.node_tree.nodes if x.type=='TEX_IMAGE');originals[n]=bytes(image.packed_file.data)
    before={n:snapshot(bpy.data.objects[n]) for n in names}
    out.mkdir(parents=True,exist_ok=False)
    report=bake('nottingham',d['source_path'],out/'replay.json',receiver_nodes=sorted({bpy.data.objects[n].get('source_node') for n in names}),
        occluder_nodes=d['occluder_nodes'],projection_label=d['projection_label'],source_mask_manifest=cfg['source_mask_manifest'],
        receiver_asset_id=cfg['asset_id'],receiver_object_names=names,exclude_occluder_components=d.get('exclude_occluder_components'),
        material_suffix='complete-'+state+'-state',preserve_authored=False,provenance_directory=out/'provenance')
    after={n:snapshot(bpy.data.objects[n]) for n in names};mismatch=[n for n in names if before[n]!=after[n]]
    recovery={}
    source=np.array(Image.open(d['source_path']).convert('RGBA'))
    for n in mismatch:
        name=hashlib.sha256(n.encode()).hexdigest()[:16];(out/(name+'-original.png')).write_bytes(originals[n]);o=bpy.data.objects[n];m=o.data.materials[o.data.polygons[0].material_index];image=next(x.image for x in m.node_tree.nodes if x.type=='TEX_IMAGE');(out/(name+'-replayed.png')).write_bytes(bytes(image.packed_file.data))
        old=np.array(Image.open(io.BytesIO(originals[n])).convert('RGBA'))[::-1];new=np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1]
        changed=(old!=new).any(2);h,w=changed.shape;best=np.full((h,w),-np.inf);matches=np.zeros((h,w),bool)
        _,uv=image_binding(o,o.data.polygons[0].material_index);o.data.calc_loop_triangles()
        for tri in o.data.loop_triangles:
            sample=triangle_samples([list(uv.data[i].uv) for i in tri.loops],np.array([w,h]))
            if sample is None:continue
            x,y,bary,score=sample;keep=changed[y,x]&(score>best[y,x]);x,y,bary,score=x[keep],y[keep],bary[keep],score[keep]
            points=bary@np.array([list(o.matrix_world@o.data.vertices[i].co) for i in tri.vertices]);sx=np.floor(points[:,0]).astype(int);sy=np.floor(-points[:,1]*math.sin(math.radians(35))-points[:,2]*math.cos(math.radians(35))).astype(int)
            valid=(sx>=0)&(sy>=0)&(sx<source.shape[1])&(sy<source.shape[0]);matches[y[valid],x[valid]]=(old[y[valid],x[valid]]==source[sy[valid],sx[valid]]).all(1);best[y,x]=score
        count=int(changed.sum());exact=int((changed&matches).sum());path=out/(name+'-historical-source.npz');np.savez_compressed(path,protected=changed&matches)
        recovery[n]=dict(count=count,source_rgb_exact=exact,path=str(path),sha256=sha(path),original_packed_image_sha256=hashlib.sha256(originals[n]).hexdigest())

    result=dict(status='PASS' if not mismatch else ('PASS-PRESERVED-HISTORICAL-SOURCE' if all(r['count']==r['source_rgb_exact'] for r in recovery.values()) else 'FAIL'),historical_source_recovery=recovery,state=state,original_model_sha256=sha(model),mismatches=mismatch,before=before,after=after,replay_report=str(out/'replay.json'))
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print('SOURCE_REPLAY',state,len(names),'mismatches',mismatch,flush=True)
if __name__=='__main__':
    a=sys.argv[sys.argv.index('--')+1:];main(Path(a[0]).resolve(),a[1],Path(a[2]).resolve())
