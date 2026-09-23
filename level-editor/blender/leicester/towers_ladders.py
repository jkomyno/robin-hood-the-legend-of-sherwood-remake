"""Closed timber beam primitive shared by tower ladder recipes."""
from mathutils import Vector

def beam(a,b,width,depth):
 a,b=Vector(a),Vector(b);direction=(b-a).normalized();u=direction.cross(Vector((0,0,1)))
 if u.length<.01:u=direction.cross(Vector((0,1,0)))
 u.normalize();u*=width/2;v=direction.cross(u).normalized()*depth/2
 pts=[p+su*u+sv*v for p in [a,b] for su,sv in [(-1,-1),(1,-1),(1,1),(-1,1)]]
 return [list(p) for p in pts],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
