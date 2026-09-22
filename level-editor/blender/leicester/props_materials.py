"""Render stored prop materials through the immutable fixed cameras."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit_stored_materials import run,digest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspaces',nargs='+',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    for workspace in a.workspaces:
        output=workspace/'inspection'/'stored-materials'
        if output.exists():
            previous=json.loads((output/'audit.json').read_text())
            if previous['model_sha256']==digest(workspace/'model.blend'):
                print('MATERIAL_AUDIT_CURRENT '+workspace.name,flush=True);continue
            archive=output.with_name('stored-materials-'+previous['model_sha256'][:16])
            output.rename(archive)
        result=run(workspace,output,render=True,export=True)
        print('MATERIAL_AUDIT_COMPLETE '+workspace.name+' '+result['status'],flush=True)
