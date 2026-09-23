"""Reopen each unseen castle candidate and render its actual saved UV/material graphs."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9');sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from audit_stored_materials import run
parser=argparse.ArgumentParser();parser.add_argument('asset',choices=['watchtower','northeast-spire','southeast-spire','northwest-spire','southwest-stair']);args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
for rd,name in [(28,'watchtower'),(27,'northeast-spire'),(4,'southeast-spire'),(1,'northwest-spire'),(5,'southwest-stair')]:
 if name!=args.asset:continue
 w=WORK/f'round-{rd}/assets/nottingham-castle-{name}';r=run(w,w/'inspection/source-coverage-materials',render=True);assert not r['problems'],r['problems'];print(name,r['status'],flush=True)
