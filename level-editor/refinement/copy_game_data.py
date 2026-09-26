"""Copy the editor's read-only game inputs into library/game-data for HTTP serving."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil

EDITOR = Path(__file__).resolve().parents[1]


def copy_game_data(source, destination):
    source, destination = Path(source).resolve(strict=True), Path(destination).resolve()
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('Source and destination must be separate directories')
    files = set()

    def include(path):
        path = path.resolve(strict=True)
        if not path.is_relative_to(source) or not path.is_file():
            raise ValueError(f'Invalid game data file: {path}')
        files.add(path.relative_to(source).as_posix())

    levels = source / 'Data/Levels'
    maps = list(levels.glob('*.rhp.json'))
    missions = list(levels.glob('*.rhm.json'))
    if not maps or not missions:
        raise ValueError(f'Missing converted levels or missions in {levels}')
    for path in maps + missions:
        include(path)
    include(source / 'Data/Configuration/profile.cpf.json')
    for category in ('Characters', 'Animations'):
        manifests = []
        for parent, dirs, _ in os.walk(source / 'Data' / category):
            for name in list(dirs):
                if name.endswith('.rhs.d'):
                    manifests.append(Path(parent) / name / 'manifest.json')
                    dirs.remove(name)
        if not manifests:
            raise ValueError(f'Missing converted sprite banks: {category}')
        for path in manifests:
            include(path)
            manifest = json.loads(path.read_text())
            for profile in manifest['profiles']:
                for row in profile['rows']:
                    # Mission previews read only the first frame of each pose/direction.
                    if not row['frames']:
                        continue
                    relative = Path(row['path']) / row['frames'][0]['file']
                    frame = path.parent / relative
                    if not frame.is_file() and len(manifest['profiles']) > 1:
                        profile_dir = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', profile['name']).strip('.')
                        frame = path.parent / profile_dir / relative
                    include(frame)
    destination.mkdir(parents=True, exist_ok=True)
    for relative in sorted(files):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    # Publish the index last; readers enumerate only the current snapshot's files.
    temporary = destination / 'index.json.tmp'
    temporary.write_text(json.dumps({'version': 1, 'files': sorted(files)}, indent=2) + '\n')
    temporary.replace(destination / 'index.json')
    return len(files)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(os.environ.get(
        'HACKABLE_DATADIR', EDITOR.parent / 'datadirs/fullgame_gog_hackable')))
    parser.add_argument('--destination', type=Path, default=EDITOR / 'library/game-data')
    args = parser.parse_args()
    print(f'Copied {copy_game_data(args.source, args.destination)} files to {args.destination}')
