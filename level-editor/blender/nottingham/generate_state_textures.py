"""Run authorized state image requests sequentially, retaining exact cache reuse."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
GEN = ROOT / 'level-editor/work/nottingham-refinement/texture-generation'
OUTPUT = 'generation-short-no-mask-with-lighting-openrouter'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=0)
    args = parser.parse_args()
    rows = json.loads((GEN / 'state-preparation-jobs.json').read_text())['jobs']
    for index, row in enumerate(rows):
        if index < args.start:
            continue
        experiment = Path(row['experiment'])
        review = json.loads((experiment / 'generation-input-review.json').read_text())
        assert review['status'] == 'ready-for-generation' and review['all_eight_views_inspected']
        for name, expected in review['artifact_sha256'].items():
            assert sha(experiment / name) == expected, name
        identity = {name: sha(experiment / name) for name in ('input.png', 'mask.png', 'solid.png')}
        for previous in rows[:index]:
            donor = Path(previous['experiment'])
            if not (donor / OUTPUT / 'generation.json').exists():
                continue
            if identity != {name: sha(donor / name) for name in identity}:
                continue
            for cache in (donor / 'api-cache').iterdir():
                target = experiment / 'api-cache' / cache.name
                if not target.exists():
                    shutil.copytree(cache, target)
            (experiment / 'generation-cache-reuse.json').write_text(json.dumps({
                'version': 1, 'donor': str(donor), 'equal_artifact_sha256': identity,
                'scope': 'Identical request cache only; each state retains its own approval and bake contract.'}, indent=2) + '\n')
            break
        command = ['node', str(ROOT / 'level-editor/pipeline/src/refinement/generate-textures.ts'),
                   str(experiment), '--generate', '--provider', 'openrouter', '--no-mask',
                   '--prompt-variant', 'short', '--lighting-reference', str(experiment / 'solid.png')]
        print(f'Generating state {index + 1}/{len(rows)}: {row["asset_id"]} / {row["state"]}', flush=True)
        with (experiment / 'generation-run.log').open('w') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f'State generation failed; see {experiment / "generation-run.log"}')
        generated = json.loads((experiment / OUTPUT / 'generation.json').read_text())
        assert generated['status'] == 200 and generated['changedProtected'] == 0
        print(f'Generated state {index + 1}; visual output review required', flush=True)


if __name__ == '__main__':
    main()
