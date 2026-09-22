"""Prepare a static village packet using the reviewed canonical dispatch job."""
import argparse
import json
from pathlib import Path
import sys
import bpy

def main():
    p=argparse.ArgumentParser();p.add_argument('asset_id');p.add_argument('--mask-manifest',type=Path);p.add_argument('--dispatch',type=Path,default=Path('level-editor/work/leicester-refinement/round-1/assets-v2/dispatch.json'));a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    d=json.loads(a.dispatch.read_text());j=next(j for j in d['jobs'] if j['asset_id']==a.asset_id)
    if Path(bpy.data.filepath).resolve()!=Path(d['source_blend']).resolve():raise ValueError('Load exact dispatch grouped checkpoint')
    argv=j['prepare_argv'];argv=argv[argv.index('--')+1:]
    if '--projection-manifest' in argv:
        i=argv.index('--projection-manifest');del argv[i:i+2]
    if a.mask_manifest:
        i=argv.index('--source-mask-manifest');argv[i+1]=str(a.mask_manifest.resolve(strict=True))
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from refinement_workspace import main as prepare
    prepare(argv)
if __name__=='__main__':main()
