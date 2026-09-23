"""Fit only the curved southern return to inspected native crown corners."""
import json,sys,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy.optimize import differential_evolution
sys.path.insert(0,str(Path(__file__).parent))
from refine_fortifications import north_wall_geometry
W=Path(__file__).resolve().parents[3]/'level-editor/work/nottingham-refinement';OUT=W/'fortifications-audit/south-curve-user-revision';OUT.mkdir(exist_ok=True);NATIVE=json.loads((W/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][200]['points'];pairs=[(7,8),(6,9),(5,10),(4,11),(3,12)];maskpath=W/'mask-review/inventory-v6/000126.png';mask=np.array(Image.open(maskpath).convert('L'))>127;xs=np.arange(1384,1519);wanted=mask[:,xs-1231].argmax(axis=0)+1920
# Numbered near/far cap observations are read from the untouched image and
# native126. These are observations, not claims of subpixel accuracy.
CORNERS=[(1383.2,2072,'far notch floor'),(1390,2072,'far notch floor end'),(1391,2061,'far cap start'),(1414,2061,'far cap end'),(1420,2064,'cap corner'),(1421,2074,'notch floor'),(1423,2071,'near cap start on bend'),(1432,2069,'far cap corner on bend'),(1450,2080,'far cap end'),(1452,2093,'far notch floor start'),(1460,2094,'far notch floor end'),(1463,2083,'far cap start'),(1478,2084,'far curve shoulder'),(1487,2082,'far curve return corner'),(1494,2092,'far notch floor start'),(1499,2089,'far notch floor end'),(1500,2079,'far cap start'),(1515,2066,'far cap return'),(1519,2066,'user split edge'),(1391,2072,'near cap edge'),(1419,2074,'near cap edge'),(1447,2090,'near cap edge'),(1463,2095,'near cap edge'),(1483,2095,'near cap edge'),(1511,2085,'near cap edge')]
def geometry(values):
 pts=[dict(p)for p in NATIVE]
 for i,(a,b)in enumerate(pairs):
  off=values[8+i]if i<4 else 1.5
  for index in [a,b]:pts[index]['z_top']+=off
 notches=[(1370,values[0]),(values[1],values[2]),(values[3],values[4]),(values[5],values[6])]
 return north_wall_geometry(pts,pairs,notches,notch_depth=values[7]),pts,notches

def project(values):
 (v,f),_,_=geometry(values);im=Image.new('1',(156,85));d=ImageDraw.Draw(im)
 for face in f:d.polygon([(v[i][0]-1373,v[i][1]-v[i][2]-2040)for i in face],fill=1)
 a=np.asarray(im);return a[:,xs-1373].argmax(axis=0)+2040

def main():
 def error(v):
  diff=project(v)-wanted
  return float(np.mean(np.abs(diff))+.15*np.sqrt(np.mean(diff**2)))
 bounds=[(1388,1394),(1416,1423),(1425,1434),(1440,1449),(1456,1464),(1484,1494),(1497,1505),(9,16)]+[(-4,4)]*4
 fit=differential_evolution(error,bounds,seed=19,popsize=8,maxiter=180,tol=.002,polish=False);got=project(fit.x);geo,pts,notches=geometry(fit.x)
 r={'version':1,'source_node':'building-200','projection_component':'wall-200-1','source_sha256':hashlib.sha256((W/'source-states/covered.png').read_bytes()).hexdigest(),'native_mask_index':126,'native_mask_sha256':hashlib.sha256(maskpath.read_bytes()).hexdigest(),'crop':[1373,2047,1529,2117],'measured_corners':[{'number':i+1,'source_xy':[x,y],'role':role,'visibility':'observed','confidence':'2-3 native pixels'}for i,(x,y,role)in enumerate(CORNERS)],'pairs':pairs,'points':pts,'notches':notches,'notch_depth':float(fit.x[7]),'values':fit.x.tolist(),'source_x':xs.tolist(),'source_skyline':wanted.tolist(),'candidate_skyline':got.tolist(),'mean_absolute_silhouette_error_pixels':float(np.mean(abs(got-wanted))),'max_silhouette_error_pixels':int(max(abs(got-wanted))),'construction_note':'Raster fit to inspected native skyline; this diagnostic is not independent confirmation of the chosen landmarks. Near and far cap corners are numbered separately. End height and splitx1519 preserve the adjoining straight section.'};(OUT/'corner-fit.json').write_text(json.dumps(r,indent=2)+'\n');print(r['mean_absolute_silhouette_error_pixels'],r['max_silhouette_error_pixels'],fit.x,flush=True)
if __name__=='__main__':main()
