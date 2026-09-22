"""Raised rubble inside the measured timber enclosure footprint.

The six source-visible pale clusters retain their screen centers. Their depths
are inferred inside the timber parallelogram, so lifting them follows the source
camera ray rather than treating each painted cluster as an independent ground
contact. A conservative closed rubble core supports the stacked clusters.
"""
import math
from mathutils import Vector

VERSION='leicester-gate-raised-rubble-v1'
SINE,COSINE=math.sin(math.radians(35)),math.cos(math.radians(35))
# x, source-image y, inferred ground-image y, horizontal/vertical world radii.
STONES=[(3107.,1064.,1083.,5.,4.),(3117.,1058.,1078.,5.,4.),
        (3125.,1052.,1071.,5.,4.),(3122.,1068.,1085.,5.,5.),
        (3113.,1075.,1090.,5.,5.),(3102.,1075.,1086.,4.,4.)]


def footprint(u,v):
    return 3093.3+26.4*u+31.2*v,1087.+12.*u-24.3*v


def local_footprint(x,ground_y):
    dx,dy=x-3093.3,ground_y-1087.
    determinant=26.4*(-24.3)-31.2*12.
    return ((dx*(-24.3)-31.2*dy)/determinant,(26.4*dy-dx*12.)/determinant)


def geometry():
    """Return world-space vertices/faces and evidence for the gate recipe."""
    vertices,faces=[],[]
    def loft(rows):
        start=len(vertices);n=len(rows[0]);vertices.extend(Vector(v) for row in rows for v in row)
        faces.append(tuple(start+i for i in reversed(range(n))))
        for row in range(len(rows)-1):
            for i in range(n):
                j=(i+1)%n;a=start+row*n;b=a+n;faces.append((a+i,a+j,b+j,b+i))
        # Triangulated cap supports the deliberately uneven pile surface.
        last=start+(len(rows)-1)*n
        faces.extend((last,last+i,last+i+1) for i in range(1,n-1))
    # Native timber points define the horizontal wedge. Core top heights are
    # intentionally below the bright stone summits, not a new visible wall.
    corners=[(.12,.08,10.),(.78,.08,11.),(.78,.88,18.),(.12,.88,20.)]
    bottom=[];top=[]
    for u,v,height in corners:
        x,y=footprint(u,v);bottom.append((x,-y/SINE,0.));top.append((x,-y/SINE,height/COSINE))
    loft([bottom,top])
    records=[]
    for x,source_y,ground_y,rx,rz in STONES:
        u,v=local_footprint(x,ground_y)
        if not (0<=u<=1 and 0<=v<=1):raise ValueError('Raised source cluster escaped timber footprint')
        center=Vector((x,-ground_y/SINE,(ground_y-source_y)/COSINE))
        if center.z-rz<0:raise ValueError('Stone extends below ground')
        rows=[];n=8
        for z,scale in [(-rz,.58),(0,1),(rz,.52)]:
            rows.append([center+Vector((rx*scale*math.cos(i*math.tau/n),
                                        rx*scale*math.sin(i*math.tau/n),z)) for i in range(n)])
        loft(rows)
        records.append({'source_center':[x,source_y],'inferred_ground_y':ground_y,
                        'center_world':list(center),'timber_footprint_uv':[u,v],
                        'screen_center_error':abs(-center.y*SINE-center.z*COSINE-source_y)})
    report={'recipe':VERSION,'source_crop':[3089,1032,3136,1106],'enlargement':10,
            'source_cluster_count':6,'closed_components':7,'clusters':records,
            'limitations':[
                'Cluster screen centers follow the covered artwork; individual stone count and buried contacts are not independently visible.',
                'Ground depths and core heights are inferred inside the measured timber parallelogram; source camera-ray lifting preserves source positions.',
                'The closed core and six closed rocks intentionally intersect as stacked rubble; no hidden internal separation is asserted.',
                'Timber geometry and source endpoints are unchanged. Native118 ownership and renewed source/solid review remain required.']}
    return vertices,faces,report


def append_to(vertices,faces):
    """Replace the old stone block with this call; do not append both versions."""
    added,polygons,report=geometry();offset=len(vertices)
    vertices.extend(added);faces.extend(tuple(offset+i for i in face) for face in polygons)
    return report
