"""Prepare an approved nonplanar UV atlas with exact source and world-light guards."""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image
from prepare_texture_packet import prepare
from review_evidence import bind_decision,load_decisions,sha
from uv_atlas import raster_lighting

def prepare_uv(manifest_path,asset_id,output,evidence_path,lighting_path,decisions=None):
    manifest_path,output,evidence_path,lighting_path=map(lambda p:Path(p).resolve(),(manifest_path,output,evidence_path,lighting_path))
    if output.exists():raise FileExistsError(output)
    eligible=prepare(manifest_path,asset_id,output,decisions,check_only=True)
    manifest=json.loads(manifest_path.read_text());item=copy.deepcopy(next(i for i in manifest['items'] if i['id']==asset_id))
    records=load_decisions(Path(decisions) if decisions else manifest_path.parent/'decisions.json',{i['id'] for i in manifest['items']}|{i['id'] for i in manifest.get('without_packets',[])})
    bind_decision(item,records)
    evidence=json.loads(evidence_path.read_text());lighting_record=json.loads(lighting_path.read_text())
    if evidence['asset_id']!=asset_id or evidence['model_sha256']!=item['revision']['model_sha256']:raise ValueError('UV evidence is not bound to current approved model')
    workspace=Path(evidence['workspace']);model=workspace/'model.blend';atlas=Path(evidence['atlas_path'])
    if sha(model)!=evidence['model_sha256'] or sha(atlas)!=evidence['atlas_sha256']:raise ValueError('Saved model or packed atlas evidence changed')
    # The current approval manifest must bind the calibrated map-light record.
    bound={str(Path(e['path']).resolve()):e['sha256'] for e in item['revision']['evidence'].values()}
    if bound.get(str(lighting_path))!=sha(lighting_path):raise ValueError('UV atlas lighting is absent from reviewed preparation evidence')
    settings=lighting_record['lighting']
    approved_lighting=item.get('preparation_lighting',{}).get('lighting')
    if approved_lighting!=settings:raise ValueError('UV atlas lighting differs from selected map lighting')
    image=np.asarray(Image.open(atlas).convert('RGBA'));height,width=image.shape[:2]
    if [width,height]!=evidence['atlas_dimensions']:raise ValueError('Atlas dimensions differ from saved UV evidence')
    if width%16 or height%16 or max(width,height)>3840 or max(width,height)/min(width,height)>3 or not 655360<=width*height<=8294400:raise ValueError('Exact atlas outside generation bounds; never resize')
    # Alpha is source-ownership data only; actual saved material was checked opaque.
    if not set(np.unique(image[:,:,3])).issubset({0,255}):raise ValueError('Expected binary known-source ownership alpha')
    known=image[:,:,3]>0
    config=json.loads((workspace/'workspace.json').read_text());source=Path(config['source_path'])
    expected=np.asarray(Image.open(source).convert('RGB'))
    if expected.shape!=image[:,:,:3].shape or np.any(expected[known]!=image[:,:,:3][known]):raise ValueError('Known source RGB differs from actual atlas')
    surface,solid,lighting_report=raster_lighting(evidence,settings)
    if np.any(known&~surface):raise ValueError('Known ownership refers to pixels outside actual UV surface')
    editable=surface&~known
    input_image=solid.copy();input_image[known]=image[known]
    mask=np.full_like(input_image,255);mask[editable,3]=0
    packet=Path(item['textured']).parent;frames=json.loads((packet/'views.json').read_text())
    output.mkdir(parents=True)
    for source_file,name in ((model,'approved-model.blend'),(atlas,'source-atlas.png'),(evidence_path,'uv-evidence.json'),(lighting_path,'lighting.json')):shutil.copy2(source_file,output/name)
    Image.fromarray(input_image).save(output/'input.png');Image.fromarray(mask).save(output/'mask.png');Image.fromarray(solid).save(output/'solid.png');Image.fromarray((surface*255).astype(np.uint8)).save(output/'surface.png');Image.fromarray((known*255).astype(np.uint8)).save(output/'known.png')
    (output/'lighting-audit.json').write_text(json.dumps(lighting_report,indent=2)+'\n')
    views=dict(asset_id=asset_id,projection_kind='uv-atlas',layout=dict(width=width,height=height),views=[dict(index=0,input='input.png',mask='mask.png',crop=dict(left=0,top=0,width=width,height=height))],reviewed_packet=str(packet),reviewed_manifest_sha256=sha(packet/'views.json'),source_blend=str(output/'approved-model.blend'),geometry_revision=eligible['revision_sha256'],uv_evidence_sha256=sha(output/'uv-evidence.json'),source_atlas_sha256=sha(output/'source-atlas.png'),lighting_sha256=sha(output/'lighting.json'),scene_name=frames['scene_name'],collection_name=frames['collection_name'],physical_coverage='Actual saved opaque mesh triangle UV pixel centers; no planar assumption',unknown_lighting_derived=True)
    (output/'views.json').write_text(json.dumps(views,indent=2)+'\n')
    decision=item['user_decision'];approval=dict(status='approved',approved_by='user',asset_id=asset_id,geometry_revision=eligible['revision_sha256'],exact_user_text=decision['exact_user_text'],source_decision=decision,texture_approval='pending',input_sha256=sha(output/'input.png'),solid_sha256=sha(output/'solid.png'),saved_model_sha256=sha(output/'approved-model.blend'),scope='Approved nonplanar UV geometry and protected source; generated texture still requires review')
    (output/'approval.json').write_text(json.dumps(approval,indent=2)+'\n')
    report=dict(status='prepared' if editable.any() else 'no-generation-needed',asset_id=asset_id,projection_kind='uv-atlas',editable_pixels=int(editable.sum()),known_pixels=int(known.sum()),protected_pixels=int((~editable).sum()),outside_or_hole_pixels=int((~surface).sum()),dimensions=[width,height],approved_revision=eligible['revision_sha256'],files={str(p.relative_to(output)):sha(p) for p in output.iterdir() if p.is_file()})
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','asset_id','output','evidence','lighting'):p.add_argument(name)
    p.add_argument('--decisions');a=p.parse_args();print(json.dumps(prepare_uv(a.manifest,a.asset_id,a.output,a.evidence,a.lighting,a.decisions),indent=2))
