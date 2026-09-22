"""Triangulate the exposed difference between the actual upper/lower footprints."""
import json,sys
from pathlib import Path
W=Path(__file__).parent;D=W/'next-zigzag-v3'
sys.path.insert(0,str(W/'python-deps'))
from shapely.geometry import LineString,box
from shapely.ops import polygonize,unary_union
from shapely import constrained_delaunay_triangles
result={}
for node,sides in json.loads((D/'join-sections.json').read_text()).items():
 shapes={side:unary_union(list(polygonize(unary_union([
   LineString([[round(v,3) for v in p] for p in edge]) for edge in edges])))) for side,edges in sides.items()}
 triangles=[]
 if node=='building-185':
  shapes={side:shape.intersection(box(1359,-10000,1567,10000)) for side,shape in shapes.items()}
 for side,other,sign in [('lower','upper',1),('upper','lower',-1)]:
  exposed=shapes[side].difference(shapes[other])
  for triangle in constrained_delaunay_triangles(exposed).geoms:
   if triangle.area<1e-8:continue
   triangles.append(dict(points=list(triangle.exterior.coords)[:-1],normal=sign))
 result[node]=dict(triangles=triangles,areas={side:shape.area for side,shape in shapes.items()})
(D/'join-triangles.json').write_text(json.dumps(result,indent=2))
print({n:dict(areas=r['areas'],triangles=len(r['triangles'])) for n,r in result.items()})
