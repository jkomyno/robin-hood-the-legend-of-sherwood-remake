"""Prepare the tower tree's continuous-crown review and preserve fringe evidence."""
import argparse
import json
from pathlib import Path
import sys
import bpy
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
import forest_volume
import foliage_packets


def run(workspace):
    workspace = Path(workspace).resolve()
    config = json.loads((workspace / 'workspace.json').read_text())
    if config['asset_id'] != 'leicester-northwest-tower-tree':
        raise ValueError('This evidence audit is specific to the tower tree')
    evidence = workspace / 'inspection/regional-fringe/derived-neutral-coverage.png'
    before = np.array(Image.open(evidence))
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'), load_ui=False)
    report = forest_volume.run(workspace)
    after = np.array(Image.open(workspace / 'inspection/continuous-volume/derived-neutral-coverage.png'))
    if not np.array_equal(before, after):
        raise ValueError('Continuous depth revision changed the frozen allocated source fringe')
    proof = workspace / 'inspection/tower-crown-evidence/constraints.json'
    constraints = json.loads(proof.read_text())
    constraints.update(front_coverage_pixel_identical=True,
                       preserved_coverage_pixels=int(np.count_nonzero(before)))
    proof.write_text(json.dumps(constraints, indent=2) + '\n')
    foliage_packets.run(workspace)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    run(args.workspace)
