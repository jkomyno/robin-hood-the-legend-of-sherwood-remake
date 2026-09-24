"""Resolve the selected experiment without assuming its directory is the model ID."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement/texture-generation'
def selected_experiment(asset):
 jobs=json.loads((WORK/'preparation-jobs.json').read_text())['assets']
 matches=[j for j in jobs if j['asset_id']==asset]
 if len(matches)!=1 or not matches[0].get('experiment'):raise ValueError('Missing unique selected experiment for '+asset)
 p=Path(matches[0]['experiment']).resolve()
 if json.loads((p/'views.json').read_text())['asset_id']!=asset:raise ValueError('Selected experiment identity differs')
 return p

def reconciliation_reference(generation):
 """Use exact cropped transport content only when its pixels prove the crop."""
 from PIL import Image
 generation=Path(generation);raw=generation/'generated-raw.png';content=generation/'generated-content.png'
 with Image.open(raw) as r,Image.open(generation/'generated-preserved.png') as preserved:
  if r.size==preserved.size:return raw
  padding=json.loads((generation/'generation.json').read_text()).get('transportPadding',{})
  box=padding.get('content_box',{})
  if (padding.get('version')!=1 or padding.get('kind')!='bottom-padding' or
      r.size!=(padding.get('width'),padding.get('height')) or
      preserved.width!=r.width or not 0<preserved.height<=r.height or
      (box.get('left'),box.get('top'))!=(0,0) or
      (box.get('width'),box.get('height'))!=preserved.size):
   raise ValueError('Unproven generation transport geometry')
  with Image.open(content) as c:
   if c.size!=preserved.size or c.convert('RGBA').tobytes()!=r.crop((0,0,*preserved.size)).convert('RGBA').tobytes():
    raise ValueError('Generation content is not the exact unscaled raw crop')
 return content
