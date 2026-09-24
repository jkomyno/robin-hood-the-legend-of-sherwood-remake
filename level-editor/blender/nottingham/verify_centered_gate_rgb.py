"""Independently compare every known pixel of the gate pair and endpoint packets."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
selector=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else ''
for round_id,asset in [(39,'nottingham-castle-gate-arch'),(43,'nottingham-castle-gate-east-tower')]:
 if selector and selector not in asset:continue
 workspace=WORK/f'round-{round_id}/assets'/asset
 script=Path(__file__).parent/'verify_workspace_known_rgb.py'
 code=script.read_text().replace("select_tooling(root/'tooling/94116d984f92dbae')","select_tooling(root/'tooling/58744eeaf71a21e9')")
 code=code.replace("packets=[w/'modified']","packets=[w/'modified']+[p.parent for p in sorted((w/'inspection/endpoints-v6').glob('*/views.json'))]+[p.parent for p in sorted((w/'inspection/endpoints-v6').glob('*/full-height/views.json'))]\nassert len(packets)==5, 'Incomplete endpoint packet'")
 sys.argv=[str(script),'--',str(workspace)]
 exec(compile(code,str(script),'exec'))
