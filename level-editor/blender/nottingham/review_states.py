"""Build authored, hash-bound Nottingham state ownership reviews and evidence.

Run with system Python. Ownership review is distinct from user approval and
does not waive geometry-readiness limitations recorded on each patch.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'work/nottingham-refinement/source-states'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def nodes(numbers):
    return [f'building-{n:03}' for n in numbers]


def authored(patch, receivers, retained, partial, exclusions, selectors, evidence, limitations=()):
    return {'version': 1, 'patch_id': patch, 'reviewed': True, 'role': 'interior',
            'reviewer': 'Codex source-state visual and native geometry review',
            'evidence': evidence,
            'source_sha256': sha(SOURCE/'revealed.png'),
            'alpha_sha256': sha(SOURCE/f'{patch}-alpha.png'),
            'receiver_nodes': nodes(receivers), 'retained_occluder_nodes': nodes(retained),
            'partial_cover_nodes': nodes(partial),
            'exclude_occluder_components': [{'source_node': f'building-{number:03}',
                                             'projection_component': component, 'patch_id': patch}
                                            for number, component in exclusions],
            'receiver_components': {'interior-'+patch: [
                {'source_node': f'building-{number:03}', 'projection_components': components, 'patch_id': patch}
                for number, components in selectors.items()]},
            'occluder_additions': {},
            'ownership_review_scope': 'Named receivers and cover partitions only; no user geometry or texture approval.',
            'geometry_ready': False, 'user_approval': 'pending', 'limitations': list(limitations)}


def noninterior(patch, evidence):
    return {'version': 1, 'patch_id': patch, 'reviewed': True, 'role': 'non-interior',
            'reviewer': 'Codex source-state visual and native geometry review', 'evidence': evidence,
            'receiver_nodes': [], 'retained_occluder_nodes': [], 'partial_cover_nodes': [],
            'exclude_occluder_components': [], 'receiver_components': {}, 'occluder_additions': {},
            'user_approval': 'pending'}


def build_reviews():
    reviews = {}
    church_cuts = [383,384,385,387,388,389,390,392,394,395,396,397,398,399,406,408]
    reviews['patch-000'] = authored('patch-000',
        [383,384,385,386,387,393,394,395,396,400,401,414,*range(418,430)],
        [380,381,382,383,384,385,386,387,393,394,395,396,398,399,400,401,402,403,404,405,406,407,408,409,410,411,412,413,414,415],
        church_cuts, [(n,'church-removable-cover') for n in church_cuts],
        {383:['church-retained'],384:['church-retained'],385:['church-retained','church-nave-floor'],
         387:['church-retained'],394:['church-retained'],395:['church-retained'],396:['church-retained'],
         386:['church-retained'],393:['church-retained'],400:['church-retained'],401:['church-retained'],
         414:['church-retained','church-side-room-floor'], **{n:['church-interior'] for n in range(418,430)}},
        'patch-000-compare.png and native projected outlines380..429 were inspected. Covered roofs obscure a nave with four columns421..424, altar426, confessional425 and candle stand427; adjoining room contains cabinet418, bed419 and table420. Separate floors are assigned to385/414. Roof406/408 and398/399 retain source-visible strips; front low walls remain while named upper components disappear.',
        ['Source cut lines approximate irregular painted roof edges.',
         'Floor datum0, concealed extent, and low-wall heights28/56/100 require camera validation.',
         'Working components exist only after refine_church.py; frozen input must use baseline projection.'])
    reviews['patch-000']['receiver_components']['exterior'] = [
        {'source_node': f'building-{number:03}', 'projection_components': parts, 'patch_id': 'patch-000'}
        for number,parts in {
            **{n:['church-removable-cover'] for n in [383,384,385,387,394,395,396]}}.items()]
    reviews['patch-001'] = noninterior('patch-001',
        'Initial and transition sprites show the upper prison door moving within an existing doorway (patch-001-compare.png). This is an independent door state, not a new room reveal. Old453 and new455 door geometry must be displayed separately and projected from their respective state graphic; do not use the room source for both.')
    reviews['patch-002'] = authored('patch-002', [435,436,438,439,440,451,452],
        [435,436,437,438,439,440,441,442,443,444,445,446,447,448,449,450,451,452,454],
        [441,442,443,454], [(n,'prison-removable-cover') for n in [441,442,443,454]],
        {438:['prison-interior-partition']},
        'patch-002-compare.png and prison-audit/upper-context.png versus upper-covered.png were inspected with native outlines435..455. The room occupies the existing terrace datum250. Floors435/436, partition438, rear wall439, lintel440 and interior upright451 remain; the terrace, upper turret and retained shell must occlude the room. Full-height facade441/442 and doorpost443/454 split into retained and removable bands.',
        ['Covered and revealed independent door states453/455 are excluded from shared receiver ownership.',
         'Wall cut boundaries and low interior partition need final fixed-camera inspection.'])
    reviews['patch-002']['receiver_nodes'] = nodes([435,436,438,439,440,441,442,451,452])
    for number in [441,442]:
        reviews['patch-002']['receiver_components']['interior-patch-002'].append({
            'source_node': f'building-{number:03}', 'projection_components': ['prison-retained'], 'patch_id': 'patch-002'})
    reviews['patch-002']['receiver_components']['exterior'] = [
        {'source_node': f'building-{number:03}', 'projection_components': ['prison-removable-cover'],
         'patch_id': 'patch-002'} for number in [441,442]]
    reviews['patch-002']['limitations'] = [
        'Retained rim270 and partition438 crown250..310 are measured hypotheses with about5 units uncertainty.',
        'Door453/455 independent states and fine arch curvature remain to be validated.']
    reviews['patch-003'] = noninterior('patch-003',
        'Initial and final sprites depict the same seven-bar portcullis lowered and raised; all41 transition frames are archived. There is no interior reveal. Explicit source-silhouette initial/applied meshes belong to canonical gate arch333 and preserve sprite ownership separately from masonry.')
    reviews['patch-004'] = noninterior('patch-004',
        'Initial and final sprites depict the winch/lever mechanism inside the gate turret; all41 transition frames are archived. This is mechanical state, distinct from room cover patch005. Separate source-preserved initial/applied components belong to canonical turret337.')
    reviews['patch-005'] = authored('patch-005', [337], [334,337,338,339], [337],
        [(337,'mechanism-removable-cover')],
        {337:['mechanism-base','mechanism-rear-wall','mechanism-left-wall','mechanism-room-floor']},
        'patch-005-compare.png shows a round exterior facade replaced by a visible wooden room floor and inner stone wall. Native projected outline337 locates the same annular tower shell. The rear/left annular walls, plinth and upper turret remain; only the authored front wall band opens. The mechanical sprite is independent patch004, so it is not projected onto the wall/floor receivers.',
        ['Native floor datum110 and front band110..235 are inferred from anchor and visible floor landmarks.',
         'Interior walls are source-backed hypotheses pending fixed-camera review.',
         'Animated source components preserve state materials and must not receive the static covered projection.'])
    reviews['patch-005']['receiver_components']['exterior'] = [
        {'source_node': 'building-337', 'projection_components': ['mechanism-upper',
           'mechanism-removable-cover','mechanism-initial','mechanism-applied'], 'patch_id': 'patch-005'}]
    reviews['patch-006'] = noninterior('patch-006',
        'Initial/transition source sprites depict the southwest prison door opening in its existing arch. The room shell reveal is separate patch007; geometry476/477 must retain independent closed/open state. No new interior receiver is assigned to this door-only patch.')
    reviews['patch-007'] = authored('patch-007', [456,457,468,469,470,471,472,473,474],
        [456,457,458,459,460,461,462,463,464,465,466,467,468,469,470,471,472,473,474],
        [456,457,470], [(n,'prison-removable-cover') for n in [456,457,470]],
        {456:['prison-retained'],457:['prison-retained','prison-retained-rear-wall'],470:['prison-retained'],
         472:['prison-interior-wall','prison-interior-floor'],473:['prison-interior-post'],474:['prison-interior-lintel']},
        'patch-007-compare.png and prison native-outline sheets456..477 were inspected. The revealed curved cell room keeps terrace320+, internal stair/landing468/469, buttress471 and low curved partition472. Facade456/457 and upright470 retain plinth and terrace support but lose their middle cover bands. New floor belongs to472;473/474 define the entrance post/lintel.',
        ['Floor extent and curved partition height65 are inferred from visible floor and masonry edges.',
         'Door states476/477 require their independent source-state pass.'])
    reviews['patch-007']['receiver_components']['exterior'] = [
        {'source_node': f'building-{number:03}', 'projection_components': parts, 'patch_id': 'patch-007'}
        for number,parts in {456:['prison-removable-cover'],457:['prison-removable-cover'],
                            470:['prison-removable-cover']}.items()]
    reviews['patch-007']['limitations'] = [
        'Lower exterior rim45/40 and curved partition25..65 follow measured contours; hidden depth and floor extent remain inferred.',
        'Door476/477 independent states and fine arch curvature remain to be validated.']
    reviews['patch-008'] = authored('patch-008', [533,534,535],
        [504,505,506,508,512,513,525,531,532],
        [505,506,507,530,531,532],
        [(n,'castle-hall-removable-cover') for n in [505,506,507,531,532]]+[(530,'castle-hall-ceiling-cover')],
        {},
        'patch-008-compare.png and castle-audit/hall-grid.png show retained back roof strips, exposed masonry back wall, chandelier, stool533 and table535. Native530 is a ceiling near590 and cannot receive the painted floor. A separately authored floor component under530 uses the continuous balcony slabs501/512 at native420, consistent with furniture533/535 at433/447;505/506 keep roof strips and507 loses its entire front triangular roof. Front walls531/532 retain their lower structural base.',
        ['Recipe components are planned and require castle geometry report before this review is operational.',
         'Floor datum420 is supported by adjacent slabs; concealed extent remains inferred and wall504 may still obstruct the room.',
         'This patch cannot be marked geometry-ready until camera and ownership validation pass.'])
    reviews['patch-008']['receiver_coverage'] = 'incomplete; visually reviewed furniture only'
    reviews['patch-008']['planned_receiver_components'] = {
        'building-530': ['castle-hall-floor']}
    for number, phrase in [(9,'activates courtyard architectural sight and mask records547..550'),
                            (10,'deactivates church-road prop sight and mask records551..554')]:
        patch = f'patch-{number:03}'
        reviews[patch] = noninterior(patch,
            'The pixel_vert pseudo-profile has no authored interior image. Native records show this patch '+phrase+
            '. Initial/applied source contexts are pixel-identical. These are simulation/occlusion switches; source appearance does not justify an invented room or deleting all render geometry.')
    return reviews


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'work/nottingham-refinement/state-review')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    layers = json.loads((SOURCE/'layers.json').read_text())
    layers['map'] = 'nottingham'
    base = Image.open(SOURCE/'revealed.png')
    covered = Image.open(SOURCE/'covered.png')
    for patch in layers['patches']:
        graphic = patch['graphic']
        if graphic:
            x,y,w,h = graphic['bbox']
            box = (max(0,x-50),max(0,y-50),min(base.width,x+w+50),min(base.height,y+h+50))
            a,b = covered.crop(box),base.crop(box)
            comparison = Image.new('RGB',(a.width*2,a.height+24))
            comparison.paste(a,(0,24)); comparison.paste(b,(a.width,24))
            draw = ImageDraw.Draw(comparison)
            draw.text((5,5),patch['id']+' COVERED',fill='white')
            draw.text((a.width+5,5),'REVEALED SUBSTRATE',fill='white')
            comparison.save(output/(patch['id']+'-compare.png'))
            for key in ['image','alpha']:
                graphic[key] = str(SOURCE/graphic[key])
    for name,path in layers['sources'].items():
        layers['sources'][name] = str(SOURCE/path)
    def resolve_evidence(value):
        if isinstance(value, dict):
            return {key: resolve_evidence(item) for key,item in value.items()}
        if isinstance(value, list):
            return [resolve_evidence(item) for item in value]
        if isinstance(value, str) and len(value) < 240 and not Path(value).is_absolute():
            candidate = SOURCE/value
            if candidate.is_file():
                return str(candidate)
        return value
    layers = resolve_evidence(layers)
    layers['projection_reviews'] = build_reviews()
    layers['geometry_approval'] = 'pending'
    layers['texture_generation'] = 'not-started'
    layers['operational_note'] = 'Apply each asset recipe before using its component selectors; this working manifest does not authorize publication.'
    sys.path.insert(0, str(ROOT/'work/nottingham-refinement/tooling/315d227e98d52a78'))
    from interior_layers import validate_projection_reviews
    validate_projection_reviews(layers, output)
    (output/'layers.json').write_text(json.dumps(layers,indent=2)+'\n')
    baseline = copy.deepcopy(layers)
    for patch, review in baseline['projection_reviews'].items():
        if review['role'] != 'interior':
            continue
        review['role'] = 'deferred-interior'
        review['geometry_ready'] = False
        review['reason'] = 'The frozen scene has no reviewed cutaway components; activate this owned review only after the geometry recipe.'
        for key in ['receiver_nodes','retained_occluder_nodes','partial_cover_nodes','exclude_occluder_components']:
            review[key] = []
        review['receiver_components'] = {}
        review['occluder_additions'] = {}
    validate_projection_reviews(baseline, output)
    (output/'baseline-layers.json').write_text(json.dumps(baseline,indent=2)+'\n')
    for asset, patch in [('nottingham-church','patch-000'),('nottingham-upper-prison','patch-002'),
                         ('nottingham-castle-gate-east-tower','patch-005'),
                         ('nottingham-southwest-prison','patch-007'),('nottingham-castle-main-hall','patch-008')]:
        working = copy.deepcopy(baseline)
        working['projection_reviews'][patch] = layers['projection_reviews'][patch]
        validate_projection_reviews(working, output)
        (output/(asset+'-layers.json')).write_text(json.dumps(working,indent=2)+'\n')
    (output/'review-validation.json').write_text(json.dumps({
        'schema_and_source_hashes_valid': True, 'base_patch_reviews': len(layers['projection_reviews']),
        'interior_patches': [p for p,r in layers['projection_reviews'].items() if r['role']=='interior'],
        'non_interior_patches': [p for p,r in layers['projection_reviews'].items() if r['role']=='non-interior'],
        'geometry_ready': False, 'user_approval': 'pending',
        'source_manifest_sha256': sha(SOURCE/'layers.json'),
        'working_manifest_sha256': sha(output/'layers.json'),
        'required_next_checks': ['Apply named geometry recipes','Verify every selected component exists',
                                 'Render fixed covered/revealed views','Validate ownership and known RGB',
                                 'Review independent door and mechanical states']},indent=2)+'\n')
    print(json.dumps({'output':str(output), 'reviews':11, 'schema_valid':True, 'geometry_ready':False}))


if __name__ == '__main__':
    main()
