"""Finish rendering an already reprojected East Hall recovery checkpoint."""
import json
import sys
from pathlib import Path

W = Path(__file__).parent
D = W / 'next-zigzag-v3'
sys.path.insert(0, str(W.parents[4] / 'blender'))
from refinement_workspace import _render

config = json.loads((D / 'authority-checkpoint/workspace.json').read_text())
config['source_mask_manifest'] = str(D / 'source-masks-reviewed.json')
_render(config, D / 'candidate-review-native/recovered-modified',
        D / 'candidate-review-native/frame-48.json')
