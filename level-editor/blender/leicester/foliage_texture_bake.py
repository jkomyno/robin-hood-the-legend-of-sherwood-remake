"""Fill approved tree material RGB while freezing physical alpha and source RGBA."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'refinement/blender'))
from project_reviewed_texture import apply, _read, _reconcile
from refinement_workspace import _geometry
from bake_reviewed_asset import _materials
from physical_opacity import OpacityRegistry
from audit_stored_materials import run as audit


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pixels(image):
    data=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(data)
    return data.reshape(image.size[1],image.size[0],4)


def physical_records(objects):
    result=[]
    for obj in objects:
        for index,mat in enumerate(obj.data.materials):
            if not mat or not mat.get('foliage_physical_opacity'):continue
            textures=[node for node in mat.node_tree.nodes if node.type=='TEX_IMAGE']
            if len(textures)!=1:raise ValueError('Expected exactly one packed physical foliage image')
            result.append((obj,index,mat,textures[0],pixels(textures[0].image).copy()))
    return result


def visibility(objects):
    vertices=[];triangles=[];opacity=OpacityRegistry()
    for obj in objects:
        mesh=obj.data;mesh.calc_loop_triangles();start=len(vertices)
        vertices.extend(obj.matrix_world@v.co for v in mesh.vertices)
        for triangle in mesh.loop_triangles:
            triangles.append(tuple(start+i for i in triangle.vertices));opacity.add(obj,mesh,triangle)
    return opacity.wrap(BVHTree.FromPolygons(vertices,triangles,all_triangles=True))


def authored_volume_seam(material, uv):
    """Only the approved continuous crown rim has collapsed atlas coverage."""
    return (str(material.get('foliage_recipe', '')).startswith('leicester-continuous-forest-volume-')
            and len(np.unique(uv, axis=0)) == 2)


def facing_score(material, cosine):
    return abs(cosine) if material.get('foliage_card_sides') == 'double-sided' else cosine


def fill_rgb(records,objects,manifest,generated,mask):
    tree=visibility(objects);height=len(generated);cameras=[]
    for view in manifest['views']:
        matrix=Matrix(view['camera_matrix_world'])
        cameras.append((view,matrix.inverted(),matrix.to_3x3()@Vector((0,0,1))))
    reports=[]
    for obj,index,mat,texture,before in records:
        if mat.get('foliage_observed'):
            reports.append(dict(material=mat.name,observed=True,rgba_unchanged=True,rgba_sha256=hashlib.sha256(before.tobytes()).hexdigest()));continue
        image=texture.image;h,w=before.shape[:2];after=before.copy();filled=np.zeros((h,w),dtype=bool)
        examined=np.zeros((h,w),dtype=bool);facing_seen=examined.copy();frame_seen=examined.copy();visible_seen=examined.copy();editable_seen=examined.copy()
        uv_name=texture.inputs['Vector'].links[0].from_node.uv_map
        layer=obj.data.uv_layers[uv_name];authored_seam_triangles=0;view_counts={str(v['index']):0 for v,_,_ in cameras}
        for triangle in obj.data.loop_triangles:
            if triangle.material_index!=index:continue
            uv=np.array([layer.data[i].uv for i in triangle.loops],dtype=float)
            uv[:,0]*=w;uv[:,1]*=h
            a,b,c=uv;ab=b-a;ac=c-a;det=ab[0]*ac[1]-ab[1]*ac[0]
            if abs(det)<1e-10:
                if not authored_volume_seam(mat, uv):
                    raise ValueError('Unexpected degenerate physical UV triangle')
                # The stitched 0.05-unit rim reads the same image edge as its
                # adjacent crown surface and has no independent atlas texels.
                authored_seam_triangles+=1
                continue
            x0=max(0,int(np.floor(uv[:,0].min())));x1=min(w,int(np.ceil(uv[:,0].max())))
            y0=max(0,int(np.floor(uv[:,1].min())));y1=min(h,int(np.ceil(uv[:,1].max())))
            yy,xx=np.mgrid[y0:y1,x0:x1];ap=np.stack((xx+.5-a[0],yy+.5-a[1]),axis=-1)
            u=(ap[:,:,0]*ac[1]-ap[:,:,1]*ac[0])/det
            v=(ab[0]*ap[:,:,1]-ab[1]*ap[:,:,0])/det
            inside=(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)&(before[y0:y1,x0:x1,3]>=.5)&~filled[y0:y1,x0:x1]
            row,col=np.nonzero(inside)
            if not len(row):continue
            examined[y0+row,x0+col]=True
            world=np.array([obj.matrix_world@obj.data.vertices[i].co for i in triangle.vertices])
            positions=world[0]+u[row,col,None]*(world[1]-world[0])+v[row,col,None]*(world[2]-world[0])
            normal=(Vector(world[1]-world[0]).cross(Vector(world[2]-world[0]))).normalized()
            remaining=np.ones(len(row),dtype=bool)
            for score,view,inverse,direction in sorted(((facing_score(mat,normal.dot(d)),v,m,d) for v,m,d in cameras),key=lambda r:r[0],reverse=True):
                if score<=.12:continue
                facing_seen[y0+row,x0+col]=True
                indices=np.flatnonzero(remaining)
                local=positions[indices]@np.asarray(inverse.to_3x3()).T+np.asarray(inverse.translation)
                crop=view['crop'];scale=view['ortho_scale']
                px=crop['left']+(.5+local[:,0]/(scale*crop['width']/crop['height']))*crop['width']
                py=height-crop['top']-(.5-local[:,1]/scale)*crop['height']
                for k,j in enumerate(indices):
                    x,y=int(np.floor(px[k])),int(np.floor(py[k]))
                    if not(crop['left']<=x<crop['left']+crop['width'] and height-crop['top']-crop['height']<=y<height-crop['top']):continue
                    frame_seen[y0+row[j],x0+col[j]]=True
                    point=Vector(positions[j]);hit,_,_,_=tree.ray_cast(point+direction*100000,-direction)
                    if hit is None or (hit-point).length>.03:continue
                    visible_seen[y0+row[j],x0+col[j]]=True
                    if mask[y,x,3]>=.5:continue
                    editable_seen[y0+row[j],x0+col[j]]=True
                    iy,ix=y0+row[j],x0+col[j]
                    after[iy,ix,:3]=generated[y,x,:3];filled[iy,ix]=True;remaining[j]=False;view_counts[str(view['index'])]+=1
        unfilled=(before[:,:,3]>=.5)&~filled
        coverage={
            'unmapped_physical_texels':int((unfilled&~examined).sum()),
            'no_eligible_facing_view':int((unfilled&examined&~facing_seen).sum()),
            'outside_review_frames':int((unfilled&facing_seen&~frame_seen).sum()),
            'occluded_in_all_eligible_views':int((unfilled&frame_seen&~visible_seen).sum()),
            'protected_in_visible_views':int((unfilled&visible_seen&~editable_seen).sum()),
            'visible_editable_unfilled':int((unfilled&editable_seen).sum()),
        }
        if sum(coverage.values())!=int(unfilled.sum()):raise ValueError('Incomplete physical coverage accounting')
        if not np.array_equal(before[:,:,3],after[:,:,3]):raise ValueError('Physical opacity changed')
        image.pixels.foreach_set(after.ravel());image.pack()
        mat['generated_foliage_rgb']=True;mat['source_ownership_fill']='synthesized'
        mat['generated_foliage_geometry_authority']=False
        reports.append(dict(material=mat.name,observed=False,physical_alpha_sha256=hashlib.sha256(before[:,:,3].tobytes()).hexdigest(),
                            alpha_unchanged=True,physical_texels=int((before[:,:,3]>=.5).sum()),filled_texels=int(filled.sum()),
                            unfilled_texels=int(((before[:,:,3]>=.5)&~filled).sum()),views=view_counts,
                            unfilled_reasons=coverage,authored_zero_area_uv_seam_triangles=authored_seam_triangles,
                            two_sided_sampling=mat.get('foliage_card_sides')=='double-sided'))
    return reports


@bpy.app.handlers.persistent
def cutout_depth(scene):scene.cycles.transparent_max_bounces=128


def run(experiment,selected,output,raw=None):
    experiment=Path(experiment).resolve();selected=Path(selected).resolve();output=Path(output).resolve()
    manifest_path=experiment/'views.json';manifest=json.loads(manifest_path.read_text())
    evidence=[manifest_path,selected,experiment/'input.png',experiment/'mask.png',experiment/'approval.json']
    if raw:
        raw=Path(raw).resolve();evidence.append(raw)
    evidence_hashes={str(path):sha(path) for path in evidence}
    approval=json.loads((experiment/'approval.json').read_text())
    if sha(bpy.data.filepath)!=approval['saved_model_sha256']:raise ValueError('Open exact approved model copy')
    scene=bpy.data.scenes[manifest['scene_name']];bpy.context.window.scene=scene
    objects=[o for o in scene.objects if o.type=='MESH' and o.get('asset_group')==manifest['asset_id'] and not o.hide_render]
    records=physical_records(objects)
    if not records:raise ValueError('No approved physical foliage')
    geometry={o.name:_geometry(o) for o in scene.objects}
    outside={o.name:_materials(o) for o in scene.objects if o.type=='MESH' and o not in objects}
    uv={o.name:{l.name:[tuple(d.uv) for d in l.data] for l in o.data.uv_layers} for o in objects if any(m and m.get('foliage_physical_opacity') for m in o.data.materials)}
    # Shared approval validation and protected source atlas fill for opaque wood.
    report=apply(manifest_path,selected,output,texels_per_unit=2,reconciliation_reference=raw)
    for obj,index,mat,texture,before in records:
        if not np.array_equal(before,pixels(texture.image)):raise ValueError('Shared bake changed protected authored foliage')
    generated=_reconcile(_read(selected),manifest,_read(raw) if raw else None)
    foliage=fill_rgb(records,objects,manifest,generated,_read(experiment/'mask.png'))
    for obj,index,mat,texture,before in records:
        current=pixels(texture.image)
        if not np.array_equal(before[:,:,3],current[:,:,3]):raise ValueError('Physical alpha changed')
        if mat.get('foliage_observed') and not np.array_equal(before,current):raise ValueError('Observed RGBA changed')
    if geometry!={o.name:_geometry(o) for o in scene.objects}:raise ValueError('Geometry changed')
    if outside!={o.name:_materials(o) for o in scene.objects if o.name in outside}:raise ValueError('Outside material/UV changed')
    if uv!={o.name:{l.name:[tuple(d.uv) for d in l.data] for l in o.data.uv_layers} for o in objects if o.name in uv}:raise ValueError('Foliage UV changed')
    if evidence_hashes!={str(path):sha(path) for path in evidence}:
        raise ValueError('Approved or generated evidence changed during foliage texture stage')
    report.update(evidence_sha256=evidence_hashes,geometry_verified=True,outside_objects_unchanged=len(outside),physical_alpha_unchanged=True,observed_foliage_rgba_unchanged=True,
                  foliage_uv_unchanged=True,foliage_materials=foliage,texture_approval='pending',generated_shape_authority=False)
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'worker.blend'))
    proxy=output/'audit-workspace';proxy.mkdir();(proxy/'model.blend').symlink_to(output/'worker.blend')
    (proxy/'workspace.json').write_text(json.dumps({'asset_id':manifest['asset_id'],'collection_name':manifest['collection_name']}))
    bpy.app.handlers.render_pre.append(cutout_depth)
    try:material_report=audit(proxy,output/'material-audit',render=True,export=True,frame_manifest=manifest_path)
    finally:bpy.app.handlers.render_pre.remove(cutout_depth)
    material_report['render']['transparent_max_bounces']=128
    (output/'material-audit/audit.json').write_text(json.dumps(material_report,indent=2)+'\n')
    actual=output/'actual';actual.mkdir();shutil.copy2(output/'material-audit/materials.png',actual/'textured.png')
    for i in range(8):shutil.copy2(output/f'material-audit/view-{i}.png',actual/f'view-{i}-textured.png')
    print(json.dumps({'asset_id':manifest['asset_id'],'physical_alpha_unchanged':True,'observed_rgba_unchanged':True,'materials':len(foliage)}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('experiment');parser.add_argument('selected');parser.add_argument('output');parser.add_argument('--raw')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);run(args.experiment,args.selected,args.output,args.raw)
