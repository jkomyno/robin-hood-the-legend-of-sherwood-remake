"""Validate and install a staged local catalog, archiving superseded library files."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from urllib.parse import unquote
from canonical_assets import digest, read_model
from promote_staged_publication import library_lock, contained_path, safe_relative


def graph(staged, previous):
    """Return the complete active graph; previews may retain their previous bytes."""
    files = {}
    def include(relative, expected=None):
        relative = str(safe_relative(relative))
        source = contained_path(staged, relative)
        if not source.is_file(): source = contained_path(previous, relative, required=True)
        value = digest(source.read_bytes())
        if expected is not None and expected != value: raise ValueError('Changed pin: '+relative)
        if relative in files and files[relative]['sha256'] != value: raise ValueError('Conflicting pin: '+relative)
        files[relative] = {'source':str(source), 'sha256':value}
        return source
    def document(relative): return json.loads(include(relative).read_text())
    index = document('3d-assets/index.json')
    entries = {entry['id']:entry for entry in index['assets']}
    if len(entries) != len(index['assets']): raise ValueError('Duplicate catalog identity')
    models = {}
    for entry in entries.values():
        relative = '3d-assets/'+entry['descriptor']
        descriptor = document(relative)
        if descriptor['id'] != entry['id']: raise ValueError('Descriptor identity mismatch')
        if any(key in descriptor for key in ('source_origin_scene', 'source_origin_game', 'reveal')):
            raise ValueError('Map metadata remains in asset: '+relative)
        model_path = str(Path(relative).parent/descriptor['model'])
        if model_path != '3d-assets/'+entry['model'] or Path(model_path).suffix not in ('.gltf', '.glb'):
            raise ValueError('Catalog must use its canonical glTF model')
        model_file = include(model_path)
        model, _, _ = read_model(model_file, staged if model_file.is_relative_to(staged) else previous)
        models[model_path] = model
        scenes = [scene.get('name') for scene in model['scenes']]
        for value in [descriptor, *descriptor.get('state_variants', {}).values(), *descriptor.get('standalone_variants', {}).values()]:
            if value['model'] != descriptor['model'] or scenes.count(value.get('model_scene')) != 1:
                raise ValueError('Invalid canonical appearance: '+relative)
        pins = {resource['path']:resource['sha256'] for resource in descriptor['resources']}
        requested = set()
        for table in ('buffers', 'images'):
            for value in model.get(table, []):
                if 'uri' not in value: continue
                resolved = (staged/Path(model_path).parent/unquote(value['uri'])).resolve()
                if not resolved.is_relative_to(staged.resolve()): raise ValueError('Model resource escapes library')
                resource = str(resolved.relative_to(staged.resolve()))
                if resource not in pins: raise ValueError('Unpinned resource: '+resource)
                include(resource, pins[resource]); requested.add(resource)
        if requested != set(pins): raise ValueError('Descriptor resources do not match model')
        if entry.get('preview_model'):
            preview = '3d-assets/'+entry['preview_model']; include(preview)
            receipt = preview+'.receipt.json'
            if (staged/receipt).is_file() or (previous/receipt).is_file(): include(receipt)
    maps = sorted((staged/'scenes').glob('*.level3d.json'))
    for path in maps:
        value = document(str(path.relative_to(staged)))
        if any(not part['node'].startswith('asset:') for part in value['objects']):
            raise ValueError('Map contains world-scene objects: '+str(path))
        for reference in value['sceneAssets']+value.get('assetSources', []):
            if reference['model'] not in models: raise ValueError('Map references a non-catalog model')
            include(reference['model'], reference['model_sha256'])
            include(reference['descriptor'], reference['descriptor_sha256'])
            descriptor = json.loads(Path(files[reference['descriptor']]['source']).read_text())
            if reference['resources'] != descriptor['resources']: raise ValueError('Map resource pins differ from catalog')
            for resource in reference['resources']: include(resource['path'], resource['sha256'])
    return files, len(entries), len(maps)


def publish(plan_path, apply=False):
    plan = json.loads(Path(plan_path).read_text())
    library, staged = Path(plan['library']).resolve(), Path(plan['output']).resolve()
    with library_lock(library):
        for relative, expected in plan['sources'].items():
            if digest(contained_path(library, safe_relative(relative), required=True).read_bytes()) != expected:
                raise ValueError('Source changed since staging: '+relative)
        files, assets, maps = graph(staged, library)
        active = set(files)
        obsolete = [path for path in (library/'3d-assets').rglob('*') if path.is_file()
                    and path.name != '.publication.lock' and str(path.relative_to(library)) not in active]
        obsolete += [path for path in (library/'scenes').iterdir() if path.is_file()
                     and path.suffix in ('.glb', '.gltf')]
        changes = [relative for relative, record in files.items()
                   if not (library/relative).exists() or digest((library/relative).read_bytes()) != record['sha256']]
        report = {'assets':assets, 'maps':maps, 'install':len(changes), 'archive':len(obsolete), 'apply':apply}
        if not apply: return report
        backup = library/'scenes/backups'/('canonical-library-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        backup.mkdir(parents=True)
        moved, installed = [], []
        try:
            for path in obsolete + [library/relative for relative in changes if (library/relative).exists()]:
                destination = backup/path.relative_to(library)
                destination.parent.mkdir(parents=True, exist_ok=True)
                path.rename(destination); moved.append((destination, path))
            # Maps and the index become visible only after their payloads exist.
            changes.sort(key=lambda relative: (relative.startswith('scenes/') or relative == '3d-assets/index.json', relative))
            for relative in changes:
                target = library/relative; target.parent.mkdir(parents=True, exist_ok=True)
                installed.append(target)
                shutil.copy2(files[relative]['source'], target)
            graph(library, library)
            (backup/'migration.json').write_text(json.dumps({**report, 'files':files}, indent=2)+'\n')
        except BaseException:
            for path in reversed(installed): path.unlink(missing_ok=True)
            for source, target in reversed(moved):
                target.parent.mkdir(parents=True, exist_ok=True); source.rename(target)
            raise
        for path in sorted((library/'3d-assets').rglob('*'), key=lambda path:len(path.parts), reverse=True):
            if path.is_dir() and not any(path.iterdir()): path.rmdir()
        return {**report, 'backup':str(backup)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('plan', type=Path); parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(); print(json.dumps(publish(args.plan, args.apply), indent=2))
