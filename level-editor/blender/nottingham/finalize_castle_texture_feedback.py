"""Finalize a visually inspected, independently checked castle mask revision."""
import argparse,hashlib,json
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);a=p.parse_args();w=a.workspace.resolve();c=json.loads((w/'candidate.json').read_text());proof=json.loads((w/'texture-feedback-correction.json').read_text());rgb=json.loads((w/'known-rgb-validation.json').read_text());assert rgb['status']=='PASS';assert json.loads((w/'validation.json').read_text())['status']=='PASS';assert proof['geometry_unchanged'];assert proof['model_sha256']==sha(w/'model.blend')
 assert all(sha(w/'input/views'/f'view-{i}-solid.png')==sha(w/'modified/views'/f'view-{i}-solid.png')for i in range(8))
 changes={'nottingham-castle-east-round-tower':['Removed the erroneous native99 exclusion: that mask contains the same tower roof and middle shaft, not just its neighboring house.','Restored the clean native293 silhouette; receiver-scoped foreground masks reject neighboring proxy overshoot while retaining own and unlisted source occluders.'],'nottingham-castle-gate-west-tower':['Restored full tower crown, courtyard-facing floor and lower shaft using native284/285/286.','Subtracted native65 cottage and67 chimney; retained complete-scene occlusion and unchanged geometry.'],'nottingham-castle-east-courtyard-wall':['Restored the wall walkway and visible lower masonry from explicitly traced source-owned polygons within native masks.','Kept neighboring shelter and foreground greenhouse excluded, with full scene first-hit occlusion retained.']}[c['asset_id']]
 limitations=['Reverse faces and portions concealed by neighboring structures are neutral because the source contains no visible artwork for them.']
 if c['asset_id'].endswith('west-tower'):changes.append('Transferred the two gate support volumes349/350 to the arch under V13; the four remaining refined tower meshes retain their geometry.')
 c['stored_material_evidence']='inspection/independent-stored-materials/audit.json'
 c.update(status='ready-for-user',geometry_reviewed=True,geometry_refined=False,no_change_reason='Source ownership correction only. Exact world vertices, faces and transforms match the displayed prior model; all eight input and modified solid views are byte-identical.',inspected_views=list(range(8)),changes=changes,limitations=limitations,model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),recipe=str(Path(__file__).with_name('refine_castle_texture_feedback.py').resolve()),user_approval='pending',texture_generation='not-started')
 (w/'candidate.json').write_text(json.dumps(c,indent=2)+'\n');(w/'review.md').write_text('# '+c['asset_id']+'\n\n'+'\n'.join('- '+x for x in changes+limitations)+'\n\nAll eight solid and source-textured views inspected. Exact source RGB independently verified. User approval pending.\n')
 proof['status']='ready-for-user';proof['inspected_views']=list(range(8));(w/'texture-feedback-correction.json').write_text(json.dumps(proof,indent=2)+'\n')
if __name__=='__main__':main()
