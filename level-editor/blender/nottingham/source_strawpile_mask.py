"""Freeze a conservative authored source mask for exposed courtyard straw.

The native silhouette combines the straw and the foreground wattle fence. This
asset-local authority keeps every existing mask unchanged and adds one explicitly
authored polygon, retaining only visibly clear straw inside that silhouette.
"""
from pathlib import Path
import hashlib
import json
import shutil

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'level-editor/work/nottingham-refinement'
POLYGON = [(633,2772),(650,2768),(666,2772),(674,2780),(685,2783),
           (691,2793),(688,2798),(678,2806),(665,2809),(653,2804),
           (648,2795),(634,2788)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    review = RUN / 'mask-review'
    original = review / 'inventory-v11'
    target = review / 'inventory-v11-strawpile'
    if target.exists():
        raise ValueError('Authored authority already exists; preserve it and choose a new revision')
    shutil.copytree(original, target)
    inventory = json.loads((original / 'manifest.json').read_text())
    index = max(row['index'] for row in inventory['masks']) + 1
    source = RUN / 'source-states/covered.png'
    bitmap = Image.new('L', (2304,3520), 0)
    ImageDraw.Draw(bitmap).polygon(POLYGON, fill=255)
    bitmap.save(target / 'authored-strawpile-visible.png')
    evidence = Image.open(source).convert('RGB').crop((600,2740,720,2860)).resize((720,720))
    draw = ImageDraw.Draw(evidence)
    points = [((x-600)*6,(y-2740)*6) for x,y in POLYGON]
    draw.line(points+[points[0]], fill=(0,255,255), width=3)
    evidence.save(review / 'strawpile-authored-review.png')
    inventory['masks'].append({
        'index': index, 'png': 'authored-strawpile-visible.png',
        'box_top_left': [0,0], 'box_size': [2304,3520],
        'layer': None, 'layer_index': None, 'synthetic': True,
        'constraint_kind': 'reviewed-authored-visible-straw-polygon',
        'source_sha256': sha(source), 'source_polygon': POLYGON,
        'review_evidence': str(review / 'strawpile-authored-review.png'),
        'scope': 'Conservative visible straw only; foreground wattle, stone wall and ambiguous edges remain unknown.'
    })
    (target / 'manifest.json').write_text(json.dumps(inventory,indent=2)+'\n')
    manifest = json.loads((review / 'source-masks-v11-baseline.json').read_text())
    manifest['mask_inventory'] = str(target / 'manifest.json')
    assignment = next(row for row in manifest['projections']['exterior']['assignments']
                      if row.get('source_node') == 'building-260')
    assignment.update(mask_indices=[index], exclude_mask_indices=[178],
        constraint_kind='reviewed-authored-visible-straw-polygon', reviewed=True,
        exclusions_reviewed=True, review_evidence=str(review / 'strawpile-authored-review.png'),
        review_note='Native182 combines straw and foreground wattle. The authored polygon accepts only clear exposed straw; no native mask identity is repurposed.',
        exclusion_reason='Native178 retains the independently reviewed foreground foliage exclusion.')
    destination = review / 'source-masks-v11-strawpile.json'
    destination.write_text(json.dumps(manifest,indent=2)+'\n')
    old = json.loads((original / 'manifest.json').read_text())
    assert inventory['masks'][:-1] == old['masks']
    assert all(sha(original / row['png']) == sha(target / row['png']) for row in old['masks'])
    (review / 'validation-v11-strawpile.json').write_text(json.dumps({
        'status':'PASS','preserved_mask_count':len(old['masks']),
        'preserved_native_mask_count':527,'new_authored_index':index,
        'source_sha256':sha(source),'manifest_sha256':sha(destination),
        'inventory_sha256':sha(target / 'manifest.json'),
        'authored_polygon':POLYGON,'accepted_pixels':sum(v>0 for v in bitmap.get_flattened_data())
    },indent=2)+'\n')
    print(destination)


if __name__ == '__main__':
    main()
