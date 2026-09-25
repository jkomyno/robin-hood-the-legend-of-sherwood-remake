"""Complete native forge artwork domain, independent of candidate acceptance."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[3]
def domain():
 folder=ROOT/'level-editor/work/nottingham-refinement/mask-review/inventory-v6'
 rows=json.loads((folder/'manifest.json').read_text())['masks']
 result=Image.new('L',(2304,3520));proof=[]
 for index in (210,211):
  row=next(r for r in rows if r['index']==index);p=folder/row['png']
  part=Image.new('L',result.size);part.paste(Image.open(p).convert('L'),tuple(row['box_top_left']))
  result=ImageChops.lighter(result,part)
  proof.append(dict(index=index,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),box_top_left=row['box_top_left']))
 return result,dict(native_masks=proof,domain_sha256=hashlib.sha256(result.tobytes()).hexdigest(),domain_size=list(result.size))
