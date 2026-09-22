"""Fit the northern parapet to native source-pixel silhouette corners."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image,ImageDraw
from scipy.optimize import differential_evolution
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'level-editor/blender/nottingham/refine_fortifications.py').is_file())
sys.path.insert(0,str(ROOT/'level-editor/blender/nottingham'))
from refine_fortifications import north_wall_geometry
WORK=ROOT/'level-editor/work/nottingham-refinement'
OUT=WORK/'fortifications-audit/north-user-revision'
NATIVE=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles']
MASK_PATH=WORK/'mask-review/inventory-v5/000115.png'
MASK=np.array(Image.open(MASK_PATH).convert('L'))>127

def target(xs):
    return MASK[:,xs-1544].argmax(axis=0)+193

def project(points,pairs,notches,depth,xs):
    v,f=north_wall_geometry(points,[(b,a)for a,b in pairs],notches,notch_depth=depth)
    left=int(min(xs))-25;top=210;w=int(max(xs))-left+26
    image=Image.new('1',(w,400));draw=ImageDraw.Draw(image)
    for face in f:draw.polygon([(v[i][0]-left,v[i][1]-v[i][2]-top)for i in face],fill=1)
    a=np.asarray(image);return a[:,xs-left].argmax(axis=0)+top

def fit_run(name,node,pairs,xrange,bounds):
    xs=np.arange(*xrange);wanted=target(xs);native=NATIVE[node]['points']
    def evaluate(values,details=False):
        height,phase,width,period,depth=values
        points=[{**p,'z_top':height}for p in native]
        notches=[(phase+i*period,phase+i*period+width)for i in range(-12,16)]
        got=project(points,pairs,notches,depth,xs);loss=float(np.mean(np.abs(got-wanted)))
        return (got,notches,loss)if details else loss
    fit=differential_evolution(evaluate,bounds,seed=27,popsize=7,maxiter=65,tol=.001,polish=False)
    got,notches,loss=evaluate(fit.x,True)
    result={'name':name,'source_node':f'building-{node:03}','pairs':pairs,'parameters':dict(zip(['height','phase','width','period','depth'],map(float,fit.x))),
            'notches':notches,'source_x':xs.tolist(),'source_top':wanted.tolist(),'candidate_top':got.tolist(),'mean_error_pixels':loss,'maximum_error_pixels':int(np.max(np.abs(got-wanted)))}
    print(name,result['parameters'],loss,flush=True);return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    runs=[fit_run('west',178,[(6,7),(5,8)],(1568,1802),[(153,159),(1587,1601),(10,23),(39.4,40.6),(8,16)]),
          fit_run('east',178,[(1,12),(0,13)],(1906,2073),[(153,159),(1909,1920),(10,23),(37,39.5),(8,16)]),
          fit_run('east-continuation',177,[(3,2),(0,1)],(2227,2304),[(153,159),(2235,2255),(10,23),(32,42),(8,16)])]
    report={'version':1,'mask_index':115,'mask_sha256':hashlib.sha256(MASK_PATH.read_bytes()).hexdigest(),'runs':runs,
            'coordinate_policy':'Measured source corners fit the back parapet edge, not the displaced front edge. Each run retains its observed repeat count and independently measured phase.'}
    (OUT/'straight-fits.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
