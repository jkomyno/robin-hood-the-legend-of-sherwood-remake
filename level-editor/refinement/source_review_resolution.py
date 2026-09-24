"""Resolve review-only source holds against an explicit exact-revision decision.

The immutable handoff remains evidence. Resolutions are separate derived state;
missing/stale records and actual technical defects never grant eligibility.
"""
import json
from pathlib import Path
from review_evidence import sha


GEOMETRY_REVIEW_ONLY = 'Fresh wall-to-roof contact revision awaits user geometry approval.'


def apply_generation_gate(item, handoff, handoff_path, resolutions_path):
    item.pop('source_review_resolution', None)
    item.pop('generation_blockers', None)
    technical = (item.get('technical_eligible') and item.get('stored_material_validation') == 'PASS')
    approved = item.get('decision_state') == 'current' and item.get('user_approval') == 'approved'
    geometry_review_only = (handoff.get('source_review') == GEOMETRY_REVIEW_ONLY
                            and handoff.get('texture_generation') == 'blocked'
                            and not handoff.get('texture_issue')
                            and not handoff.get('generation_blocked'))
    blockers = {key: handoff[key] for key in ('generation_blocked', 'texture_issue', 'source_review', 'texture_generation')
                if handoff.get(key) and (key != 'source_review' or handoff[key] == 'pending' or geometry_review_only)
                and (key != 'texture_generation' or handoff[key] == 'blocked')}
    errors = []
    # Manifest-level holds must match the frozen handoff; decisions cannot carry
    # an unresolved texture issue and also clear it via a sidecar.
    for key in ('generation_blocked', 'texture_issue'):
        derived_geometry_hold = (key == 'generation_blocked' and geometry_review_only
                                 and item.get(key) is True)
        if item.get(key) and item[key] != handoff.get(key) and not derived_geometry_hold:
            errors.append('additional manifest ' + key)
        if item.get('user_decision', {}).get(key):
            errors.append('decision ' + key)
    if blockers:
        path = Path(resolutions_path)
        entries = []
        if path.exists():
            data = json.loads(path.read_text())
            if data.get('version') != 1 or not isinstance(data.get('resolutions'), list):
                raise ValueError('Expected source review resolutions version 1')
            entries = [r for r in data['resolutions'] if r.get('asset_id') == item['id']]
        if len(entries) != 1:
            errors.append('missing or duplicate source review resolution')
        else:
            resolution = entries[0]
            decision = item.get('user_decision', {})
            issue = handoff.get('texture_issue')
            review_only = geometry_review_only or (isinstance(issue, dict) and issue.get('status') == 'correction-awaiting-user-review') or (
                handoff.get('source_review') == 'pending' and
                issue == 'Source mapping correction pending review; approved geometry unchanged.')
            if not review_only:
                errors.append('hold is not a corrected source packet awaiting review')
            if not technical or not approved:
                errors.append('current approval and completed technical validation required')
            if (resolution.get('revision_sha256') != item['revision']['sha256'] or
                    decision.get('revision_sha256') != item['revision']['sha256'] or
                    resolution.get('approval_decision') != decision or decision.get('decision') != 'approved'):
                errors.append('resolution does not match exact current approval decision')
            handoff_path = Path(handoff_path).resolve()
            handoff_hash = sha(handoff_path)
            bound = item['revision']['evidence'].get('handoff', {})
            if (resolution.get('handoff_sha256') != handoff_hash or bound.get('sha256') != handoff_hash or
                    Path(bound.get('path', '')).resolve() != handoff_path):
                errors.append('resolution handoff differs from approved evidence')
            expected = {'handoff.' + key: value for key, value in blockers.items()}
            if resolution.get('cleared_blockers') != expected:
                errors.append('resolution does not name exactly the current review-only blockers')
            if not errors:
                item['source_review_resolution'] = {'path': str(path.resolve()), 'sha256': sha(path),
                                                  'record': resolution}
    item['generation_blockers'] = errors
    item['generation_eligible'] = bool(technical and approved and not errors)
    item['publication_eligible'] = item['generation_eligible']
    return item['generation_eligible']
