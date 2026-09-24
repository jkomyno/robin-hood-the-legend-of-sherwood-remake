"""Resolve the selected experiment without assuming its directory is the model ID."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement/texture-generation'
def selected_experiment(asset):
 jobs=json.loads((WORK/'preparation-jobs.json').read_text())['assets']
 matches=[j for j in jobs if j['asset_id']==asset]
 if len(matches)!=1 or not matches[0].get('experiment'):raise ValueError('Missing unique selected experiment for '+asset)
 p=Path(matches[0]['experiment']).resolve()
 if json.loads((p/'views.json').read_text())['asset_id']!=asset:raise ValueError('Selected experiment identity differs')
 return p
