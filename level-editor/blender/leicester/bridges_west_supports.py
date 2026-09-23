"""Measured visible west footbridge braces and deep timber support."""
# Image coordinates measured on the covered source, with depth constrained by
# the corresponding native landing edge. Concealed sections remain hypotheses.
SUPPORTS = [
    ('tower landing diagonal 1', (5, 4), [(292.5,960),(312.5,946.5),(318,947),(296.5,964.5)]),
    ('tower landing diagonal 2', (5, 4), [(313,948),(317.5,945.5),(340,959.5),(340,965.5)]),
    ('tower landing visible post', (5, 4), [(338.5,945),(342.5,944.5),(346,1058),(342,1059.5),(339,980)]),
    ('castle landing diagonal', (3, 2), [(403,1025),(408,1023),(423.5,1036),(423.5,1042)]),
]

def add_supports(template, collection, points, object_mesh):
    import math
    from mathutils import Vector
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    toward=Vector((0,-cosine,sine))
    result=[]
    for label,edge,outline in SUPPORTS:
        a,b=(points[i] for i in edge)
        vertices=[]
        for depth in (-1.75,1.75):
            for x,y in outline:
                native_y=a['y']+(x-a['x'])*(b['y']-a['y'])/(b['x']-a['x'])
                vertices.append(Vector((x,-native_y/sine,(native_y-y)/cosine))+toward*depth)
        n=len(outline)
        faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
        faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
        obj=object_mesh(template.get('asset_name','West Tower Footbridge')+' / '+label,vertices,faces,template,collection)
        obj['bridge_support_profile']='measured-covered-source-v1'
        result.append(obj)
    return result
