"""Fit a curved roof-of-revolution profile to the isolated native roof contour."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy.optimize import differential_evolution
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'level-editor/blender/nottingham/freeze_tooling.py').is_file())
WORK=ROOT/'level-editor/work/nottingham-refinement';OUT=WORK/'fortifications-audit/north-user-revision'
MASK_PATH=WORK/'mask-review/inventory-v5/000116.png';native=np.array(Image.open(MASK_PATH).convert('L'))>127
YS=np.arange(263,339);LEFT=native[YS-194].argmax(axis=1)+2073;RIGHT=native.shape[1]-1-native[YS-194,::-1].argmax(axis=1)+2073
ANGLES=np.linspace(0,2*np.pi,73)[:-1];RADII=np.linspace(.18,1,17)

def profile(values):
    rx,ry,top,power=values;cx,cy,eave=2147.0,510.82,195.358
    return [[(cx+rx*r*np.cos(a),cy+ry*r*np.sin(a)-(eave+(top-eave)*((1-r)/.82)**power))for a in ANGLES]for r in RADII]

def evaluate(values,details=False):
    rings=profile(values);im=Image.new('1',(170,180));draw=ImageDraw.Draw(im)
    draw.polygon([(x-2065,y-190)for x,y in rings[0]],fill=1)
    for i in range(len(rings)-1):
        for j in range(72):
            k=(j+1)%72;draw.polygon([(x-2065,y-190)for x,y in [rings[i][j],rings[i][k],rings[i+1][k],rings[i+1][j]]],fill=1)
    a=np.asarray(im)[YS-190];left=a.argmax(axis=1)+2065;right=a.shape[1]-1-a[:,::-1].argmax(axis=1)+2065
    loss=float(np.mean(np.abs(left-LEFT)+np.abs(right-RIGHT))/2)
    return (loss,left,right,im)if details else loss

def main():
    OUT.mkdir(exist_ok=True,parents=True)
    result=differential_evolution(evaluate,[(72,77),(38,47),(256,267),(.5,1.4)],seed=49,popsize=7,maxiter=50,tol=.001,polish=False)
    loss,left,right,im=evaluate(result.x,True)
    report={'version':1,'parameters':dict(zip(['radius_x','radius_native_y','top_height','power'],map(float,result.x))),'axis_native':[2147,510.82],'eave_height':195.358,'inner_radius_fraction':.18,'mask_index':116,'mask_sha256':hashlib.sha256(MASK_PATH.read_bytes()).hexdigest(),'mean_outline_error_pixels':loss,'source_y':YS.tolist(),'source_left':LEFT.tolist(),'source_right':RIGHT.tolist(),'candidate_left':left.tolist(),'candidate_right':right.tolist(),'interpretation':'Roof tiles use the lower, curved bell profile. Separate measured metal cap, two finial balls and pole continue above it.'}
    (OUT/'tower-roof-fit.json').write_text(json.dumps(report,indent=2)+'\n');im.save(OUT/'tower-roof-fit-mask.png');print(report['parameters'],loss)
if __name__=='__main__':main()
