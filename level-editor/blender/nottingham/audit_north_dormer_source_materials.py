"""Audit actual saved dormer atlases against source and exact accepted receiver census."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).parent))
import audit_small_hut_source_materials as sampler
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'level-editor/work/nottingham-refinement';A='nottingham-north-dormer-house'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 out=Path(sys.argv[sys.argv.index('--')+1]).resolve();old=W/'round-38/assets'/A
 sampler.A=A;sampler.box=(1620,280,1840,630);box=sampler.box
 before,bo,_=sampler.sample(old/'model.blend');after,ao,_=sampler.sample(out/'model.blend');source=np.array(Image.open(out/'reference/source.png').convert('RGB').crop(box))
 census=json.loads((out/'inspection/source-receiver-census.json').read_text());assert census['model_sha256']==sha(out/'model.blend');accepted=np.zeros(ao.shape,bool);added=np.zeros(ao.shape,bool);suspects=[];witnesses=[]
 for row in census['pixels']:
  x,y=row['source'];ix,iy=x-box[0],y-box[1]
  if row['new']!='accepted':continue
  accepted[iy,ix]=True;added[iy,ix]=row['old']!='accepted';rgb=after[iy,ix];src=source[iy,ix]
  if (rgb.max()-rgb.min()<3 and src.max()-src.min()>20):suspects.append(dict(source=[x,y],receiver=int(ao[iy,ix]),atlas=rgb.tolist(),art=src.tolist(),original_atlas=before[iy,ix].tolist(),original_receiver=int(bo[iy,ix]),newly_accepted=bool(added[iy,ix])))
  if added[iy,ix]:witnesses.append(dict(source=[x,y],receiver=int(ao[iy,ix]),atlas=rgb.tolist(),art=src.tolist()))
 panels=[]
 for arr in [source,before,after]:
  arr=arr.copy();arr[~accepted]//=3;panels.append(Image.fromarray(arr).resize((440,700),Image.Resampling.NEAREST))
 sheet=Image.new('RGB',(1320,725));draw=ImageDraw.Draw(sheet)
 for i,(im,title) in enumerate(zip(panels,['Original artwork (accepted domain)','Approved saved atlas','Candidate saved atlas'])):sheet.paste(im,(i*440,25));draw.text((i*440+4,5),title,fill='white')
 sheet.save(out/'inspection/source-material-comparison.png')
 overlay=source.copy();overlay[added]=[0,255,255];Image.fromarray(overlay).resize((880,1400),Image.Resampling.NEAREST).save(out/'inspection/added-source-overlay.png')
 report=dict(status='AWAITING-VISUAL-REVIEW',model_sha256=sha(out/'model.blend'),source_census_sha256=sha(out/'inspection/source-receiver-census.json'),accepted_count=int(accepted.sum()),added_count=int(added.sum()),gray_atlas_suspects=suspects,added_saved_material_witnesses=witnesses,limitations=['Nearest saved UV atlas samples may differ from exact source RGB due to atlas resolution. Gray screening is diagnostic, not a completeness verdict.','Source acceptance includes complete scene occlusion; atlas sampling isolates this asset to compare accepted receiver surfaces.'])
 (out/'inspection/source-material-comparison.json').write_text(json.dumps(report,indent=2)+'\n');print(dict(accepted=report['accepted_count'],added=report['added_count'],gray_suspects=len(suspects)))
if __name__=='__main__':main()
