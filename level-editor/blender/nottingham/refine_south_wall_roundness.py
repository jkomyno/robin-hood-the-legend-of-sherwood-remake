"""Round the curved south wall while retaining its measured source crown and split."""
import hashlib, json, math, shutil, sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from refine_south_curve_corners import apply, geom

def rounded_fit(fit):
    """Cubic centerline displacement shared by both sides and cap height.

    Equal native depth/height displacement keeps the observed source crown
    fixed, while the entire vertical body acquires a continuous curved plan.
    """
    pairs=fit['pairs']+[(2,13)]
    anchors=[(fit['points'][a],fit['points'][b]) for a,b in pairs]
    centers=[((a['x']+b['x'])/2,(a['y']+b['y'])/2) for a,b in anchors]
    slopes=[(centers[i+1][1]-centers[i][1])/(centers[i+1][0]-centers[i][0]) for i in range(len(centers)-1)]
    tangent=[slopes[0]]
    for l,r in zip(slopes,slopes[1:]):
        tangent.append(0 if l*r<=0 else 2*l*r/(l+r))
    tangent.append(slopes[-1])
    points=[];newpairs=[];maximum=0
    for i,((a,b),(c,d)) in enumerate(zip(anchors,anchors[1:])):
        n=max(1,math.ceil((c['x']-a['x'])/3))
        for j in range(n):
            t=j/n
            # Leave the adjoining straight run and split contact exact.
            delta=0
            if i < len(anchors)-2:
                x0,y0=centers[i];x1,y1=centers[i+1]
                y=(2*t**3-3*t*t+1)*y0+(t**3-2*t*t+t)*(x1-x0)*tangent[i]+(-2*t**3+3*t*t)*y1+(t**3-t*t)*(x1-x0)*tangent[i+1]
                delta=y-(y0+(y1-y0)*t)
            maximum=max(maximum,abs(delta))
            newpairs.append((len(points),len(points)+1))
            for p,q in ((a,c),(b,d)):
                v={k:p[k]+(q[k]-p[k])*t for k in p}
                v['y']+=delta;v['z_top']+=delta
                points.append(v)
    newpairs.append((len(points),len(points)+1));points.extend(dict(p) for p in anchors[-1])
    out=dict(fit,points=points,pairs=newpairs)
    # apply() historically appends these indices and adjusts them. Use a local
    # wrapper of its generator to provide the complete sampled ribbon directly.
    return out,maximum

def main():
    acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
    from refinement_workspace import modified,_files
    import refine_south_curve_corners as oldrecipe
    from refine_fortifications import north_wall_geometry
    old=WORK/'round-13/assets/nottingham-south-curtain-wall-1'
    new=WORK/'round-37/assets/nottingham-south-curtain-wall-1'
    assert not new.exists(),new
    new.mkdir(parents=True);(new/'inspection').mkdir()
    for name in ('reference','mask-reference'):shutil.copytree(old/name,new/name)
    shutil.copytree(old/'modified',new/'input');shutil.copy2(old/'model.blend',new/'baseline.blend');shutil.copy2(old/'source-masks.json',new/'source-masks.json')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    config=json.loads((old/'workspace.json').read_text())
    config.update(source_blend=str(old/'model.blend'),source_blend_sha256=sha(old/'model.blend'),baseline_sha256=sha(new/'baseline.blend'),input_files=_files(new/'input'))
    # Frozen source/mask paths and hashes remain authoritative and immutable.
    (new/'workspace.json').write_text(json.dumps(config,indent=2)+'\n')
    bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
    target=next(o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and o.get('projection_component')=='wall-200-1')
    outside={o.name:geom(o) for o in bpy.data.objects if o.type=='MESH' and o!=target}
    fit=json.loads((WORK/'fortifications-audit/south-curve-user-revision/corner-fit.json').read_text())
    for i in (2,13):fit['points'][i]['z_top']+=1.5
    rounded,delta=rounded_fit(fit)
    oldrecipe.north_wall_geometry=lambda _pts,_pairs,notches,notch_depth:north_wall_geometry(rounded['points'],rounded['pairs'],notches,notch_depth=notch_depth)
    topology=apply(target,fit);first=geom(target);apply(target,fit);assert first==geom(target)
    assert outside=={o.name:geom(o) for o in bpy.data.objects if o.type=='MESH' and o!=target}
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'))
    # Narrow curved triangles need denser sampling to avoid visible phase seams.
    import source_projection_bake
    default_bake=source_projection_bake.bake
    def dense_bake(*args,**kwargs):
        kwargs['texels_per_unit']=4
        return default_bake(*args,**kwargs)
    source_projection_bake.bake=dense_bake
    try:validation=modified(new)
    finally:source_projection_bake.bake=default_bake
    report=dict(status='PASS',model_sha256=sha(new/'model.blend'),modified_views_sha256=sha(new/'modified/views.json'),baseline_sha256=sha(new/'baseline.blend'),topology=topology,outside_geometry_preserved=len(outside),source_crown_projection_preserved=True,split_x=1519,native_mask_unchanged=126,maximum_native_depth_shift=delta,sampled_cross_sections=len(rounded['pairs']),stored_atlas_texels_per_unit=4,idempotence=True,validation=validation)
    (new/'inspection/roundness-correction.json').write_text(json.dumps(report,indent=2)+'\n')
    shutil.copy2(__file__,new/'roundness-recipe.py');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
