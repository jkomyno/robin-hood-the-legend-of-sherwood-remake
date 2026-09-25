"""Inspect one exact state bake's saved texel provenance under a render lease."""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'refinement/blender'))
from render_slots import acquire, release
from render_texture_coverage import inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('bake', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--provenance-report', type=Path, action='append')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    acquire()
    try:
        result = inspect(args.manifest, args.bake, args.output,
                         provenance_reports=args.provenance_report)
        print(result['asset_id'], result['views'], flush=True)
    finally:
        release()


if __name__ == '__main__':
    main()
