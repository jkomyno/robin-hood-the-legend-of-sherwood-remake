"""Export bounded reviewed projection revisions for the upper green and dormer houses."""
from pathlib import Path
import hashlib, json

root = Path(__file__).resolve().parents[3]
work = root/'level-editor/work/nottingham-refinement'
out = work/'mask-review'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
source = work/'source-states/covered.png'
assignment = dict(source_node='building-155',reviewed=True,mask_indices=[106,107,108,109],
    exclude_mask_indices=[105],exclusions_reviewed=True,
    exclusion_reason='Native105 isolates the separate foreground turret; its painted roof and stone shaft are not the green-house facade.',
    constraint_kind='reviewed-native-silhouette',review_evidence='upper-green-lower-wall-review.png',
    review_note='Native107 supplies the previously omitted lower left stone facade and doorway. Existing106/108/109 cover the upper structure. Assignment is restricted to receiver155; native105 is subtracted and source-camera first-hit visibility remains mandatory.')
report=dict(version=1,projection='exterior',assignments=[assignment],source_sha256=sha(source),
    evidence_sha256={'upper-green-lower-wall-review.png':sha(out/'upper-green-lower-wall-review.png')},
    depth_evidence=str((work/'town-audit/upper-houses-depth-trace.json').resolve()),
    depth_witnesses=[s for s in json.loads((work/'town-audit/upper-houses-depth-trace.json').read_text())['building-155']['samples']
        if s['first_hit']=='building-155' and s['gap']<.01 and s['cosine']>0],
    geometry_change=False)
(out/'upper-green-wall-overrides.json').write_text(json.dumps(report,indent=2)+'\n')
p=work/'round-1/assets/nottingham-north-dormer-house'
policy=dict(version=1,asset_id='nottingham-north-dormer-house',model_sha256_before=sha(p/'model.blend'),
    object_properties=[dict(source_node=f'building-{n:03}',property='projection_min_cosine',before=.18,after=.0001)for n in [122,124,125]],
    geometry_change=False,source_mask_change=False,
    reason='Per-object0.18 rejects actual source-visible right walls with facing cosines0.159/0.160. Restore ordinary positive-facing threshold on these owned receivers; exact source masks and scene first-hit depth continue to reject hidden surfaces.',
    evidence=[str((work/'town-audit/coverage-normals.json').resolve()),str((out/'coverage-loss-highlight.png').resolve())],
    validation_required='Unchanged vertices/faces/transforms/other object properties; rebake and fixed-camera validation; inspect recovered right facade and all reverse views.')
(out/'north-dormer-facing-policy-review.json').write_text(json.dumps(policy,indent=2)+'\n')
print('Reviewed upper green155 mask and north dormer122/124/125 facing policy exported')
