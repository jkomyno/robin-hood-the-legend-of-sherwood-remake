"""Construct a supported notch-floor band with explicit upper/lower cross sections."""
import json,sys,math
from pathlib import Path
W=Path(__file__).parent;D=W/'next-zigzag-v3';sys.path.insert(0,str(W/'python-deps'))
from shapely.geometry import LineString,Polygon,box
from shapely.ops import polygonize,unary_union
from shapely import constrained_delaunay_triangles
clip=box(1359,-10000,1567,10000)
def shape(edges):
 return unary_union(list(polygonize(unary_union([LineString([[round(v,3) for v in p] for p in e]) for e in edges])))).intersection(clip)
sections=json.loads((D/'join-sections.json').read_text())['building-185']
bottom=shape(json.loads((D/'join-sections-bottom.json').read_text())['building-185']['lower'])
lower=shape(sections['lower']);upper=shape(sections['upper'])
def y(x):return -1915.7435+(x-1365.2279)*(-2210.0918+1915.7435)/(1622.5542-1365.2279)
offset=(-6,-5/math.sin(math.radians(35)))
strip=Polygon([(1359,y(1359)),(1567,y(1567)),(1567+offset[0],y(1567)+offset[1]),(1359+offset[0],y(1359)+offset[1])]).intersection(clip)
band=lower.union(strip)
faces=[]
def triangles(poly,z,sign):
 for t in constrained_delaunay_triangles(poly).geoms:
  if t.area>1e-8:faces.append(dict(points=[[x,y,z] for x,y in list(t.exterior.coords)[:-1]],normal=sign))
triangles(band.difference(upper),376,1);triangles(upper.difference(band),376,-1)
triangles(bottom.difference(band),365.01,1);triangles(band.difference(bottom),365.01,-1)
for poly in ([band] if band.geom_type=='Polygon' else band.geoms):
 for ring in [poly.exterior,*poly.interiors]:
  for a,b in zip(ring.coords,list(ring.coords)[1:]):
   segments=[LineString([a,b])]
   if abs(a[0]-b[0])<.001 and (abs(a[0]-1359)<.001 or abs(a[0]-1567)<.001):
    remaining=segments[0].difference(lower.buffer(.001))
    segments=[] if remaining.is_empty else ([remaining] if remaining.geom_type=='LineString' else list(remaining.geoms))
   for segment in segments:
    a,b=segment.coords[0],segment.coords[-1]
    faces.append(dict(points=[[a[0],a[1],365.01],[b[0],b[1],365.01],[b[0],b[1],376],[a[0],a[1],376]],normal=0))
(D/'rear-band-faces.json').write_text(json.dumps(dict(faces=faces,areas=dict(bottom=bottom.area,lower=lower.area,upper=upper.area,band=band.area)),indent=2))
print('Band faces',len(faces),'areas',bottom.area,lower.area,band.area)
