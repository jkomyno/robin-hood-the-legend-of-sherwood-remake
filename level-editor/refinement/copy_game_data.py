"""Copy mission preview inputs and idle sprites for authorable mission characters."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import warnings

from game_data_atlas import pack_atlas

EDITOR = Path(__file__).resolve().parents[1]
# Keep aligned with app/src/sprite-profiles.ts (checked by test_copy_game_data.py).
BONUS_SPRITES = [
    ('BONUS_Arrows', 'BONUS Fleches'), ('BONUS_Stones', 'BONUS Cailloux'),
    ('BONUS_Apples', 'BONUS Pommes'), ('BONUS_Ale', 'BONUS Ale'),
    ('BONUS_LegOfLamb', 'BONUS Gigots'), ('BONUS_Plants', 'BONUS Plantes'),
    ('BONUS_Nets', 'BONUS Filets'), ('BONUS_WaspsNest', 'BONUS Guepes'),
    ('BONUS_MoneyBag', "BONUS Bourses d'argent"), ('BONUS_GoldBagsRansom', "BONUS Sac d'or rancon"),
    ('BONUS_FourLeavedClover', 'BONUS Trefle'), ('BONUS_Shield', 'Shield'),
    ('RELIC_Ampulla', 'Huile'), ('RELIC_Spoon', 'Cuillere'), ('RELIC_Crown', 'Couronne'),
    ('RELIC_Stamp', 'Sceau'), ('RELIC_Sceptre', 'Sceptre'), ('RELIC_Book', 'Registre'),
    ('RELIC_Sword', 'Epee'),
]
AMBIANCES = dict(zip((1, 2, 4, 8, 16, 32, 64, 128),
                    ('Day', 'Fog', 'Night', 'Attack', 'Custom1', 'Custom2', 'Custom3', 'Custom4')))


def mission_sprites(mission, profiles):
    """Match MissionEntities.load: characters, pickups, targets and active mobiles."""
    for group, order, category, id_key in (
        ('soldiers', 'soldier_order', 'soldiers', 'profile_number'),
        ('civilians', 'civilian_order', 'civilians', 'profile_number'),
        ('pcs_to_rescue', 'character_order', 'characters', 'profile_index'),
    ):
        for entity in mission.get(group, []):
            profile = profiles[category][profiles[order][entity[id_key]]]
            yield 'character', profile['filename'], profile['profile_name'], entity['action']
    for entity in mission.get('bonuses', []):
        bonus_type, quantity = entity['bonus_type'], entity['quantity']
        if not 0 <= bonus_type < len(BONUS_SPRITES) or not 1 <= quantity <= 5:
            raise ValueError('Invalid mission bonus type or quantity')
        yield 'pickup', *BONUS_SPRITES[bonus_type], 189 + quantity
    for entity in mission.get('scrolls', []):
        yield 'pickup', 'BONUS_Parchment', 'BONUS Parchemin', entity['action']
    for entity in mission.get('targets', []):
        yield 'scenery', entity['filename'], entity['profile_name'], entity['action']
    for entity in mission.get('mobile_elements', []):
        for fx in entity.get('sprites', []):
            if fx.get('active') is False:
                continue
            sprite = fx['sprite']
            yield 'scenery', sprite['frame_profile_name'], sprite['profile_name'], 0


def authorable_character_sprites(profiles):
    """Include profiles absent from saved missions so every chooser entry can render."""
    for category, order in (('characters', 'character_order'), ('soldiers', 'soldier_order')):
        for key in profiles[order]:
            profile = profiles[category][key]
            yield 'character', profile['filename'], profile['profile_name'], 3


def copy_game_data(source, destination):
    source, destination = Path(source).resolve(strict=True), Path(destination).resolve()
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('Source and destination must be separate directories')
    files, generated, atlases = set(), {}, {}

    def include(path):
        path = path.resolve(strict=True)
        if not path.is_relative_to(source) or not path.is_file():
            raise ValueError(f'Invalid game data file: {path}')
        relative = path.relative_to(source).as_posix()
        files.add(relative)
        return relative

    # Match the loader's exact-case lookup followed by case-insensitive directory fallback.
    def directory(parts):
        current = source
        for part in parts:
            if not part or part in ('.', '..') or re.search(r'[\\/\x00]', part):
                raise ValueError(f'Invalid sprite directory: {part!r}')
            exact = current / part
            if exact.is_dir():
                current = exact
            else:
                matches = [p for p in current.iterdir() if p.is_dir() and p.name.lower() == part.lower()]
                if not matches:
                    return None
                if len(matches) != 1:
                    raise ValueError(f'Ambiguous sprite directory: {exact}')
                current = matches[0]
        return current

    levels = source / 'Data/Levels'
    maps = list(levels.glob('*.rhp.json'))
    missions = list(levels.glob('*.rhm.json'))
    if not maps or not missions:
        raise ValueError(f'Missing converted levels or missions in {levels}')
    for path in maps + missions:
        generated[include(path)] = json.loads(path.read_text())
    profile_path = source / 'Data/Configuration/profile.cpf.json'
    profiles = json.loads(profile_path.read_text())
    generated[include(profile_path)] = profiles
    banks, selected, output_banks = {}, {}, {}
    requests = [('authorable characters', 'Day', authorable_character_sprites(profiles), True)]
    for mission_path in missions:
        mission = json.loads(mission_path.read_text())
        ambiance = AMBIANCES[mission['header']['ambiance']]
        requests.append((mission_path.name, ambiance, mission_sprites(mission, profiles), False))
    for context, ambiance, sprites, require_directions in requests:
        for kind, filename, profile_name, action in sprites:
            paths = ([['Data', 'Animations', *([a] if a else []), filename + '.rhs.d']
                      for a in dict.fromkeys((ambiance, 'Day', ''))] if kind == 'scenery'
                     else [['Data', 'Characters', filename + '.rhs.d']])
            bank = None
            for parts in paths:
                bank = directory(parts)
                if bank is not None:
                    break
            if bank is None:
                if kind == 'character':
                    raise ValueError(f'{context}: missing character sprite {filename}')
                warnings.warn(f'{context}: missing sprite {filename}; preview uses a marker')
                continue
            # Browser URLs are case-sensitive even when the input loader finds a bank
            # through its case-insensitive directory fallback.
            output_bank = (Path('Data/Characters') / (filename + '.rhs.d')
                           if kind in ('character', 'pickup') else bank.relative_to(source))
            output_banks.setdefault(bank, set()).add(output_bank)
            if bank not in banks:
                manifest_path = (bank / 'manifest.json').resolve(strict=True)
                if not manifest_path.is_relative_to(source):
                    raise ValueError(f'Sprite manifest escapes source: {manifest_path}')
                banks[bank] = json.loads(manifest_path.read_text())
            manifest = banks[bank]
            profile = next((p for p in manifest['profiles'] if p['name'] == profile_name), None)
            if profile is None:
                raise ValueError(f'{bank}: missing profile {profile_name}')
            rows = profile['rows']
            actions = (action, 3, 0) if kind == 'character' else (action,)
            chosen = []
            for candidate in actions:
                chosen = [i for i, row in enumerate(rows) if row['action_id'] == candidate]
                if chosen:
                    break
            if not chosen:
                raise ValueError(f'{bank}: no initial or idle pose for {profile_name}, action {action}')
            if require_directions and {rows[i]['direction'] for i in chosen} != set(range(16)):
                raise ValueError(f'{bank}: incomplete idle directions for {profile_name}')
            selected.setdefault(bank, {}).setdefault(profile_name, set()).update(chosen)

    for bank, chosen_profiles in selected.items():
        manifest = deepcopy(banks[bank])
        kept, frame_sources = [], []
        for profile in manifest['profiles']:
            chosen_rows = chosen_profiles.get(profile['name'])
            if chosen_rows is None:
                continue
            rows = []
            for i in sorted(chosen_rows):
                row = profile['rows'][i]
                if not row['frames']:
                    raise ValueError(f'{bank}: empty preview row {row["path"]}')
                frame = row['frames'][0]
                parts = [p for p in row['path'].split('/') if p != '.']
                frame_dir = directory([*bank.relative_to(source).parts, *parts])
                if frame_dir is None and len(manifest['profiles']) > 1:
                    profile_dir = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', profile['name']).strip('.')
                    frame_dir = directory([*bank.relative_to(source).parts, profile_dir, *parts])
                if frame_dir is None:
                    raise ValueError(f'{bank}: missing frame directory {row["path"]}')
                if Path(frame['file']).name != frame['file'] or '\\' in frame['file']:
                    raise ValueError('Invalid sprite frame filename')
                source_frame = (frame_dir / frame['file']).resolve(strict=True)
                if not source_frame.is_relative_to(source):
                    raise ValueError(f'Sprite frame escapes source: {source_frame}')
                frame_sources.append((frame, source_frame))
                row['path'] = '.'
                row['frames'] = [frame]
                rows.append(row)
            profile['rows'] = rows
            kept.append(profile)
        manifest['profiles'] = kept
        atlas_bytes, rectangles = pack_atlas([path for _, path in frame_sources])
        manifest['atlas'] = 'atlas.webp'
        for frame, path in frame_sources:
            frame['file'] = 'atlas.webp'
            frame['rect'] = rectangles[path]
        for output_bank in output_banks[bank]:
            atlas_relative = (output_bank / 'atlas.webp').as_posix()
            relative = (output_bank / 'manifest.json').as_posix()
            files.update((atlas_relative, relative))
            atlases[atlas_relative] = atlas_bytes
            generated[relative] = manifest

    # Only remove files owned by the previous generated index, never arbitrary user files.
    previous = set()
    if (destination / 'index.json').exists():
        previous = set(json.loads((destination / 'index.json').read_text())['files'])
        for relative in previous:
            if (not isinstance(relative, str) or '\\' in relative
                    or any(p in ('', '.', '..') for p in relative.split('/'))
                    or not (destination / relative).resolve().is_relative_to(destination)):
                raise ValueError(f'Unsafe previous game data path: {relative!r}')
    destination.mkdir(parents=True, exist_ok=True)
    for relative in sorted(files):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative in generated:
            target.write_text(json.dumps(generated[relative], separators=(',', ':')) + '\n')
        else:
            target.write_bytes(atlases[relative])
    temporary = destination / 'index.json.tmp'
    temporary.write_text(json.dumps({'version': 1, 'files': sorted(files)}, separators=(',', ':')) + '\n')
    temporary.replace(destination / 'index.json')
    for relative in sorted(previous - files):
        (destination / relative).unlink(missing_ok=True)
    for parent, _, _ in os.walk(destination, topdown=False):
        path = Path(parent)
        if path != destination and not any(path.iterdir()):
            path.rmdir()
    return len(files)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(os.environ.get(
        'HACKABLE_DATADIR', EDITOR.parent / 'datadirs/fullgame_gog_hackable')))
    parser.add_argument('--destination', type=Path, default=EDITOR / 'library/game-data')
    args = parser.parse_args()
    print(f'Copied {copy_game_data(args.source, args.destination)} files to {args.destination}')
