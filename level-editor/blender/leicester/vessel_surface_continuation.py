"""Diagnose and preview unknown-only vessel hoop continuation.

Run with -- collect EXPERIMENT... or -- preview EXPERIMENT....
The bounded preview is experimental, not an accepted source-projection repair.
Its remaining protected-source distortions require a separate review decision.
"""
import sys,json
from pathlib import Path
import bpy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'refinement/blender'))
import project_reviewed_texture as projector
from bake_reviewed_asset import stage


def collect(experiment):
    e=Path(experiment).resolve();m=json.loads((e/'views-single.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(e/'bake-single-v1/worker.blend'))
    m['texture_material_suffix']='vessel-surface-diagnostic-v1'
    p=e/'views-surface-diagnostic-v1.json'
    if p.exists():raise FileExistsError(p)
    p.write_text(json.dumps(m,indent=2)+'\n')
    original=projector.bake;records=[]
    def intercept(*args,**kwargs):
        sample=kwargs['hidden_sampler']
        def record(obj,normal,positions,accepted,colors,*,face_index):
            sample(obj,normal,positions,accepted,colors,face_index=face_index)
            records.append(np.column_stack((positions,np.tile(np.asarray(normal),(len(positions),1)),accepted,colors,np.full(len(positions),face_index))))
        kwargs['hidden_sampler']=record
        return original(*args,**kwargs)
    projector.bake=intercept
    try:
        stage(p,e/'generation-short-no-mask-with-lighting-openrouter/generated-preserved.png',e/'bake-surface-diagnostic-v1',texels_per_unit=2)
    finally:
        projector.bake=original
    np.save(e/'surface-samples-v1.npy',np.concatenate(records))
    print('SAMPLES',e,len(np.concatenate(records)),flush=True)



def continuation(experiment):
    """Warp only inferred outward wall texels onto measured source hoop endpoints."""
    from scipy.spatial import cKDTree
    from scipy.ndimage import gaussian_filter1d, map_coordinates
    from architecture_texture_packets import original_layers, digest
    e=Path(experiment).resolve();s=np.load(e/'surface-samples-v1.npy');p=s[:,:3]
    low=p.min(0);size=p.max(0)-low;center=low+size/2
    rad=p[:,:2]-center[:2];theta=np.arctan2(rad[:,1]/size[1],rad[:,0]/size[0]);height=(p[:,2]-low[2])/size[2]
    outward=(rad*s[:,3:5]).sum(1)/np.maximum(np.linalg.norm(rad,axis=1),1e-8)
    wall=(outward>.3)&(np.abs(s[:,5])<.85)
    coords=np.column_stack((theta[wall],height[wall]*2))
    tree=cKDTree(np.concatenate([coords+[-2*np.pi,0],coords,coords+[2*np.pi,0]]));ss=np.tile(s[wall],(3,1))
    rows,cols=256,512;hh,tt=np.mgrid[0:1:complex(rows),-np.pi:np.pi:complex(cols)]
    _,ix=tree.query(np.column_stack((tt.ravel(),hh.ravel()*2)))
    field=ss[ix,7:10].reshape(rows,cols,3)
    asset=m_id(e)
    if asset not in ('leicester-mill-south-barrel','leicester-village-well-bucket'):
        raise ValueError('No measured hoop anchors for '+asset)
    bucket=asset=='leicester-village-well-bucket'
    targets=([.283,.780],[.358,.730]) if bucket else ([.258,.679],[.296,.730])
    ranges=[(.15,.43),(.48,.85)] if bucket else [(.18,.37),(.60,.80)]
    result=field.copy();height_axis=np.linspace(0,1,rows);anchors=[]
    for col in range(cols//2,cols):
        t=(col-(cols-1)/2)/((cols-1)/2)
        signal=gaussian_filter1d(field[:,col].mean(1),2)
        predicted=[]
        for a,b in ranges:
            lo,hi=int(a*(rows-1)),int(b*(rows-1));predicted.append((lo+int(np.argmin(signal[lo:hi+1])))/(rows-1))
        desired=np.asarray(targets[0])*(1-t)+np.asarray(targets[1])*t
        mapped=np.interp(height_axis,[0,*desired,1],[0,*predicted,1])
        for channel in range(3):result[:,col,channel]=np.interp(mapped,height_axis,field[:,col,channel])
        anchors.append({'column':col,'predicted':predicted,'target':desired.tolist()})
    # A bounded gain continues the source illumination only near each seam.
    # Ratios use already aligned wall profiles; broad smoothing retains wood detail.
    gains=[]
    for known_col,unknown_col in [(241,265),(29,489)]:
        observed=gaussian_filter1d(field[:,known_col-3:known_col+4].mean(1),4,axis=0)
        inferred=gaussian_filter1d(result[:,unknown_col-3:unknown_col+4].mean(1),4,axis=0)
        gains.append(np.log(np.clip(observed/np.maximum(inferred,.02),.5,3)))
    for col in range(cols//2,cols):
        angle=(col-(cols-1)/2)/(cols-1)*2*np.pi
        gain=gains[0]*np.exp(-angle/.55)+gains[1]*np.exp(-(np.pi-angle)/.55)
        result[:,col]=np.clip(result[:,col]*np.exp(gain),0,1)
    m=json.loads((e/'views-single.json').read_text());source=e/'bake-single-v1/worker.blend'
    bpy.ops.wm.open_mainfile(filepath=str(source));original=original_layers(m)
    m['texture_material_suffix']='surface-continuation-v1';manifest=e/'views-surface-continuation-v1.json'
    if manifest.exists():raise FileExistsError(manifest)
    manifest.write_text(json.dumps(m,indent=2)+'\n');original_bake=projector.bake;changed=[0]
    def intercept(*args,**kwargs):
        sampler=kwargs['hidden_sampler']
        def adjust(obj,normal,positions,accepted,colors,*,face_index):
            sampler(obj,normal,positions,accepted,colors,face_index=face_index)
            radial=positions[:,:2]-center[:2]
            facing=(radial@np.asarray(normal)[:2])/np.maximum(np.linalg.norm(radial,axis=1),1e-8)
            angle=np.arctan2(radial[:,1]/size[1],radial[:,0]/size[0])
            selection=(~accepted)&(facing>.3)&(abs(normal.z)<.85)&(angle>=0)
            if not selection.any():return
            z=np.clip((positions[selection,2]-low[2])/size[2],0,1)
            xy=np.vstack((z*(rows-1),(angle[selection]+np.pi)/(2*np.pi)*(cols-1)))
            for channel in range(3):colors[selection,channel]=map_coordinates(result[:,:,channel],xy,order=1,mode='nearest')
            changed[0]+=int(selection.sum())
        kwargs['hidden_sampler']=adjust
        return original_bake(*args,**kwargs)
    projector.bake=intercept
    out=e/'bake-surface-continuation-v1'
    try:
        stage(manifest,e/'generation-short-no-mask-with-lighting-openrouter/generated-preserved.png',out,texels_per_unit=2)
    finally:
        projector.bake=original_bake
    if original!=original_layers(m,original):raise ValueError('Original atlas/UV changed')
    report={'status':'candidate-awaiting-visual-QA','geometry_verified':True,'source_uv_and_atlases_preserved':True,
        'source_worker':str(source),'source_worker_sha256':digest(source),'worker_sha256':digest(out/'worker.blend'),
        'sample_evidence':str(e/'surface-samples-v1.npy'),'sample_evidence_sha256':digest(e/'surface-samples-v1.npy'),
        'source_band_endpoint_heights':targets,'height_range_world':[float(low[2]),float(low[2]+size[2])],
        'height_warp_anchors':anchors,'changed_unknown_samples_including_gutters':changed[0],
        'method':'Measured source hoop heights interpolated across unseen angle; unknown wall samples vertically warped from cached atlas then bounded seam-local RGB gain. Original source accepted samples, inner walls and caps unchanged.'}
    (out/'continuation-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    projector.bake=original_bake
    print('CONTINUATION',e,changed[0],flush=True)


def m_id(e):return json.loads((e/'views-single.json').read_text())['asset_id']


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    if not args or args[0] not in ('collect','preview'):
        raise ValueError('Expected collect or preview followed by experiment paths')
    for experiment in args[1:]:
        (collect if args[0]=='collect' else continuation)(experiment)
