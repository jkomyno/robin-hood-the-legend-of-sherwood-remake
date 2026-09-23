"""Prepare exact approved eight-view evidence for the shared texture driver.

This copies reviewed pixels/cameras without resizing or rerendering. Local edit
masks expose only geometry pixels that the reviewed ownership buffers mark as
unknown. An explicit matching geometry decision is required before any output.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from PIL import Image

from review_evidence import bind_decision, load_decisions, sha


def prepare(manifest_path, asset_id, output, decisions_path=None, *, check_only=False):
    manifest_path = Path(manifest_path).resolve(strict=True)
    data = json.loads(manifest_path.read_text())
    matches = [i for i in data['items'] if i['id'] == asset_id]
    if len(matches) != 1:
        raise ValueError('Expected one complete review packet for the requested asset')
    item = copy.deepcopy(matches[0])
    decisions = load_decisions(Path(decisions_path) if decisions_path else
                               manifest_path.parent / 'decisions.json',
                               {i['id'] for i in data['items']} | {i['id'] for i in data.get('without_packets', [])})
    bind_decision(item, decisions)
    if item['user_approval'] != 'approved':
        raise ValueError('Texture preparation requires an explicit current geometry approval')
    if (not item.get('technical_eligible') or not item.get('generation_eligible')
            or item.get('stored_material_validation') != 'PASS'):
        raise ValueError('Texture preparation requires completed technical validation')
    workspace = Path(item['workspace'])
    if not workspace.is_absolute():
        workspace = manifest_path.parent / workspace
    workspace = workspace.resolve(strict=True)
    handoff = json.loads((workspace / 'handoff.json').read_text()) if (workspace / 'handoff.json').exists() else {}
    for record in (item, item.get('user_decision', {}), handoff):
        if record.get('generation_blocked') or record.get('texture_issue'):
            raise ValueError('Texture preparation blocked by recorded generation or texture issue')
    identity = {'asset_id': asset_id, 'model_sha256': item['revision']['model_sha256'],
                'evidence': {key: value['sha256'] for key, value in item['revision']['evidence'].items()}}
    if hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest() != item['revision']['sha256']:
        raise ValueError('Review revision identity differs from its evidence')
    model = workspace / 'model.blend'
    if sha(model) != item['revision']['model_sha256']:
        raise ValueError('Approved model changed')
    for key, evidence in item['revision']['evidence'].items():
        if sha(Path(evidence['path'])) != evidence['sha256']:
            raise ValueError('Approved evidence changed: ' + key)
    packet = Path(item['textured']).parent.resolve(strict=True)
    frames_path = packet / 'views.json'
    bound_frames = list(item['revision']['evidence'].values()) + list(item['user_decision'].get('geometry_basis', {}).get('files', {}).values())
    if not any(Path(entry['path']).resolve() == frames_path and entry['sha256'] == sha(frames_path) for entry in bound_frames):
        raise ValueError('Camera and ownership manifest is absent from approved evidence')
    frames = json.loads(frames_path.read_text())
    if frames['asset_id'] != asset_id or [v['index'] for v in frames['views']] != list(range(8)):
        raise ValueError('Expected eight ordered views for the approved asset')
    width, height = frames['tile_size']
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in (width, height)):
        raise ValueError('Frozen camera tile dimensions must be positive integers')
    canvas = (width * 4, height * 2)
    cw, ch = canvas
    if (cw % 16 or ch % 16 or max(canvas) > 3840 or max(canvas) / min(canvas) > 3
            or not 655360 <= cw * ch <= 8294400):
        raise ValueError('Approved canvas is outside Sunburst custom-size constraints; never rescale')
    for path in (Path(item['textured']), Path(item['solid'])):
        with Image.open(path) as image:
            if image.size != canvas:
                raise ValueError('Approved sheet dimensions differ from fixed camera tiles')
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    mask_sheet = Image.new('RGBA', canvas, (255, 255, 255, 255))
    input_sheet = Image.new('RGBA', canvas)
    solid_sheet = Image.new('RGBA', canvas)
    prepared_views = []
    editable = 0
    for view in frames['views']:
        index = view['index']
        known_path = packet / 'views' / f'view-{index}-known.png'
        if sha(known_path) != view['ownership_sha256']:
            raise ValueError('Reviewed ownership pixels changed')
        known_image = Image.open(known_path).convert('RGBA')
        solid_image = Image.open(packet / 'views' / f'view-{index}-solid.png').convert('RGBA')
        input_image = Image.open(packet / 'views' / f'view-{index}-textured.png').convert('RGBA')
        if any(image.size != (width, height) for image in (known_image, solid_image, input_image)):
            raise ValueError('Per-view image dimensions differ from frozen cameras')
        known = np.asarray(known_image)[:, :, 0] > 127
        solid = np.asarray(solid_image)[:, :, 3] > 0
        unknown = solid & ~known
        editable += int(unknown.sum())
        pixels = np.full((height, width, 4), 255, dtype=np.uint8)
        pixels[unknown, 3] = 0
        mask = Image.fromarray(pixels)
        input_name, mask_name = f'views/view-{index}-input.png', f'views/view-{index}-mask.png'
        prepared_views.append((index, input_name, mask_name, mask))
        left, top = index % 4 * width, index // 4 * height
        mask_sheet.paste(mask, (left, top))
        input_sheet.paste(input_image, (left, top))
        solid_sheet.paste(solid_image, (left, top))
        view.update(input=input_name, mask=mask_name,
                    crop={'left': left, 'top': top, 'width': width, 'height': height})
    if not np.array_equal(np.asarray(input_sheet), np.asarray(Image.open(item['textured']).convert('RGBA'))):
        raise ValueError('Per-view assembly differs from the actual approved source sheet')
    if not np.array_equal(np.asarray(solid_sheet), np.asarray(Image.open(item['solid']).convert('RGBA'))):
        raise ValueError('Per-view solid assembly differs from actual approved geometry sheet')
    if check_only:
        return {'asset_id': asset_id, 'status': 'eligible', 'editable_pixels': editable,
                'revision_sha256': item['revision']['sha256']}
    output.mkdir(parents=True)
    (output / 'views').mkdir()
    shutil.copyfile(model, output / 'approved-model.blend')
    shutil.copyfile(item['textured'], output / 'input.png')
    shutil.copyfile(item['solid'], output / 'solid.png')
    for index, input_name, mask_name, mask in prepared_views:
        shutil.copyfile(packet / 'views' / f'view-{index}-textured.png', output / input_name)
        mask.save(output / mask_name)
    mask_sheet.save(output / 'mask.png')
    revision = item['revision']['sha256']
    frames['layout'].update(width=cw, height=ch)
    frames.update(reviewed_packet=str(packet), reviewed_manifest_sha256=sha(frames_path),
                  source_blend=str(output / 'approved-model.blend'), geometry_revision=revision,
                  input_sha256=sha(output / 'input.png'))
    (output / 'views.json').write_text(json.dumps(frames, indent=2) + '\n')
    approval = {'status': 'approved', 'approved_by': 'user', 'asset_id': asset_id,
                'scope': 'geometry; texture candidate generation only',
                'exact_user_text': item['user_decision']['exact_user_text'],
                'geometry_revision': revision, 'input_sha256': sha(output / 'input.png'),
                'solid_sha256': sha(output / 'solid.png'), 'lighting_sha256': sha(output / 'solid.png'),
                'saved_model_sha256': sha(output / 'approved-model.blend'),
                'source_decision': item['user_decision'], 'texture_approval': 'pending'}
    (output / 'approval.json').write_text(json.dumps(approval, indent=2) + '\n')
    report = {'asset_id': asset_id, 'approved_revision': revision, 'editable_pixels': editable,
              'source_review_manifest': str(manifest_path), 'review_manifest_sha256': sha(manifest_path),
              'source_ownership_evidence': frames.get('source_mask_evidence'),
              'files': {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*')) if p.is_file()}}
    (output / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    return {'output': str(output), 'asset_id': asset_id, 'editable_pixels': editable,
            'input_sha256': approval['input_sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('asset_id')
    parser.add_argument('output', type=Path)
    parser.add_argument('--decisions', type=Path)
    parser.add_argument('--check-only', action='store_true', help='Validate complete approved packet without writing output')
    args = parser.parse_args()
    print(json.dumps(prepare(args.manifest, args.asset_id, args.output, args.decisions, check_only=args.check_only)))
