"""Resolve individual northern battlement corners against the native silhouette."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import differential_evolution
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'level-editor/blender/nottingham/fit_north_curtain_pixels.py').is_file())
sys.path.insert(0,str(ROOT/'level-editor/blender/nottingham'))
from fit_north_curtain_pixels import WORK,OUT,NATIVE,MASK_PATH,target,project
HEIGHT=156.5
DEPTH=10.6

def main():
    seed=json.loads((OUT/'straight-fits.json').read_text());runs=[]
    for base in seed['runs']:
        node=int(base['source_node'][-3:]);xs=np.array(base['source_x']);wanted=target(xs);points=[{**q,'z_top':HEIGHT}for q in NATIVE[node]['points']];pairs=base['pairs']
        notches=[list(n)for n in base['notches']if xs[0]-30<n[0]<xs[-1]+20]
        for cycle in range(2):
            for index,notch in enumerate(copy.deepcopy(notches)):
                def error(values):
                    candidate=copy.deepcopy(notches);candidate[index]=list(values);got=project(points,pairs,candidate,DEPTH,xs);return float(np.mean(np.abs(got-wanted)))
                fit=differential_evolution(error,[(notch[0]-4,notch[0]+4),(notch[1]-4,notch[1]+4)],seed=35+index,popsize=6,maxiter=22,polish=False,tol=.001)
                notches[index]=list(map(float,fit.x))
        got=project(points,pairs,notches,DEPTH,xs);result={**base,'notches':notches,'parameters':{'height':HEIGHT,'depth':DEPTH},'candidate_top':got.tolist(),'mean_error_pixels':float(np.mean(np.abs(got-wanted))),'maximum_error_pixels':int(np.max(np.abs(got-wanted)))};runs.append(result);print(base['name'],result['mean_error_pixels'],flush=True)
    xs=np.arange(1806,1906);wanted=target(xs);points=[{**q,'z_top':HEIGHT}for q in NATIVE[178]['points']];pairs=[(5,8),(4,9),(3,10),(2,11),(1,12)]
    def evaluate(v):
        got=project(points,pairs,[(v[0],v[1]),(v[2],v[3])],DEPTH,xs);return float(np.mean(np.abs(got-wanted)))
    fit=differential_evolution(evaluate,[(1825,1839),(1838,1851),(1862,1877),(1878,1889)],seed=66,popsize=9,maxiter=65,polish=False,tol=.001)
    v=fit.x;notches=[list(map(float,v[:2])),list(map(float,v[2:]))];got=project(points,pairs,notches,DEPTH,xs)
    runs.append({'name':'central-projecting-turret','source_node':'building-178','pairs':pairs,'notches':notches,'parameters':{'height':HEIGHT,'depth':DEPTH},'source_x':xs.tolist(),'source_top':wanted.tolist(),'candidate_top':got.tolist(),'mean_error_pixels':float(np.mean(np.abs(got-wanted))),'maximum_error_pixels':int(np.max(np.abs(got-wanted)))})
    report={'version':1,'height':HEIGHT,'notch_depth':DEPTH,'runs':runs,'mask_index':115,'mask_sha256':hashlib.sha256(MASK_PATH.read_bytes()).hexdigest(),'coordinate_policy':seed['coordinate_policy'],'corner_policy':'Each final notch has individually fitted source-pixel corners; periodic spacing was only the seed, not the final geometry.'}
    (OUT/'final-fit.json').write_text(json.dumps(report,indent=2)+'\n');print('central',runs[-1]['mean_error_pixels'])
if __name__=='__main__':main()
