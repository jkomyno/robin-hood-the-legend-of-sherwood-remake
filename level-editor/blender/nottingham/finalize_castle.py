"""Record the completed visual castle audit without implying user approval."""
import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parents[2] / 'work/nottingham-refinement'
AUDIT = {
 'castle-northeast-spire': ('ready-for-user', ['Replaced paired ridge prisms with one closed source-aligned apex and continuous roof.'], ['Rear roof and concealed thickness are inferred; polygonal masonry footprint retained.']),
 'castle-northwest-spire': ('ready-for-user', ['Replaced stretched roof ridge with a single measured apex and closed roof.'], ['Hidden roof underside and masonry rear remain inferred.']),
 'castle-southwest-spire': ('ready-for-user', ['Closed single-apex roof; all three parts explicitly belong to covered hall state.'], ['Entire asset is absent when hall patch008 is revealed; no empty-state mesh is invented.', 'Unsupported masonry source pixels remain neutral.']),
 'castle-southeast-spire': ('ready-for-user', ['Closed single-apex roof; fresh immutable camera margin includes the tip in all eight views.'], ['Concealed roof and wall depth are inferred.']),
 'castle-upper-stair': ('ready-for-user', ['Ten upper risers and five lower risers replace continuous ramps.'], ['Hidden stair supports preserve the source-volume depth hypothesis.']),
 'castle-west-stair-tower': ('ready-for-user', ['Sixteen measured stair treads and supported roof body replace coarse ramps and roof columns.'], ['Concealed tower shell remains polygonal; unresolved source ownership stays neutral.']),
 'castle-west-annex': ('ready-for-user', ['Thin roof shell with overhang, inset masonry body, recessed closed door and narrow slit.', 'Reviewed native430 minus foreground283/282 constrains roof/body source ownership.'], ['Concealed wall inset, eave thickness and recess depth are inferred; hidden rear remains neutral.']),
 'castle-west-conical-tower': ('ready-for-user', ['Replaced stretched ridge with a closed single-apex cone; retained the measured lower roof skirt.', 'Reviewed isolated native mask436 projects the tower and skirt without foreground stairs.'], ['Rear roof depth is inferred; the lower shaft below the native mask cutoff remains neutral.']),
 'castle-west-stair': ('ready-for-user', ['Corrected lower stair contact from native100 to195 and authored seven measured risers.'], ['Concealed underside remains inherited; no approved source pixels for this stair, so projection remains neutral.']),
 'castle-entry-steps': ('ready-for-user', ['Two risers surround landing115; underside meets courtyard100; adjacent corner endpoints are normalized to remove overlapping spikes.'], ['Step depth interpolation is inferred between measured outer/inner edges; source ownership remains unknown.']),
 'castle-east-round-tower': ('ready-for-user', ['Closed curved drum, two molded courses, two upper openings and lower arrow slit.', 'Five curved conical roof sectors share the measured cap, teardrop, sphere, rod and spike; fresh camera margin includes the full finial.'], ['Rear ellipse, concealed continuations and shallow recess depth are inferred; unsupported rear remains neutral.']),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(name, workspace=None):
    asset = 'nottingham-' + name
    workspace = workspace or WORK / 'round-1/assets' / asset
    status, changes, limitations = AUDIT[name]
    changes, limitations = list(changes), list(limitations)
    if (workspace / 'closed-envelope-report.json').exists():
        changes.append('Rebuilt inherited per-face mesh seams as closed native-coordinate envelopes; all eight final views reviewed.')
    validation = json.loads((workspace / 'validation.json').read_text())
    if validation['status'] != 'PASS':
        raise ValueError('Cannot record completed audit over a failed validation')
    views = json.loads((workspace / 'modified/views.json').read_text())
    if len(views['views']) != 8:
        raise ValueError('Incomplete modified view packet')
    data = dict(version=1, asset_id=asset, status=status, geometry_reviewed=True,
        geometry_refined=True, inspected_views=list(range(8)), changes=changes,
        limitations=limitations, model_sha256=sha(workspace/'model.blend'),
        modified_views_sha256=sha(workspace/'modified/views.json'),
        recipe=str(Path(__file__).resolve()), user_approval='pending', texture_generation='not-started')
    if name == 'castle-southwest-spire':
        data['display_states'] = {'patch-008': {'covered': ['building-509','building-514','building-515'],
                                              'revealed': [], 'revealed_note': 'Entire asset hidden by hall cutaway.'}}
    (workspace/'candidate.json').write_text(json.dumps(data,indent=2)+'\n')
    (workspace/'review.md').write_text('# '+asset+'\n\nInspected original source and all eight solid/source-textured views.\n\n'+
        '\n'.join('- '+line for line in changes+limitations)+'\n\nUser geometry approval pending. Texture generation not started.\n')
    return data


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset', choices=AUDIT)
    parser.add_argument('--workspace', type=Path)
    args=parser.parse_args()
    finalize(args.asset,args.workspace)
